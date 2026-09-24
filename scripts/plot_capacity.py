"""Plot capacity-fade curves for NASA PCoE battery cells.

Reads the raw .mat files (nested MATLAB struct arrays, loaded by scipy.io as
arrays of numpy.void records) for B0005/B0006/B0007/B0018, pulls the
discharged capacity (Ah) out of every 'discharge' cycle, and plots capacity
vs. discharge-cycle index for all four cells on one figure.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import scipy.io as sio

DATA_DIR = Path("data/raw")
OUTPUT_PATH = Path("figures/capacity_fade.png")
BATTERY_IDS = ["B0005", "B0006", "B0007", "B0018"]

# dataviz categorical palette, first 4 slots (blue/orange/aqua/yellow),
# validated for adjacent-pair CVD safety on line charts.
SERIES_COLORS = {
    "B0005": "#2a78d6",
    "B0006": "#eb6834",
    "B0007": "#1baf7a",
    "B0018": "#eda100",
}


def load_discharge_capacities(mat_path: Path) -> list[float]:
    """Extract the discharge capacity (Ah) of each discharge cycle, in order."""
    battery_id = mat_path.stem
    mat = sio.loadmat(mat_path, simplify_cells=False)

    # mat[battery_id] is a (1, 1) struct array; [0, 0] pulls out the single
    # numpy.void record, whose 'cycle' field is itself a (1, N) struct array.
    cycles = mat[battery_id][0, 0]["cycle"][0]

    capacities = []
    for cycle in cycles:
        if str(cycle["type"][0]) != "discharge":
            continue
        # 'data' is a (1, 1) struct array; 'Capacity' inside it is a (1, 1)
        # numeric array holding a single scalar.
        capacity = cycle["data"][0, 0]["Capacity"][0, 0]
        capacities.append(float(capacity))
    return capacities


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)

    for battery_id in BATTERY_IDS:
        mat_path = DATA_DIR / f"{battery_id}.mat"
        capacities = load_discharge_capacities(mat_path)
        cycle_numbers = range(1, len(capacities) + 1)
        ax.plot(
            cycle_numbers,
            capacities,
            label=battery_id,
            color=SERIES_COLORS[battery_id],
            linewidth=2,
        )

    ax.set_xlabel("Discharge cycle number")
    ax.set_ylabel("Capacity (Ah)")
    ax.set_title("NASA PCoE Battery Capacity Fade")
    ax.grid(True, alpha=0.3)
    ax.legend(title="Battery")

    fig.tight_layout()
    fig.savefig(OUTPUT_PATH)
    print(f"Saved figure to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
