"""
corpus/contextualize.py — contextual retrieval (the ablation switch).

    uv run python -m batteryagent.corpus.contextualize

For every chunk, a cheap model writes one or two sentences that situate the
chunk in its paper (which chemistry, which experiment, which conditions).
The context is prepended to the chunk ONLY for embedding and BM25 in the
`contextual` variants; the text returned to a system is the original chunk.

The whole paper is sent with every chunk of that paper, marked for prompt
caching, so after the first chunk each call pays only for the chunk.
Resumable: chunks already in chunks_ctx.jsonl are skipped.
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

from ..config import cfg, path
from ..llm import create, text_of
from .chunk import count_tokens

INSTRUCTION = (
    "Here is a chunk from the document above:\n<chunk>\n{chunk}\n</chunk>\n\n"
    "Write one or two sentences that situate this chunk within the document, to "
    "improve search retrieval of the chunk. Name the cell chemistry, the "
    "experiment or method, and the conditions the chunk refers to when the "
    "document states them. Answer with the context only."
)


def doc_text(doc_id: str, max_tokens: int) -> str:
    blocks = json.loads((path("parsed") / f"{doc_id}.json").read_text())["blocks"]
    parts, used = [], 0
    for b in blocks:
        n = count_tokens(b["text"])
        if used + n > max_tokens:
            break
        parts.append(b["text"])
        used += n
    return "\n\n".join(parts)


def contextualize_chunk(doc: str, chunk: dict) -> str:
    resp = create(
        model=cfg()["models"]["helper"],
        max_tokens=150,
        system=[{"type": "text", "text": f"<document>\n{doc}\n</document>",
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": INSTRUCTION.format(chunk=chunk["text"])}],
    )
    return text_of(resp)


def main() -> int:
    c = cfg()["contextual"]
    chunks = [json.loads(line) for line in path("chunks").open()]
    out = path("chunks_ctx")
    done = set()
    if out.exists():
        done = {json.loads(line)["chunk_id"] for line in out.open()}
    todo = [ch for ch in chunks if ch["chunk_id"] not in done]
    print(f"{len(done)} done, {len(todo)} to go")

    lock = threading.Lock()
    by_doc: dict[str, list[dict]] = {}
    for ch in todo:
        by_doc.setdefault(ch["doc_id"], []).append(ch)

    with out.open("a") as fh:
        def work(doc, ch):
            ctx = contextualize_chunk(doc, ch)
            with lock:
                fh.write(json.dumps({**ch, "context": ctx}, ensure_ascii=False) + "\n")
                fh.flush()

        for i, (doc_id, chs) in enumerate(by_doc.items(), 1):
            doc = doc_text(doc_id, c["max_doc_tokens"])
            work(doc, chs[0])                      # first call writes the cache
            with ThreadPoolExecutor(c["workers"]) as ex:
                list(ex.map(lambda ch: work(doc, ch), chs[1:]))
            print(f"[{i}/{len(by_doc)}] {doc_id}: {len(chs)} chunks")

    # keep the file in chunks.jsonl order, one line per chunk
    rows = {json.loads(line)["chunk_id"]: line for line in out.open()}
    with out.open("w") as fh:
        for ch in chunks:
            if ch["chunk_id"] in rows:
                fh.write(rows[ch["chunk_id"]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
