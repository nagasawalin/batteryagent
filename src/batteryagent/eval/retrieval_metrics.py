"""
eval/retrieval_metrics.py — recall@k and MRR.

Relevance is labelled at the level of (doc_id, page), not chunk_id: chunk ids
change whenever chunking changes, a page does not. A retrieved chunk is
relevant to a label if it comes from that paper and its page range covers
that page, so the same labels serve every chunking and contextual variant.

  recall@k  fraction of a query's relevant (doc, page) items that at least one
            of the top-k chunks covers; averaged over queries
  MRR       1 / rank of the first relevant chunk (0 if none in the list);
            averaged over queries
"""

from __future__ import annotations


def covers(chunk: dict, rel: dict) -> bool:
    if chunk["doc_id"] != rel["doc_id"]:
        return False
    lo, hi = chunk.get("page_start"), chunk.get("page_end")
    if lo is None:
        return False
    return lo <= int(rel["page"]) <= (hi if hi is not None else lo)


def recall_at_k(ranked: list[dict], relevant: list[dict], k: int) -> float:
    if not relevant:
        return 0.0
    top = ranked[:k]
    return sum(any(covers(c, r) for c in top) for r in relevant) / len(relevant)


def reciprocal_rank(ranked: list[dict], relevant: list[dict]) -> float:
    for rank, c in enumerate(ranked, start=1):
        if any(covers(c, r) for r in relevant):
            return 1.0 / rank
    return 0.0


def evaluate(search, qrels: list[dict], ks=(5, 10)) -> dict:
    """search(query, k) -> ranked chunks. Returns means and per-query rows."""
    kmax = max(ks)
    rows = []
    for q in qrels:
        ranked = search(q["query"], kmax)
        row = {"qid": q["qid"], "rr": reciprocal_rank(ranked, q["relevant"])}
        for k in ks:
            row[f"recall@{k}"] = recall_at_k(ranked, q["relevant"], k)
        rows.append(row)
    n = len(rows) or 1
    means = {key: round(sum(r[key] for r in rows) / n, 3)
             for key in rows[0] if key != "qid"} if rows else {}
    means["mrr"] = means.pop("rr", 0.0)
    return {"mean": means, "per_query": rows}
