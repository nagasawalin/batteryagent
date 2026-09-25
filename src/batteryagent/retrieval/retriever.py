"""
retrieval/retriever.py — one Retriever per named variant in config.yaml.

    r = get_retriever("hybrid_rerank")
    hits = r.search("lithium plating fast charging graphite", k=5)

Pipeline for a variant {mode, rerank, contextual, rewrite}:
  queries  = [question] (+ 2-3 rewrites if rewrite)
  rankings = dense and/or BM25 top-k for every query
  fused    = RRF over all rankings (a single ranking is used as is)
  if rerank: cross-encoder over the top rerank_in, scored against the ORIGINAL question
  return top k, each hit carrying the original chunk text and its metadata

In contextual variants, dense and BM25 search context + chunk, but the text
returned is the chunk alone: the context helps finding, not answering.
"""

from __future__ import annotations

import json
from functools import lru_cache

from ..config import cfg, path
from .bm25 import BM25Index
from .fusion import rrf


class Retriever:
    def __init__(self, name: str):
        self.name = name
        self.v = cfg()["retrieval_variants"][name]
        self.r = cfg()["retrieval"]
        ctx = self.v["contextual"]
        f = path("chunks_ctx" if ctx else "chunks")
        self.chunks = {c["chunk_id"]: c for c in map(json.loads, f.open())}
        search_text = {cid: (f"{c['context']}\n\n{c['text']}" if ctx else c["text"])
                       for cid, c in self.chunks.items()}
        self.bm25 = (BM25Index(list(search_text), list(search_text.values()))
                     if self.v["mode"] in ("bm25", "hybrid") else None)
        self.dense = None
        if self.v["mode"] in ("dense", "hybrid"):
            from .dense import DenseIndex
            self.dense = DenseIndex(ctx)

    def search(self, query: str, k: int | None = None) -> list[dict]:
        k = k or self.r["final_k"]
        queries = [query]
        if self.v["rewrite"]:
            from .rewrite import rewrite
            queries += rewrite(query)

        rankings: list[list[tuple[str, float]]] = []
        for q in queries:
            if self.dense:
                rankings.append(self.dense.search(q, self.r["dense_k"]))
            if self.bm25:
                rankings.append(self.bm25.search(q, self.r["bm25_k"]))

        if len(rankings) == 1:
            fused = rankings[0]
        else:
            fused = rrf([[cid for cid, _ in rk] for rk in rankings], k=self.r["rrf_k"])

        if self.v["rerank"]:
            from .rerank import rerank
            pool = fused[: max(self.r["rerank_in"], k)]
            fused = rerank(query, [(cid, self.chunks[cid]["text"]) for cid, _ in pool])

        hits = []
        for rank, (cid, score) in enumerate(fused[:k], start=1):
            c = self.chunks[cid]
            hits.append({"rank": rank, "score": round(score, 4), "chunk_id": cid,
                         "doc_id": c["doc_id"], "title": c["title"], "year": c["year"],
                         "doi": c["doi"], "section": c["section"],
                         "page_start": c["page_start"], "page_end": c["page_end"],
                         "text": c["text"]})
        return hits


@lru_cache(maxsize=None)
def get_retriever(name: str | None = None) -> Retriever:
    return Retriever(name or cfg()["retrieval"]["runtime_variant"])
