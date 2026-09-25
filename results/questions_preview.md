# Question set preview

Cell roles (rules in scripts/build_questions.py):

- `short` = b1c20
- `long` = b1c5
- `median` = b1c11
- `accel` = b1c6
- `irmax` = b1c21
- `hottest` = b1c28
- `coolest` = b1c31
- `fastest` = b1c45
- `slowest` = b1c7
- `twostep` = b1c9
- `var_short` = b1c6
- `var_long` = b1c7
- `trunc` = b1c0
- `never` = b1c8
- `missing` = b1c46

| id | split | type | question | lit |
|---|---|---|---|---|
| S1 | dev | spec_lookup | What charging protocol was cell b1c9 cycled with? For each charging step give the C-rate, the current in amperes and the SOC range it covers. |  |
| S2 | dev | spec_lookup | What are the chemistry, form factor and nominal capacity of cell b1c20, and at what discharge capacity is it considered at end of life? |  |
| S3 | test | spec_lookup | Under what ambient temperature and discharge conditions was cell b1c5 cycled? |  |
| S4 | test | spec_lookup | What is the highest charging current, in amperes, applied to cell b1c45, and over which SOC window? |  |
| S5 | test | spec_lookup | What voltage window is cell b1c11 operated in? |  |
| D1 | dev | data_interpretation | What is the capacity retention of cell b1c11 at the end of its recorded data, and what is its state of health relative to nominal capacity? |  |
| D2 | dev | data_interpretation | How many cycles does cell b1c20 last before reaching end of life, and how was that number obtained? |  |
| D3 | test | data_interpretation | At which cycle does the discharge capacity of cell b1c5 peak, and by how much does it exceed its first recorded value? |  |
| D4 | test | data_interpretation | How much did the internal resistance of cell b1c21 change over its recorded life? |  |
| D5 | test | data_interpretation | Does the capacity fade of cell b1c6 accelerate late in life? Quantify it. |  |
| D6 | test | data_interpretation | What was the discharge capacity of cell b1c11 around cycle 400? |  |
| D7 | test | data_interpretation | What were the mean and the maximum cell temperatures recorded for cell b1c28? |  |
| M1 | dev | mechanism | Cell b1c6 fades much faster late in life than early. Which degradation mechanisms could explain this acceleration in an LFP/graphite cell cycled with fast charging? | yes |
| M2 | dev | mechanism | Discharge capacity of cell b1c5 rises during the first tens of cycles before it fades. What could explain this initial rise? | yes |
| M3 | test | mechanism | Why might the internal resistance of cell b1c21 increase with cycling, and how is resistance growth related to capacity fade? | yes |
| M4 | test | mechanism | Cell b1c45 starts charging at a higher C-rate than cell b1c7. What degradation mechanism does the literature associate with high-rate charging of graphite anodes, and is it consistent with the observed cycle lives? | yes |
| M5 | test | mechanism | With the measurements available for cell b1c11, can loss of lithium inventory be distinguished from loss of active material? What would be needed? | yes |
| M6 | test | mechanism | According to the study that produced this dataset, why is cycle life hard to predict from early capacity, and which early-cycle signal did the authors find predictive? | yes |
| C1 | dev | comparison | Why does cell b1c20 reach end of life so much earlier than cell b1c5? | yes |
| C2 | dev | comparison | Cells b1c6 and b1c7 were charged with the same protocol. How different are their cycle lives, and what could explain the difference? | yes |
| C3 | test | comparison | Compare the internal resistance growth of cells b1c20 and b1c5. |  |
| C4 | test | comparison | Compare the average charge time and cycle life of cells b1c45 and b1c7. Is faster charging associated with shorter life here? |  |
| C5 | test | comparison | Rank cells b1c20, b1c11 and b1c5 by their late-life fade rate. |  |
| C6 | test | comparison | Cells b1c28 and b1c31 ran at different average temperatures. Do their cycle lives differ, and could temperature explain it? | yes |
| T1 | dev | trap | What is the cycle life of cell b1c0? |  |
| T2 | dev | trap | How many cycles did cell b1c8 take to reach 80% of its nominal capacity? |  |
| T3 | test | trap | What was the discharge capacity of cell b1c11 in its first cycle? |  |
| T4 | test | trap | How does ambient temperature affect the cycle life of the cells in this dataset? |  |
| T5 | test | trap | What is the cycle life of cell b1c46? |  |
| T6 | test | trap | Which cell in this dataset has an NMC cathode, and how does its degradation compare with the LFP cells? |  |

## Reference facts

**S1** `{"chemistry": "LFP/graphite", "cathode": "LFP (LiFePO4)", "anode": "graphite", "form_factor": "18650 cylindrical", "nominal_capacity_Ah": 1.1, "voltage_window_V": [2.0, 3.6], "ambient_temperature_C": 30, "discharge_protocol": "4C CC-CV to 2.0 V, cut-off C/50, identical for every cell", "charge_tail": "1C CC-CV to 3.6 V from 80% SOC, cut-off C/50", "eol_definition": "discharge capacity at 80% of nominal, i.e. 0.88 Ah", "charge_policy": {"policy": "5.4C(40%)-3.6C", "parsed": true, "step1_c_rate": 5.4, "step1_current_A": 5.94, "switch_soc_pct": 40, "step2_c_rate": 3.6, "step2_current_A": 3.96}}`

**S2** `{"chemistry": "LFP/graphite", "cathode": "LFP (LiFePO4)", "anode": "graphite", "form_factor": "18650 cylindrical", "nominal_capacity_Ah": 1.1, "voltage_window_V": [2.0, 3.6], "ambient_temperature_C": 30, "discharge_protocol": "4C CC-CV to 2.0 V, cut-off C/50, identical for every cell", "charge_tail": "1C CC-CV to 3.6 V from 80% SOC, cut-off C/50", "eol_definition": "discharge capacity at 80% of nominal, i.e. 0.88 Ah", "charge_policy": {"policy": "5.4C(80%)-5.4C", "parsed": true, "step1_c_rate": 5.4, "step1_current_A": 5.94, "switch_soc_pct": 80, "step2_c_rate": 5.4, "step2_current_A": 5.94}}`

**S3** `{"chemistry": "LFP/graphite", "cathode": "LFP (LiFePO4)", "anode": "graphite", "form_factor": "18650 cylindrical", "nominal_capacity_Ah": 1.1, "voltage_window_V": [2.0, 3.6], "ambient_temperature_C": 30, "discharge_protocol": "4C CC-CV to 2.0 V, cut-off C/50, identical for every cell", "charge_tail": "1C CC-CV to 3.6 V from 80% SOC, cut-off C/50", "eol_definition": "discharge capacity at 80% of nominal, i.e. 0.88 Ah", "charge_policy": {"policy": "4.4C(80%)-4.4C", "parsed": true, "step1_c_rate": 4.4, "step1_current_A": 4.84, "switch_soc_pct": 80, "step2_c_rate": 4.4, "step2_current_A": 4.84}}`

**S4** `{"chemistry": "LFP/graphite", "cathode": "LFP (LiFePO4)", "anode": "graphite", "form_factor": "18650 cylindrical", "nominal_capacity_Ah": 1.1, "voltage_window_V": [2.0, 3.6], "ambient_temperature_C": 30, "discharge_protocol": "4C CC-CV to 2.0 V, cut-off C/50, identical for every cell", "charge_tail": "1C CC-CV to 3.6 V from 80% SOC, cut-off C/50", "eol_definition": "discharge capacity at 80% of nominal, i.e. 0.88 Ah", "charge_policy": {"policy": "8C(35%)-3.6C", "parsed": true, "step1_c_rate": 8.0, "step1_current_A": 8.8, "switch_soc_pct": 35, "step2_c_rate": 3.6, "step2_current_A": 3.96}}`

**S5** `{"chemistry": "LFP/graphite", "cathode": "LFP (LiFePO4)", "anode": "graphite", "form_factor": "18650 cylindrical", "nominal_capacity_Ah": 1.1, "voltage_window_V": [2.0, 3.6], "ambient_temperature_C": 30, "discharge_protocol": "4C CC-CV to 2.0 V, cut-off C/50, identical for every cell", "charge_tail": "1C CC-CV to 3.6 V from 80% SOC, cut-off C/50", "eol_definition": "discharge capacity at 80% of nominal, i.e. 0.88 Ah", "charge_policy": {"policy": "5.4C(50%)-3C", "parsed": true, "step1_c_rate": 5.4, "step1_current_A": 5.94, "switch_soc_pct": 50, "step2_c_rate": 3.0, "step2_current_A": 3.3}}`

**D1** `{"cell_id": "b1c11", "policy": "5.4C(50%)-3C", "cycle_life_field": 788.0, "q_first_Ah": 1.0538, "q_last_Ah": 0.8805, "retention_pct": 83.56, "soh_last_pct": 80.05, "last_cycle": 787.0}`

**D2** `{"cell_id": "b1c20", "policy": "5.4C(80%)-5.4C", "cycle_life_field": 534.0, "cycles_to_eol": 534.0, "eol_method": "dataset_field", "last_cycle": 533.0, "q_last_Ah": 0.8808}`

**D3** `{"cell_id": "b1c5", "policy": "4.4C(80%)-4.4C", "cycle_life_field": 1074.0, "q_first_Ah": 1.0761, "q_max_Ah": 1.0821, "cycle_at_q_max": 70.0, "first_cycle": 2.0, "rise_Ah": 0.006}`

**D4** `{"cell_id": "b1c21", "policy": "5.4C(80%)-5.4C", "cycle_life_field": 559.0, "ir_first_ohm": 0.01535, "ir_last_ohm": 0.02008, "ir_growth_pct": 30.8}`

**D5** `{"cell_id": "b1c6", "policy": "4.8C(80%)-4.8C", "cycle_life_field": 636.0, "fade_pct_per_100cyc_early": 0.467, "fade_pct_per_100cyc_late": 12.043, "cycle_at_q_max": 28.0, "last_cycle": 635.0}`

**D6** `{"cell_id": "b1c11", "cycle": 400, "QDischarge_Ah": 1.0457}`

**D7** `{"cell_id": "b1c28", "policy": "6C(50%)-3C", "cycle_life_field": 860.0, "tavg_mean_C": 35.11, "tmax_max_C": 42.74}`

**M1** `{"cell_id": "b1c6", "policy": "4.8C(80%)-4.8C", "cycle_life_field": 636.0, "fade_pct_per_100cyc_early": 0.467, "fade_pct_per_100cyc_late": 12.043}`

**M2** `{"cell_id": "b1c5", "policy": "4.4C(80%)-4.4C", "cycle_life_field": 1074.0, "cycle_at_q_max": 70.0, "q_first_Ah": 1.0761, "q_max_Ah": 1.0821}`

**M3** `{"cell_id": "b1c21", "policy": "5.4C(80%)-5.4C", "cycle_life_field": 559.0, "ir_growth_pct": 30.8, "retention_pct": 81.31}`

**M4** `{"a": {"policy": "8C(35%)-3.6C", "parsed": true, "step1_c_rate": 8.0, "step1_current_A": 8.8, "switch_soc_pct": 35, "step2_c_rate": 3.6, "step2_current_A": 3.96, "cell_id": "b1c45", "cycle_life_field": 599.0, "cycles_to_eol": 599.0}, "b": {"policy": "4.8C(80%)-4.8C", "parsed": true, "step1_c_rate": 4.8, "step1_current_A": 5.28, "switch_soc_pct": 80, "step2_c_rate": 4.8, "step2_current_A": 5.28, "cell_id": "b1c7", "cycle_life_field": 870.0, "cycles_to_eol": 870.0}}`

**M5** `{"available": ["QDischarge", "QCharge", "IR", "Tavg", "Tmax", "Tmin", "chargetime"]}`

**M6** `{}`

**C1** `{"a": {"cell_id": "b1c20", "policy": "5.4C(80%)-5.4C", "cycle_life_field": 534.0, "cycles_to_eol": 534.0, "fade_pct_per_100cyc_late": 7.145}, "b": {"cell_id": "b1c5", "policy": "4.4C(80%)-4.4C", "cycle_life_field": 1074.0, "cycles_to_eol": 1074.0, "fade_pct_per_100cyc_late": 8.844}, "policy_a": {"policy": "5.4C(80%)-5.4C", "parsed": true, "step1_c_rate": 5.4, "step1_current_A": 5.94, "switch_soc_pct": 80, "step2_c_rate": 5.4, "step2_current_A": 5.94}, "policy_b": {"policy": "4.4C(80%)-4.4C", "parsed": true, "step1_c_rate": 4.4, "step1_current_A": 4.84, "switch_soc_pct": 80, "step2_c_rate": 4.4, "step2_current_A": 4.84}}`

**C2** `{"a": {"cell_id": "b1c6", "policy": "4.8C(80%)-4.8C", "cycle_life_field": 636.0, "cycles_to_eol": 636.0, "tavg_mean_C": 33.11, "tmax_max_C": 40.6, "q_first_Ah": 1.0758}, "b": {"cell_id": "b1c7", "policy": "4.8C(80%)-4.8C", "cycle_life_field": 870.0, "cycles_to_eol": 870.0, "tavg_mean_C": 32.9, "tmax_max_C": 40.47, "q_first_Ah": 1.0939}}`

**C3** `{"a": {"cell_id": "b1c20", "policy": "5.4C(80%)-5.4C", "cycle_life_field": 534.0, "ir_first_ohm": 0.01574, "ir_last_ohm": 0.01943, "ir_growth_pct": 23.44}, "b": {"cell_id": "b1c5", "policy": "4.4C(80%)-4.4C", "cycle_life_field": 1074.0, "ir_first_ohm": 0.01644, "ir_last_ohm": 0.01953, "ir_growth_pct": 18.8}}`

**C4** `{"a": {"cell_id": "b1c45", "policy": "8C(35%)-3.6C", "cycle_life_field": 599.0, "chargetime_mean_min": 11.28, "cycles_to_eol": 599.0}, "b": {"cell_id": "b1c7", "policy": "4.8C(80%)-4.8C", "cycle_life_field": 870.0, "chargetime_mean_min": 10.49, "cycles_to_eol": 870.0}}`

**C5** `{"b1c20": {"cell_id": "b1c20", "policy": "5.4C(80%)-5.4C", "cycle_life_field": 534.0, "fade_pct_per_100cyc_late": 7.145}, "b1c11": {"cell_id": "b1c11", "policy": "5.4C(50%)-3C", "cycle_life_field": 788.0, "fade_pct_per_100cyc_late": 7.98}, "b1c5": {"cell_id": "b1c5", "policy": "4.4C(80%)-4.4C", "cycle_life_field": 1074.0, "fade_pct_per_100cyc_late": 8.844}}`

**C6** `{"a": {"cell_id": "b1c28", "policy": "6C(50%)-3C", "cycle_life_field": 860.0, "tmax_max_C": 42.74, "tavg_mean_C": 35.11, "cycles_to_eol": 860.0}, "b": {"cell_id": "b1c31", "policy": "6C(50%)-3.6C", "cycle_life_field": 876.0, "tmax_max_C": 34.4, "tavg_mean_C": 30.98, "cycles_to_eol": 876.0}, "policy_a": "6C(50%)-3C", "policy_b": "6C(50%)-3.6C"}`

**T1** `{"cell_id": "b1c0", "policy": "3.6C(80%)-3.6C", "cycle_life_field": 1190.0, "cycles_to_eol": null, "eol_method": "not_reached", "retention_pct": 95.85, "q_last_Ah": 1.0262, "last_cycle": 1189.0}`

**T2** `{"cell_id": "b1c8", "policy": "5.4C(40%)-3.6C", "cycle_life_field": 879.0, "cycles_to_eol": null, "eol_method": "not_reached", "q_last_Ah": 0.969, "soh_last_pct": 88.09, "last_cycle": 878.0}`

**T3** `{"cell_id": "b1c11", "policy": "5.4C(50%)-3C", "cycle_life_field": 788.0, "first_cycle": 2.0, "q_first_Ah": 1.0538, "cycle_1": "recorded but empty; dropped by the loader"}`

**T4** `{"ambient_temperature_C": 30}`

**T5** `{"exists": false, "n_cells": 46}`

**T6** `{"chemistry": "LFP/graphite"}`
