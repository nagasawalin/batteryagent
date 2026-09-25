"""
eval/trajectory.py — the tool-trajectory dimension, scored by rule, not by
the judge.

It exists only for System C (A, B and D make no tool calls: reported as n/a,
not 0, so they do not drag a mean). Starting from 5:

  -2  per expected tool never called           (coverage)
  -1  a cell's data interpreted without its spec being fetched first (rule 1)
  -1  literature needed but searched only after the answer was drafted
      (i.e. never) — covered by coverage, so not double-counted
  -1  any duplicate call attempted
  -1  budget spent (step_limit / token_budget)
  clamp to [1, 5]

A rule-based score is transparent and costs nothing; the components are
stored so the report can show why each score is what it is.
"""

from __future__ import annotations


def score_trajectory(trace: dict, q: dict) -> dict | None:
    if trace["system"] != "C":
        return None
    calls = [s for s in trace["steps"] if s["type"] == "tool"]
    names = [c["name"] for c in calls]
    expected = set(q.get("expected_tools", []))

    # a non-existent cell: either cell tool is an acceptable way to find out
    if q["reference"]["facts"].get("exists") is False:
        cell_tools = {"get_cell_spec", "get_cell_data"}
        if expected & cell_tools and set(names) & cell_tools:
            expected -= cell_tools

    missing = sorted(t for t in expected if t not in names)

    spec_first = True
    if "get_cell_spec" in expected:
        for i, c in enumerate(calls):
            if c["name"] == "get_cell_data":
                cid = c["args"].get("cell_id")
                if not any(p["name"] == "get_cell_spec" and p["args"].get("cell_id") == cid
                           for p in calls[:i]):
                    spec_first = False

    dup = any(c["duplicate"] for c in calls)
    budget = trace["status"] in ("step_limit", "token_budget")

    score = 5 - 2 * len(missing) - (not spec_first) - dup - budget
    return {"trajectory": max(1, min(5, score)), "missing_tools": missing,
            "spec_before_data": spec_first, "duplicate_call": dup,
            "budget_hit": budget, "n_calls": len(calls),
            "n_errors": sum(c["error"] for c in calls)}
