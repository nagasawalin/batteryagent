"""
eval/judge.py — LLM-as-judge, pointwise and blind.

    uv run python -m batteryagent.eval.judge --run-id dev-2026-09-23

For every (question, system) answer the judge sees: the question, the
reference (facts, must_include, must_not), the answer, and the evidence the
answering system had. It never sees the system name. Answers are judged one
at a time (pointwise), so there is no answer order and hence no position
bias; the job order is shuffled with a fixed seed only so that a mid-run
failure does not hit one system systematically.

The judge model comes from a different vendor than the system model
(self-preference bias) and is called through litellm.

Evidence per system
  A  none
  B  the retrieved passages
  C  every tool result from the trace (long series dropped, derived kept)
  D  the pages of the core papers that the answer cites
"""

from __future__ import annotations

import argparse
import json
import random
import re

from ..config import cfg, path
from .run_eval import load_questions
from .trajectory import score_trajectory

DIMENSIONS = ("factual", "grounded", "reasoning", "calibration")

RUBRIC = """\
You are grading one answer to a question about lithium-ion battery cells.
Score each dimension from 1 (worst) to 5 (best):

factual     - Numbers and facts agree with the reference facts. A number absent
              from the reference is not wrong by default; judge it against the
              evidence. A fact the question needs but the answer does not give
              counts against this score; omission is not neutral.
grounded    - Every factual claim is supported by the evidence shown, or is
              explicitly marked as general knowledge or as uncertain. Invented
              citations score 1.
reasoning   - The causal chain from observation to explanation is sound and
              cited. Use null if the question asks for no explanation.
calibration - Confidence matches what the evidence supports: uncertainty is
              stated where the evidence is insufficient, and nothing is
              claimed that the evidence cannot support.

The REFERENCE FACTS, MUST INCLUDE and MUST NOT lists describe what a correct
answer contains; they are NOT part of the answer. Credit the answer only for
what the ANSWER TO GRADE itself says.

For each MUST INCLUDE point, in order: "met" is true only if the answer
covers it, and "quote" is a verbatim excerpt of at most 25 words copied from
the ANSWER TO GRADE that shows it (null if not met).
For each MUST NOT point, in order: "violated" is true only if the answer does
what the point forbids, and "quote" is the verbatim excerpt that does it
(null if not violated).

Work in this order and fill the JSON fields in this order: first copy what
the answer actually states, then check the points, and only then score.

Return JSON only:
{"answer_states": ["verbatim excerpt of each number or key claim in the ANSWER TO GRADE, at most 8"],
 "must_include": [{"met": bool, "quote": str|null}, ...],
 "must_not": [{"violated": bool, "quote": str|null}, ...],
 "factual": int, "grounded": int, "reasoning": int|null, "calibration": int,
 "rationale": "two sentences"}"""

# CHANGED 2026-09-27: the old pattern needed "[" right before the doc_id, so in
# "[severson2019, p. 6; attia2022, p. 7]" only the first source was found, and
# "p. 9-10" gave page 9 only; D's evidence missed 3 of 10 cited pages on dev M1.
_CITE = re.compile(r"([A-Za-z][A-Za-z\-]*\d{4}[a-z]?),\s*pp?\.?\s*(\d+)(?:\s*[–-]\s*(\d+))?")


def _slim(result: dict) -> dict:
    """Drop long series from get_cell_data results; derived values stay."""
    if isinstance(result, dict) and "series" in result:
        result = {k: v for k, v in result.items() if k != "series"}
        result["series"] = "(omitted for grading)"
    return result


def evidence(trace: dict) -> str:
    s, steps = trace["system"], trace["steps"]
    if s == "A":
        return "(none: this answer was written without data or literature access)"
    if s == "B":
        hits = [h for st in steps if st["type"] == "retrieval" for h in st["hits"]]
        return "\n\n".join(f"[{h['doc_id']}, p. {h['page_start']}] {h['text']}" for h in hits)
    if s == "C":
        return "\n\n".join(
            f"TOOL {st['name']}({json.dumps(st['args'])}) ->\n"
            f"{json.dumps(_slim(st['result']), ensure_ascii=False)}"
            for st in steps if st["type"] == "tool")
    if s == "D":
        cited = set()
        for doc_id, lo, hi in _CITE.findall(trace.get("answer") or ""):
            lo, hi = int(lo), int(hi or lo)
            if hi < lo or hi - lo > 5:          # typo guard: treat as a single page
                hi = lo
            cited |= {(doc_id, str(p)) for p in range(lo, hi + 1)}
        parts = []
        for doc_id, page in sorted(cited):
            f = path("parsed") / f"{doc_id}.json"
            if not f.exists():
                parts.append(f"[{doc_id}, p. {page}] (no such document in the corpus)")
                continue
            blocks = json.loads(f.read_text())["blocks"]
            text = " ".join(b["text"] for b in blocks if str(b["page"]) == page)
            parts.append(f"[{doc_id}, p. {page}] {text or '(no such page)'}")
        return "\n\n".join(parts) or "(the answer cites no pages)"
    raise ValueError(s)


def build_prompt(q: dict, trace: dict) -> str:
    # CHANGED 2026-09-25: truncation used to be silent. Evidence for C is the
    # tool results in call order, so a cut removes the LAST results (usually
    # the literature) and lowers C's grounded score systematically. The cap was
    # raised in config.yaml; any remaining cut is printed and recorded.
    full = evidence(trace)
    cap = cfg()["judge"]["max_evidence_chars"]
    trace["_evidence_chars"] = len(full)
    if len(full) > cap:
        print(f"  evidence truncated: {trace['system']} {trace['qid']} "
              f"{len(full)} > {cap} chars")
    ev = full[:cap]
    ref = q["reference"]
    return (f"QUESTION\n{q['question']}\n\n"
            f"REFERENCE FACTS\n{json.dumps(ref['facts'], ensure_ascii=False)}\n\n"
            f"MUST INCLUDE\n{json.dumps(ref['must_include'])}\n\n"
            f"MUST NOT\n{json.dumps(ref['must_not'])}\n\n"
            f"EVIDENCE AVAILABLE TO THE ANSWERER\n{ev}\n\n"
            f"ANSWER TO GRADE (the only text being graded)\n"
            f"{trace.get('answer') or '(no answer produced)'}")


def parse_json(text: str) -> dict:
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)


def _norm(s: str) -> str:
    s = s.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = re.sub(r"[*_`#]", "", s)        # markdown marks would break verbatim matching
    return re.sub(r"\s+", " ", s).strip().lower()


def verified(items, answer: str | None, key: str) -> tuple[list[bool], list[dict]]:
    """CHANGED 2026-09-27: a point counts only if the judge's quote is really in
    the answer. On dev, haiku credited D (no data access) with fade numbers that
    appear only in the reference facts, and marked a must_not as violated while
    its rationale said the opposite. Quotes are checked as verbatim substrings
    (whitespace and case normalised; '...' splits a quote into fragments that
    must all be present)."""
    ans = _norm(answer or "")
    flags, detail = [], []
    for it in items or []:
        if isinstance(it, bool):                     # old schema: cannot verify
            flags.append(it)
            detail.append({key: it, "quote": None, "verified": None})
            continue
        claim = bool(it.get(key))
        q = it.get("quote") or ""
        frags = [_norm(f).strip(' "\'') for f in re.split(r"\.\.\.|\u2026", q)]
        frags = [f for f in frags if f]
        ok = bool(frags) and all(f in ans for f in frags)
        flags.append(claim and ok)
        detail.append({key: claim, "quote": q or None, "verified": ok if claim else None})
    return flags, detail


def call_judge(prompt: str) -> dict:
    import litellm
    from dotenv import load_dotenv

    from ..config import ROOT
    load_dotenv(ROOT / ".env")
    model = cfg()["models"]["judge"]
    kw = dict(model=model, temperature=0,
              messages=[{"role": "system", "content": RUBRIC},
                        {"role": "user", "content": prompt}])
    try:
        resp = litellm.completion(response_format={"type": "json_object"}, **kw)
    except Exception:  # noqa: BLE001  (provider without JSON mode)
        resp = litellm.completion(**kw)
    return parse_json(resp.choices[0].message.content)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--force", action="store_true", help="re-judge existing items")
    a = ap.parse_args()

    run_dir = path("runs") / a.run_id
    qs = {q["id"]: q for q in load_questions("all")}
    out = run_dir / "judgements.jsonl"
    done = {}
    if out.exists() and not a.force:
        for line in out.open():
            j = json.loads(line)
            done[(j["system"], j["qid"])] = j

    jobs = []
    for f in sorted((run_dir / "traces").glob("*/*.json")):
        t = json.loads(f.read_text())
        if (t["system"], t["qid"]) not in done:
            jobs.append(t)
    random.Random(cfg()["judge"]["seed"]).shuffle(jobs)

    model = cfg()["models"]["judge"]
    for i, t in enumerate(jobs, 1):
        q = qs[t["qid"]]
        try:
            j = call_judge(build_prompt(q, t))
        except Exception as exc:  # noqa: BLE001
            print(f"judge failed on {t['system']} {t['qid']}: {exc}")
            continue
        inc, inc_d = verified(j.get("must_include"), t.get("answer"), "met")
        bad, bad_d = verified(j.get("must_not"), t.get("answer"), "violated")
        rec = {"system": t["system"], "qid": t["qid"], "type": q["type"],
               "judge_model": model,
               **{d: j.get(d) for d in DIMENSIONS},
               "must_include": inc,
               "must_not": bad,
               "must_include_detail": inc_d,
               "must_not_detail": bad_d,
               "rationale": j.get("rationale", ""),
               "answer_states": j.get("answer_states"),     # CHANGED 2026-09-27: audit trail
               "evidence_chars": t.get("_evidence_chars"),   # CHANGED 2026-09-25
               "trajectory": score_trajectory(t, q)}
        done[(t["system"], t["qid"])] = rec
        print(f"[{i}/{len(jobs)}] judged")
        with out.open("w") as fh:        # rewrite: always a complete, consistent file
            for r in done.values():
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
