"""
scripts/plot_b1c6.py — Figure for Appendix B: capacity of cell b1c6 per cycle,
with the windows of the early and late fade rates and the 0.88 Ah threshold.

    uv run python scripts/plot_b1c6.py            # -> results/figures/b1c6_capacity.pdf

Reads the same Parquet tables as get_cell_data and takes the windows and
rates from features.derive_cell, so the figure shows exactly what the tool
reports (early window [peak, peak+100), late window [last-100, last]).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CELL = "b1c6"
EOL_AH = 0.88

INK = "#1f2328"          # text, fitted lines
DATA = "#2f6db5"         # the one data series
MUTED = "#6e7781"        # threshold line, secondary labels
SHADE = "#e6e9ee"        # fade-rate windows (neutral, prints as light gray)


def plot(cyc: np.ndarray, q: np.ndarray, d: dict, out: str) -> None:
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9,
                         "xtick.labelsize": 8, "ytick.labelsize": 8,
                         "pdf.fonttype": 42})
    fig, ax = plt.subplots(figsize=(6.3, 2.35))

    peak, last = d["cycle_at_q_max"], d["last_cycle"]
    windows = [("early", peak, peak + 100, d["fade_pct_per_100cyc_early"]),
               ("late", last - 100, last + 1, d["fade_pct_per_100cyc_late"])]

    for name, lo, hi, rate in windows:
        ax.axvspan(lo, hi - 1, color=SHADE, lw=0, zorder=0)
        m = (cyc >= lo) & (cyc < hi)
        s, a = np.polyfit(cyc[m], q[m], 1)
        xs = np.array([cyc[m].min(), cyc[m].max()])
        ax.plot(xs, a + s * xs, color=INK, lw=1.4, zorder=3)
        # labels sit beside their window at mid-height, where the curve is not
        x, ha = (hi + 8, "left") if name == "early" else (lo - 8, "right")
        ax.annotate(f"{name} window\n{rate:.3f} % per 100 cycles",
                    xy=(x, 0.35), xycoords=("data", "axes fraction"),
                    ha=ha, va="center", fontsize=8, color=INK)

    ax.plot(cyc, q, color=DATA, lw=1.0, zorder=2)

    ax.axhline(EOL_AH, color=MUTED, lw=1.0, ls=(0, (4, 3)), zorder=1)
    ax.annotate(f"end of life, {EOL_AH:.2f} Ah", xy=(0.01, EOL_AH),
                xycoords=("axes fraction", "data"), xytext=(0, 3),
                textcoords="offset points", fontsize=8, color=MUTED)

    qpk = d["q_max_Ah"]
    ax.plot([peak], [qpk], "o", ms=5, color=DATA, mec="white", mew=1.2, zorder=4)
    ax.annotate(f"peak, cycle {peak:.0f}", xy=(peak, qpk), xytext=(4, 6),
                textcoords="offset points", fontsize=8, color=INK)

    ax.set_xlabel("Cycle")
    ax.set_ylabel("Discharge capacity (Ah)")
    ax.set_xlim(0, last + 15)
    lo_y = min(q.min(), EOL_AH) - 0.01
    ax.set_ylim(lo_y, qpk + 0.02)           # headroom for the peak label
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelcolor=INK)
    ax.grid(axis="y", color="#d0d7de", lw=0.5)
    ax.set_axisbelow(True)

    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    print(f"wrote {out}")


def main() -> int:
    from batteryagent.config import path
    from batteryagent.data.features import derive_cell

    cells = pd.read_parquet(path("processed") / "cells.parquet").set_index("cell_id")
    summary = pd.read_parquet(path("processed") / "summary.parquet")
    g = summary[summary.cell_id == CELL].sort_values("cycle")
    d = derive_cell(g, cycle_life=float(cells.loc[CELL, "cycle_life"]))

    # check against the numbers in the report (Appendix B, question D5)
    print({k: d[k] for k in ("first_cycle", "last_cycle", "cycle_at_q_max",
                             "q_first_Ah", "fade_pct_per_100cyc_early",
                             "fade_pct_per_100cyc_late", "cycles_to_eol")})

    out_dir = path("results") / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    plot(g["cycle"].to_numpy(float), g["QDischarge"].to_numpy(float), d,
         str(out_dir / "b1c6_capacity.pdf"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
