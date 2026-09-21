# Changelog

## 2026-09-21 — Paper-artefact sync: final figure builders and analysis inputs

**Added (files only; nothing re-run).** Five artefacts used for the submitted
manuscript were missing from this folder:

- `build_figs_gpem.py` — regenerates the final manuscript figure set (the
  eleven figures included by the paper) with the revised terminology and
  print-size layout.
- `build_fig16_firerate_pool.py` — two-panel Lexi2 mechanism figure
  (size-tiebreak invocation rate and post-case candidate-pool size).
- `survivor_pool_lexi2_bygen.csv` — per-generation post-case candidate-pool
  size, the input for the right panel of that figure.
- `SURVIVOR_POOL_COMPARISON.md` — the pool-logging caveat for the ε-lexicase
  vs Lexi2 comparison.
- `hardware_results_frozen_10seed.csv` — consolidated deployment-time
  hardware results (26 August 2026 session).
- `infra/capture_noise.py` and `noise/SHA256SUMS.txt` — provenance for the
  frozen environment: the capture script, plus checksums for the distributed
  bundle (`d51b5d53…`) and the source noise-model snapshot (`fb5973eb…`) it
  embeds. The snapshot itself (17.6 MB) is not distributed. See the README
  provenance section.

The analysis-output list in `README.md` was updated to include the two
figure builders. `run_experiment.py` in this folder remains the revision that
produced the 240-run frozen batch; the 2026-09-04 pool-logging patch below
postdates the batch and is not part of the frozen artefact.

## 2026-09-04 — Symmetric post-case pool logging for both lexicase-family selectors

**Change (code only; nothing was run).** The 3-objective ε-lexicase selector
(`selEpsilonLexicaseQuantum`) now records the same per-selection post-case
survivor-pool information that Lexi2 (`selLexi2Quantum`) records, and both
selectors additionally log the shuffled case order for every selection. Per
generation per run, `selection_pool_log_<state>_run<id>.json` contains
`n_cases`, the MAD-based `epsilons` per case, `selections`,
`post_case_pool_sizes` (survivor count after all cases for **every** parent
selection, not only non-singleton ones), and `case_shuffles`. This makes
cross-arm pool-size comparisons computable for any future control arm;
historical ε-lexicase runs predate this log and cannot be retro-computed.

The shuffled order is recorded *after* `random.shuffle`, so no additional RNG
draws are consumed and runs remain byte-reproducible under the master run seed
(the per-run seed is already logged in `run_metadata`). The legacy Lexi2
`lexi2_log_*.json` output is unchanged.

## 2026-08-27 — Fix: `two_qubit_gates` now reports the transpiled 2Q count

**Bug:** `run_result.json` (and everything derived from it) stored the **raw**
(pre-transpile) two-qubit gate count in the field labeled `two_qubit_gates`,
which the deployment rule, Lexi2 tiebreak, and the paper tables use as the
*transpiled* 2Q count. The raw count came from `best_qc.count_ops()` on the
untranspiled circuit; the transpiled circuits routinely had fewer 2Q gates
(e.g. ε-lexicase |000⟩ deployed circuit: raw 2Q = 4, transpiled 2Q = 0).

**Impacted outputs (all regenerated from data already on disk; no experiments
re-run):**
- `experiments_frozen_10seed/*/pop300/noise/state_*/run_*/run_result_*.json`
  (160 files) — `two_qubit_gates` corrected to the transpiled value; the raw
  value preserved in `raw_two_qubit_gates`; `two_qubit_provenance` notes the
  source. One run (tournament |111⟩, seed 91197) is not byte-reproducible with
  the frozen target + run seed (known transpile-seed-sensitive circuit); its
  value is the re-transpiled 2Q and is flagged in
  `two_qubit_corrections_frozen_10seed.json`.
- `AGGREGATE_*.json` / `deployed_best.json` (16 each) — regenerated with the
  corrected 2Q under the unified λ-free rule
  (fidelity → transpiled 2Q → total gates → depth). Deployed picks unchanged.
- `PAPER_DATA_FROZEN_10SEED.md`, `SUPP_TABLES_FROZEN_10SEED.md`,
  `STATS_SUPPLEMENT_frozen.md`, `STATS_SUPPLEMENT_FROZEN_10SEED.md`,
  `results_table_frozen_10seed.csv`, `per_run_frozen_10seed.csv`,
  `hardware_results_frozen_10seed.csv`, and
  `paper_figures/frozen_10seed/fig04_circuit_cost.*`.

**Numbers that changed (raw → transpiled 2Q):**
- Deployed-circuit 2Q columns in the main/head-to-head tables (e.g. ε-lex |000⟩
  4 → 0, |111⟩ 7 → 3; tournament mostly 4 → 0).
- Circuit-quality summary: ε-lex median 2Q 4 → 2 (tournament stays 2); pairs
  with tournament 2Q > ε-lex 25 → 34 of 80; 2Q ≥ +2 17 → 21 of 80; paired
  Wilcoxon p 0.052 → 0.125 (no longer borderline).
- |111⟩ deployment counterfactual: size-aware rule (b) now selects seed 29440
  (8g/4d/2Q=1, sim 0.9798) instead of seed 47182; conclusion unchanged — the
  deployed depth-10 pick was avoidably bloated.

**Also in this release:** Lexi2 selection arm (8-case ε-lexicase on output-state
probabilities + 2Q/gates/depth tiebreak), per-generation ε + tiebreak logging,
gen-0 population hash records, and the unified deployment rule across arms.
