"""
retrieval/bm25.py — sparse keyword retrieval.

The tokenizer keeps tokens such as "dq/dv", "lifepo4", "3.6c" and "b1c20"
whole; a default whitespace/punctuation split would cut exactly the exact-match
terms BM25 is in the pipeline for.
"""

from __future__ import annotations

import re

import numpy as np

_TOKEN = re.compile(r"[a-z0-9]+(?:[./\-][a-z0-9]+)*")
_STOP = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the "
    "this to was were which with we our these those can may also than".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


class BM25Index:
    def __init__(self, ids: list[str], texts: list[str]):
        from rank_bm25 import BM25Okapi

        self.ids = ids
        self.bm25 = BM25Okapi([tokenize(t) for t in texts])

    def search(self, query: str, k: int) -> list[tuple[str, float]]:
        scores = self.bm25.get_scores(tokenize(query))
        top = np.argsort(-scores)[:k]
        return [(self.ids[i], float(scores[i])) for i in top if scores[i] > 0]
