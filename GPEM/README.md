# GE-for-Grover: frozen 3-arm sweep — paper essentials

Curated export of the files behind the three-arm frozen-noise study
(3-case ε-lexicase, Lexi2, tournament; 10 seeds × 8 states × 3 arms;
population 300; frozen noise + transpile-target bundle). Everything here is
experiment code, raw outputs, and analysis artifacts. LaTeX, notebooks, and
per-individual evaluation logs are deliberately not included; the only
infrastructure script kept is `infra/capture_noise.py`, which documents how
the frozen bundle was produced.

## Layout

```
run_experiment.py                     headless evolution driver (CLI)
requirements.txt                      pinned dependencies
redeploy_hardware.py                  deployment-time hardware runner (manual)
submit_hardware_session_2026-09-02.py matched-window hardware runner (manual)
grammars/grover.bnf                   BNF grammar used by all runs
noise/frozen_env_ibm_fez_2026-08-20.pkl  frozen noise + transpile target
                                       (SHA-256 d51b5d53a60dd7a0e873b02b356d7bec
                                        529887cab0bae9aff9aefd62d8d036b3)
noise/SHA256SUMS.txt                  checksums (bundle + source snapshot)
infra/capture_noise.py                frozen-bundle capture script (provenance)
experiments_frozen_10seed/            ε-lexicase + tournament runs (160)
experiments_frozen_10seed_lexi2/      Lexi2 runs (80)
logs_hardware_session_2026-09-02/     matched-window hardware results (25 jobs)
logs_hardware/deploy.log              deployment-time hardware log (ε-lex/tour)
logs_hardware_lexi2/deploy_lexi2.log  deployment-time hardware log (Lexi2)
per_run_frozen_3arm.csv               per-run final results, all 240 runs
results_table_frozen_3arm.csv         summary table data
hardware_results_frozen_10seed.csv    deployment-time hardware results (26 Aug)
lexi2_tiebreak_firerate_bygen.csv     tiebreak fire rate by generation
survivor_pool_lexi2_bygen.csv         post-case candidate-pool size by generation
PAPER_DATA_FROZEN_3ARM.md             corrected per-state/per-arm result packs
STATS_3ARM_frozen.md                  three-arm statistics
STATS_SUPPLEMENT_frozen.md            primary paired battery (ε-lex vs tour)
LEXI2_MECHANISM.md                    tiebreak mechanism analysis
SURVIVOR_POOL_COMPARISON.md           pool-logging caveat (ε-lex vs Lexi2)
DEPLOYMENT_RESELECTION.md             size-aware reselection across 24 slots
FROZEN_SWEEP_NOTES.md                 protocol, pins, determinism notes
CHANGELOG.md                          change log incl. transpiled-2Q fix
build_*.py                            analysis/figure builders
```

`run_experiment.py` here is the revision that produced the 240-run frozen
batch. A later, behaviour-preserving pool-logging patch (2026-09-04, see
CHANGELOG) postdates the batch and is not part of the frozen artefact.

## Frozen-bundle provenance

All 240 runs loaded one environment bundle:

- `noise/frozen_env_ibm_fez_2026-08-20.pkl` — `ibm_fez` noise model plus the
  156-qubit transpile target, captured 2026-08-20T12:34:53Z; SHA-256
  `d51b5d53a60dd7a0e873b02b356d7bec529887cab0bae9aff9aefd62d8d036b3`.
- `noise/noise_ibm_fez_2026-08-19.pkl` — the source noise-model snapshot
  embedded in that bundle, captured 2026-08-19; SHA-256
  `fb5973eba35682aff3d0130db5688668ee0911763a1a8d92afe5e713b95c9b23`. This
  17.6 MB snapshot is **not distributed** (the bundle already carries the same
  `NoiseModel` object); only its checksum is recorded, in
  `noise/SHA256SUMS.txt`.
- `infra/capture_noise.py` — the script that produced both files. It reads
  credentials from `QISKIT_IBM_TOKEN`/`QISKIT_IBM_INSTANCE` (or the saved
  account) and submits no hardware job.

No live device calibration was accessed during the sweep; simulation noise
and transpilation both came from this bundle.

## Per-run data kept

Each run folder contains the essential artifacts only:
`run_result_*.json`, `run_metadata_*.json`, `early_stopping_*.json`,
`diagnostics_*.csv`, `circuit_raw_*.png`, `circuit_transpiled_*.png`, and
(where present) `hof_1_ibm_hardware_data.json`. Lexi2 runs additionally keep
`lexi2_log_*.json` (per-case ε and tiebreak-fire counts) and
`gen0_genome_hashes.json`. State folders keep `AGGREGATE_*.json`,
`deployed_best.json`, and `experiment_seeds.json`.

Excluded per run: `eval_gen*` per-individual evaluation records and
`checkpoints/` (regenerable, several GB).

## Re-running evolution (simulation only)

```bash
python run_experiment.py run \
    --state 000 --seed 21315 --selection epsilon_lexicase \
    --population 300 --generations 100 --outdir experiments
```

The frozen bundle is loaded from `noise/` (never live calibration). Hardware
deployment is manual and separate (`redeploy_hardware.py`,
`submit_hardware_session_2026-09-02.py`); credentials are read from
`QISKIT_IBM_TOKEN`/`QISKIT_IBM_INSTANCE` or the saved IBM account, and no
token is stored in this folder.

## Regenerating analysis outputs

```bash
python build_paper_pack_3arm.py                 # result packs + most figures
python build_stats_supplement_frozen_final.py   # primary paired battery
python build_figs_070910_3arm.py                # 3-arm paired figures
python build_figs_matched_hw.py                 # fig05 from matched session
python build_fig16_firerate_pool.py             # fig16 (tiebreak rate + pool size)
python build_figs_gpem.py                       # final manuscript figures
python build_cliffs_ci_unified.py               # unified Cliff's δ CIs
python build_deployed_circuit_figures.py        # deployed circuit images
```
