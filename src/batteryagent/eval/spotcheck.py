"""
eval/spotcheck.py — human check of the judge.

    uv run python -m batteryagent.eval.spotcheck sample --run-id RUN [--n 5]
    (fill in the human_* columns of spotcheck.csv, without looking at the judge)
    uv run python -m batteryagent.eval.spotcheck agree --run-id RUN

`sample` draws n judgements, spread over systems, and writes a CSV with the
question, the reference, the answer and EMPTY human columns. The judge's
scores go to a separate file so they cannot anchor the human rating.
`agree` reports exact and within-one agreement per dimension.
"""

from __future__ import annotations

import argparse
import json
import random

import pandas as pd

from ..config import path
from .judge import DIMENSIONS
from .run_eval import load_questions


def sample(run_dir, n: int, seed: int) -> None:
    js = [json.loads(line) for line in (run_dir / "judgements.jsonl").open()]
    rng = random.Random(seed)
    by_sys: dict[str, list] = {}
    for j in js:
        by_sys.setdefault(j["system"], []).append(j)
    picked = []
    while len(picked) < min(n, len(js)):              # round-robin over systems
        for s in sorted(by_sys):
            if by_sys[s] and len(picked) < n:
                picked.append(by_sys[s].pop(rng.randrange(len(by_sys[s]))))
    qs = {q["id"]: q for q in load_questions("all")}
    rows, hidden = [], []
    for k, j in enumerate(picked):
        t = json.loads((run_dir / "traces" / j["system"] / f"{j['qid']}.json").read_text())
        q = qs[j["qid"]]
        rows.append({"item": k, "qid": j["qid"], "question": q["question"],
                     "reference": json.dumps(q["reference"], ensure_ascii=False),
                     "answer": t["answer"],
                     **{f"human_{d}": "" for d in DIMENSIONS}})
        hidden.append({"item": k, "system": j["system"], **{d: j[d] for d in DIMENSIONS}})
    pd.DataFrame(rows).to_csv(run_dir / "spotcheck.csv", index=False)
    pd.DataFrame(hidden).to_csv(run_dir / "spotcheck_judge.csv", index=False)
    print(f"fill {run_dir / 'spotcheck.csv'}; judge scores are in spotcheck_judge.csv")


def agree(run_dir) -> None:
    h = pd.read_csv(run_dir / "spotcheck.csv")
    j = pd.read_csv(run_dir / "spotcheck_judge.csv")
    m = h.merge(j, on="item")
    rows = []
    for d in DIMENSIONS:
        x = m[[f"human_{d}", d]].dropna()
        if x.empty:
            continue
        diff = (x[f"human_{d}"].astype(float) - x[d].astype(float)).abs()
        rows.append({"dimension": d, "n": len(x), "exact": round((diff == 0).mean(), 2),
                     "within_1": round((diff <= 1).mean(), 2),
                     "mean_abs_diff": round(diff.mean(), 2)})
    out = pd.DataFrame(rows)
    out.to_csv(run_dir / "spotcheck_agreement.csv", index=False)
    print(out.to_string(index=False))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "agree"])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    run_dir = path("runs") / a.run_id
    sample(run_dir, a.n, a.seed) if a.cmd == "sample" else agree(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
