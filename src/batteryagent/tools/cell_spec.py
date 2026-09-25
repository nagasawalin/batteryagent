"""
batteryagent/tools/cell_spec.py — tool 1 of 3: get_cell_spec.

Returns what a cell IS. None of it is in the .mat file: the chemistry, the
nominal capacity and the protocol live in the dataset documentation and the
Methods of the source publication. That is exactly why this tool separates
System C from every system without tool access — the facts cannot be guessed
and appear in the literature only incidentally.

JSON in, JSON out. No prose: the tool supplies facts, the model supplies
wording.
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from ..config import path

from ..data.features import parse_policy

CACHE_DIR = path("processed")   # absolute, independent of cwd

# --------------------------------------------------------------------------
# Checked line by line against the Methods of Severson et al., Nature Energy 4,
# 383-391 (2019), and the dataset documentation at data.matr.io. These values
# are the reference answers for the specification questions S1-S5, so any
# change here changes those references: re-run scripts/build_questions.py.
#
# `charge_tail`: an earlier reading of the Methods (MIT-hosted PDF) found the
# sentence "1C CC-CV to 3.6 V, cut-off C/50" for 80->100% SOC. The time series
# of b1c7 and b1c45 (cycle 101) show the matching shape: a 1C constant-current
# step followed by a decaying current. CHECK before submission: re-read that
# Methods sentence yourself; voltage and cut-off current were not checked in
# the data. The value is unchanged, so S1-S5 need no regeneration.
#
# CHANGED 2026-09-25: `batch_note` and `cell_id_convention` below. Neither key
# enters the S1-S5 reference facts (build_questions.spec() picks a fixed key
# list), so eval/questions.jsonl does NOT need to be regenerated.
# --------------------------------------------------------------------------
CELL_SPEC: dict = {
    "manufacturer": "A123 Systems",
    "model": "APR18650M1A",
    "cathode": "LFP (LiFePO4)",
    "anode": "graphite",
    "chemistry": "LFP/graphite",
    "form_factor": "18650 cylindrical",
    "nominal_capacity_Ah": 1.1,
    "voltage_window_V": [2.0, 3.6],
    "ambient_temperature_C": 30,
    "discharge_protocol": ("4C CC-CV to 2.0 V, cut-off C/50, identical for "
                           "every cell"),
    "charge_tail": "1C CC-CV to 3.6 V from 80% SOC, cut-off C/50",
    "eol_definition": "discharge capacity at 80% of nominal, i.e. 0.88 Ah",
    "ir_measurement": ("internal resistance is the average over ten +/-3.6C "
                       "current pulses applied at 80% SOC; a single scalar per "
                       "cycle, not an impedance spectrum"),
    # CHANGED 2026-09-25: was "a one-minute rest after charging, which the
    # later batches do not". The time series (b1c7, b1c45, cycle 101) show the
    # rest at Qc = 0.880 Ah, i.e. at 80% SOC between the fast-charging steps and
    # the 1C tail; charging ends and discharge starts with no rest in between.
    # What the later batches do is not checked here, hence "differ".
    "batch_note": ("batch 1 (2017-05-12) rests for one minute after reaching "
                   "80% SOC, before the 1C tail; rest periods differ in the "
                   "later batches"),
    "source": ("Severson et al., Nature Energy 4, 383-391 (2019), Methods; "
               "dataset documentation at data.matr.io"),
}

# Cells excluded from analysis, with the reason. Both lists were reproduced
# independently from the capacity data by the inventory script.
EXCLUSIONS: dict = {
    "continued_in_batch2": ["b1c0", "b1c1", "b1c2", "b1c3", "b1c4"],
    "never_reached_eol": ["b1c8", "b1c10", "b1c12", "b1c13", "b1c22"],
}


@lru_cache(maxsize=1)
def _cells() -> pd.DataFrame:
    return pd.read_parquet(CACHE_DIR / "cells.parquet").set_index("cell_id")


def get_cell_spec(cell_id: str) -> dict:
    """Specification and charging protocol of one cell.

    Returns {"error": ..., "known_cell_ids": [...]} for an unknown id rather
    than raising: a tool failure has to come back as a tool result the model
    can read and recover from, never as an exception that kills the loop.
    """
    cells = _cells()
    if cell_id not in cells.index:
        ids = list(cells.index)
        return {
            "error": f"unknown cell_id {cell_id!r}",
            "known_cell_ids": ids[:10] + (["..."] if len(ids) > 10 else []),
            "n_known": len(ids),
        }

    row = cells.loc[cell_id]
    out: dict = {"cell_id": cell_id, **CELL_SPEC}
    out["charge_policy"] = parse_policy(str(row["policy"]))
    out["batch"] = str(row.get("batch", ""))

    for key, ids in EXCLUSIONS.items():
        if cell_id in ids:
            out["exclusion_flag"] = key
    out.setdefault("exclusion_flag", None)

    # The dataset has no usable per-cell identifier: barcode and channel_id do
    # not decode to text, so cells are named by position in the batch.
    # CHANGED 2026-09-25: was "assigned by this work". The official Python
    # loader of the dataset (BuildPkl_Batch1.ipynb in the rdbraatz GitHub repo)
    # builds exactly these keys, 'b1c' + str(i) over the same 0-based index, so
    # the convention is the dataset's, not ours.
    out["cell_id_convention"] = ("position in the batch, 0-based: b<batch>c<index>; "
                                 "follows the dataset's official Python loader")
    return out
