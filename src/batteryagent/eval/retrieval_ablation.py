"""
eval/retrieval_ablation.py — the retrieval ablation table.

    uv run python -m batteryagent.eval.retrieval_ablation
    uv run python -m batteryagent.eval.retrieval_ablation --variants dense bm25 hybrid

Every variant in config.yaml is run over eval/qrels.jsonl. Writes
results/retrieval_ablation.csv and .md, and per-query rows for failure analysis.
Metrics are free to compute: iterate here as often as needed.
"""

from __future__ import annotations

import argparse
import json
import time

import pandas as pd

from ..config import cfg, path
from .retrieval_metrics import evaluate


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="*", default=list(cfg()["retrieval_variants"]))
    a = ap.parse_args()

    from ..retrieval.retriever import get_retriever

    qrels = [json.loads(line) for line in path("qrels").open()]
    print(f"{len(qrels)} labelled queries")
    rows, per_q = [], []
    for name in a.variants:
        r = get_retriever(name)
        t = time.perf_counter()
        res = evaluate(lambda q, k: r.search(q, k=k), qrels)
        ms = 1000 * (time.perf_counter() - t) / max(len(qrels), 1)
        rows.append({"variant": name, **res["mean"], "ms_per_query": round(ms)})
        per_q += [{"variant": name, **x} for x in res["per_query"]]
        print(rows[-1])

    df = pd.DataFrame(rows)
    df.to_csv(path("results") / "retrieval_ablation.csv", index=False)
    (path("results") / "retrieval_ablation.md").write_text(df.to_markdown(index=False))
    pd.DataFrame(per_q).to_csv(path("results") / "retrieval_ablation_per_query.csv",
                               index=False)
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
