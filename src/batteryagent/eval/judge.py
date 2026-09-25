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
              evidence.
grounded    - Every factual claim is supported by the evidence shown, or is
              explicitly marked as general knowledge or as uncertain. Invented
              citations score 1.
reasoning   - The causal chain from observation to explanation is sound and
              cited. Use null if the question asks for no explanation.
calibration - Confidence matches what the evidence supports: uncertainty is
              stated where the evidence is insufficient, and nothing is
              claimed that the evidence cannot support.

Also check the reference's must_include points (true if the answer covers
the point) and must_not points (true if the answer VIOLATES it).

Return JSON only:
{"factual": int, "grounded": int, "reasoning": int|null, "calibration": int,
 "must_include": [bool, ...], "must_not": [bool, ...], "rationale": "two sentences"}"""

_CITE = re.compile(r"\[([A-Za-z0-9_\-]+),\s*p+\.?\s*(\d+)")


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
        cited = sorted(set(_CITE.findall(trace.get("answer") or "")))
        parts = []
        for doc_id, page in cited:
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
            f"ANSWER TO GRADE\n{trace.get('answer') or '(no answer produced)'}")


def parse_json(text: str) -> dict:
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)


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
        rec = {"system": t["system"], "qid": t["qid"], "type": q["type"],
               "judge_model": model,
               **{d: j.get(d) for d in DIMENSIONS},
               "must_include": j.get("must_include", []),
               "must_not": j.get("must_not", []),
               "rationale": j.get("rationale", ""),
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
