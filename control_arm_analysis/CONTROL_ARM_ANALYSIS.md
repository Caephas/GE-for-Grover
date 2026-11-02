# lexi8_random control-arm analysis

Pre-registered analysis of the completed 80-run control sweep. All results below use existing artifacts only; no evolution or hardware job was run.

## 0. Integrity checks

| Check | Result |
|---|---|
| Control run_result files | 80 |
| States x seeds exactly match Lexi2 | True |
| gen-0 hash mismatches | 0 |
| Scored ISA QPY/metadata errors | 0 |
| Workers per run | 1 |
| Overall gate | PASS |

The worker check is structural: `infra/run_sweep.py` hardcodes `--workers 1` in the sole child-process spawn path.

## 0.5 Exact-fidelity reconciliation

The control-only exact values previously reported here are superseded. That path loaded the stored control ISA QPY, removed measurements, and saved probabilities before readout; Lexi2 was left at its sampled value. The two arms therefore did not share a scoring path, and only the control benefited from removal of readout error. Its sampled-minus-exact mean was -0.012204, compared with approximately +0.0015 for the earlier readout-inclusive Lexi2 Task A check.

The common exact calculation is now: obtain the scored circuit, run `AerSimulator(method="density_matrix")` on the fixed noise model, save pre-readout probabilities, then apply the frozen per-qubit readout confusion matrices. No shot sampling is used. For the phenotype-based comparison, both arms are reconstructed with the run seed and fixed target; a run is eligible only when the reconstructed gate, depth, and 2Q counts equal the stored metrics. All 80 controls are additionally scored from their persisted QPY circuits.

| Method | n | Sampled minus exact: mean | Median | Min | Max |
|---|---|---|---|---|---|
| lexi2 | 68 | +0.001573 | +0.001706 | -0.007504 | +0.004601 |
| lexi8_random | 80 | +0.001480 | +0.002153 | -0.012401 | +0.005390 |

In this table the control summary uses all 80 stored QPY circuits; the Lexi2 summary uses the 68 phenotype reconstructions that reproduce the stored transpiled metrics. The paired comparison below uses the same 68 phenotype-reconstructed pairs in both arms.

The unified Lexi2 sample-minus-exact mean is +0.001573, comparable to the earlier Task A mean of approximately +0.0015.

Unified exact-value paired comparison:

| Quantity | Unified exact result |
|---|---|
| lexi8_random higher / Lexi2 higher / ties | 28 / 40 / 0 |
| Median paired difference (control - Lexi2) | -0.000458 |
| Wilcoxon W / p / non-zero n | 943.0 / 0.159908 / 68 |
| Cliff's delta (control vs Lexi2) | -0.075476 |

The earlier 64/16 control advantage was not a finding about the methods. It was produced by omitting readout error for only the control arm. Applying readout confusion to both arms removes that systematic advantage.
The shared phenotype reconstruction matches the stored transpiled metrics for 72/80 Lexi2 runs and 74/80 control runs, giving 68 complete pairs. The remaining pairs contain at least one endpoint whose transpiled circuit cannot be reconstructed from the saved phenotype with the current Qiskit pass manager; the older Lexi2 runs have no QPY. They are excluded from the paired exact comparison rather than silently substituting a different transpilation.

The reconstructed gate/depth/2Q metrics matched the stored logged metrics in 146/160 runs. For the control's stored QPY, measurement layout matched the common-path reconstruction in 75/80 runs. Full per-run provenance is in `exact_fidelity_unified.csv`.

## 1. Pre-registered analysis

### 1.1 Primary: task success and exact McNemar

Task success requires final fidelity >= 0.95, transpiled gates <= 20, and transpiled depth <= 15.

| Cell | Count |
|---|---|
| Both succeed | 40 |
| Only Lexi2 succeeds | 17 |
| Only lexi8_random succeeds | 12 |
| Neither succeeds | 11 |

Task-success totals: Lexi2 57/80, lexi8_random 52/80. Exact two-sided McNemar p = 0.458258.
The exact test conditions on the discordant pairs and uses no normal approximation or continuity correction.

Pre-registered interpretation: the condition for a causal claim is not met. Do not attribute the observed task-success difference to the size tiebreak.

### 1.2 Secondary: final fidelity and generations to stop

| Quantity | Value |
|---|---|
| Pairs | 80 |
| lexi8_random higher / Lexi2 higher / ties | 39 / 41 / 0 |
| Median paired difference (control - Lexi2) | -0.000400 |
| Mean paired difference (control - Lexi2) | +0.007759 |
| Paired Wilcoxon W | 1536.5 |
| Paired Wilcoxon p | 0.688790 |
| Non-zero pairs used | 80 |
| Cliff's delta (control vs Lexi2) | -0.022500 |
| State-cluster bootstrap 95% CI | [-0.210156, +0.145469] |

The Cliff's delta interval resamples the eight state blocks with replacement, preserving all ten paired seeds within a sampled state (10,000 draws, NumPy seed 20260827). A positive delta means lexi8_random has the higher fidelity. The Wilcoxon test is two-sided and uses scipy's default zero handling; this dataset has 80 non-zero paired differences.

| Method | Generations-to-stop mean | Median | IQR |
|---|---|---|---|
| lexi2 | 58.288 | 46.5 | [31.0, 99.0] |
| lexi8_random | 67.562 | 69.0 | [37.5, 99.0] |

Generations-to-stop follows the existing v0.1 convention `early_stopped_gen or 100`.

### 1.3 Mechanism

Population maximum fidelity is read from `p<target>_max`. Post-case pool size is the shared `post_case_pool_sizes` field, which contains only non-singleton tiebreak pools in both methods.

| Gen | Lexi2 max-fid mean | Lexi2 max-fid IQR | Control max-fid mean | Control max-fid IQR | Lexi2 pool mean | Lexi2 pool IQR | Control pool mean | Control pool IQR |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.542 | [0.488, 0.544] | 0.542 | [0.489, 0.544] | 2.170 | [2.000, 2.000] | 2.170 | [2.000, 2.000] |
| 1 | 0.579 | [0.515, 0.578] | 0.581 | [0.521, 0.586] | 7.495 | [3.000, 11.000] | 7.557 | [2.000, 11.000] |
| 2 | 0.626 | [0.538, 0.713] | 0.639 | [0.543, 0.698] | 7.739 | [3.000, 11.000] | 7.623 | [3.000, 11.000] |
| 5 | 0.771 | [0.638, 0.933] | 0.786 | [0.656, 0.923] | 8.126 | [4.000, 12.000] | 7.291 | [3.000, 10.000] |
| 10 | 0.862 | [0.734, 0.971] | 0.867 | [0.786, 0.969] | 8.947 | [5.000, 12.000] | 7.988 | [4.000, 11.000] |
| 25 | 0.915 | [0.870, 0.978] | 0.933 | [0.924, 0.976] | 9.582 | [6.000, 12.000] | 9.180 | [5.000, 12.000] |
| 50 | 0.912 | [0.862, 0.977] | 0.944 | [0.929, 0.976] | 8.876 | [5.000, 12.000] | 9.385 | [6.000, 12.000] |
| 75 | 0.908 | [0.836, 0.976] | 0.949 | [0.941, 0.976] | 8.590 | [5.000, 11.000] | 9.628 | [6.000, 13.000] |
| 99 | 0.911 | [0.856, 0.975] | 0.941 | [0.929, 0.976] | 7.654 | [4.000, 10.000] | 9.379 | [5.000, 13.000] |

The full per-generation distributions are in the two mechanism CSV files. The vector PDF contains both panels and uses the method names Lexi2 and lexi8_random. Later-generation summaries are based only on runs still active at that generation; the `n` column in each CSV records the changing sample size.

### 1.4 Robustness: exact density-matrix rescoring

All 80 lexi8_random endpoints were re-scored from stored QPY. The paired exact comparison uses the 68 (state, seed) pairs for which both phenotype reconstructions reproduce the stored transpiled metrics and therefore share the same reconstruction path. Exact task success uses exact fidelity with the stored transpiled size metrics.

| Quantity | Lexi2 sampled | Lexi2 exact | Control sampled | Control exact |
|---|---|---|---|---|
| Task success on comparable set | see stored 80-run result | 55/68 | see stored 80-run result | 48/68 |
| Median final fidelity | 0.977150 | 0.976290 | 0.977200 | 0.975842 |
| Mean final fidelity | 0.906595 | 0.949772 | 0.914354 | 0.939094 |

Exact-value paired comparison:

| Quantity | Exact-value result |
|---|---|
| McNemar cells (both / only Lexi2 / only control / neither) | 40 / 15 / 8 / 5 |
| Exact McNemar p | 0.210040 |
| Control higher / Lexi2 higher / ties | 28 / 40 / 0 |
| Median paired difference | -0.000458 |
| Wilcoxon W / p / non-zero n | 943.0 / 0.159908 / 68 |
| Cliff's delta (control vs Lexi2) | -0.075476 |

The paired exact comparison is not the primary task-success test; the primary analysis remains based on the stored sampled endpoint.

## 2. Descriptive tables

### 2.1 Per-state task success

| State | Lexi2 | lexi8_random | Control - Lexi2 |
|---|---|---|---|
| 000 | 8/10 | 4/10 | -4 |
| 001 | 8/10 | 6/10 | -2 |
| 010 | 9/10 | 8/10 | -1 |
| 011 | 5/10 | 8/10 | +3 |
| 100 | 8/10 | 8/10 | +0 |
| 101 | 6/10 | 9/10 | +3 |
| 110 | 8/10 | 5/10 | -3 |
| 111 | 5/10 | 4/10 | -1 |

### 2.2 lexi8_random failure composition

| State | Early stop | Late success | Fidelity fail | Size fail | Total |
|---|---|---|---|---|---|
| 000 | 4 | 0 | 3 | 3 | 10 |
| 001 | 6 | 0 | 2 | 2 | 10 |
| 010 | 8 | 0 | 0 | 2 | 10 |
| 011 | 8 | 0 | 0 | 2 | 10 |
| 100 | 7 | 1 | 0 | 2 | 10 |
| 101 | 9 | 0 | 1 | 0 | 10 |
| 110 | 5 | 0 | 3 | 2 | 10 |
| 111 | 4 | 0 | 3 | 3 | 10 |

| Category | Total |
|---|---|
| early stop | 51 |
| late success | 1 |
| fidelity fail | 12 |
| size fail | 16 |

Classification is mutually exclusive and uses the final stored champion: early stop, late task success, fidelity failure, or size failure.

### 2.3 Run-level median circuit size

| Method | Population | n | Gates | Depth | 2Q |
|---|---|---|---|---|---|
| lexi2 | all runs | 80 | 17.0 | 10.0 | 3.0 |
| lexi2 | task-success runs | 57 | 13.0 | 8.0 | 2.0 |
| lexi8_random | all runs | 80 | 18.0 | 10.0 | 3.0 |
| lexi8_random | task-success runs | 52 | 16.0 | 9.0 | 3.0 |

### 2.4 Control-only highest-fidelity-individual fields

These fields are descriptive for lexi8_random only and are not used for between-method inference.

| Gen | n | Fid mean [IQR] | Gates mean [IQR] | Depth mean [IQR] | 2Q mean [IQR] | Any meets all targets |
|---|---|---|---|---|---|---|
| 0 | 80 | 0.529 [0.482, 0.539] | 157.96 [67.00, 234.50] | 112.91 [45.75, 172.00] | 32.33 [12.00, 50.00] | 0.025 |
| 1 | 80 | 0.585 [0.521, 0.583] | 135.50 [67.75, 191.50] | 96.74 [46.00, 133.25] | 27.48 [12.00, 40.00] | 0.025 |
| 2 | 80 | 0.656 [0.542, 0.768] | 141.93 [70.75, 198.75] | 101.81 [50.50, 143.50] | 29.02 [13.75, 43.50] | 0.037 |
| 5 | 80 | 0.759 [0.607, 0.927] | 138.90 [70.00, 180.00] | 98.69 [49.75, 129.25] | 28.25 [13.75, 39.00] | 0.037 |
| 10 | 80 | 0.853 [0.740, 0.967] | 106.08 [30.00, 149.25] | 74.21 [19.00, 106.25] | 21.43 [6.00, 29.50] | 0.050 |
| 25 | 75 | 0.927 [0.920, 0.976] | 70.25 [25.00, 104.50] | 47.23 [14.00, 74.00] | 13.69 [4.00, 21.00] | 0.133 |
| 50 | 50 | 0.939 [0.928, 0.976] | 62.62 [25.25, 95.50] | 41.48 [15.25, 61.50] | 11.76 [5.00, 17.75] | 0.100 |
| 75 | 38 | 0.942 [0.936, 0.975] | 62.89 [25.00, 90.00] | 41.84 [16.00, 62.75] | 11.63 [5.00, 16.50] | 0.079 |
| 99 | 29 | 0.942 [0.931, 0.974] | 62.07 [25.00, 101.00] | 40.45 [16.00, 67.00] | 11.14 [5.00, 16.00] | 0.000 |

The complete per-generation descriptive table is in `control_highest_fidelity_individual_by_generation.csv`.

## EXPLORATORY (post hoc; not pre-registered)

### E1. Paired task-success difference

Lexi2 minus lexi8_random task-success difference: **+0.062500** (5/80, or 6.25 percentage points). Exact conditional 95% CI: **[-0.080212, +0.191951]**. The interval conditions on the 17 Lexi2-only and 12 control-only discordant pairs and applies a Clopper-Pearson interval to their win probability.

### E2. Four-method task success and failure composition

| Method | Task successes | n | Proportion |
|---|---|---|---|
| epsilon_lexicase | 79 | 80 | 0.988 |
| tournament | 75 | 80 | 0.938 |
| lexi2 | 57 | 80 | 0.713 |
| lexi8_random | 52 | 80 | 0.650 |

| State | epsilon_lexicase | tournament | lexi2 | lexi8_random |
|---|---|---|---|---|
| 000 | 10 | 10 | 8 | 4 |
| 001 | 10 | 10 | 8 | 6 |
| 010 | 10 | 9 | 9 | 8 |
| 011 | 10 | 8 | 5 | 8 |
| 100 | 10 | 10 | 8 | 8 |
| 101 | 10 | 10 | 6 | 9 |
| 110 | 9 | 10 | 8 | 5 |
| 111 | 10 | 8 | 5 | 4 |

| Method | Early stop | Late success | Fidelity fail | Size fail | Total |
|---|---|---|---|---|---|
| epsilon_lexicase | 79 | 0 | 1 | 0 | 80 |
| tournament | 75 | 0 | 1 | 4 | 80 |
| lexi2 | 55 | 2 | 14 | 9 | 80 |
| lexi8_random | 51 | 1 | 12 | 16 | 80 |

### E3. Mechanism summary at selected generations

| Method | Gen | Max-fid mean | Runs | Pool mean | Selections |
|---|---|---|---|---|---|
| epsilon_lexicase | 5 | 0.692157 | 80 | NA | 0 |
| epsilon_lexicase | 10 | 0.801223 | 80 | NA | 0 |
| epsilon_lexicase | 20 | 0.849592 | 51 | NA | 0 |
| epsilon_lexicase | 50 | 0.845514 | 7 | NA | 0 |
| tournament | 5 | 0.554827 | 80 | NA | 0 |
| tournament | 10 | 0.725204 | 80 | NA | 0 |
| tournament | 20 | 0.788158 | 50 | NA | 0 |
| tournament | 50 | 0.849433 | 15 | NA | 0 |
| lexi2 | 5 | 0.771356 | 80 | 8.126310 | 15937 |
| lexi2 | 10 | 0.861799 | 80 | 8.946653 | 18839 |
| lexi2 | 20 | 0.911399 | 75 | 9.401760 | 20002 |
| lexi2 | 50 | 0.912086 | 37 | 8.875681 | 10095 |
| lexi8_random | 5 | 0.786276 | 80 | 7.290738 | 16465 |
| lexi8_random | 10 | 0.867434 | 80 | 7.987864 | 19199 |
| lexi8_random | 20 | 0.920585 | 78 | 9.177706 | 20562 |
| lexi8_random | 50 | 0.944314 | 50 | 9.384824 | 13627 |

Population maximum fidelity is available for all four methods. Post-case pool size is available only for Lexi2 and lexi8_random; the v0.1 epsilon-lexicase and tournament artifacts did not log those pools, so no values are reconstructed or invented here.

## Outputs

- `integrity_check.json`
- `control_arm_results.json`
- `run_level_paired.csv`
- `exact_fidelity_unified.csv`
- `per_state_task_success.csv`
- `control_failure_composition.csv`
- `run_level_median_sizes.csv`
- `four_arm_task_success.csv`
- `four_arm_task_success_by_state.csv`
- `four_arm_failure_composition.csv`
- `mechanism_selected_generations.csv`
- `mechanism_population_max_fidelity_by_generation.csv`
- `mechanism_post_case_pool_size_by_generation.csv`
- `control_highest_fidelity_individual_by_generation.csv`
- `cliffs_delta_state_cluster_bootstrap.csv`
- `figures/control_arm_mechanism.pdf`
