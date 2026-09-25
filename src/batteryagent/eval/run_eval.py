"""
eval/run_eval.py — run systems on a split and store traces.

    uv run python -m batteryagent.eval.run_eval --split dev --systems A B C D
    uv run python -m batteryagent.eval.run_eval --split test --run-id test-final

Isolation: a system receives the question text and the question id, nothing
else. The reference answer is never read here except to select the split.

Reproducibility: the run folder gets a copy of config.yaml and the git
commit. Resumable: a (system, question) whose trace has status ok is skipped.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import date

from ..agent.loop import run_agent
from ..config import ROOT, path
from .baselines import RUNNERS

ALL = {"A": RUNNERS["A"], "B": RUNNERS["B"], "C": run_agent, "D": RUNNERS["D"]}


def load_questions(split: str | None = None) -> list[dict]:
    qs = [json.loads(line) for line in path("questions").open()]
    return [q for q in qs if split in (None, "all", q["split"])]


def runtime_view(q: dict) -> tuple[str, str]:
    """The only two fields a system may see."""
    return q["question"], q["id"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "test", "all"])
    ap.add_argument("--systems", nargs="+", default=list(ALL))
    ap.add_argument("--only", nargs="*", help="question ids")
    ap.add_argument("--run-id", default=None)
    a = ap.parse_args()

    run_id = a.run_id or f"{a.split}-{date.today().isoformat()}"
    run_dir = path("runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "config.yaml", run_dir / "config.yaml")
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                         text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT,
                                             text=True).strip())
    except Exception:  # noqa: BLE001
        commit, dirty = "unknown", None
    (run_dir / "meta.json").write_text(json.dumps(
        {"run_id": run_id, "split": a.split, "systems": a.systems, "commit": commit,
         "dirty_worktree": dirty}, indent=1))

    qs = [q for q in load_questions(a.split) if not a.only or q["id"] in a.only]
    for s in a.systems:
        for q in qs:
            f = run_dir / "traces" / s / f"{q['id']}.json"
            if f.exists() and json.loads(f.read_text())["status"] == "ok":
                continue
            text, qid = runtime_view(q)
            d = ALL[s](text, qid, run_dir)
            tot = d.get("totals", {})
            print(f"{s} {qid:4s} {d['status']:12s} tools={tot.get('tool_calls', 0)} "
                  f"in={tot.get('input_tokens', 0)} out={tot.get('output_tokens', 0)}")

    # flat answers file for reading
    with (run_dir / "answers.jsonl").open("w") as fh:
        for s in a.systems:
            for q in qs:
                f = run_dir / "traces" / s / f"{q['id']}.json"
                if f.exists():
                    d = json.loads(f.read_text())
                    fh.write(json.dumps({"system": s, "qid": q["id"], "status": d["status"],
                                         "answer": d["answer"]}, ensure_ascii=False) + "\n")
    print(f"run folder: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
