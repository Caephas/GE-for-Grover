# Changelog

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
