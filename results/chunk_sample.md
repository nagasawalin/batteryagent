# Chunk sample — read every one

## lewerenz2017b::0011 — 2.3. DVA evaluation strategy — p.3–3 (381 tok)

The DVA is carried out for all constant current discharge curves of the full cell measured at each check-up. Special characteristic points are evaluated for each curve as illustrated in Fig. 1: these are the minimum at high SOC (MinHi), the minimum at low SOC

(MinLo) and the maximum at low SOC (MaxLo). Meaningful relative values turned out to be, on the one hand, the Ah-distance between the minima:

and, on the other hand, the difference between the minimum and maximum of the identified peaks at low SOC:

While D MinMax can be analyzed over the entire test, D Minima is only determinable as long as enough active lithium is available to reach the necessary degree of lithiation of the graphite to measure MinHi [16 e 18]. This is generally the case where the capacity goes down to approx. 75 e 80% remaining capacity when only loss of active lithium takes place (Fig. 1c).

The shape of the DVA is basically originated from the anode curve as the LiFePO4 cathode exhibits aflat voltage characteristic during most of the discharge process (Fig. 1b). Therefore, the trend of D Minima can be correlated directly to the capacity of the anode. This correlation is reported in many publications [17 e 20]. In case of high inhomogeneities of lithium distribution, the curve shape might change significantly (as shown in section 4.2.3).

Besides the already named characteristic points, the curve shape will be qualified by the sharpness (or shape) of the MinHi peak and the detectability of the two shoulders recognizable at MinLo peak. A quantification of the homogeneity of lithium distribution (HLD) or aging is possible evaluating only the peak characteristics (position and shape) of MinHi in a rather homogenized state of the cell.

## edge2021::0014 — Positive electrode structural change and decomposition — p.6–6 (484 tok)

Recent studies 48,50,51 show that, apart from TM fluoride (MF2), TM carbonates, along with minor quantities of hydroxides and water, are the few other species that are present in the pSEI.

Exacerbating and mitigating factors. Mechanisms (i)-(iv) outlined above are all influenced by the chemical and structural stability of the material. Each of the constituent TMs impart different properties into the electrode material, with advantages and disadvantages for each. High cobalt content results in greater stability of the layered crystalline structure, but lower chemical stability. LiMnO2 has a greater chemical stability due to its lower redox potential, but suffers from structural instability, undergoing a phase change from layered to spinel structure. 24 Pure LiNiO2 electrodes are more unstable, but when mixed with Co and Mn to form NMC composites, their chemical and structural stabilities are intermediate to those of their cobalt and manganese analogues. They are less prone to phase change and are unlikely to decompose during oxidation (delithiation), due to the Ni 3+/4+ redox couple (which carries out the bulk of the redox work) sitting at a lower potential than that of Co 3+/4+ (and, crucially, the O 2  p band). However, high nickel content electrode materials can be prone to Li + -Ni 2+ site exchange. 49 Furthermore, Ni 4+ will react when in contact with the electrolyte, leading to dissolved nickel ions and electrolyte oxidation products. 52

High degrees of delithiation (Li x MO2 with x o 0.3), corresponding to high cell SoCs, cause NMC structures, especially Ni-rich positive electrodes such as NMC811, to become thermodynamically unstable. 53 High enough voltages can also lead to decomposition, due to oxidation of lattice oxygen.

Chemical and structural decomposition are both most likely to occur at the electrode surface. This is due to increased surface reactivity and the higher potentials experienced at the particle surface. 53 To mitigate degradation, protective surface films or coatings are used in some batteries to protect the PE from attack by the electrolyte. 54

High temperatures will accelerate the rate of degradation for all the mechanisms listed above.

Electrolytes tend to be non-aqueous organics and therefore highly reactive with water.

## bloom2005::0014 — 3.3. Analysis of 18650-cell data — p.5–6 (336 tok)

Since the peaks in the - Q 0d V /d Q curve have been assigned, let us now analyze the 18650-cell data given in Fig. 7 to determine if the source of capacity fade can be identified. In this analysis we are going to classify capacity fade into two groups. The first is when there is a loss of accessible active material (LAAM) in an electrode; the second is when

Fig. 7. The discharge-only portion of Q 0d V /d Q vs. capacity density for a calendar life cell. The time interval between curves is 4 weeks. A vertical offset was added for the sake of clarity.

2

Fig. 8. Distances between peaks as a function of time. Peaks 1 and 2a are from the cathode; Peaks 2, 3, and 4 are from the anode. Cross-electrode peak distances were not calculated.

there is a shift in the alignment of the electrodes due to side reactions (SASR) at one of the electrodes. The latter source of capacity fade is equivalent to the adjustments we made above to align the electrodes with the cell data. We saw that, as the curves were brought together, the overall cell capacity would decrease without decreasing the capacity of either electrode.

The calculated distances between the cathode and anode peaks in Fig. 7 are given in Fig. 8. Part of the data for the distance between Peaks 1 and 2a is projected since Peak 2a is hard to discern at t < 16 weeks. From this figure, the distances between peaks do not change, within experimental error.

## lewerenz2017a::0020 — 3.3. Passive electrode effect — p.5–6 (42 tok)

Table 4 OCV cell voltage of the full cell and initial maximum potential difference between the passive anode of 99% SOC and the active anode at the corresponding SOC of the test.

Table 5

## attia2022::0059 — Appendix — p.25–25 (930 tok)

Table A·I. (Continued).

|                        | Variable    | Reference                                                                                            | Cell Description                                                | Range of Variable                                 | Knee Acceleration                                    | Proposed Mechanism(s)                                        |
|------------------------|-------------|------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------|---------------------------------------------------|------------------------------------------------------|--------------------------------------------------------------|
|                        |             | Petzl et al. 2015 62 Commercial 26650 LFP/Gr Zhu et al. 2021 130 Samsung INR 18650 25R NMC + NCA/ Gr | 0% - 80% vs 0% - 100% SOC 20% - 60% DOD, 15% - 85% SOC midpoint | Higher DOD Lower SOC                              | Li plating SEI growth                                |                                                              |
|                        | Rests       | Keil et al. 2019 21 Ma et al. 2019 6                                                                 | Commercial 18650 NMC/Gr Lab-made pouch NMC/Gr                   | 10 - 900s at TOC and BOD 0 - 30min at TOC and BOD | Longer rest time Longer rest time                    | Li plating, SEI growth Positive electrode impe- dance growth |
|                        | Temperature | Epding et al. 2019 172 Zhang et al. 2019 40                                                          | Commercial prismatic NMC/Gr Commercial NMC/Gr                   | 0 - every 100 cycles 25 - 45 °C                   | Shorter rest time Temperature above and below 25 °C  | Li plating Li plating                                        |
|                        |             | Broussely et al. 2005 14                                                                             | Saft VLE NCA/Gr                                                 | 20 - 60 °C                                        | Higher temperature                                   | Electrolyte oxidation                                        |
|                        |             | Schuster et al. 2015 17                                                                              | E-One Moli Energy IHR18650A NMC/ Gr                             | 25 - 50 °C                                        | Temperature above and below 35 °C                    | Li plating, SEI growth                                       |
|                        |             | Safari et al. 2011 105 Waldmann et al. 2014 61                                                       | Commercial 26650 LFP/Gr Commercial 18650 NMC + LMO/Gr           | 25 - 45 °C - 20 - 70 °C                           | Higher temperature Temperature above and below 25 °C | LAM (graphite) Li plating, SEI growth                        |
|                        |             | Coron et al. 2020 66                                                                                 | Commercial 18650 NMC + LMO/Gr Commercial 18650 NMC/Gr           | 0 - 25 °C                                         | Lower temperature                                    | SEI growth, LAM                                              |
|                        | Pressure    | Waldmann et al. 2015 63                                                                              | Commercial 18650 NCA/Gr                                         | 0 - 60 °C                                         | Temperature below 25 °C                              | Li plating, SEI growth                                       |
|                        |             | Wunsch et al. 2019 133                                                                               | Commercial pouch NMC/Gr                                         | 4 bracing approaches                              | More rigid bracing or zero bracing                   | N/A                                                          |
|                        |             | Cannarella and Arnold 2014 53                                                                        | Commercial pouch LCO/Gr                                         | 0 - 5 MPa                                         | Higher stack pressure or zero pressure               | LAM (graphite) or Li plating                                 |
| Cell-to-cell variation |             | Harris et al. 2017 152                                                                               | Commercial pouch LCO/Gr                                         | 24 cells                                          | N/A                                                  | N/A                                                          |
|                        |             | Baumhofer et al. 2014 151                                                                            | Sanyo UR18650E NMC/Gr                                           | 48 cells                                          | N/A                                                  | N/A                                                          |
|                        |             | Willenberg et al. 2020 55                                                                            | Samsung INR18650 35E NCA/Gr + Si                                | 4 cells                                           | N/A                                                  | Mechanical deformation                                       |
|                        |             | Stiaszny et al. 127                                                                                  |                                                                 |                                                   |                                                      | N/A                                                          |
|                        |             |                                                                                                      | Commercial 18650 NMC + LMO/Gr                                   | 6 cells                                           | N/A                                                  |                                                              |

## attia2022::0033 — Pathways and Internal State Trajectories for Knee Points — p.14–15 (469 tok)

In these equations, ε is the volume fraction of the active graphite ( ε LiC6 ), inactive graphite ( ε LiC ,inactive 6 ), electrolyte ( ε elyte ) and gas ( ε gas , which is produced during SEI growth). Activity describes how much of the electrode material is active and available for reaction, while saturation describes the amount of pore space occupied by the liquid electrolyte. The loss of ionic contact of graphite caused by electrolyte dry-out is then described by a kinetic rate law that is proportional to the difference in activity and equilibrium activity, which is assumed to be a function of only saturation. To predict a knee in cell capacity, the equilibrium activity-saturation relationships were formulated to be nonlinear and contain a percolation threshold value, around which the equilibrium activity varies rapidly between 0 and 1. The functional forms of these relationships were assumed given the absence of theoretical or experimental guidance. Figure 14 plots two such nonlinear relationships, named relationships 3 and 4, adapted from Fig. 5 of Kupper et al. 25 The authors concluded that relationship 4 best fitted experimental aging data.

The knee caused by this electrolyte dry-out model is a threshold trajectory, where the threshold is the critical saturation value illustrated in Fig. 14. Although Kupper et al. 25 did not provide convincing experimental validation to definitively prove that electrolyte dry-out Kupper et al.

Relationship 3 (nonlinear, symmetric at s = 0.5): a=0.5·tanh(10(s−0.5))+0.5

Relationship 4 (nonlinear, asymmetric): a= (0.5s+0.5) · (0.5· tanh(15(s −0.5))+0.5)

Figure 14. Two activity-saturation relationships describing percolationlimited electrolyte dry-out, adapted from Fig. 5 of Kupper et al. 25 Relationships 3 and 4 model percolation of the liquid electrolyte where activity depends nonlinearly on saturation. The key feature of both relationships is the presence of a percolation threshold value ( s = 0.5), around which activity varies rapidly between 0 and 1. The sensitivity of activity to small changes in saturation is apparent.

## lewerenz2017b::0031 — 5. Conclusions — p.10–11 (470 tok)

Using the differential voltage analysis, a trend of increasing homogeneity of lithium distribution can be measured with three characteristic points. The highest sensitivity is revealed by the sharpness of MinHi, followed by the appearance of the shoulders of the peak at MinLo. If the anode exhibits two or more disjunctive lithium concentrations, the distance D MinMax between minimum and maximum at low SOC decreases.

For all cells of the different calendaric aging tests the homogeneity of lithium distribution increases with aging. Up to 40  C the cells age solely by loss of active lithium; at 60  C additional loss of capacity measured by reducing D Minima needs to be considered. The LAAM is associated with the deposition of dissolved Fe from the cathode on the anode. The influence of the LAAM on capacity fade could be quantified assuming that the pores are clogged in the degree of lithiation during storage. However, after subtracting the estimated influence of LAAM, two slopes of capacity fade are still present, showing that there is another contribution to aging. As the influence of the deposited Fe on the LAAM decreases, the Fe is most likely deposited on previously deposited Fe and will therefore not clog additional pores of the anode. The higher slope of capacity fade in the beginning might be attributed to high reactivity of the first deposited Fe with active lithium.

With respect to cycling, operating the cells at 100% DOD leads to continuous LAAM. The active material is lost in a low state of charge of less than 10%, as calculated from the higher average capacity fade, compared to 50% DOD test without LAAM. The LAAM is assumed to be inhomogeneously distributed, while the higher losses should be located where the mechanical pressure in the cylindrical cell is the lowest: edgewise at the anode overhang, outer windings and anode facing outside. This is supported by continuously reducing homogeneity measured according to flattening of MinHi.

The evolution of a covering layer is detectable when a sudden strong reduction of capacity occurs, while D Minima and D MinMax decreases and MinHi flattens. The increasing inhomogeneous lithium distribution could be linked to a locally increasing path length, due to masking or to locally increased pressure caused by covering layer on top of the anode.

## ansean2017::0025 — 5. Conclusion — p.9–9 (235 tok)

This simple, in situ , and cost efficient strategy can be easily implemented to improve battery management system (BMS) functions for diagnosis and prognosis.

This work also demonstrates the potential of the ' alawa toolbox to estimate the irreversible and reversible parts of lithium plating. The presented framework could be used by researchers focused on the correlation of cell design parameters (i.e., cell chemistry, electrolytes and electrode architecture) with lithium plating appearance. A first estimation of the reversible and irreversible ratio could be easily attained without carrying out laborious, ex-situ experiments, thus accelerating the research processes.

To conclude this work, we discussed the plausible underlying causes of cell degradation under the used driving scheme. The analyses indicated a probable connection of rapid cell aging with vast repetitive intercalation/deintercalation processes derived from regenerative braking. Future work will investigate the relationship between the number and intensity of the intercalation/deintercalation processes, and its effects on cell degradation. Additional validation via cell disassembling and postmortem analysis is to be expected. This shall further elucidate the effects of dynamic cycling and lithium plating, to evaluate the convenience of using regeneration schemes.

## attia2022::0024 — Pathways and Internal State Trajectories for Knee Points — p.10–11 (461 tok)

Reproduced from Fig. 2c - d of Frisco et al. 77 Copyright 2016, The Electrochemical Society.

Electrode saturation can also be rate dependent, sometimes in counterintuitive ways. Ma et al. 6 found that single-crystal nickel manganese cobalt oxide (NMC)/graphite cells exhibited no capacity fade in 1C diagnostic cycles but exhibited capacity fade in C/20 diagnostic cycles. The authors attributed this result to the poor rate capability of the single-crystal NMC particles. At low rates, the cells are ' negative electrode limited ' ; as lithium inventory loss shifts the negative electrode voltage curve, the available discharge capacity decreases and thus capacity loss is observed. At high rates, the cells are ' positive electrode limited ' because the positive electrode saturates before the negative electrode fully depletes; thus, the 1C capacities are unaffected. We refer the reader to Ma et al. 6 for further discussion of this phenomenon.

Overall, electrode saturation can be modeled and predicted using electrochemical modeling. This pathway can be considered either a threshold trajectory, where the knee is triggered by electrode saturation, or a hidden trajectory, where LAM of one electrode outpaces both LAM of the other electrode and LLI. While modeling of just the degradation modes (i.e., LLI, LAM, etc.) can capture the key dynamics of this pathway, models that capture the shifts in stoichiometry as a function of cycling can capture more subtle effects. As Ma et al. 6 demonstrate, periodic diagnostic cycles at multiple rates can aid in identifying electrode saturation, especially if the saturation is rate-dependent.

Figure 10. Early models of ' hidden ' knee mechanisms due to electrode saturation. (a) The exponentially increasing positive electrode loss eventually limits the capacity and causes a knee. Adapted from Fig. 17 of Dubarry et al. 89 (b) The linearly decreasing negative electrode capacity eventually overtakes the sublinearly decreasing lithium inventory, causing a knee in the relative capacity. Adapted from Fig. 1 of Smith et al. 90

Resistance growth-induced knees. - Cell internal resistance often increases during aging, in part due to the growth of side reaction products on the surface of the electrode particles.

## ahmed2017::0025 — 3.2. Modeling the performance and cost — p.8–8 (405 tok)

Let us consider a battery pack for an all-EV rated for a total energy storage capacity of 80 kWh, and capable of delivering a burst power of 300 kW for 10 s. BatPaC, a spreadsheet tool developed at Argonne to design automotive lithium-ion batteries, was used to size batteries and their cost for the various scenarios reported here [97]. For a NMC622 (LiNi0.6Mn0.2Co0.2O2) positive electrode and a graphite negative electrode, the pack is designed to operate at a nominal voltage of 900 V. The pack is configured with 6 modules (6S-1P), each with 40 cells (40S-1P), for a total of 240 cells. It is assumed that lithium plating or deposition in the negative electrode can be avoided if the current density during charge is limited to less than 4 mA cm-2 [21]; this limit is called the maximum allowable current density (MACD).

The pack is designed to meet the above specifications and is capable of being charged to increase the SOC from 15% to 95%, so that D SOC ¼ 80% can be achieved in 60 min with a negative electrode thickness of 103 m m(the ratio assumed for the thicknesses of the negative-to-positive electrode is 1.12). The designed battery pack is estimated to cost the vehicle manufacturer $10,945, or $129 per kWhTotal. At the cell level, the cost is $103 per kWh. The configuration of the baseline pack and some characteristics are shown in Table 1.

For the baseline pack shown in Table 1, the total heat generated during the 60 min of charging is 1.45 kWh for the pack, and 6 W for each cell. Assuming adiabatic conditions, the heat can be absorbed by the thermal mass of the cells to raise the cell centerline temperature from 10  C to 25  C.
