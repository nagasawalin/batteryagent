"""
sign_test.py — paired comparison of System C against A, B and D, per question.

    uv run python sign_test.py results/runs/test-final/judgements.jsonl

For every test question, C's score is compared with the other system's score
on the same question: C better = win, equal = tie, C worse = loss. Ties are
dropped, and the two-sided exact sign test asks how likely at least this many
wins (or losses) would be if C and the other system were equally likely to be
better on a question (binomial, p = 0.5). No scipy needed.

Metrics
  inc_rate    share of must_include points met (quote-verified), per answer
  inc_claimed same, but counting what the judge claimed before the quote check
              (sensitivity check; needs must_include_detail in the file)
  violation   1 if any must_not point was violated (only questions that have
              must_not points)
  factual, grounded, reasoning, calibration   the 1-5 judge scores
Reasoning is compared only on the questions where all four systems have a
score (7 on the test set), as in eval/report.py.
"""

from __future__ import annotations

import json
import sys
from math import comb

import pandas as pd

DIMS = ["factual", "grounded", "reasoning", "calibration"]


def sign_test(wins: int, losses: int) -> float:
    """Two-sided exact sign test; ties already removed."""
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def load(path: str) -> pd.DataFrame:
    rows = []
    for line in open(path, encoding="utf-8"):
        j = json.loads(line)
        inc = j.get("must_include") or []
        det = j.get("must_include_detail")
        claimed = [bool(d.get("met")) for d in det] if det else None
        mn = j.get("must_not") or []
        rows.append({
            "system": j["system"], "qid": j["qid"], "type": j["type"],
            **{d: j.get(d) for d in DIMS},
            "inc_rate": sum(inc) / len(inc) if inc else None,
            "inc_claimed": sum(claimed) / len(claimed) if claimed else None,
            # lower is better, so flip the sign: C "wins" if it violates less
            "no_violation": (0.0 if any(mn) else 1.0) if mn else None,
        })
    return pd.DataFrame(rows)


def main(path: str) -> int:
    df = load(path)
    # same rule as eval/report.py: reasoning only on questions where all four
    # systems have a score, so every comparison uses the same 7 questions
    n_sys = df.system.nunique()
    same = df.groupby("qid")["reasoning"].transform(
        lambda s: bool(s.notna().all()) and len(s) == n_sys).astype(bool)
    df.loc[~same, "reasoning"] = None
    print("answers per system:", df.groupby("system").size().to_dict(), "\n")

    metrics = ["inc_rate", "inc_claimed", "no_violation", *DIMS]
    print("means per system (no_violation = 1 - violation rate):")
    print(df.groupby("system")[metrics].mean().round(2).to_string(), "\n")

    out = []
    for other in ["A", "B", "D"]:
        for m in metrics:
            c = df[df.system == "C"].set_index("qid")[m]
            o = df[df.system == other].set_index("qid")[m]
            both = pd.concat([c, o], axis=1, keys=["C", "O"]).dropna()
            if both.empty:
                continue
            d = both["C"] - both["O"]
            w, t, l = int((d > 1e-9).sum()), int((d.abs() <= 1e-9).sum()), int((d < -1e-9).sum())
            out.append({"C vs": other, "metric": m, "n": len(both),
                        "win": w, "tie": t, "loss": l, "p_two_sided": sign_test(w, l)})
    res = pd.DataFrame(out)
    res["p_two_sided"] = res["p_two_sided"].map(lambda p: f"{p:.2g}")
    print(res.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "judgements.jsonl"))
