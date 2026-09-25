"""
agent/loop.py — System C: the tool-calling loop.

    messages = [question]
    repeat up to max_steps:
        response = model(messages, tools)
        if no tool call: return the text
        run every tool call, append the results, continue
    step or token budget spent: one last call with tools disabled, asking for
    an answer from what has been gathered

Guards
  * max_steps and max_total_tokens cap cost and runaway loops.
  * An identical repeated call (same tool, same arguments) is not executed; the
    model gets an error telling it the result is already in the conversation.
  * dispatch() never raises, so a failing tool is a tool result, not a crash.
  * The trace is written on every exit path, including an exception.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..config import cfg
from ..llm import create, text_of
from ..tools.schemas import TOOL_SCHEMAS, dispatch
from .prompts import system_prompt
from .trace import Trace

FORCE_ANSWER = ("The tool budget is spent. Answer now using only the tool results "
                "above, and state what is missing.")


def run_agent(question: str, qid: str, run_dir: Path) -> dict:
    a = cfg()["agent"]
    model = cfg()["models"]["system"]
    system = system_prompt("C")
    trace = Trace(run_dir, "C", qid, question, model)
    messages: list[dict] = [{"role": "user", "content": question}]
    seen: set[str] = set()
    used_tokens = 0
    answer, status = None, "error"

    try:
        for step in range(a["max_steps"]):
            t = time.perf_counter()
            resp = create(model=model, system=system, tools=TOOL_SCHEMAS, messages=messages)
            trace.llm(step, resp, time.perf_counter() - t)
            used_tokens += resp.usage.input_tokens + resp.usage.output_tokens
            messages.append({"role": "assistant",
                             "content": [b.model_dump(exclude_none=True) for b in resp.content]})

            calls = [b for b in resp.content if b.type == "tool_use"]
            if not calls:
                answer, status = text_of(resp), "ok"
                return trace.finish(answer, status)

            results = []
            for call in calls:
                key = f"{call.name}:{json.dumps(call.input, sort_keys=True)}"
                t = time.perf_counter()
                if key in seen:
                    out = {"error": "duplicate call: this exact call was already made and "
                                    "its result is above. Use it, or change the arguments."}
                    dup = True
                else:
                    out = dispatch(call.name, call.input)
                    dup = False
                    seen.add(key)
                trace.tool(step, call.name, call.input, out, time.perf_counter() - t, dup)
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                "content": json.dumps(out, ensure_ascii=False),
                                "is_error": "error" in out})
            messages.append({"role": "user", "content": results})

            if used_tokens > a["max_total_tokens"]:
                status = "token_budget"
                break
        else:
            status = "step_limit"

        # budget spent: ask for an answer with tools disabled. The instruction is
        # appended to the last user turn (roles must alternate).
        messages[-1]["content"].append({"type": "text", "text": FORCE_ANSWER})
        t = time.perf_counter()
        resp = create(model=model, system=system, tools=TOOL_SCHEMAS,
                      tool_choice={"type": "none"}, messages=messages)
        trace.llm(a["max_steps"], resp, time.perf_counter() - t)
        answer = text_of(resp)
        return trace.finish(answer, status)
    except Exception as exc:  # noqa: BLE001
        trace.note(exception=f"{type(exc).__name__}: {exc}")
        return trace.finish(answer, "error")
