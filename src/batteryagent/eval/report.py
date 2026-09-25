"""
eval/report.py — the results tables.

    uv run python -m batteryagent.eval.report --run-id RUN

Writes into the run folder:
  results_by_system.csv / .tex   mean of each dimension per system (the 4x5 table)
  results_by_type.csv            the same, per question type
  hallucination.csv              must_not violation rate and must_include coverage
  cost.csv                       tokens, tool calls and wall time per system
"""

from __future__ import annotations

import argparse
import json

import pandas as pd

from ..config import path
from .judge import DIMENSIONS

COLS = [*DIMENSIONS, "trajectory"]


def load(run_dir) -> pd.DataFrame:
    rows = []
    for line in (run_dir / "judgements.jsonl").open():
        j = json.loads(line)
        tr = j.get("trajectory")
        rows.append({"system": j["system"], "qid": j["qid"], "type": j["type"],
                     **{d: j[d] for d in DIMENSIONS},
                     "trajectory": tr["trajectory"] if tr else None,
                     "inc_rate": (sum(j["must_include"]) / len(j["must_include"])
                                  if j["must_include"] else None),
                     "violation": any(j["must_not"]) if j["must_not"] else None})
    return pd.DataFrame(rows)


def to_latex(t: pd.DataFrame) -> str:
    fmt = t.copy().astype(object)
    for c in fmt.columns:
        fmt[c] = [("--" if pd.isna(v) else f"{v:.2f}") for v in t[c]]
    head = " & ".join(["System", *[c.capitalize() for c in fmt.columns]])
    body = "\n".join(f"{s} & " + " & ".join(r) + r" \\" for s, r in
                     zip(fmt.index, fmt.values.tolist()))
    return ("\\begin{tabular}{@{}l" + "c" * len(fmt.columns) + "@{}}\n\\toprule\n"
            f"{head} \\\\\n\\midrule\n{body}\n\\bottomrule\n\\end{{tabular}}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    run_dir = path("runs") / ap.parse_args().run_id
    df = load(run_dir)

    by_sys = df.groupby("system")[COLS].mean().round(2)
    by_sys.to_csv(run_dir / "results_by_system.csv")
    (run_dir / "results_by_system.tex").write_text(to_latex(by_sys))
    print(by_sys.to_string(), "\n")

    by_type = df.groupby(["type", "system"])[COLS].mean().round(2)
    by_type.to_csv(run_dir / "results_by_type.csv")
    print(by_type.to_string(), "\n")

    hall = df.groupby("system").agg(must_include=("inc_rate", "mean"),
                                    must_not_violated=("violation", "mean"),
                                    n=("qid", "count")).round(2)
    hall.to_csv(run_dir / "hallucination.csv")
    print(hall.to_string(), "\n")

    cost = []
    for f in (run_dir / "traces").glob("*/*.json"):
        t = json.loads(f.read_text())
        cost.append({"system": t["system"], **t.get("totals", {}), "wall_s": t.get("wall_s")})
    cost = pd.DataFrame(cost).groupby("system").mean(numeric_only=True).round(1)
    cost.to_csv(run_dir / "cost.csv")
    print(cost.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
