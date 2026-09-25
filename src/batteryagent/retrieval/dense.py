"""
retrieval/dense.py — BGE-M3 query embedding + Chroma nearest neighbours.
"""

from __future__ import annotations

from ..corpus.embed import COLLECTION, chroma, embed


class DenseIndex:
    def __init__(self, contextual: bool):
        self.col = chroma().get_collection(COLLECTION[contextual])

    def search(self, query: str, k: int) -> list[tuple[str, float]]:
        vec = embed([query])[0].tolist()
        r = self.col.query(query_embeddings=[vec], n_results=k, include=["distances"])
        return [(cid, 1.0 - d) for cid, d in zip(r["ids"][0], r["distances"][0])]
