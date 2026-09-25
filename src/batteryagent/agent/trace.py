"""
agent/trace.py — one JSON trace per (run, system, question).

    results/runs/<run_id>/traces/<system>/<question_id>.json

Every step is recorded: each model call (tokens, latency, stop reason) and
each tool call or retrieval (arguments, full result, size, latency, error).
The trace is written even if the run crashes, because an unrecorded failure
is the one you cannot analyse.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path


class Trace:
    def __init__(self, run_dir: Path, system: str, qid: str, question: str, model: str):
        self.path = Path(run_dir) / "traces" / system / f"{qid}.json"
        self.t0 = time.perf_counter()
        self.d = {"qid": qid, "system": system, "model": model, "question": question,
                  "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "steps": [], "answer": None, "status": "running"}

    def llm(self, step: int, resp, latency_s: float) -> None:
        from ..llm import usage_of

        self.d["steps"].append({"type": "llm", "step": step,
                                "stop_reason": resp.stop_reason,
                                "latency_s": round(latency_s, 2), **usage_of(resp)})

    def tool(self, step: int, name: str, args: dict, result: dict, latency_s: float,
             duplicate: bool = False) -> None:
        body = json.dumps(result, ensure_ascii=False)
        self.d["steps"].append({"type": "tool", "step": step, "name": name, "args": args,
                                "result": result, "result_chars": len(body),
                                "error": "error" in result, "duplicate": duplicate,
                                "latency_s": round(latency_s, 3)})

    def retrieval(self, query: str, hits: list[dict], latency_s: float,
                  variant: str) -> None:
        self.d["steps"].append({"type": "retrieval", "variant": variant, "query": query,
                                "hits": hits, "latency_s": round(latency_s, 3)})

    def note(self, **kw) -> None:
        self.d.setdefault("notes", {}).update(kw)

    def finish(self, answer: str | None, status: str) -> dict:
        s = self.d["steps"]
        self.d.update(answer=answer, status=status,
                      wall_s=round(time.perf_counter() - self.t0, 2),
                      totals={
                          "llm_calls": sum(x["type"] == "llm" for x in s),
                          "tool_calls": sum(x["type"] == "tool" for x in s),
                          "tool_errors": sum(x["type"] == "tool" and x["error"] for x in s),
                          "input_tokens": sum(x.get("input_tokens", 0) for x in s),
                          "output_tokens": sum(x.get("output_tokens", 0) for x in s),
                          "cache_read_tokens": sum(x.get("cache_read_tokens", 0) for x in s),
                      })
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.d, indent=1, ensure_ascii=False, default=str))
        return self.d
