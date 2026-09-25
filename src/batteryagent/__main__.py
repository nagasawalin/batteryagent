"""
python -m batteryagent — command line entry point.

    uv run python -m batteryagent ask "Why does b1c20 fail earlier than b1c5?"
    uv run python -m batteryagent ask --system B "..."
    uv run python -m batteryagent tool get_cell_data '{"cell_id": "b1c6"}'
"""

from __future__ import annotations

import argparse
import json
import sys

from .config import path


def main() -> int:
    ap = argparse.ArgumentParser(prog="batteryagent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ask = sub.add_parser("ask", help="answer one question with one system")
    ask.add_argument("question")
    ask.add_argument("--system", default="C", choices=list("ABCD"))
    tool = sub.add_parser("tool", help="call one tool directly")
    tool.add_argument("name")
    tool.add_argument("args", nargs="?", default="{}")
    a = ap.parse_args()

    if a.cmd == "tool":
        from .tools.schemas import dispatch
        print(json.dumps(dispatch(a.name, json.loads(a.args)), indent=1, ensure_ascii=False))
        return 0

    from .agent.loop import run_agent
    from .eval.baselines import RUNNERS
    run = run_agent if a.system == "C" else RUNNERS[a.system]
    d = run(a.question, "adhoc", path("runs") / "adhoc")
    print(d["answer"] or f"(no answer, status {d['status']})")
    print(f"\n[{d['status']}] trace: {path('runs') / 'adhoc' / 'traces' / a.system / 'adhoc.json'}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
