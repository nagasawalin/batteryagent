"""
scripts/inventory_severson.py — read the raw batches once, cache them, and
print everything needed to write the 30-question set.

    uv run python scripts/inventory_severson.py data/raw/2017-05-12_*.mat
    uv run python scripts/inventory_severson.py data/raw/2017-05-12_*.mat data/raw/2017-06-30_*.mat

Writes data/processed/{cells,summary}.parquet and results/cell_inventory.csv,
plus results/capacity_fade.png.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from batteryagent.data.severson import (  # noqa: E402
    EOL_CAPACITY_AH,
    NEVER_REACH_EOL,
    build_cache,
    cycles_to_capacity,
)

CACHE_DIR = Path("data/processed")
RESULTS_DIR = Path("results")


def derive(cells: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    """Per-cell quantities the question set will be written against."""
    life = cells.set_index("cell_id")["cycle_life"]
    rows = []
    for cell_id, g in summary.groupby("cell_id"):
        g = g.sort_values("cycle")
        q, cyc, ir = g.QDischarge.to_numpy(), g.cycle.to_numpy(), g.IR.to_numpy()

        cycles_to_eol, eol_method = cycles_to_capacity(
            cyc, q, cycle_life=life[cell_id]
        )

        rows.append(
            {
                "cell_id": cell_id,
                "q_first": q[0],
                "q_max": q.max(),
                "cycle_at_q_max": float(cyc[int(np.argmax(q))]),
                "q_last": q[-1],
                "retention_pct": 100 * q[-1] / q[0],
                "cycles_to_eol_measured": cycles_to_eol,
                "eol_method": eol_method,
                "reaches_eol": not np.isnan(cycles_to_eol),
                "ir_first": ir[0],
                "ir_last": ir[-1],
                "ir_growth_pct": 100 * (ir[-1] / ir[0] - 1) if ir[0] > 0 else np.nan,
                "chargetime_mean": g.chargetime.mean(),
                "tavg_mean": g.Tavg.mean(),
                "tmax_max": g.Tmax.max(),
            }
        )

    out = cells.merge(pd.DataFrame(rows), on="cell_id", how="left")
    out["cycle_life_delta"] = out.cycle_life - out.cycles_to_eol_measured
    return out


def report(inv: pd.DataFrame) -> None:
    n = len(inv)
    print(f"\ncells: {n}   policies: {inv.policy.nunique()} distinct")
    print(f"cycle_life (field): min {inv.cycle_life.min():.0f}  "
          f"median {inv.cycle_life.median():.0f}  max {inv.cycle_life.max():.0f}")
    print(f"retention: min {inv.retention_pct.min():.1f}%  "
          f"max {inv.retention_pct.max():.1f}%")

    print("\n-- cells that never reach 0.88 Ah in the data --")
    never = sorted(inv.loc[~inv.reaches_eol, "cell_id"])
    print(f"measured : {never}")
    print(f"LoadData.m: {sorted(NEVER_REACH_EOL)}")
    if set(never) != set(NEVER_REACH_EOL) and "b1c0" in set(inv.cell_id):
        print("MISMATCH -> check before excluding anything")

    print("\n-- cycle_life field vs cycles-to-0.88Ah measured --")
    d = inv.cycle_life_delta.dropna()
    print(f"delta: median {d.median():.0f}  min {d.min():.0f}  max {d.max():.0f}")
    worst = inv.reindex(inv.cycle_life_delta.abs().sort_values(ascending=False).index)
    print(worst[["cell_id", "cycle_life", "cycles_to_eol_measured",
                 "cycle_life_delta"]].head(5).to_string(index=False))

    print("\n-- capacity rise before fade (the cycle of peak capacity) --")
    rise = inv[inv.cycle_at_q_max > inv.first_cycle]
    print(f"{len(rise)}/{n} cells peak after their first recorded cycle; "
          f"median peak at cycle {rise.cycle_at_q_max.median():.0f}")

    print("\n-- policy spread --")
    print(inv.policy.value_counts().head(10).to_string())

    print("\n-- longest / shortest lived --")
    s = inv.sort_values("cycle_life")
    cols = ["cell_id", "policy", "cycle_life", "n_cycles", "retention_pct",
            "ir_growth_pct", "merged_from"]
    cols = [c for c in cols if c in inv.columns]
    print(pd.concat([s.head(3), s.tail(3)])[cols].to_string(index=False))


def plot(summary: pd.DataFrame, inv: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    order = inv.sort_values("cycle_life").cell_id
    cmap = plt.get_cmap("viridis")
    for rank, cell_id in enumerate(order):
        g = summary[summary.cell_id == cell_id].sort_values("cycle")
        ax.plot(g.cycle, g.QDischarge, lw=0.7,
                color=cmap(rank / max(len(order) - 1, 1)), alpha=0.8)
    ax.axhline(EOL_CAPACITY_AH, color="k", ls="--", lw=0.8)
    ax.set_xlabel("Cycle")
    ax.set_ylabel("Discharge capacity (Ah)")
    ax.set_title("Severson LFP — capacity fade (colour = cycle life)")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"\nwrote {out}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    raw = {}
    for p in argv[1:]:
        name = Path(p).name
        if "2017-05-12" in name:
            raw["b1"] = p
        elif "2017-06-30" in name:
            raw["b2"] = p
        elif "2018-04-12" in name:
            raw["b3"] = p
        else:
            print(f"unrecognised batch file: {name}")
            return 2

    print(f"reading {len(raw)} batch file(s): {sorted(raw)}")
    cells, summary = build_cache(raw, CACHE_DIR, merge="b1" in raw and "b2" in raw)

    inv = derive(cells, summary)
    RESULTS_DIR.mkdir(exist_ok=True)
    inv.to_csv(RESULTS_DIR / "cell_inventory.csv", index=False)

    report(inv)
    plot(summary, inv, RESULTS_DIR / "capacity_fade.png")
    print(f"wrote {RESULTS_DIR / 'cell_inventory.csv'} and {CACHE_DIR}/*.parquet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
