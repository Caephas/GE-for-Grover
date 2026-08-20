# PAPER_DATA — Grammatical Evolution for Quantum Algorithms (Grover)

Assembled 2026-08-11 08:36 from existing `experiments/` trees, aggregates, hardware JSONs and diagnostics. No experiments were re-run.

**Definitions used throughout:** success = run fidelity >= 0.95; converged = peak fidelity >= 0.9; sim fidelity = per-run final re-evaluated fidelity in AGGREGATE (unless noted); hardware p_marked = p(|state>) from ibm_fez, 10,000 shots, matched to a per_run entry via raw_fitness + raw gates/depth.

### A. Main results (epsilon-lexicase, pop=300) (one row per state, epsilon_lexicase, pop300)

| State | Best sim fid | Seed | Transpiled D/G/2Q | Raw D/G | HW p_marked | HW seed | HW seed sim fid | HW job_id | HW timestamp | Success (k/5) | Mean±std fid | Mean stop gen | Stop reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 000 | 0.9865 | 33537 | 5/11/2 | 12/26 | 0.9766 | 33537 | 0.9865 | d9h3du8gk0ls73f2eig0 | 2026-07-23T16:45:09 | 4/5 | 0.9772±0.0171 | 20.4 | {"Hardware targets achieved": 4, "Fidelity stagnant": 1} |
| 001 | 0.9875 | 21315 | 4/9/2 | 15/29 | 0.9837 | 21315 | 0.9875 | d9is2tjhdfks73chf9jg | 2026-07-26T09:26:01 | 3/5 | 0.7942±0.2632 | 17.0 | {"Hardware targets achieved": 3, "Fidelity stagnant": 2} |
| 010 | 0.9911 | 33537 | 5/8/4 | 19/41 | 0.9803 | 33537 | 0.9911 | d9h3a0bsbqfc73epgjh0 | 2026-07-23T16:36:44 | 5/5 | 0.9860±0.0033 | 20.2 | {"Hardware targets achieved": 5} |
| 011 | 0.9887 | 12147 | 2/5/4 | 23/45 | 0.9771 | 12147 | 0.9887 | d9j4f4rjf64c739g9us0 | 2026-07-26T18:58:56 | 3/5 | 0.7885±0.2684 | 19.4 | {"Fidelity stagnant": 2, "Hardware targets achieved": 2, "Hardware metrics stagnant": 1} |
| 100 | 0.9902 | 33537 | 3/5/5 | 20/42 | 0.9902 | 33537 | 0.9902 | d9j4f80ii2cc73eeacag | 2026-07-26T18:59:14 | 4/5 | 0.8864±0.2242 | 21.8 | {"Hardware targets achieved": 4, "Fidelity stagnant": 1} |
| 101 | 0.9894 | 70300 | 5/9/4 | 19/42 | 0.9827 | 70300 | 0.9894 | d9q6oc17s9kc73ausk70 | 2026-08-07T09:15:33 | 3/5 | 0.7898±0.2709 | 23.8 | {"Hardware targets achieved": 3, "Fidelity stagnant": 2} |
| 110 | 0.9857 | 70300 | 5/9/2 | 11/27 | 0.9767 | 70300 | 0.9857 | d9j4ifibr2fc73e5er6g | 2026-08-11T08:34:21 | 3/5 | 0.7863±0.2545 | 23.0 | {"Hardware targets achieved": 3, "Fidelity stagnant": 2} |
| 111 | 0.9900 | 70300 | 5/9/4 | 19/41 | 0.9742 | 70300 | 0.9900 | d9q6oc17s9kc73ausk7g | 2026-08-07T09:15:33 | 5/5 | 0.9739±0.0168 | 23.0 | {"Hardware targets achieved": 4, "Hardware metrics stagnant": 1} |

Overall converged runs (fidelity >= 0.95): **30/40** (75%)


---

### B. Tournament baseline (pop=300) (one row per state, tournament, pop300)

| State | Best sim fid | Seed | Transpiled D/G/2Q | Raw D/G | HW p_marked | HW seed | HW seed sim fid | HW job_id | HW timestamp | Success (k/5) | Mean±std fid | Mean stop gen | Stop reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 000 | 0.9810 | 33537 | 5/11/2 | 11/25 | 0.9773 | 33537 | 0.9810 | d9r3i6fpemts73cs37jg | 2026-08-07T21:53:59 | 4/5 | 0.8987±0.1794 | 17.8 | {"Hardware targets achieved": 4, "Fidelity stagnant": 1} |
| 001 | 0.9868 | 21315 | 4/9/3 | 12/27 | 0.9765 | 21315 | 0.9868 | d9r84lvpemts73cs99n0 | 2026-08-08T02:12:05 | 4/5 | 0.8853±0.2114 | 22.2 | {"Hardware targets achieved": 4, "Fidelity stagnant": 1} |
| 010 | 0.9796 | 47182 | 7/13/2 | 11/26 | 0.9712 | 47182 | 0.9796 | d9r82i9dsedc73agaglg | 2026-08-08T02:07:35 | 2/5 | 0.6928±0.2611 | 22.2 | {"Hardware targets achieved": 2, "Fidelity stagnant": 3} |
| 011 | 0.9776 | 21315 | 5/10/2 | 11/25 | 0.9661 | 21315 | 0.9776 | d9r6cvpdsedc73ag8hdg | 2026-08-08T00:13:14 | 3/5 | 0.7902±0.2475 | 19.2 | {"Hardware targets achieved": 3, "Fidelity stagnant": 2} |
| 100 | 0.9788 | 47182 | 5/10/2 | 11/26 | 0.9720 | 47182 | 0.9788 | d9r56tftfhrs73dr76ig | 2026-08-11T08:34:20 | 3/5 | 0.7823±0.2613 | 18.0 | {"Fidelity stagnant": 2, "Hardware targets achieved": 3} |
| 101 | 0.9668 | 12147 | 8/12/2 | 12/26 | 0.9595 | 12147 | 0.9668 | d9r6fqgpdb6s73e4gu70 | 2026-08-08T00:19:15 | 1/5 | 0.5955±0.2092 | 19.4 | {"Fidelity stagnant": 4, "Hardware targets achieved": 1} |
| 110 | 0.9796 | 47182 | 6/10/2 | 11/25 | 0.9750 | 47182 | 0.9796 | d9r1tthdsedc73ag263g | 2026-08-11T08:34:20 | 2/5 | 0.6864±0.2666 | 16.6 | {"Fidelity stagnant": 3, "Hardware targets achieved": 2} |
| 111 | 0.9873 | 47182 | 4/8/3 | 13/27 | 0.9719 | 47182 | 0.9873 | d9r676vtfhrs73dr8g5g | 2026-08-08T00:06:42 | 3/5 | 0.7820±0.2643 | 19.0 | {"Hardware targets achieved": 3, "Fidelity stagnant": 2} |

Overall converged runs (fidelity >= 0.95): **22/40** (55%)


---

### C. Head-to-head summary (pop=300)

| State | Lex success | Tour success | Lex best fid | Tour best fid | Lex D/2Q | Tour D/2Q |
|---|---|---|---|---|---|---|
| 000 | 4/5 | 4/5 | 0.9865 | 0.9810 | 5/2 | 5/2 |
| 001 | 3/5 | 4/5 | 0.9875 | 0.9868 | 4/2 | 4/3 |
| 010 | 5/5 | 2/5 | 0.9911 | 0.9796 | 5/4 | 7/2 |
| 011 | 3/5 | 3/5 | 0.9887 | 0.9776 | 2/4 | 5/2 |
| 100 | 4/5 | 3/5 | 0.9902 | 0.9788 | 3/5 | 5/2 |
| 101 | 3/5 | 1/5 | 0.9894 | 0.9668 | 5/4 | 8/2 |
| 110 | 3/5 | 2/5 | 0.9857 | 0.9796 | 5/2 | 6/2 |
| 111 | 5/5 | 3/5 | 0.9900 | 0.9873 | 5/4 | 4/3 |

Overall converged: lexicase **30/40 (75%)** vs tournament **22/40 (55%)** (run fidelity >= 0.95).

### D. Population ablation (epsilon-lexicase, pop=100 vs pop=300)

| State | Success pop100 | Success pop300 | std fid pop100 | std fid pop300 |
|---|---|---|---|---|
| 000 | 2/5 | 4/5 | 0.3196 | 0.0171 |
| 001 | 4/5 | 3/5 | 0.2082 | 0.2632 |
| 010 | 2/5 | 5/5 | 0.2614 | 0.0033 |
| 011 | 3/5 | 3/5 | 0.3347 | 0.2684 |
| 100 | 3/5 | 4/5 | 0.2616 | 0.2242 |
| 101 | 3/5 | 3/5 | 0.2626 | 0.2709 |
| 110 | 2/5 | 3/5 | 0.2648 | 0.2545 |
| 111 | 3/5 | 5/5 | 0.2652 | 0.0168 |

Overall convergence: **22/40 (55%)** at pop=100 vs **30/40 (75%)** at pop=300 (fidelity >= 0.95).
Bimodal states (std > 0.15): pop100 = ['000', '001', '010', '011', '100', '101', '110', '111']; pop300 = ['001', '011', '100', '101', '110'].

### E. Mechanism analysis numbers

**Diversity (mean unique behaviors, gens 0-15; % of population = /300):**

| Group | Lexicase (n) | % of pop | Tournament (n) | % of pop |
|---|---|---|---|---|
| converged | 211.0 (n=32) | 70.3% | 237.6 (n=23) | 79.2% |
| failed | 200.7 (n=8) | 66.9% | 229.2 (n=17) | 76.4% |
| all | 208.9 (n=40) | 69.6% | 234.1 (n=40) | 78.0% |

Gen-0 diversity: lexicase 154.7 vs tournament 184.5 — the two arms do NOT share initial populations despite identical seeds (environment difference between sweeps); treat raw diversity differences as confounded and use gen-0-normalized trajectories.

**Failed-run peak fidelity (failed = peak < 0.9):**

| Metric | Lexicase (n=8) | Tournament (n=17) |
|---|---|---|
| Fraction crossing >= 0.6 | 0% | 24% |
| Fraction crossing >= 0.7 | 0% | 24% |
| Fraction crossing >= 0.8 | 0% | 6% |
| Mean peak fidelity | 0.5485 | 0.6141 |
| Median peak fidelity | 0.5625 | 0.5828 |
| Mann-Whitney U p (two-sided) | 0.1747 | (n=8 vs 17) |

**Coverage evidence:** lexicase failed runs never exceeded a peak fidelity of **0.5928** (i.e., never reached ~0.6), consistent with 'never reached the basin' rather than premature convergence. Tournament failures reach 0.6-0.87 in 24% of cases then stall (scalar gate-penalty tradeoff).

### F. Transpile / evolution-vs-transpiler numbers

**Opt-0 (raw, pre-transpile) vs opt-3 (transpiled) for the deployed best circuit per state (epsilon-lexicase, pop=300):**

| State | Raw D/G | Transpiled D/G | Depth reduction | Gate reduction |
|---|---|---|---|---|
| 000 | 12/26 | 5/11 | 58% | 58% |
| 001 | 15/29 | 4/9 | 73% | 69% |
| 010 | 19/41 | 5/8 | 74% | 80% |
| 011 | 23/45 | 2/5 | 91% | 89% |
| 100 | 20/42 | 3/5 | 85% | 88% |
| 101 | 19/42 | 5/9 | 74% | 79% |
| 110 | 11/27 | 5/9 | 55% | 67% |
| 111 | 19/41 | 5/9 | 74% | 78% |

**Transpile-seed sensitivity** (20 seed_transpiler values, real ibm_fez target, opt-3; see transpile_seed_sensitivity.csv): the 8 deployed best circuits are all **seed-stable** (min = median = max for every state). The July-deployed circuit for state 111 (run 4, seed 33537) is the one seed-sensitive circuit found: 7g/3d at seed 33537 vs 34g/23d at seed 0/70300 on the current target (the July hardware file recorded 37g/24d with the wrong stale seed 70300). State 011's deployed circuit is seed-stable but target-sensitive: recorded in-loop 5g/2d (July) vs 17g/12d transpiled today — i.e., layout depended on that day's calibration. Implication: evolution produces short raw circuits; the transpiler adds most of the deployed cost, and a small number of circuits are sensitive to transpile seed/calibration.

### G. Figure inventory

**Analysis figures (project root):**

| File | Type | Resolution | Description |
|---|---|---|---|
| `fig_diversity_converged_vs_stalled.png` | PNG | 200 dpi (below 300 - regenerate for print) | Epsilon-lexicase pop300: fidelity + unique-behaviors trajectories, converged vs never-reached runs. |
| `fig_diversity_lexicase_vs_tournament.pdf` | PDF | vector (print-ready) | Vector version of the same figure. |
| `fig_diversity_lexicase_vs_tournament.png` | PNG | 200 dpi (below 300 - regenerate for print) | Lexicase vs tournament pop300: fidelity, raw diversity, and gen-0-normalized diversity trajectories (4 groups). |
| `fig_failed_fidelity_lexicase_vs_tournament.pdf` | PDF | vector (print-ready) | Vector version of the same figure. |
| `fig_failed_fidelity_lexicase_vs_tournament.png` | PNG | 200 dpi (below 300 - regenerate for print) | Failed-run fidelity trajectories + peak-fidelity ECDF, lexicase vs tournament. |

**Print-resolution versions:** `paper_figures/` contains 300-dpi PNGs and vector PDFs of the three analysis figures (regenerated via `make_paper_figures.py` from the saved CSVs — no experiments re-run).

**Circuit diagrams** (240 PNG files, all 150 dpi, in run folders):

- `experiments/epsilon_lexicase/pop100/noise`: 70 circuit images (`circuit_raw_<state>_run<n>.png`, `circuit_transpiled_<state>_run<n>.png`)
- `experiments/epsilon_lexicase/pop300/noise`: 80 circuit images (`circuit_raw_<state>_run<n>.png`, `circuit_transpiled_<state>_run<n>.png`)
- `experiments/tournament/pop300/noise`: 80 circuit images (`circuit_raw_<state>_run<n>.png`, `circuit_transpiled_<state>_run<n>.png`)
- `experiments_epsilon_lexicase_noise_pop100`: 10 circuit images (`circuit_raw_<state>_run<n>.png`, `circuit_transpiled_<state>_run<n>.png`)

Deployed best-run circuit images per state (epsilon-lexicase pop300; also available for tournament and pop100 in the same layout):

| State | Best run | Raw circuit | Transpiled circuit |
|---|---|---|---|
| 000 | run 4 (seed 33537) | `experiments/epsilon_lexicase/pop300/noise/state_000/run_4_seed_33537/circuit_raw_000_run4.png` | `experiments/epsilon_lexicase/pop300/noise/state_000/run_4_seed_33537/circuit_transpiled_000_run4.png` |
| 001 | run 1 (seed 21315) | `experiments/epsilon_lexicase/pop300/noise/state_001/run_1_seed_21315/circuit_raw_001_run1.png` | `experiments/epsilon_lexicase/pop300/noise/state_001/run_1_seed_21315/circuit_transpiled_001_run1.png` |
| 010 | run 4 (seed 33537) | `experiments/epsilon_lexicase/pop300/noise/state_010/run_4_seed_33537/circuit_raw_010_run4.png` | `experiments/epsilon_lexicase/pop300/noise/state_010/run_4_seed_33537/circuit_transpiled_010_run4.png` |
| 011 | run 3 (seed 12147) | `experiments/epsilon_lexicase/pop300/noise/state_011/run_3_seed_12147/circuit_raw_011_run3.png` | `experiments/epsilon_lexicase/pop300/noise/state_011/run_3_seed_12147/circuit_transpiled_011_run3.png` |
| 100 | run 4 (seed 33537) | `experiments/epsilon_lexicase/pop300/noise/state_100/run_4_seed_33537/circuit_raw_100_run4.png` | `experiments/epsilon_lexicase/pop300/noise/state_100/run_4_seed_33537/circuit_transpiled_100_run4.png` |
| 101 | run 5 (seed 70300) | `experiments/epsilon_lexicase/pop300/noise/state_101/run_5_seed_70300/circuit_raw_101_run5.png` | `experiments/epsilon_lexicase/pop300/noise/state_101/run_5_seed_70300/circuit_transpiled_101_run5.png` |
| 110 | run 5 (seed 70300) | `experiments/epsilon_lexicase/pop300/noise/state_110/run_5_seed_70300/circuit_raw_110_run5.png` | `experiments/epsilon_lexicase/pop300/noise/state_110/run_5_seed_70300/circuit_transpiled_110_run5.png` |
| 111 | run 5 (seed 70300) | `experiments/epsilon_lexicase/pop300/noise/state_111/run_5_seed_70300/circuit_raw_111_run5.png` | `experiments/epsilon_lexicase/pop300/noise/state_111/run_5_seed_70300/circuit_transpiled_111_run5.png` |

### H. Experimental configuration

**Evolution:** population size 300; max generations 100; 5 runs per state; seeds [21315, 47182, 12147, 33537, 70300].
Crossover probability 0.8; mutation probability 0.01; elite size 1; HOF size 1; codon size 400; max tree depth 50; init depth 20-40; codon consumption lazy; genome representation list.
Checkpoint frequency 10; resume-from-checkpoint False; transfer learning False.

**Selection:** epsilon-lexicase (epsilon via Median Absolute Deviation, `epsilon_method="mad"`) over 3 per-objective test cases: fidelity (p_marked), gate efficiency (1 - gates/MAX_EXPECTED_GATES, MAX=200), depth efficiency (1 - depth/MAX_EXPECTED_DEPTH, MAX=150); tournament baseline `selTournament` with tournament size 5 selecting on the scalar fitness.

**Fitness:** scalar `fitness = 10*miss + (1 - p_marked) + lambda * gate_count`, `miss = 1 if p_marked < 0.48 else 0`, lambda = GATE_PENALTY_WEIGHT = 0.02; shots = 10000. Fidelity success threshold 0.48.

**Early stopping:** enabled=True, mode=nisq_focused, strategy=nisq_hierarchical; min generations before stopping=15; targets: fidelity>=0.95, gate_count<=20, depth<=15; patience {'fitness': 25, 'fidelity': 8, 'gate_count': 10, 'depth': 10, 'composite': 15}; min improvement {'fitness': 0.01, 'fidelity': 0.005, 'gate_count': 1, 'depth': 1}; metric weights {'fitness': 0.15, 'fidelity': 0.35, 'gate_count': 0.3, 'depth': 0.2}; moving-average window=3; relative improvement=True.

**Backend / simulation:** IBM Quantum `ibm_fez` (156 qubits), fetched live via `QiskitRuntimeService` (channel ibm_cloud); 10000 shots; noise model = `AerSimulator.from_backend(backend)` built from the **live backend calibration at kernel start** (i.e., calibration is live, not a frozen snapshot; the July epsilon-lexicase runs and the August tournament runs therefore used different calibrations). Ideal simulation = `QasmSimulator`. Transpilation: `transpile(..., optimization_level=3, seed_transpiler=run_seed)` in-loop; hardware re-transpiles with `generate_preset_pass_manager(..., optimization_level=3, seed_transpiler=deployed_run_seed)`.

**Grammar** (`grammars/grover.bnf`): 3 qubits / 3 classical bits; program = Initialize + HadamardAll + GroverIterations + Measure; iteration = OracleBlock | DiffuserBlock; oracle block is injected via `inject_oracle` into `## Begin Oracle ... ## End Oracle` markers (a no-op when the phenotype lacks the marker). Gate set: single-qubit x, y, z, h, s, sdg, t, tdg, id; two-qubit cx, cy, cz, swap; three-qubit ccx, cswap; parameterized rx, ry, rz, u, rxx, ryy, rzz, rzx with angles in {0, pi/4, pi/2, pi, 3pi/2, 2pi, 0.5, 1.3, 2.7, 0.314, 1.5708, 3.1415}; standard 3-qubit diffuser block is fixed in the grammar.

**Software versions (report environment):** Python 3.11.15; qiskit 2.4.1; qiskit-aer 0.17.2; qiskit-ibm-runtime 0.46.1; numpy 2.2.2; pandas 2.2.3; scipy 1.15.1; matplotlib 3.10.0; deap 1.4.2; grape_bds 0.1.3. Notebook sets `PYTHONHASHSEED=0` (only fully effective when set before kernel launch).

### Notes / caveats

- The epsilon-lexicase (July) and tournament (August) sweeps ran under different environments: gen-0 unique-behaviors differ per (state, seed) despite identical seeds and initialization code. Raw cross-method diversity comparisons are confounded; use the gen-0-normalized figure.
- Hardware results for states 000-011 are from July pre-patch runs (matched to the best-fidelity circuit by raw_fitness, but transpiled with the then-stale RANDOM_SEED; for these states the transpiled metrics in the hof files match the in-loop metrics). States 100, 101, 110, 111 have August re-deployments with the deployed run's own seed; 111/101 values are the corrected ones (0.9742 / 0.9827).
- Tournament states 100/110 hardware (0.9720 / 0.9750, seed 47182) were recovered from jobs d9r56tftfhrs73dr76ig / d9r1tthdsedc73ag263g after the original notebook runs timed out locally; these results are stored in the tournament run folders. The lexicase state-110 July result (0.9767, job d9j4ifibr2fc73e5er6g) was restored after an earlier misattribution, and the misplaced tournament copy in the lexicase state-100 folder was quarantined (`.misattributed_tournament`).
- `transpile_seed_sensitivity.csv` (168 rows) holds the 20-seed sweep of the deployed best circuits; `results_table.csv` holds the one-row-per-state consolidated table.
- Success counts use the per-run final fidelity from AGGREGATE (75% / 55% for lexicase/tournament pop300); diagnostics peak fidelity gives 78% / 57% (one extra run each).
