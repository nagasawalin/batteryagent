"""
corpus/embed.py — BGE-M3 dense vectors -> Chroma.

    uv run python -m batteryagent.corpus.embed            # plain chunks
    uv run python -m batteryagent.corpus.embed --contextual

Two collections, `chunks` and `chunks_ctx`, so the contextual ablation is a
config switch, not a rebuild. Runs on CPU on purpose (MPS hits unimplemented
operators). The text embedded for `chunks_ctx` is context + chunk.
"""

from __future__ import annotations

import argparse
import json
from functools import lru_cache

import numpy as np

from ..config import cfg, path

COLLECTION = {False: "chunks", True: "chunks_ctx"}


@lru_cache(maxsize=1)
def embedder():
    from FlagEmbedding import BGEM3FlagModel

    name = cfg()["retrieval"]["embed_model"]
    try:
        return BGEM3FlagModel(name, use_fp16=False, devices=["cpu"])
    except TypeError:                              # older FlagEmbedding
        return BGEM3FlagModel(name, use_fp16=False, device="cpu")


def embed(texts: list[str]) -> np.ndarray:
    r = cfg()["retrieval"]
    out = embedder().encode(texts, batch_size=r["embed_batch"],
                            max_length=r["embed_max_length"])["dense_vecs"]
    out = np.asarray(out, dtype=np.float32)
    return out / np.linalg.norm(out, axis=1, keepdims=True)


def embed_text(ch: dict, contextual: bool) -> str:
    return f"{ch['context']}\n\n{ch['text']}" if contextual else ch["text"]


@lru_cache(maxsize=1)
def chroma():
    import chromadb

    return chromadb.PersistentClient(path=str(path("chroma")))


def load_chunks(contextual: bool) -> list[dict]:
    f = path("chunks_ctx" if contextual else "chunks")
    return [json.loads(line) for line in f.open()]


def build(contextual: bool) -> None:
    chunks = load_chunks(contextual)
    name = COLLECTION[contextual]
    client = chroma()
    try:
        client.delete_collection(name)
    except Exception:  # noqa: BLE001  (did not exist)
        pass
    col = client.create_collection(name, metadata={"hnsw:space": "cosine"})

    B = 256
    for i in range(0, len(chunks), B):
        part = chunks[i:i + B]
        vecs = embed([embed_text(c, contextual) for c in part])
        col.add(ids=[c["chunk_id"] for c in part],
                embeddings=vecs.tolist(),
                metadatas=[{"doc_id": c["doc_id"]} for c in part])
        print(f"{name}: {min(i + B, len(chunks))}/{len(chunks)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contextual", action="store_true")
    build(ap.parse_args().contextual)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
