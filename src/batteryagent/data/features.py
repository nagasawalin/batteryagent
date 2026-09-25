"""
batteryagent/data/features.py — derived per-cell quantities.

Single source of truth for the runtime and the references:
tools/cell_data.py (runtime) and scripts/build_questions.py (reference facts)
both import from here, so a number in a reference answer and the same number
in an agent answer cannot drift apart.

CHANGED 2026-09-25 (docstring only): this used to say the inventory script
imports from here too. It does not: scripts/inventory_severson.py keeps its
own derive() with the same formulas and the same cycles_to_capacity(). Do not
claim in the report that the inventory table comes from this file.

Note on chargetime (checked 2026-09-25 on b1c7 / b1c45, cycle 101): the native
`chargetime` field is the duration of the fast-charging step from 0 to 0.88 Ah
(80% of nominal), in minutes -- not the whole charge (~30 min). It rises
steeply in the last quarter of life, so chargetime_mean_min below reflects
both the policy and ageing.

Nothing in this file is a dataset field. Every quantity below is defined here
and must appear in the report's column-definition table with its formula and
its baseline.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .severson import EOL_CAPACITY_AH, NOMINAL_CAPACITY_AH, cycles_to_capacity

# ------------------------------------------------------------------ policy
# Charging policies read "C1(Q%)-C2": C1 from 0 to Q% SOC, C2 from Q% to 80%,
# then a uniform tail. The tail is a dataset-wide constant, see cell_spec.py.
_POLICY_RE = re.compile(r"^\s*([\d.]+)C\((\d+)%\)-([\d.]+)C\s*$")


def parse_policy(policy: str) -> dict:
    """'5.4C(80%)-3.6C' -> C-rates and the currents they correspond to.

    A C-rate is a current normalised by the nominal capacity, so 5.4C on a
    1.1 Ah cell is 5.94 A. Converting it needs the nominal capacity, which
    lives in the specification, not in the .mat file.
    """
    m = _POLICY_RE.match(policy or "")
    if not m:
        return {"policy": policy, "parsed": False}

    c1, soc, c2 = float(m.group(1)), int(m.group(2)), float(m.group(3))
    return {
        "policy": policy,
        "parsed": True,
        "step1_c_rate": c1,
        "step1_current_A": round(c1 * NOMINAL_CAPACITY_AH, 3),
        "switch_soc_pct": soc,
        "step2_c_rate": c2,
        "step2_current_A": round(c2 * NOMINAL_CAPACITY_AH, 3),
    }


# ------------------------------------------------------------------ helpers
def _fade_rate(cycle: np.ndarray, q: np.ndarray, q_ref: float,
               lo: int, hi: int) -> float:
    """Capacity loss over cycles [lo, hi), as % of q_ref per 100 cycles."""
    m = (cycle >= lo) & (cycle < hi)
    if m.sum() < 2:
        return float("nan")
    c, y = cycle[m], q[m]
    slope = np.polyfit(c, y, 1)[0]          # Ah per cycle, negative while fading
    return float(-100 * slope * 100 / q_ref)


def _none_if_nan(d: dict) -> dict:
    """JSON has no NaN: an undefined quantity is reported as null."""
    return {k: (None if isinstance(v, float) and np.isnan(v) else v)
            for k, v in d.items()}


# ------------------------------------------------------------------ main
def derive_cell(g: pd.DataFrame, cycle_life: float | None = None) -> dict:
    """Per-cell derived quantities from one cell's summary rows.

    Parameters
    ----------
    g : the summary rows of ONE cell. Sorted here, so the caller need not.
    cycle_life : the dataset's own cycle_life field for this cell, used only
        by cycles_to_capacity to recognise a record that stops one cycle short
        of the end-of-life threshold.
    """
    g = g.sort_values("cycle")
    cyc = g["cycle"].to_numpy(dtype=float)
    q = g["QDischarge"].to_numpy(dtype=float)
    ir = g["IR"].to_numpy(dtype=float)

    if len(q) < 2:
        return {"n_cycles": int(len(q)), "error": "too few recorded cycles"}

    eol_cycle, eol_method = cycles_to_capacity(cyc, q, cycle_life=cycle_life)
    q_first = float(q[0])                     # cycle 2: cycle 1 is empty
    last = float(cyc[-1])
    peak = float(cyc[int(np.argmax(q))])       # capacity rises before it fades

    return _none_if_nan({
        "n_cycles": int(len(q)),
        "first_cycle": float(cyc[0]),
        "last_cycle": last,

        # capacity
        "q_first_Ah": round(q_first, 4),
        "q_last_Ah": round(float(q[-1]), 4),
        "q_max_Ah": round(float(q.max()), 4),
        "cycle_at_q_max": peak,

        # retention is relative to this cell's own first recorded cycle;
        # SOH is relative to the nominal capacity of the cell model.
        "retention_pct": round(100 * float(q[-1]) / q_first, 2),
        "soh_last_pct": round(100 * float(q[-1]) / NOMINAL_CAPACITY_AH, 2),

        # end of life
        "eol_threshold_Ah": EOL_CAPACITY_AH,
        "cycles_to_eol": None if np.isnan(eol_cycle) else round(eol_cycle, 1),
        "eol_method": eol_method,

        # resistance
        "ir_first_ohm": round(float(ir[0]), 5),
        "ir_last_ohm": round(float(ir[-1]), 5),
        "ir_growth_pct": (round(100 * (float(ir[-1]) / float(ir[0]) - 1), 2)
                          if ir[0] > 0 else None),

        # Fade rate early vs late: two slopes instead of a knee detector.
        # A knee estimate needs a fit whose failure modes are invisible to the
        # agent; a pair of slopes shows acceleration just as well. The early
        # window starts at the capacity peak, because every cell rises before
        # it fades and a window starting at cycle 2 would measure the rise.
        "fade_pct_per_100cyc_early": round(
            _fade_rate(cyc, q, q_first, peak, peak + 100), 3),
        "fade_pct_per_100cyc_late": round(
            _fade_rate(cyc, q, q_first, max(last - 100, 0), last + 1), 3),

        # operating conditions actually seen
        "chargetime_mean_min": round(float(g["chargetime"].mean()), 2),
        "tavg_mean_C": round(float(g["Tavg"].mean()), 2),
        "tmax_max_C": round(float(g["Tmax"].max()), 2),
    })


def derive_all(cells: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    """derive_cell over every cell; one row each. Used by the inventory script."""
    life = cells.set_index("cell_id")["cycle_life"]
    rows = []
    for cell_id, g in summary.groupby("cell_id"):
        row = {"cell_id": cell_id}
        row.update(derive_cell(g, cycle_life=float(life.get(cell_id, np.nan))))
        rows.append(row)
    derived = pd.DataFrame(rows)
    # cells.parquet already has n_cycles / first_cycle / last_cycle; merging
    # both would silently rename them to _x / _y.
    clash = [c for c in derived.columns if c in cells.columns and c != "cell_id"]
    return cells.merge(derived.drop(columns=clash), on="cell_id", how="left")
