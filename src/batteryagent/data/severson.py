"""
batteryagent/data/severson.py — Severson/MIT LFP dataset loader.

Data layer. Imports no agent, LLM or tool code; tools/ imports this.

Two access paths, deliberately separate:

    load_batch(path, "b1")  -> (cells_df, summary_df)   cheap, per-cycle scalars
    load_cycle(path, i, j)  -> dict of arrays           expensive, one cycle

The tools only ever need the first. See "Why two paths" at the bottom.

Source of the cleaning rules: LoadData.m in
github.com/rdbraatz/data-driven-prediction-of-battery-cycle-life-before-capacity-degradation
(MATLAB, 1-based) converted to 0-based here.
"""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pandas as pd

# Per-cycle scalars living under batch/summary. Order is the schema.
SUMMARY_FIELDS = (
    "cycle", "QDischarge", "QCharge", "IR", "Tmax", "Tavg", "Tmin", "chargetime",
)

# Within-cycle time series living under batch/cycles.
CYCLE_FIELDS = (
    "t", "I", "V", "Qc", "Qd", "T", "Qdlin", "Tdlin", "discharge_dQdV",
)

NOMINAL_CAPACITY_AH = 1.1
EOL_CAPACITY_AH = 0.88  # 80% of nominal; the dataset's own end-of-life definition

def cycles_to_capacity(
    cycle: np.ndarray,
    q: np.ndarray,
    cycle_life: float | None = None,
    threshold: float = EOL_CAPACITY_AH,
    cycle_tol: int = 2,
    capacity_tol: float = 0.01,
) -> tuple[float, str]:
    """Cycle at which discharge capacity reaches `threshold`.

    Returns (cycle, method). Cycling was stopped once capacity reached the
    threshold and the terminating cycle is absent from `summary`, so a plain
    `q <= threshold` mask does not fire for most cells.

    method:
      'interpolated'  threshold crossed inside the record
      'dataset_field' record stops just short; cycle_life field adopted
      'not_reached'   record ends far above threshold (e.g. a cell whose
                      testing continued in another batch)
    """
    if len(q) < 2:
        return float("nan"), "not_reached"

    below = np.flatnonzero(q <= threshold)
    if below.size:
        j = int(below[0])
        if j == 0:
            return float(cycle[0]), "interpolated"
        x0, x1, y0, y1 = cycle[j - 1], cycle[j], q[j - 1], q[j]
        return float(x0 + (y0 - threshold) * (x1 - x0) / (y0 - y1)), "interpolated"

    ends_just_short = (
        cycle_life is not None
        and cycle_life - cycle[-1] <= cycle_tol
        and q[-1] - threshold <= capacity_tol
    )
    if ends_just_short:
        return float(cycle_life), "dataset_field"

    return float("nan"), "not_reached"

# --------------------------------------------------------------- primitives
def _is_empty(ds: h5py.Dataset) -> bool:
    """MATLAB writes [] as a small uint64 dataset flagged with MATLAB_empty."""
    return bool(ds.attrs.get("MATLAB_empty", 0)) or ds.dtype.kind == "u" and ds.shape == (2,)


def _mat_str(ds: h5py.Dataset) -> str:
    """MATLAB char array -> str. Stored as uint16 code points."""
    return "".join(chr(int(c)) for c in np.asarray(ds[()]).ravel() if int(c))


def _deref(f: h5py.File, ref_ds: h5py.Dataset, i: int):
    """Follow element i of an object-reference dataset."""
    return f[np.asarray(ref_ds[()]).ravel()[i]]


# --------------------------------------------------------------- summary path
def load_batch(
    path: str | Path,
    batch_id: str,
    drop_invalid_leading: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read descriptors + per-cycle scalars for every cell in one batch file.

    Returns
    -------
    cells   : one row per cell  (cell_id, policy, cycle_life, n_cycles, ...)
    summary : long format, one row per (cell_id, cycle)
    """
    path = Path(path)
    cell_rows: list[dict] = []
    summary_frames: list[pd.DataFrame] = []

    with h5py.File(path, "r") as f:
        batch = f["batch"]
        n_cells = batch["summary"].shape[0]

        for i in range(n_cells):
            cell_id = f"{batch_id}c{i}"

            cycle_life = float(np.asarray(_deref(f, batch["cycle_life"], i)[()]).ravel()[0])
            policy = _mat_str(_deref(f, batch["policy_readable"], i))
            policy_raw = _mat_str(_deref(f, batch["policy"], i))

            s = _deref(f, batch["summary"], i)
            data = {k: np.asarray(s[k][()]).ravel() for k in SUMMARY_FIELDS}
            df = pd.DataFrame(data)
            df.insert(0, "cell_id", cell_id)

            n_raw = len(df)
            n_dropped = 0
            if drop_invalid_leading:
                # Cycle 1 is recorded but empty (all scalars 0.0, time series []).
                # Drop only the leading run of such rows; a zero in the middle is
                # a different problem and must stay visible.
                valid = df["QDischarge"].to_numpy() > 0
                first = int(np.argmax(valid)) if valid.any() else len(df)
                n_dropped = first
                df = df.iloc[first:].reset_index(drop=True)

            summary_frames.append(df)
            cell_rows.append(
                {
                    "cell_id": cell_id,
                    "batch": batch_id,
                    "cell_index": i,
                    "policy": policy,
                    "policy_raw": policy_raw,
                    "cycle_life": cycle_life,
                    "n_cycles_raw": n_raw,
                    "n_cycles": len(df),
                    "n_dropped_leading": n_dropped,
                    "first_cycle": float(df["cycle"].iloc[0]) if len(df) else np.nan,
                    "last_cycle": float(df["cycle"].iloc[-1]) if len(df) else np.nan,
                }
            )

    return pd.DataFrame(cell_rows), pd.concat(summary_frames, ignore_index=True)


# --------------------------------------------------------------- cycle path
def load_cycle(
    path: str | Path,
    cell_index: int,
    cycle_index: int,
    fields: tuple[str, ...] = CYCLE_FIELDS,
) -> dict[str, np.ndarray]:
    """Read the within-cycle time series for ONE cycle of ONE cell.

    cycle_index is positional inside batch/cycles, i.e. 0 == the empty cycle 1.
    """
    path = Path(path)
    out: dict[str, np.ndarray] = {}
    with h5py.File(path, "r") as f:
        cycles = _deref(f, f["batch"]["cycles"], cell_index)
        for name in fields:
            ds = _deref(f, cycles[name], cycle_index)
            out[name] = np.array([]) if _is_empty(ds) else np.asarray(ds[()]).ravel()
    return out


def load_vdlin(path: str | Path, cell_index: int) -> np.ndarray:
    """The 1000-point voltage grid that Qdlin / Tdlin are interpolated onto."""
    with h5py.File(Path(path), "r") as f:
        return np.asarray(_deref(f, f["batch"]["Vdlin"], cell_index)[()]).ravel()


# --------------------------------------------------------------- cleaning
# LoadData.m: five batch-1 cells continued testing in batch 2.
# MATLAB batch2_idx = [8:10,16:17] -> 0-based below.
CONTINUATIONS: dict[str, str] = {
    "b1c0": "b2c7",
    "b1c1": "b2c8",
    "b1c2": "b2c9",
    "b1c3": "b2c15",
    "b1c4": "b2c16",
}

# LoadData.m: batch_combined([9,11,13,14,23]) = [] -> 0-based, batch-1 cells
# that never reach the 0.88 Ah end-of-life threshold.
NEVER_REACH_EOL: tuple[str, ...] = ("b1c8", "b1c10", "b1c12", "b1c13", "b1c22")


def merge_continuations(
    cells: pd.DataFrame, summary: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Append each batch-2 continuation onto its batch-1 cell; drop the donor.

    Cycle numbers in the batch-2 tail restart at 1, so they are offset by the
    last cycle of the batch-1 head before concatenation.
    """
    summary = summary.copy()
    keep_cells = cells.copy()

    for head, tail in CONTINUATIONS.items():
        if head not in set(summary.cell_id) or tail not in set(summary.cell_id):
            continue  # that batch not loaded; leave the pair alone

        head_df = summary[summary.cell_id == head]
        tail_df = summary[summary.cell_id == tail].copy()
        offset = head_df["cycle"].max()
        tail_df["cycle"] = tail_df["cycle"] + offset
        tail_df["cell_id"] = head

        summary = pd.concat(
            [summary[~summary.cell_id.isin([head, tail])], head_df, tail_df],
            ignore_index=True,
        )
        keep_cells = keep_cells[keep_cells.cell_id != tail]

    summary = summary.sort_values(["cell_id", "cycle"]).reset_index(drop=True)

    counts = summary.groupby("cell_id")["cycle"].agg(["count", "min", "max"])
    keep_cells = keep_cells.set_index("cell_id")
    keep_cells.loc[counts.index, "n_cycles"] = counts["count"]
    keep_cells.loc[counts.index, "first_cycle"] = counts["min"]
    keep_cells.loc[counts.index, "last_cycle"] = counts["max"]
    keep_cells["merged_from"] = keep_cells.index.map(CONTINUATIONS).fillna("")

    return keep_cells.reset_index(), summary


# --------------------------------------------------------------- cache
def build_cache(
    raw_files: dict[str, str | Path],
    out_dir: str | Path,
    merge: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the .mat files once, write cells.parquet + summary.parquet."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_cells, all_summary = [], []
    for batch_id, path in raw_files.items():
        c, s = load_batch(path, batch_id)
        all_cells.append(c)
        all_summary.append(s)

    cells = pd.concat(all_cells, ignore_index=True)
    summary = pd.concat(all_summary, ignore_index=True)
    if merge:
        cells, summary = merge_continuations(cells, summary)

    cells.to_parquet(out_dir / "cells.parquet", index=False)
    summary.to_parquet(out_dir / "summary.parquet", index=False)
    return cells, summary


def read_cache(cache_dir: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    cache_dir = Path(cache_dir)
    return (
        pd.read_parquet(cache_dir / "cells.parquet"),
        pd.read_parquet(cache_dir / "summary.parquet"),
    )


# --------------------------------------------------------------- notes
# Why two paths:
#   The file is ~3 GB per batch, almost all of it within-cycle time series.
#   The per-cycle scalars for all 46 cells are a few MB. Every number the
#   agent's tools need (SOH, retention, cycles-to-80%, IR growth, knee) comes
#   from the scalars. So the scalars get read once into a parquet cache, and
#   the time series stay on disk behind load_cycle(), used only when a question
#   genuinely needs a voltage curve. Loading everything eagerly would blow up
#   a 16 GB laptop and make every tool call take minutes.
