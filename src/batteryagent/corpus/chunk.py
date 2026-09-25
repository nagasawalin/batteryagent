"""
corpus/chunk.py — page-tagged blocks -> chunks.jsonl.

    uv run python -m batteryagent.corpus.chunk

Rules
-----
* Section-aware: a heading ends the current chunk; chunks never span sections,
  and no overlap is carried across a section boundary.
* ~512 tokens with ~64 tokens of overlap, built from whole sentences so a
  chunk never starts or ends mid-sentence.
* Tables are never split: each table is its own chunk.
* A tail shorter than min_tokens is merged into the previous chunk of the
  same section instead of becoming a fragment.

Token counts use tiktoken cl100k_base. BGE-M3 has its own tokenizer, so 512
here is approximate; embed_max_length in config leaves headroom for that.

Also writes results/chunk_sample.md: ten random chunks for the manual
readability check. Read them before embedding anything.
"""

from __future__ import annotations

import json
import random
import re
from functools import lru_cache

from ..config import cfg, path
from .sources import load_sources

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")


@lru_cache(maxsize=1)
def _encoder():
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # noqa: BLE001  (offline: fall back to an estimate)
        return None


def count_tokens(text: str) -> int:
    enc = _encoder()
    return len(enc.encode(text)) if enc else int(len(text.split()) * 1.3) + 1


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text) if s.strip()]


def chunk_doc(meta: dict, blocks: list[dict], size: int, overlap: int,
              min_tokens: int) -> list[dict]:
    chunks: list[dict] = []
    buf: list[tuple[str, int | None, int, bool]] = []   # (sentence, page, ntok, para_start)
    section = ""

    def emit(items, kind="text", sec=None):
        text = ""
        for s, _p, _n, para in items:
            text += ("\n\n" if para and text else (" " if text else "")) + s
        pages = [p for _s, p, _n, _para in items if p is not None]
        chunks.append({
            **meta,
            "section": sec if sec is not None else section,
            "page_start": min(pages) if pages else None,
            "page_end": max(pages) if pages else None,
            "kind": kind,
            "n_tokens": sum(n for _s, _p, n, _para in items),
            "text": text,
        })

    def flush(carry: bool):
        nonlocal buf
        if not buf:
            return
        n = sum(x[2] for x in buf)
        if (n < min_tokens and chunks and chunks[-1]["section"] == section
                and chunks[-1]["kind"] == "text"):
            prev = chunks[-1]                       # merge a small tail
            prev["text"] += " " + " ".join(x[0] for x in buf)
            prev["n_tokens"] += n
            pages = [x[1] for x in buf if x[1] is not None]
            if pages:
                prev["page_end"] = max(prev["page_end"] or 0, max(pages))
        else:
            emit(buf)
        if carry:                                   # overlap: trailing sentences
            tail, t = [], 0
            for item in reversed(buf):
                if t + item[2] > overlap:
                    break
                tail.insert(0, (item[0], item[1], item[2], False))
                t += item[2]
            buf = tail
        else:
            buf = []

    for b in blocks:
        if b["kind"] == "heading":
            flush(carry=False)
            section = b["text"]
            continue
        if b["kind"] == "table":
            flush(carry=False)
            emit([(b["text"], b["page"], count_tokens(b["text"]), True)], kind="table")
            continue
        for j, s in enumerate(_sentences(b["text"])):
            n = count_tokens(s)
            if buf and sum(x[2] for x in buf) + n > size:
                flush(carry=True)
            buf.append((s, b["page"], n, j == 0))
    flush(carry=False)

    for i, c in enumerate(chunks):
        c["chunk_id"] = f"{meta['doc_id']}::{i:04d}"
    return chunks


def main() -> int:
    c = cfg()["chunking"]
    df = load_sources()
    all_chunks: list[dict] = []
    for doc_id, row in df.iterrows():
        f = path("parsed") / f"{doc_id}.json"
        if not f.exists():
            print(f"not parsed yet: {doc_id}")
            continue
        blocks = json.loads(f.read_text())["blocks"]
        meta = {"doc_id": doc_id, "title": row.title, "year": row.year, "doi": row.doi}
        all_chunks += chunk_doc(meta, blocks, c["size_tokens"], c["overlap_tokens"],
                                c["min_tokens"])

    out = path("chunks")
    with out.open("w") as fh:
        for ch in all_chunks:
            fh.write(json.dumps(ch, ensure_ascii=False) + "\n")

    n = sorted(ch["n_tokens"] for ch in all_chunks)
    if n:
        print(f"{len(all_chunks)} chunks from {len(set(ch['doc_id'] for ch in all_chunks))} "
              f"papers; tokens median {n[len(n) // 2]}, p95 {n[int(.95 * len(n))]}, max {n[-1]}; "
              f"{sum(ch['kind'] == 'table' for ch in all_chunks)} tables")
        sample = random.Random(0).sample(all_chunks, min(10, len(all_chunks)))
        md = ["# Chunk sample — read every one\n"]
        for ch in sample:
            md.append(f"## {ch['chunk_id']} — {ch['section']} — p.{ch['page_start']}"
                      f"–{ch['page_end']} ({ch['n_tokens']} tok)\n\n{ch['text']}\n")
        (path("results") / "chunk_sample.md").write_text("\n".join(md))
        print("wrote results/chunk_sample.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
