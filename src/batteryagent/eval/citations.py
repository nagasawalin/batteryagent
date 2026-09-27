"""
eval/citations.py — rule-based citation check, no LLM.

    uv run python -m batteryagent.eval.citations --run-id RUN

Each cited (doc_id, page) in an answer is checked against what the system
actually had when it answered:
  A  nothing: every citation is unsupported
  B  the retrieved passages (the chunk's page range covers the cited page)
  C  the passages returned by search_literature (same rule)
  D  the full text of the core papers (the cited doc is core and has that page)
Added 2026-09-27 because the judge gave C grounded = 5 on all dev questions,
while dev-smoke showed C citing pages it never retrieved.
Writes citations.csv (one row per answer) and prints per-system totals.
"""

from __future__ import annotations

import argparse
import json

import pandas as pd

from ..config import path
from .judge import _CITE


def cited_pages(answer: str | None) -> set[tuple[str, int]]:
    out = set()
    for d, lo, hi in _CITE.findall(answer or ""):
        lo, hi = int(lo), int(hi or lo)
        if hi < lo or hi - lo > 5:
            hi = lo
        out |= {(d, p) for p in range(lo, hi + 1)}
    return out


def hit_ranges(trace: dict) -> list[tuple[str, int, int]]:
    s, steps = trace["system"], trace["steps"]
    if s == "B":
        hits = [h for st in steps if st["type"] == "retrieval" for h in st["hits"]]
    elif s == "C":
        hits = [h for st in steps if st["type"] == "tool" and st["name"] == "search_literature"
                for h in ((st.get("result") or {}).get("results") or [])]
    else:
        return []
    out = []
    for h in hits:
        lo = h.get("page_start")
        if lo is None:
            continue
        hi = h.get("page_end") if h.get("page_end") is not None else lo
        out.append((h["doc_id"], int(lo), int(hi)))
    return out


def core_pages(doc_ids) -> dict[str, set[int]]:
    out = {}
    for d in doc_ids:
        f = path("parsed") / f"{d}.json"
        if f.exists():
            blocks = json.loads(f.read_text())["blocks"]
            out[d] = {int(b["page"]) for b in blocks if b.get("page") is not None}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    run_dir = path("runs") / ap.parse_args().run_id
    rows, core = [], None
    for f in sorted((run_dir / "traces").glob("*/*.json")):
        t = json.loads(f.read_text())
        cited = cited_pages(t.get("answer"))
        if t["system"] == "D":
            if core is None:
                core = core_pages((t.get("notes") or {}).get("core_docs", []))
            ok = {c for c in cited if c[1] in core.get(c[0], set())}
        else:
            rng = hit_ranges(t)
            ok = {c for c in cited if any(d == c[0] and lo <= c[1] <= hi for d, lo, hi in rng)}
        bad = sorted(cited - ok)
        rows.append({"system": t["system"], "qid": t["qid"], "n_cited": len(cited),
                     "n_supported": len(ok),
                     "unsupported": "; ".join(f"{d} p.{p}" for d, p in bad)})
    df = pd.DataFrame(rows)
    df.to_csv(run_dir / "citations.csv", index=False)
    tot = df.groupby("system").agg(answers=("qid", "count"), cited=("n_cited", "sum"),
                                   supported=("n_supported", "sum"),
                                   answers_with_unsupported=("unsupported", lambda s: (s != "").sum()))
    tot["supported_rate"] = (tot.supported / tot.cited.where(tot.cited > 0)).round(2)
    print(tot.to_string(), "\n")
    print(df[df.unsupported != ""].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
