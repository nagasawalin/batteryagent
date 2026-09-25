"""
retrieval/fusion.py — Reciprocal Rank Fusion.

score(d) = sum over rankings of 1 / (k + rank_d), rank starting at 1.
Only ranks are used, never raw scores: cosine similarity and BM25 live on
different scales, and RRF needs no normalisation to combine them.
"""

from __future__ import annotations

from collections import defaultdict


def rrf(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            scores[doc] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))
