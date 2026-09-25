"""
tools/literature.py — tool 3 of 3: search_literature.

Returns what the literature SAYS: the top chunks for a query, each with the
metadata a citation needs (doc_id, page). The retrieval variant is fixed in
config (retrieval.runtime_variant) and reported in every response, so a trace
shows which retriever produced the evidence.
"""

from __future__ import annotations

from ..config import cfg

MAX_K = 10


def search_literature(query: str, k: int = 5) -> dict:
    if not isinstance(query, str) or not query.strip():
        return {"error": "query must be a non-empty string"}
    try:
        k = max(1, min(int(k), MAX_K))
    except (TypeError, ValueError):
        return {"error": f"k must be an integer between 1 and {MAX_K}"}

    from ..retrieval.retriever import get_retriever

    r = get_retriever()
    hits = r.search(query, k=k)
    return {
        "query": query,
        "retriever": r.name,
        "n_results": len(hits),
        "results": [{key: h[key] for key in ("doc_id", "title", "year", "section",
                                             "page_start", "page_end", "score", "text")}
                    for h in hits],
        "cite_as": "[doc_id, p. page_start]",
    }


if __name__ == "__main__":
    import json
    import sys

    print(json.dumps(search_literature(" ".join(sys.argv[1:]) or "lithium plating"),
                     indent=1, ensure_ascii=False)[:3000])
    print("runtime variant:", cfg()["retrieval"]["runtime_variant"])
