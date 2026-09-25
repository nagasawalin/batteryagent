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

# CHANGED 2026-09-25: no split after common abbreviations. "Fig. 4b", "Eq. 3",
# "et al. 12" and "Ref. 5" used to end a sentence, so chunks could stop at
# "... is given in Fig." (seen in chunk_sample.md, lewerenz2017b::0016).
_SENT = re.compile(
    r"(?<!\bFig\.)(?<!\bFigs\.)(?<!\bEq\.)(?<!\bEqs\.)(?<!\bRef\.)(?<!\bRefs\.)"
    r"(?<!\bal\.)(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bvs\.)(?<!\bNo\.)(?<!\bca\.)"
    r"(?<=[.!?])\s+(?=[A-Z0-9(\[©])"
)

# ------------------------------------------------------------------ text cleaning
# CHANGED 2026-09-25: added after reading results/chunk_sample.md.
#  1. Ligatures. Many Elsevier/ACS PDFs extract fi/fl/ff as separate tokens:
#     "signi fi cantly", "di ff erent", "in fl uence", "the fi rst". BM25 then
#     never matches "significantly" / "different" / "influence" / "first".
#     A split is rejoined only if the joined word is a known word: known =
#     every intact word in the corpus (the ACS/RSC/ECS papers are mostly clean)
#     plus /usr/share/dict/words when it exists (macOS ships it). "the fi rst"
#     -> "the first" because "thefirst" is unknown and "first" is known.
#  2. Control characters (\x0e for the degree sign, \x0f for bullets, \x13
#     for an accent) are removed.
#  3. Publisher boilerplate sentences are dropped ("Contents lists available
#     at ScienceDirect", "journal homepage", "(c) 2017 Elsevier...", e-mail
#     and corresponding-author lines).
# Only chunk text is cleaned; data/processed/parsed/*.json stays as parsed, so
# system D's full text and the judge's page evidence are unaffected.
_LIG = r"(ffi|ffl|ff|fi|fl)"
_LIG_MID = re.compile(r"\b([A-Za-z]+) " + _LIG + r" ([a-z]+)\b")
_LIG_START = re.compile(r"(?<![A-Za-z] )\b" + _LIG + r" ([a-z]+)\b")
_LIG_END = re.compile(r"\b([A-Za-z]+) " + _LIG + r"\b(?! [a-z])")
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f]")
_BOILER = re.compile(
    r"^(Contents lists available at|journal homepage|©|\(c\)\s*\d{4}|"
    r"\*+\s*Corresponding author|E-mail address|Available online|"
    r"This content was downloaded from|View the article online|All rights reserved)",
    re.I,
)
_SUFFIXES = ("", "s", "es", "d", "ed", "ing", "ly", "al", "ally", "ation", "ations")


def build_vocab(texts) -> set[str]:
    vocab = {w.lower() for t in texts for w in re.findall(r"[A-Za-z]{3,}", t)}
    from pathlib import Path

    d = Path("/usr/share/dict/words")
    if d.exists():
        vocab |= {w.strip().lower() for w in d.read_text(errors="ignore").split()}
    return vocab


def _known(word: str, vocab: set[str]) -> bool:
    """Known word, allowing simple inflections: influenc-ing, quantifi-ed."""
    w = word.lower()
    for s in _SUFFIXES:
        if not w.endswith(s) or len(w) - len(s) < 3:
            continue
        stem = w[: len(w) - len(s)]
        if stem in vocab or (s and stem + "e" in vocab) or \
                (s in ("ed", "es") and stem.endswith("i") and stem[:-1] + "y" in vocab):
            return True
    return False


def clean_text(text: str, vocab: set[str], stats: dict | None = None) -> str:
    stats = stats if stats is not None else {}
    text = _CTRL.sub("", text)

    def mid(m):
        left, lig, right = m.groups()
        if _known(left + lig + right, vocab):
            stats["ligatures"] = stats.get("ligatures", 0) + 1
            return left + lig + right
        if _known(lig + right, vocab):
            stats["ligatures"] = stats.get("ligatures", 0) + 1
            return f"{left} {lig}{right}"
        return m.group(0)

    def start(m):
        lig, right = m.groups()
        if _known(lig + right, vocab):
            stats["ligatures"] = stats.get("ligatures", 0) + 1
            return lig + right
        return m.group(0)

    def end(m):
        left, lig = m.groups()
        if not _known(left, vocab) and _known(left + lig, vocab):
            stats["ligatures"] = stats.get("ligatures", 0) + 1
            return left + lig
        return m.group(0)

    for _ in range(2):                      # adjacent splits: "di ff erent fi eld"
        text = _LIG_MID.sub(mid, text)
    text = _LIG_START.sub(start, text)
    text = _LIG_END.sub(end, text)
    return text


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
    out = [s.strip() for s in _SENT.split(text) if s.strip()]
    return [s for s in out if not _BOILER.match(s)]      # CHANGED 2026-09-25


def chunk_doc(meta: dict, blocks: list[dict], size: int, overlap: int,
              min_tokens: int) -> list[dict]:
    chunks: list[dict] = []
    buf: list[tuple[str, int | None, int, bool]] = []   # (sentence, page, ntok, para_start)
    # CHANGED 2026-09-25: buf starts with the overlap copied from the previous
    # chunk. The old flush() treated those sentences as new content, so a short
    # section tail produced a near-duplicate chunk (tested: 4 of 5 sentences
    # copied) or, when merged, appended the overlap to the previous chunk twice.
    n_carried = 0                                       # leading items of buf copied as overlap
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
        nonlocal buf, n_carried
        if not buf:
            return
        new = buf[n_carried:]                       # sentences not already in chunks[-1]
        n_new = sum(x[2] for x in new)
        if (n_new < min_tokens and chunks and chunks[-1]["section"] == section
                and chunks[-1]["kind"] == "text"):
            prev = chunks[-1]                       # merge a small tail, without the overlap
            if new:
                prev["text"] += " " + " ".join(x[0] for x in new)
                prev["n_tokens"] += n_new
                pages = [x[1] for x in new if x[1] is not None]
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
            buf, n_carried = tail, len(tail)
        else:
            buf, n_carried = [], 0

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

    # CHANGED 2026-09-25: a text chunk this small could not be merged (it is
    # the first chunk of its section) and is almost always front matter, e.g.
    # "Contents lists available at ScienceDirect" (lewerenz2017b::0000).
    chunks = [c for c in chunks if c["kind"] == "table" or c["n_tokens"] >= MIN_KEEP_TOKENS]
    for i, c in enumerate(chunks):
        c["chunk_id"] = f"{meta['doc_id']}::{i:04d}"
    return chunks


MIN_KEEP_TOKENS = 20


def main() -> int:
    c = cfg()["chunking"]
    df = load_sources()
    parsed: dict[str, list[dict]] = {}
    for doc_id in df.index:
        f = path("parsed") / f"{doc_id}.json"
        if not f.exists():
            print(f"not parsed yet: {doc_id}")
            continue
        parsed[doc_id] = json.loads(f.read_text())["blocks"]

    # CHANGED 2026-09-25: clean every block before chunking (see clean_text)
    vocab = build_vocab(b["text"] for blocks in parsed.values() for b in blocks)
    stats: dict = {}
    all_chunks: list[dict] = []
    for doc_id, blocks in parsed.items():
        row = df.loc[doc_id]
        blocks = [{**b, "text": clean_text(b["text"], vocab, stats)} for b in blocks]
        meta = {"doc_id": doc_id, "title": row.title, "year": row.year, "doi": row.doi}
        all_chunks += chunk_doc(meta, blocks, c["size_tokens"], c["overlap_tokens"],
                                c["min_tokens"])
    print(f"cleaning: {stats.get('ligatures', 0)} split ligatures rejoined; "
          f"vocabulary {len(vocab)} words")

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
        # CHANGED 2026-09-25: list the oversized chunks. The embedder reads at
        # most embed_max_length (1024) BGE tokens, so the tail of anything
        # larger is not embedded (BM25 and the reranker still see all of it).
        big = sorted((ch for ch in all_chunks if ch["n_tokens"] > 1024),
                     key=lambda ch: -ch["n_tokens"])
        for ch in big:
            print(f"  over 1024 tok: {ch['chunk_id']} ({ch['kind']}, {ch['n_tokens']} tok)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
