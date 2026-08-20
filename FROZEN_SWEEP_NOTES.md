# Frozen Sweep Notes — 2026-08-20

## What is frozen

- **Environment bundle**: `noise/frozen_env_ibm_fez_2026-08-20.pkl`
  (SHA-256 `d51b5d53a60dd7a0e873b02b356d7bec529887cab0bae9aff9aefd62d8d036b3`)
  contains:
  - the noise model (SHA-256
    `fb5973eba35682aff3d0130db5688668ee0911763a1a8d92afe5e713b95c9b23`,
    captured 2026-08-19), and
  - the frozen `ibm_fez` transpile target (156 qubits).
- Every run loads the bundle via `--noise-file` (or `QISKIT_NOISE_MODEL_JSON`).
  There is **no live ibm_fez dependency** for simulation noise or for
  transpilation/layout decisions.
- Pinned environment: `requirements.txt` (qiskit 2.4.1, qiskit-aer 0.17.2,
  qiskit-ibm-runtime 0.46.1, deap 1.4.2, grape-bds 0.1.3, numpy 2.2.2, ...).

## Early stopping (option a)

- Converged runs (fidelity >= 0.95 AND gates <= 20 AND depth <= 15, with the
  hardware-optimization patience) stop early with
  `stop_reason = "Hardware targets achieved"`.
- Non-converged runs are **never** killed by patience: they run the full 100
  generations and end with `stop_reason = "completed_all_generations"`.
- Full per-generation history, patience counters, and stop reason are recorded
  in `early_stopping_<state>_run<i>.json` for every run.

## Determinism status (documented residual)

Under the frozen bundle, two identical 4-generation runs produced
**byte-identical** `run_result`, `early_stopping`, circuit PNGs, and 2,380 of
2,382 per-individual eval records. The residual:

- A Qiskit 2.4.1 **internal transpiler nondeterminism** on isolated circuits:
  the same circuit, frozen target, and `seed_transpiler` occasionally yield two
  gate-count variants (observed 218 vs 220 gates, same layout `[8,10,9]`, same
  depth) within a single process.
- Impact: at most one record per ~2,400, `p_marked` delta <= 0.0004. It does
  **not** affect deployed/reported results (`run_result` and aggregate outputs
  are byte-identical).
- Not fixed by `PYTHONHASHSEED=0` or global RNG reseeding; it is upstream
  Qiskit behavior. The version pin is intentionally unchanged.

## Batch

- 160 runs = 10 seeds x 8 states x 2 arms (epsilon_lexicase, tournament),
  pop300, max 100 generations, 4 concurrent.
- Seeds: 21315, 47182, 12147, 33537, 70300, 74135, 67154, 80248, 91197, 29440.
- Outputs: `experiments_frozen_10seed/` (tagged; old live-calibration runs are
  archived under `archive/` and are NOT comparable to this batch).
- Launch: `bash infra/run_local_sweep.sh` (caffeinate -i -s, resume-safe via
  run_result markers + checkpoint resume).
- Monitor: `tail -f logs_frozen_10seed/sweep.log` and
  `cat logs_frozen_10seed/sweep_progress.json`.
