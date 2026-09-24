"""
batteryagent/tools/schemas.py — tool definitions, separate from implementations.

Kept apart on purpose: the functions stay plain Python, callable and testable
without any model in the loop, and the schema layer is what changes if the
tools are later exposed over MCP or through a framework.

search_literature is declared here but implemented in tools/literature.py once
the corpus exists.
"""

from __future__ import annotations

from .cell_data import DEFAULT_MAX_POINTS, SERIES_FIELDS, get_cell_data
from .cell_spec import get_cell_spec

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "get_cell_spec",
        "description": (
            "Specification and charging protocol of one cell: chemistry, form "
            "factor, nominal capacity, voltage window, temperature, discharge "
            "protocol, end-of-life definition, and the charging policy in both "
            "C-rate and amperes. Call this before interpreting any measurement."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cell_id": {"type": "string",
                            "description": "e.g. 'b1c20'"},
            },
            "required": ["cell_id"],
        },
    },
    {
        "name": "get_cell_data",
        "description": (
            "Per-cycle measurements and derived quantities for one cell: "
            "capacity retention, state of health, cycles to end of life with "
            "the method used to obtain it, internal-resistance growth, and "
            "early vs late fade rate. Series are subsampled and the response "
            "reports the subsampling."
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
]

DISPATCH = {
    "get_cell_spec": get_cell_spec,
    "get_cell_data": get_cell_data,
}
