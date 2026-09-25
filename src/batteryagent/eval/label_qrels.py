"""
eval/label_qrels.py — interactive relevance labelling.

    uv run python -m batteryagent.eval.label_qrels

For each query in eval/retrieval_queries.jsonl that has no labels yet, the
candidates are POOLED from several retrievers (top 8 each of BM25, dense and
hybrid+rerank where available), shown in random order without scores, and you
type the numbers of the relevant ones. Pooling from several systems keeps the
labels from favouring the one retriever that produced the candidates.

Input: "1 4 7" relevant items; "" none relevant; "s" skip; "q" quit.
Labels are appended to eval/qrels.jsonl as (doc_id, page) pairs.
"""

from __future__ import annotations

import json
import random
import textwrap

from ..config import path

POOL = ("bm25", "dense", "hybrid_rerank")
PER_RETRIEVER = 8


def main() -> int:
    from ..retrieval.retriever import get_retriever

    queries = [json.loads(line) for line in path("retrieval_queries").open()]
    qf = path("qrels")
    done = {json.loads(line)["qid"] for line in qf.open()} if qf.exists() else set()

    retrievers = []
    for name in POOL:
        try:
            retrievers.append(get_retriever(name))
        except Exception as exc:  # noqa: BLE001
            print(f"(pool without {name}: {exc})")

    rng = random.Random(0)
    for q in queries:
        if q["qid"] in done:
            continue
        pool = {}
        for r in retrievers:
            for h in r.search(q["query"], k=PER_RETRIEVER):
                pool.setdefault(h["chunk_id"], h)
        items = list(pool.values())
        rng.shuffle(items)

        print("\n" + "=" * 78 + f"\n{q['qid']}: {q['query']}\n" + "=" * 78)
        for i, h in enumerate(items, 1):
            body = textwrap.shorten(h["text"], 420)
            print(f"\n[{i}] {h['doc_id']} p.{h['page_start']}-{h['page_end']} | "
                  f"{h['section']}\n    {body}")
        ans = input("\nrelevant numbers (blank = none, s = skip, q = quit): ").strip()
        if ans == "q":
            break
        if ans == "s":
            continue
        picked = [items[int(x) - 1] for x in ans.split() if x.isdigit()
                  and 1 <= int(x) <= len(items)]
        rel = sorted({(h["doc_id"], h["page_start"]) for h in picked})
        with qf.open("a") as fh:
            fh.write(json.dumps({"qid": q["qid"], "query": q["query"],
                                 "relevant": [{"doc_id": d, "page": p} for d, p in rel],
                                 "pool_size": len(items)}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
