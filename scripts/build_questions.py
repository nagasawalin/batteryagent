"""
scripts/build_questions.py — generate the 30-question evaluation set.

    uv run python scripts/build_questions.py

Reads data/processed/{cells,summary}.parquet, picks cells by fixed rules,
fills the question templates, and writes

    eval/questions.jsonl          the set every system and the judge use
    results/questions_preview.md  a review table (paste into the appendix)

Design
------
* Cells are chosen by RULES (shortest-lived valid cell, same policy with the
  largest life spread, ...), not by hand, so the choice is reproducible and
  can be stated in one sentence in the report.
* Reference facts come from features.derive_cell and the two tools — the same
  code the agent calls — so a reference number and a tool number cannot drift.
  The price is circularity: the facts are only as right as features.py. Say so
  in Limitations; the spot-check of 5 judgements partly covers it.
* `reference` is EVALUATION MATERIAL ONLY. Nothing under agent/ or
  eval/baselines.py may read it. run_eval.py passes systems `question` only.

Split: 2 questions per type go to dev (10), the rest to test (20).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from batteryagent.data.features import derive_cell, parse_policy  # noqa: E402
from batteryagent.tools.cell_spec import CELL_SPEC, EXCLUSIONS, get_cell_spec  # noqa: E402

CACHE_DIR = Path("data/processed")
OUT_JSONL = Path("eval/questions.jsonl")
OUT_MD = Path("results/questions_preview.md")

VALID = ("interpolated", "dataset_field")


# ------------------------------------------------------------------ helpers
def clean(x):
    """NaN -> None and numpy scalars -> Python, recursively. JSON has no NaN."""
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if math.isnan(float(x)) else float(x)
    if isinstance(x, np.integer):
        return int(x)
    return x


def build_inventory() -> tuple[pd.DataFrame, pd.DataFrame]:
    cells = pd.read_parquet(CACHE_DIR / "cells.parquet")
    summary = pd.read_parquet(CACHE_DIR / "summary.parquet")
    rows = []
    for _, c in cells.iterrows():
        g = summary[summary.cell_id == c.cell_id]
        d = derive_cell(g, cycle_life=float(c.cycle_life))
        d = {f"d_{k}": v for k, v in d.items()}      # prefix: no clash with cells cols
        p = parse_policy(c.policy)
        rows.append({"cell_id": c.cell_id, **d,
                     "c1": p.get("step1_c_rate"), "c2": p.get("step2_c_rate"),
                     "switch_soc": p.get("switch_soc_pct")})
    inv = cells.merge(pd.DataFrame(rows), on="cell_id").sort_values("cell_index")
    return inv.set_index("cell_id", drop=False), summary


def pick_roles(inv: pd.DataFrame) -> dict[str, str]:
    """Every role is a fixed rule over the valid cells. Ties -> lowest index."""
    v = inv[inv.d_eol_method.isin(VALID)].copy()
    life = v.d_cycles_to_eol
    r: dict[str, str] = {}

    r["short"] = life.idxmin()
    r["long"] = life.idxmax()
    r["median"] = (life - life.median()).abs().idxmin()

    # Later roles avoid cells already used, so the set covers more cells;
    # falls back to a used cell only if nothing else qualifies.
    def first_unused(ordered) -> str:
        used = set(r.values())
        for c in ordered:
            if c not in used:
                return c
        return ordered[0]

    # Acceleration as late minus early rate. A ratio is dominated by the
    # near-zero early rates of LFP and just picks the flattest early window.
    accel = (v.d_fade_pct_per_100cyc_late - v.d_fade_pct_per_100cyc_early)
    r["accel"] = first_unused(accel.sort_values(ascending=False).index)
    r["irmax"] = first_unused(v.d_ir_growth_pct.sort_values(ascending=False).index)
    # Mean temperature, not the max: a single-cycle spike decides Tmax.
    r["hottest"] = first_unused(v.d_tavg_mean_C.sort_values(ascending=False).index)
    r["coolest"] = first_unused(v.d_tavg_mean_C.sort_values().index)

    by_c1 = v.sort_values(["c1", "cell_index"])
    r["fastest"] = first_unused(by_c1.index[::-1])
    slow = by_c1[by_c1.c1 < v.loc[r["fastest"], "c1"]]   # strictly slower
    r["slowest"] = first_unused(slow.index) if len(slow) else by_c1.index[0]

    two = v[v.switch_soc < 80]
    r["twostep"] = first_unused((two if len(two) else v).index)

    # same policy, largest spread in life: cell-to-cell variability
    grp = v.groupby("policy").d_cycles_to_eol
    multi = grp.count()[grp.count() >= 2].index
    if len(multi):
        spread = (grp.max() - grp.min())[multi]
        pol = spread.idxmax()
        same = v[v.policy == pol].sort_values("d_cycles_to_eol")
        r["var_short"], r["var_long"] = same.index[0], same.index[-1]
    else:
        r["var_short"], r["var_long"] = r["short"], r["long"]

    # trap cells: fixed by the data-layer findings, not by rule
    trunc = [c for c in EXCLUSIONS["continued_in_batch2"]
             if c in inv.index and inv.loc[c, "d_eol_method"] == "not_reached"]
    never = [c for c in EXCLUSIONS["never_reached_eol"]
             if c in inv.index and inv.loc[c, "d_eol_method"] == "not_reached"]
    r["trunc"] = trunc[0] if trunc else inv.index[0]
    r["never"] = never[0] if never else inv.index[-1]
    r["missing"] = f"b1c{int(inv.cell_index.max()) + 1}"   # one past the last cell
    return r


# ------------------------------------------------------------------ facts
DERIVED_KEYS = ("q_first_Ah", "q_last_Ah", "q_max_Ah", "cycle_at_q_max",
                "retention_pct", "soh_last_pct", "cycles_to_eol", "eol_method",
                "ir_first_ohm", "ir_last_ohm", "ir_growth_pct",
                "fade_pct_per_100cyc_early", "fade_pct_per_100cyc_late",
                "chargetime_mean_min", "tavg_mean_C", "tmax_max_C",
                "first_cycle", "last_cycle")


def F(inv, cid, *keys) -> dict:
    """Named derived facts of one cell, plus its policy."""
    row = inv.loc[cid]
    out = {"cell_id": cid, "policy": row.policy, "cycle_life_field": row.cycle_life}
    for k in keys or DERIVED_KEYS:
        out[k] = row[f"d_{k}"]
    return out


def close(a: float, b: float, rel: float = 0.15) -> bool:
    """Two cycle lives within 15% of each other count as 'similar'."""
    return abs(a - b) <= rel * max(a, b)


def spec(cid) -> dict:
    s = get_cell_spec(cid)
    return {k: s[k] for k in ("chemistry", "cathode", "anode", "form_factor",
                              "nominal_capacity_Ah", "voltage_window_V",
                              "ambient_temperature_C", "discharge_protocol",
                              "charge_tail", "eol_definition", "charge_policy")
            if k in s}


def q_at(summary, cid, target) -> dict:
    g = summary[summary.cell_id == cid]
    row = g.iloc[(g.cycle - target).abs().argmin()]
    return {"cell_id": cid, "cycle": int(row.cycle),
            "QDischarge_Ah": round(float(row.QDischarge), 4)}


# ------------------------------------------------------------------ templates
# type -> list of question builders; the first two of each type are dev.
# Each builder returns (question, cell_ids, facts, must_include, must_not,
# expected_tools, requires_literature, notes).

def build(inv, summary, R) -> list[dict]:
    life = lambda c: float(inv.loc[c, "d_cycles_to_eol"])          # noqa: E731
    ctime = lambda c: float(inv.loc[c, "d_chargetime_mean_min"])   # noqa: E731

    # Data-dependent rubric lines: the "right" conclusion for these pairs
    # depends on the numbers, so it is written from them, not assumed.
    fa, sl = R["fastest"], R["slowest"]
    m4_line = ("the two lives are similar, so the higher peak C-rate alone does not "
               "explain life here; per-step currents and cell variation matter"
               if close(life(fa), life(sl)) else
               "the higher-C-rate cell is shorter-lived, consistent with but not proof "
               "of the mechanism" if life(fa) < life(sl) else
               "the higher-C-rate cell lives longer, which the mechanism alone does "
               "not predict")
    c4_line = ("the cell with the higher initial C-rate does NOT have the shorter mean "
               "charge time, so 'faster charging' must be defined before answering"
               if ctime(fa) >= ctime(sl) else
               "the higher-C-rate cell also charges faster on average")
    ho, co = R["hottest"], R["coolest"]
    c6_line = ("lives are similar despite the temperature gap, so temperature does "
               "not explain a life difference here"
               if close(life(ho), life(co)) else
               "lives differ, but temperature is not independently controlled")

    S = []  # specification lookup
    S.append(dict(
        q=f"What charging protocol was cell {R['twostep']} cycled with? For each "
          f"charging step give the C-rate, the current in amperes and the SOC range "
          f"it covers.",
        cells=[R["twostep"]], facts=spec(R["twostep"]),
        inc=["step 1 C-rate, current in A and SOC range",
             "step 2 C-rate, current in A and SOC range",
             "the common charge tail above 80% SOC"],
        tools=["get_cell_spec"], lit=False))
    S.append(dict(
        q=f"What are the chemistry, form factor and nominal capacity of cell "
          f"{R['short']}, and at what discharge capacity is it considered at end of life?",
        cells=[R["short"]], facts=spec(R["short"]),
        inc=["LFP/graphite", "18650 cylindrical", "1.1 Ah nominal",
             "0.88 Ah, i.e. 80% of nominal"],
        tools=["get_cell_spec"], lit=False))
    S.append(dict(
        q=f"Under what ambient temperature and discharge conditions was cell "
          f"{R['long']} cycled?",
        cells=[R["long"]], facts=spec(R["long"]),
        inc=["chamber temperature", "discharge rate and cut-off voltage",
             "discharge identical across cells"],
        tools=["get_cell_spec"], lit=False))
    S.append(dict(
        q=f"What is the highest charging current, in amperes, applied to cell "
          f"{R['fastest']}, and over which SOC window?",
        cells=[R["fastest"]], facts=spec(R["fastest"]),
        inc=["step-1 current in A (C-rate x nominal capacity)", "SOC window 0 to switch SOC"],
        tools=["get_cell_spec"], lit=False))
    S.append(dict(
        q=f"What voltage window is cell {R['median']} operated in?",
        cells=[R["median"]], facts=spec(R["median"]),
        inc=["lower and upper voltage limit"],
        tools=["get_cell_spec"], lit=False))

    D = []  # data interpretation
    D.append(dict(
        q=f"What is the capacity retention of cell {R['median']} at the end of its "
          f"recorded data, and what is its state of health relative to nominal capacity?",
        cells=[R["median"]],
        facts=F(inv, R["median"], "q_first_Ah", "q_last_Ah", "retention_pct",
                "soh_last_pct", "last_cycle"),
        inc=["retention relative to the first recorded cycle",
             "SOH relative to 1.1 Ah", "the two are different baselines"],
        tools=["get_cell_spec", "get_cell_data"], lit=False))
    D.append(dict(
        q=f"How many cycles does cell {R['short']} last before reaching end of life, "
          f"and how was that number obtained?",
        cells=[R["short"]],
        facts=F(inv, R["short"], "cycles_to_eol", "eol_method", "last_cycle", "q_last_Ah"),
        inc=["cycles to end of life",
             "how it was obtained (eol_method), e.g. record stops one cycle "
             "before the 0.88 Ah threshold"],
        tools=["get_cell_spec", "get_cell_data"], lit=False))
    D.append(dict(
        q=f"At which cycle does the discharge capacity of cell {R['long']} peak, "
          f"and by how much does it exceed its first recorded value?",
        cells=[R["long"]],
        facts={**F(inv, R["long"], "q_first_Ah", "q_max_Ah", "cycle_at_q_max",
                   "first_cycle"),
               "rise_Ah": round(inv.loc[R["long"], "d_q_max_Ah"]
                                - inv.loc[R["long"], "d_q_first_Ah"], 4)},
        inc=["cycle of peak capacity", "rise in Ah or %",
             "first recorded cycle is cycle 2"],
        tools=["get_cell_data"], lit=False))
    D.append(dict(
        q=f"How much did the internal resistance of cell {R['irmax']} change over its "
          f"recorded life?",
        cells=[R["irmax"]],
        facts=F(inv, R["irmax"], "ir_first_ohm", "ir_last_ohm", "ir_growth_pct"),
        inc=["first and last IR", "growth in %"],
        tools=["get_cell_data"], lit=False))
    D.append(dict(
        q=f"Does the capacity fade of cell {R['accel']} accelerate late in life? "
          f"Quantify it.",
        cells=[R["accel"]],
        facts=F(inv, R["accel"], "fade_pct_per_100cyc_early",
                "fade_pct_per_100cyc_late", "cycle_at_q_max", "last_cycle"),
        inc=["early and late fade rate with their windows", "yes, with the ratio"],
        tools=["get_cell_data"], lit=False))
    mid = int(round(inv.loc[R["median"], "d_last_cycle"] / 2, -2))
    D.append(dict(
        q=f"What was the discharge capacity of cell {R['median']} around cycle {mid}?",
        cells=[R["median"]], facts=q_at(summary, R["median"], mid),
        inc=["capacity near that cycle, within the subsampling"],
        tools=["get_cell_data"], lit=False,
        notes="Should use cycle_range; accept any recorded cycle within +/-10."))
    D.append(dict(
        q=f"What were the mean and the maximum cell temperatures recorded for cell "
          f"{R['hottest']}?",
        cells=[R["hottest"]],
        facts=F(inv, R["hottest"], "tavg_mean_C", "tmax_max_C"),
        inc=["mean of per-cycle Tavg", "maximum Tmax"],
        tools=["get_cell_data"], lit=False))

    M = []  # mechanism attribution
    M.append(dict(
        q=f"Cell {R['accel']} fades much faster late in life than early. Which "
          f"degradation mechanisms could explain this acceleration in an LFP/graphite "
          f"cell cycled with fast charging?",
        cells=[R["accel"]],
        facts=F(inv, R["accel"], "fade_pct_per_100cyc_early", "fade_pct_per_100cyc_late"),
        inc=["the early vs late fade numbers from the data",
             "at least one mechanism supported by a citation (e.g. lithium plating, "
             "loss of lithium inventory, loss of negative-electrode active material)",
             "states that the capacity data alone cannot identify the mechanism"],
        bad=["asserts a single mechanism as proven by the data"],
        tools=["get_cell_spec", "get_cell_data", "search_literature"], lit=True))
    M.append(dict(
        q=f"Discharge capacity of cell {R['long']} rises during the first tens of "
          f"cycles before it fades. What could explain this initial rise?",
        cells=[R["long"]], facts=F(inv, R["long"], "cycle_at_q_max", "q_first_Ah", "q_max_Ah"),
        # CHANGED 2026-09-27: the accepted explanation goes into must_include,
        # because the judge sees facts, must_include and must_not but NOT notes.
        inc=["the rise from the data (cycle of peak, size)",
             "a cited explanation; accepted: charge (lithium) stored in the part "
             "of the negative electrode that extends beyond the positive electrode "
             "(anode overhang / passive electrode effect); another explanation "
             "counts only if the cited passage supports it",
             "uncertainty about whether it applies to this cell (e.g. the storage "
             "history before testing is not reported, the literature evidence "
             "comes from other cells, or temperature affects the exact peak)"],
        bad=["states the cause without a citation"],
        tools=["get_cell_data", "search_literature"], lit=True,
        notes="Sources for the accepted explanation: severson2019 p. 3 (also: "
              "capacity at cycle 100 exceeded the initial value for 81% of "
              "cells); lewerenz2017a pp. 2, 4-5; gyenes2015 pp. 2, 4-6. Data "
              "check 2026-09-27: the smooth rise plateaus near cycles 38-56 at "
              "about 1.081 Ah; the maximum at cycle 70 coincides with a Tavg "
              "excursion (32.6 C at cycle 68 vs about 30.8 C), and peak cycles "
              "of all batch-1 cells cluster at 53-57 and 68-71, matching the "
              "chamber temperature fluctuations near cycles 55 and 70 reported "
              "in severson2019 pp. 5-6. Mentioning temperature is acceptable, "
              "not required."))
    M.append(dict(
        q=f"Why might the internal resistance of cell {R['irmax']} increase with "
          f"cycling, and how is resistance growth related to capacity fade?",
        cells=[R["irmax"]], facts=F(inv, R["irmax"], "ir_growth_pct", "retention_pct"),
        inc=["the IR growth from the data", "a cited mechanism (e.g. SEI growth)",
             "the link to capacity fade, cited"],
        tools=["get_cell_data", "search_literature"], lit=True))
    M.append(dict(
        q=f"Cell {R['fastest']} starts charging at a higher C-rate than cell "
          f"{R['slowest']}. What degradation mechanism does the literature associate "
          f"with high-rate charging of graphite anodes, and is it consistent with the "
          f"observed cycle lives?",
        cells=[R["fastest"], R["slowest"]],
        facts={"a": {**spec(R["fastest"])["charge_policy"],
                     **F(inv, R["fastest"], "cycles_to_eol")},
               "b": {**spec(R["slowest"])["charge_policy"],
                     **F(inv, R["slowest"], "cycles_to_eol")}},
        inc=["both policies and both cycle lives",
             "lithium plating on graphite at high charge rate, cited",
             m4_line, "one pair is not evidence of a trend"],
        tools=["get_cell_spec", "get_cell_data", "search_literature"], lit=True))
    M.append(dict(
        q=f"With the measurements available for cell {R['median']}, can loss of "
          f"lithium inventory be distinguished from loss of active material? What "
          f"would be needed?",
        cells=[R["median"]], facts={"available": ["QDischarge", "QCharge", "IR",
                                                   "Tavg", "Tmax", "Tmin", "chargetime"]},
        inc=["no, not from per-cycle capacity and one IR value",
             "what would be needed, cited (e.g. slow-rate ICA/DVA, EIS)"],
        bad=["claims a split between LLI and LAM from the data"],
        tools=["get_cell_data", "search_literature"], lit=True))
    M.append(dict(
        q="According to the study that produced this dataset, why is cycle life hard "
          "to predict from early capacity, and which early-cycle signal did the "
          "authors find predictive?",
        cells=[], facts={},
        inc=["capacity barely changes in early cycles",
             "the change in the discharge voltage curve between two early cycles "
             "(Delta Q(V)), cited to Severson et al. 2019"],
        tools=["search_literature"], lit=True,
        notes="Requires the Severson 2019 paper in the corpus."))

    C = []  # comparison
    C.append(dict(
        q=f"Why does cell {R['short']} reach end of life so much earlier than cell "
          f"{R['long']}?",
        cells=[R["short"], R["long"]],
        facts={"a": F(inv, R["short"], "cycles_to_eol", "fade_pct_per_100cyc_late"),
               "b": F(inv, R["long"], "cycles_to_eol", "fade_pct_per_100cyc_late"),
               "policy_a": spec(R["short"])["charge_policy"],
               "policy_b": spec(R["long"])["charge_policy"]},
        inc=["both cycle lives", "same cell model, so charging policy is the "
             "controlled difference", "cited mechanism for the policy effect",
             "cell-to-cell variation as a caveat"],
        tools=["get_cell_spec", "get_cell_data", "search_literature"], lit=True))
    C.append(dict(
        q=f"Cells {R['var_short']} and {R['var_long']} were charged with the same "
          f"protocol. How different are their cycle lives, and what could explain the "
          f"difference?",
        cells=[R["var_short"], R["var_long"]],
        facts={"a": F(inv, R["var_short"], "cycles_to_eol", "tavg_mean_C", "tmax_max_C",
                      "q_first_Ah"),
               "b": F(inv, R["var_long"], "cycles_to_eol", "tavg_mean_C", "tmax_max_C",
                      "q_first_Ah")},
        inc=["both lives and the gap", "policy is identical, so not the cause",
             "cell-to-cell variability, cited", "cannot be pinned down from this data"],
        bad=["attributes the gap to the charging policy"],
        tools=["get_cell_spec", "get_cell_data", "search_literature"], lit=True))
    C.append(dict(
        q=f"Compare the internal resistance growth of cells {R['short']} and "
          f"{R['long']}.",
        cells=[R["short"], R["long"]],
        facts={"a": F(inv, R["short"], "ir_first_ohm", "ir_last_ohm", "ir_growth_pct"),
               "b": F(inv, R["long"], "ir_first_ohm", "ir_last_ohm", "ir_growth_pct")},
        inc=["both growth figures", "which grew more"],
        tools=["get_cell_data"], lit=False))
    C.append(dict(
        q=f"Compare the average charge time and cycle life of cells {R['fastest']} and "
          f"{R['slowest']}. Is faster charging associated with shorter life here?",
        cells=[R["fastest"], R["slowest"]],
        facts={"a": F(inv, R["fastest"], "chargetime_mean_min", "cycles_to_eol"),
               "b": F(inv, R["slowest"], "chargetime_mean_min", "cycles_to_eol")},
        inc=["both charge times and lives", c4_line,
             "two cells cannot establish a trend"],
        tools=["get_cell_spec", "get_cell_data"], lit=False))
    C.append(dict(
        q=f"Rank cells {R['short']}, {R['median']} and {R['long']} by their late-life "
          f"fade rate.",
        cells=[R["short"], R["median"], R["long"]],
        facts={c: F(inv, c, "fade_pct_per_100cyc_late")
               for c in (R["short"], R["median"], R["long"])},
        inc=["correct order with the three rates", "definition of the late window"],
        tools=["get_cell_data"], lit=False))
    C.append(dict(
        q=f"Cells {R['hottest']} and {R['coolest']} ran at different average "
          f"temperatures. Do their cycle lives differ, and could temperature explain it?",
        cells=[R["hottest"], R["coolest"]],
        facts={"a": F(inv, R["hottest"], "tmax_max_C", "tavg_mean_C", "cycles_to_eol"),
               "b": F(inv, R["coolest"], "tmax_max_C", "tavg_mean_C", "cycles_to_eol"),
               "policy_a": inv.loc[R["hottest"], "policy"],
               "policy_b": inv.loc[R["coolest"], "policy"]},
        inc=["both temperatures and lives", c6_line,
             "cell temperature is measured, not set: all cells share one chamber "
             "setpoint, so differences come from policy, cell or fixture",
             "hedged conclusion"],
        bad=["treats temperature as an independent cause"],
        tools=["get_cell_spec", "get_cell_data", "search_literature"], lit=True))

    T = []  # traps: the right answer is (partly) "the data cannot say"
    T.append(dict(
        q=f"What is the cycle life of cell {R['trunc']}?",
        cells=[R["trunc"]],
        facts=F(inv, R["trunc"], "cycles_to_eol", "eol_method", "retention_pct",
                "q_last_Ah", "last_cycle"),
        inc=["cannot be determined from this data",
             "record stops far above 0.88 Ah (give retention or last capacity)",
             "testing continued in a batch not used here, if flagged by the tools"],
        bad=["states the cycle_life field value as the cell's cycle life"],
        tools=["get_cell_spec", "get_cell_data"], lit=False))
    T.append(dict(
        q=f"How many cycles did cell {R['never']} take to reach 80% of its nominal "
          f"capacity?",
        cells=[R["never"]],
        facts=F(inv, R["never"], "cycles_to_eol", "eol_method", "q_last_Ah",
                "soh_last_pct", "last_cycle"),
        inc=["it did not reach 80% within the record",
             "last recorded cycle and capacity or SOH"],
        bad=["gives a number of cycles to 80%"],
        tools=["get_cell_data"], lit=False))
    T.append(dict(
        q=f"What was the discharge capacity of cell {R['median']} in its first cycle?",
        cells=[R["median"]],
        facts={**F(inv, R["median"], "first_cycle", "q_first_Ah"),
               "cycle_1": "recorded but empty; dropped by the loader"},
        inc=["cycle 1 has no valid measurement",
             "first valid value is cycle 2 with its capacity"],
        bad=["presents the cycle-2 value as cycle 1"],
        tools=["get_cell_data"], lit=False))
    T.append(dict(
        q="How does ambient temperature affect the cycle life of the cells in this "
          "dataset?",
        cells=[], facts={"ambient_temperature_C": CELL_SPEC["ambient_temperature_C"]},
        inc=["all cells were cycled at the same chamber temperature",
             "so the dataset cannot show an ambient-temperature effect",
             "any general statement is from literature and cited"],
        bad=["infers an ambient-temperature effect from these cells"],
        tools=["get_cell_spec"], lit=False))
    T.append(dict(
        q=f"What is the cycle life of cell {R['missing']}?",
        cells=[R["missing"]], facts={"exists": False, "n_cells": int(len(inv))},
        inc=["the cell does not exist in the dataset"],
        bad=["gives any cycle life"],
        tools=["get_cell_data"], lit=False))
    T.append(dict(
        q="Which cell in this dataset has an NMC cathode, and how does its degradation "
          "compare with the LFP cells?",
        cells=[], facts={"chemistry": CELL_SPEC["chemistry"]},
        inc=["no cell has an NMC cathode; all are LFP/graphite",
             "a comparison can only come from literature, cited"],
        bad=["names a cell as NMC"],
        tools=["get_cell_spec"], lit=False))

    out = []
    for code, group in (("S", S), ("D", D), ("M", M), ("C", C), ("T", T)):
        for i, t in enumerate(group, 1):
            out.append({
                "id": f"{code}{i}",
                "split": "dev" if i <= 2 else "test",
                "type": {"S": "spec_lookup", "D": "data_interpretation",
                         "M": "mechanism", "C": "comparison", "T": "trap"}[code],
                "question": t["q"],
                "cell_ids": t["cells"],
                "expected_tools": t["tools"],
                "requires_literature": t["lit"],
                "reference": {
                    "facts": clean(t["facts"]),
                    "must_include": t["inc"],
                    "must_not": t.get("bad", []),
                    "notes": t.get("notes", ""),
                },
            })
    return out


# ------------------------------------------------------------------ outputs
def write_md(qs: list[dict], roles: dict, path: Path) -> None:
    lines = ["# Question set preview", "",
             "Cell roles (rules in scripts/build_questions.py):", ""]
    lines += [f"- `{k}` = {v}" for k, v in roles.items()]
    lines += ["", "| id | split | type | question | lit |", "|---|---|---|---|---|"]
    for q in qs:
        lines.append(f"| {q['id']} | {q['split']} | {q['type']} | {q['question']} | "
                     f"{'yes' if q['requires_literature'] else ''} |")
    lines += ["", "## Reference facts", ""]
    for q in qs:
        lines.append(f"**{q['id']}** `{json.dumps(q['reference']['facts'])}`")
        lines.append("")
    path.write_text("\n".join(lines))


def main() -> int:
    inv, summary = build_inventory()
    roles = pick_roles(inv)
    qs = build(inv, summary, roles)

    assert len(qs) == 30, len(qs)
    assert sum(q["split"] == "dev" for q in qs) == 10

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSONL.open("w") as f:
        for q in qs:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    write_md(qs, roles, OUT_MD)

    print("roles:", json.dumps(roles))
    dup = {k: v for k, v in roles.items() if list(roles.values()).count(v) > 1}
    if dup:
        print("note: some roles share a cell:", dup)
    print(f"wrote {OUT_JSONL} ({len(qs)} questions) and {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
