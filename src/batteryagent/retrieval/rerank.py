"""
retrieval/rerank.py — cross-encoder reranking with bge-reranker-v2-m3.

A bi-encoder embeds query and chunk separately; a cross-encoder reads them
together and scores the pair, which is slower but far more precise. So the
cheap stage recalls rerank_in candidates and this stage orders them.
"""

from __future__ import annotations

from functools import lru_cache

from ..config import cfg


@lru_cache(maxsize=1)
def reranker():
    from FlagEmbedding import FlagReranker

    name = cfg()["retrieval"]["rerank_model"]
    try:
        return FlagReranker(name, use_fp16=False, devices=["cpu"])
    except TypeError:
        return FlagReranker(name, use_fp16=False, device="cpu")


def rerank(query: str, cands: list[tuple[str, str]]) -> list[tuple[str, float]]:
    """cands: (chunk_id, text). Returns (chunk_id, score) best first."""
    if not cands:
        return []
    scores = reranker().compute_score([[query, t] for _, t in cands],
                                      normalize=True, batch_size=16, max_length=1024)
    if not isinstance(scores, list):
        scores = [scores]
    return sorted(((cid, float(s)) for (cid, _), s in zip(cands, scores)),
                  key=lambda x: -x[1])
