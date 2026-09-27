"""
eval/baselines.py — Systems A, B and D. Same model, temperature, prompt text
(apart from the access block) and trace format as System C.

  A  question only
  B  question + top-k passages from the runtime retriever, one generation
  D  question + full text of the core papers (sources.csv core=1), one generation
"""

from __future__ import annotations

import json
import time
from functools import lru_cache
from pathlib import Path

from ..agent.prompts import system_prompt
from ..agent.trace import Trace
from ..config import cfg, path
from ..corpus.chunk import count_tokens
from ..corpus.sources import load_sources
from ..llm import create, text_of


def _single_call(system_id: str, question: str, qid: str, run_dir: Path,
                 system, user_content: str, trace: Trace | None = None) -> dict:
    model = cfg()["models"]["system"]
    trace = trace or Trace(run_dir, system_id, qid, question, model)
    try:
        t = time.perf_counter()
        resp = create(model=model, system=system,
                      messages=[{"role": "user", "content": user_content}])
        trace.llm(0, resp, time.perf_counter() - t)
        return trace.finish(text_of(resp), "ok")
    except Exception as exc:  # noqa: BLE001
        trace.note(exception=f"{type(exc).__name__}: {exc}")
        return trace.finish(None, "error")


# ------------------------------------------------------------------ A
def run_a(question: str, qid: str, run_dir: Path) -> dict:
    return _single_call("A", question, qid, run_dir, system_prompt("A"), question)


# ------------------------------------------------------------------ B
def format_passages(hits: list[dict]) -> str:
    return "\n\n".join(
        # CHANGED 2026-09-27: was "[i] doc_id=X, p. N", which B copied into its
        # citations ("[doc_id=X, p. N]"), a style that told the judge it was B.
        f"Passage {i} (cite as [{h['doc_id']}, p. {h['page_start']}]; "
        f"section: {h['section']})\n{h['text']}"
        for i, h in enumerate(hits, 1))


def run_b(question: str, qid: str, run_dir: Path) -> dict:
    from ..retrieval.retriever import get_retriever

    trace = Trace(run_dir, "B", qid, question, cfg()["models"]["system"])
    r = get_retriever()
    t = time.perf_counter()
    hits = r.search(question, k=cfg()["baseline_b"]["k"])
    trace.retrieval(question, hits, time.perf_counter() - t, r.name)
    user = f"Retrieved passages:\n\n{format_passages(hits)}\n\nQuestion: {question}"
    return _single_call("B", question, qid, run_dir, system_prompt("B"), user, trace)


# ------------------------------------------------------------------ D
def _doc_with_pages(doc_id: str) -> str:
    blocks = json.loads((path("parsed") / f"{doc_id}.json").read_text())["blocks"]
    out, page = [], None
    for b in blocks:
        if b["page"] != page and b["page"] is not None:
            page = b["page"]
            out.append(f"[p. {page}]")
        out.append(b["text"])
    return "\n".join(out)


@lru_cache(maxsize=1)
def core_context() -> tuple[str, dict]:
    """Full text of the core papers within the token budget.

    If the budget is exceeded every paper is truncated by the same fraction, and
    the fraction is reported, so the report can state exactly what D saw.
    """
    df = load_sources()
    core = [d for d in df.doc_id[df.core] if (path("parsed") / f"{d}.json").exists()]
    texts = {d: _doc_with_pages(d) for d in core}
    tokens = {d: count_tokens(t) for d, t in texts.items()}
    budget = cfg()["baseline_d"]["max_context_tokens"]
    total = sum(tokens.values())
    frac = min(1.0, budget / total) if total else 1.0
    parts = []
    for d, t in texts.items():
        keep = t if frac >= 1.0 else t[: int(len(t) * frac)]
        title = df.loc[d, "title"]
        parts.append(f'<document doc_id="{d}" title="{title}">\n{keep}\n</document>')
    info = {"core_docs": core, "tokens_full": total, "kept_fraction": round(frac, 3)}
    return "\n\n".join(parts), info


def run_d(question: str, qid: str, run_dir: Path) -> dict:
    trace = Trace(run_dir, "D", qid, question, cfg()["models"]["system"])
    ctx, info = core_context()
    trace.note(**info)
    # the papers are identical for every question: cache them
    system = [{"type": "text", "text": system_prompt("D")},
              {"type": "text", "text": ctx, "cache_control": {"type": "ephemeral"}}]
    return _single_call("D", question, qid, run_dir, system, question, trace)


RUNNERS = {"A": run_a, "B": run_b, "D": run_d}
