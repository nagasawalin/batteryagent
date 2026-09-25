"""
retrieval/rewrite.py — query rewriting.

A question is turned into 2-3 short search queries in the vocabulary of the
literature ("knee point" -> "accelerated capacity fade onset", "nonlinear
aging"). Results are cached on disk, so the ablation is reproducible and
repeated runs cost nothing.
"""

from __future__ import annotations

import json
import threading

from ..config import cfg, path
from ..llm import create, text_of

PROMPT = (
    "Rewrite the question below into 2 or 3 short search queries for a corpus of "
    "lithium-ion battery degradation papers. Use the technical terms such papers "
    "use, include synonyms, and drop cell identifiers such as b1c20, which do not "
    "appear in any paper. Return a JSON list of strings only.\n\nQuestion: {q}"
)
_lock = threading.Lock()


def _load() -> dict:
    f = path("rewrite_cache")
    return json.loads(f.read_text()) if f.exists() else {}


def rewrite(question: str) -> list[str]:
    with _lock:
        cache = _load()
    if question in cache:
        return cache[question]
    resp = create(model=cfg()["models"]["helper"], max_tokens=200,
                  messages=[{"role": "user", "content": PROMPT.format(q=question)}])
    raw = text_of(resp).strip().strip("`").removeprefix("json").strip()
    try:
        queries = [q for q in json.loads(raw) if isinstance(q, str) and q.strip()][:3]
    except json.JSONDecodeError:
        queries = []
    with _lock:
        cache = _load()
        cache[question] = queries
        path("rewrite_cache").write_text(json.dumps(cache, indent=1, ensure_ascii=False))
    return queries
