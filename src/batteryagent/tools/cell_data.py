"""
batteryagent/tools/cell_data.py — tool 2 of 3: get_cell_data.

Returns what a cell DID: per-cycle measurements plus the derived quantities
in data/features.py.

Two rules decide whether the agent is usable or makes things up:

1. Every derived number is computed here, in Python. The model never does
   arithmetic on an array of 1188 floats — it would produce a plausible wrong
   number with complete confidence, and nothing downstream could detect it.
2. Series are downsampled and the downsampling is reported. A full cell is
   1188 cycles across several fields; returning all of it would spend most of
   the context window on numbers the model cannot use anyway.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from ..config import path

from ..data.features import derive_cell

CACHE_DIR = path("processed")   # absolute, independent of cwd

SERIES_FIELDS = ("QDischarge", "IR", "Tavg", "Tmax", "chargetime", "QCharge")
DEFAULT_FIELDS = ("QDischarge", "IR")
DEFAULT_MAX_POINTS = 40

_ROUND = {"QDischarge": 4, "QCharge": 4, "IR": 5,
          "Tavg": 2, "Tmax": 2, "Tmin": 2, "chargetime": 2}


@lru_cache(maxsize=1)
def _cache() -> tuple[pd.DataFrame, pd.DataFrame]:
    cells = pd.read_parquet(CACHE_DIR / "cells.parquet")
    summary = pd.read_parquet(CACHE_DIR / "summary.parquet")
    return cells.set_index("cell_id"), summary


def _downsample(n: int, max_points: int) -> np.ndarray:
    """Evenly spaced row indices, always keeping the first and the last."""
    if n <= max_points:
        return np.arange(n)
    return np.unique(np.linspace(0, n - 1, max_points).round().astype(int))


def get_cell_data(
    cell_id: str,
    fields: list[str] | None = None,
    cycle_range: tuple[int, int] | None = None,
    max_points: int = DEFAULT_MAX_POINTS,
) -> dict:
    """Per-cycle measurements and derived quantities for one cell.

    Parameters
    ----------
    cell_id : e.g. "b1c20".
    fields : subset of SERIES_FIELDS; defaults to capacity and resistance.
    cycle_range : inclusive (first, last) cycle numbers, or None for all.
    max_points : cap on returned points per series; the response says what the
        stride was, so the model knows it is not seeing every cycle.

    `derived` is always computed over the FULL record, never over the
    requested window — otherwise "capacity at cycle 100" would silently change
    the reported cycle life.
    """
    cells, summary = _cache()
    if cell_id not in cells.index:
        ids = list(cells.index)
        return {"error": f"unknown cell_id {cell_id!r}",
                "known_cell_ids": ids[:10] + (["..."] if len(ids) > 10 else []),
                "n_known": len(ids)}

    fields = list(fields) if fields else list(DEFAULT_FIELDS)
    unknown = [f for f in fields if f not in SERIES_FIELDS]
    if unknown:
        return {"error": f"unknown field(s): {unknown}",
                "available_fields": list(SERIES_FIELDS)}

    full = summary[summary.cell_id == cell_id].sort_values("cycle")
    cycle_life = float(cells.loc[cell_id, "cycle_life"])
    derived = derive_cell(full, cycle_life=cycle_life)

    window = full
    if cycle_range is not None:
        lo, hi = float(cycle_range[0]), float(cycle_range[1])
        window = full[(full.cycle >= lo) & (full.cycle <= hi)]
        if window.empty:
            return {
                "cell_id": cell_id,
                "error": f"no recorded cycles in range {cycle_range}",
                "recorded_cycle_range": [derived["first_cycle"],
                                         derived["last_cycle"]],
                "note": ("cycle 1 is recorded but empty and is dropped; "
                         "the record stops before the end-of-life cycle"),
            }

    idx = _downsample(len(window), max_points)
    sampled = window.iloc[idx]

    series = {"cycle": [int(c) for c in sampled["cycle"]]}
    for f in fields:
        series[f] = [round(float(v), _ROUND.get(f, 4)) for v in sampled[f]]

    return {
        "cell_id": cell_id,
        "policy": str(cells.loc[cell_id, "policy"]),
        "cycle_range_returned": [int(sampled["cycle"].iloc[0]),
                                 int(sampled["cycle"].iloc[-1])],
        "sampling": {
            "points_returned": int(len(sampled)),
            "points_in_range": int(len(window)),
            "note": ("evenly spaced subsample; first and last cycle kept"
                     if len(sampled) < len(window) else "every recorded cycle"),
        },
        "series": series,
        "derived": derived,
    }
