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

    # CHANGED 2026-09-25: the judge may return reasoning = null ("no explanation
    # asked"), and may do so for one system but not another on the same
    # question. Reasoning is therefore compared only on questions where every
    # system got a score, so the per-system means cover the same questions.
    n_sys = df.system.nunique()
    same = df.groupby("qid")["reasoning"].transform(
        lambda s: bool(s.notna().all()) and len(s) == n_sys).astype(bool)
    df.loc[~same, "reasoning"] = None
    print(f"reasoning compared on {df.loc[same, 'qid'].nunique()} questions; "
          f"judgements per system: {df.groupby('system').size().to_dict()}\n")

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
        # CHANGED 2026-09-27: input_tokens excludes cached prompt tokens, so D's
        # ~150k-token cached context showed up as a few dozen tokens. Count every
        # prompt token from the llm steps (works for traces written before the fix).
        llm = [x for x in t["steps"] if x["type"] == "llm"]
        cost.append({"system": t["system"], **t.get("totals", {}),
                     "cache_write_tokens": sum(x.get("cache_write_tokens", 0) for x in llm),
                     "prompt_tokens_all": sum(x.get("input_tokens", 0)
                                              + x.get("cache_read_tokens", 0)
                                              + x.get("cache_write_tokens", 0) for x in llm),
                     "wall_s": t.get("wall_s"),
                     "answer_words": len((t.get("answer") or "").split())})
    cost = pd.DataFrame(cost).groupby("system").mean(numeric_only=True).round(1)
    cost.to_csv(run_dir / "cost.csv")
    print(cost.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
