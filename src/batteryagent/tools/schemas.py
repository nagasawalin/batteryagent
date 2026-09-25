"""
tools/schemas.py — tool definitions and the dispatcher, separate from the
implementations.

Format: Anthropic Messages API ("input_schema"). For an OpenAI-style client
the same content goes under {"type": "function", "function": {..., "parameters"}}.

dispatch() is the only way the agent executes a tool. It never raises: an
unknown tool, bad arguments or an exception inside a tool all come back as
{"error": ...}, which the model reads as a tool result and can recover from.
"""

from __future__ import annotations

import traceback

from .cell_data import DEFAULT_MAX_POINTS, SERIES_FIELDS, get_cell_data
from .cell_spec import get_cell_spec

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "get_cell_spec",
        "description": (
            "Specification and charging protocol of one cell: chemistry, form "
            "factor, nominal capacity, voltage window, temperature, discharge "
            "protocol, end-of-life definition, the charging policy in both C-rate "
            "and amperes, and whether the cell is flagged for exclusion. Call this "
            "before interpreting any measurement of the cell."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cell_id": {"type": "string", "description": "e.g. 'b1c20'"},
            },
            "required": ["cell_id"],
        },
    },
    {
        "name": "get_cell_data",
        "description": (
            "Per-cycle measurements and derived quantities for one cell: capacity "
            "retention, state of health, cycles to end of life with the method used "
            "to obtain it (null if not reached), internal-resistance growth, and "
            "early vs late fade rate. Derived values always cover the full record. "
            "Series are subsampled and the response reports the subsampling; use "
            "cycle_range to see a specific window."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cell_id": {"type": "string", "description": "e.g. 'b1c20'"},
                "fields": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(SERIES_FIELDS)},
                    "description": "series to return; defaults to QDischarge and IR",
                },
                "cycle_range": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 2, "maxItems": 2,
                    "description": "inclusive [first, last] cycle; omit for the whole record",
                },
                "max_points": {
                    "type": "integer",
                    "description": f"cap on points per series (default {DEFAULT_MAX_POINTS})",
                },
            },
            "required": ["cell_id"],
        },
    },
    {
        "name": "search_literature",
        "description": (
            "Search a corpus of peer-reviewed papers on lithium-ion battery "
            "degradation. Returns the most relevant passages with doc_id, title, "
            "year, section and page. Use it before naming or explaining any "
            "degradation mechanism, and cite what you use as [doc_id, p. N]. Cell "
            "identifiers such as b1c20 do not occur in the papers; search with "
            "technical terms."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "a short technical search query"},
                "k": {"type": "integer", "description": "number of passages, 1-10 (default 5)"},
            },
            "required": ["query"],
        },
    },
]


def _search_literature(**kw):
    from .literature import search_literature   # lazy: data tools work without the corpus
    return search_literature(**kw)


DISPATCH = {
    "get_cell_spec": get_cell_spec,
    "get_cell_data": get_cell_data,
    "search_literature": _search_literature,
}


def dispatch(name: str, args: dict) -> dict:
    fn = DISPATCH.get(name)
    if fn is None:
        return {"error": f"unknown tool {name!r}", "available_tools": list(DISPATCH)}
    try:
        out = fn(**(args or {}))
    except TypeError as exc:                         # wrong / missing arguments
        return {"error": f"bad arguments for {name}: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{name} failed: {type(exc).__name__}: {exc}",
                "trace": traceback.format_exc(limit=2)[-500:]}
    return out if isinstance(out, dict) else {"result": out}
