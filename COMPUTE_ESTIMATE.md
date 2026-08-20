# Compute-Cost Estimate — Re-running Experiments with More Seeds

**Date:** 2026-08-19
**Basis:** Measured runtime from all 120 completed runs on disk (logs only, no new experiments run).
**Hardware (from run metadata):** Apple M4, 10 cores, 16 GB RAM, Python 3.11, Qiskit 2.4.1 / Aer 0.17.2, backend `ibm_fez`, noise model on.

---

## Step 1 — Measured per-run cost

Every run directory contains a `run_metadata_*.json` (authoritative timing), a `diagnostics_*.csv` (per-generation `gen_time_sec`), and an `early_stopping_*.json`. The sum of per-generation times from the diagnostics agrees with the metadata `total_seconds` to within ~2–5 s on every run; metadata totals are used below.

### Total run time per arm

| Arm | n | Mean | Median | Min | Max |
|---|---:|---:|---:|---:|---:|
| epsilon-lexicase, pop100 | 40 | 0.86 h (51 m 49 s) | 0.83 h (50 m 05 s) | 0.27 h (16 m 27 s) | 1.57 h (1 h 34 m) |
| epsilon-lexicase, pop300 | 40 | 1.83 h (1 h 49 m 50 s) | 1.56 h (1 h 33 m 28 s) | 1.07 h (1 h 04 m) | 3.03 h (3 h 02 m) |
| tournament, pop300 | 40 | 7.06 h (7 h 03 m 38 s) | 6.71 h (6 h 42 m 42 s) | 3.21 h (3 h 13 m) | 13.89 h (13 h 54 m) |

Tournament at pop300 is the dominant cost: ~4× the per-run time of lexicase pop300, and its variance is large (max ≈ 2.0× the mean).

### Generations executed before early stopping

| Arm | Mean | Median | Min | Max |
|---|---:|---:|---:|---:|
| epsilon-lexicase, pop100 | 19.3 | 18.5 | 15 | 34 |
| epsilon-lexicase, pop300 | 21.1 | 20.0 | 15 | 43 |
| tournament, pop300 | 19.3 | 18.5 | 15 | 30 |

No run reached the `max_generations = 100` cap; every run stopped early (stagnation or hardware targets).

### Seconds per generation

| Arm | Mean of per-run averages | Median of per-run averages | Pooled (Σ total / Σ gens) |
|---|---:|---:|---:|
| epsilon-lexicase, pop100 | 152.0 s | 159.3 s | 153.3 s |
| epsilon-lexicase, pop300 | 300.1 s | 304.5 s | 298.5 s |
| tournament, pop300 | 1255.8 s | 1190.2 s | 1252.1 s |

### Converged vs failed runs

Classification from `stop_reason`:

| Arm | Outcome | n | Mean run time | Mean gens |
|---|---|---:|---:|---:|
| epsilon-lexicase, pop100 | converged (targets achieved) | 15 | 0.95 h | 21.2 |
| epsilon-lexicase, pop100 | failed — fidelity stagnant | 18 | 0.76 h | 17.9 |
| epsilon-lexicase, pop100 | failed — hardware metrics stagnant | 7 | 0.94 h | 18.7 |
| epsilon-lexicase, pop300 | converged (targets achieved) | 28 | 1.99 h | 22.9 |
| epsilon-lexicase, pop300 | failed — fidelity stagnant | 10 | 1.51 h | 17.2 |
| epsilon-lexicase, pop300 | failed — hardware metrics stagnant | 2 | 1.26 h | 15.0 |
| tournament, pop300 | converged (targets achieved) | 22 | 7.20 h | 19.9 |
| tournament, pop300 | failed — fidelity stagnant | 18 | 6.89 h | 18.6 |

**The hypothesis that failed runs are slower does not hold here — the opposite does.** Failed runs stop *earlier* (stagnation triggers the early stop sooner than the hardware targets are achieved), so they are slightly *faster* than converged runs in every arm. The difference is small for tournament (7.20 h vs 6.89 h) and modest for lexicase pop300 (1.99 h vs 1.51 h). A "converged vs failed" mix shift would therefore move the mean by at most ~±15% for lexicase arms and ~±2% for tournament.

**Total measured cost of the completed 120 runs:** 390.2 h = 16.3 serial-equivalent days.

---

## Step 2 — Current experiment count (confirmation)

Stated design: 8 states × 5 seeds × 2 selection methods at pop300 (80 runs) + pop100 ablation 8 × 5 (40 runs) = **120 runs**.

On disk (115 diagnostics + 5 in the older flat folder, all with matching `run_metadata`):

| Arm | States | Runs |
|---|---:|---:|
| `experiments/epsilon_lexicase/pop300/noise` | 8 (000–111) | 40 |
| `experiments/tournament/pop300/noise` | 8 (000–111) | 40 |
| `experiments/epsilon_lexicase/pop100/noise` | 7 (000–110) | 35 |
| `experiments_epsilon_lexicase_noise_pop100` (older flat folder) | 1 (111) | 5 |
| **Total** | | **120** |

**Confirmed: 120 runs, matching the stated 80 + 40 design.** The pop100 ablation is complete but split across two folders: the organized tree holds states 000–110 and the older flat folder holds state 111. All pop100 runs are epsilon-lexicase at pop100.

---

## Step 3 — Scenario projections

Projections use the **mean measured run time per arm**:

- epsilon-lexicase pop300: **1.83 h/run**
- tournament pop300: **7.06 h/run**
- epsilon-lexicase pop100: **0.86 h/run**

Parallel estimates assume **N = 8 concurrent runs** on the same M4 (idealized linear speedup: parallel days = serial days / 8). This is consistent with how the original runs were actually executed — the tournament batch (282 h of per-run time) completed in ~38 h of wall-clock, i.e. effective concurrency ≈ 7.4, and the later lexicase/pop100 batches ran 2–6 at a time. Correct N and the numbers rescale linearly.

| Scenario | Description | Runs | Serial hours | Serial days | Parallel days @ N=8 |
|---|---|---:|---:|---:|---:|
| **A** | 10 seeds × 8 states × 2 methods, pop300 | 160 | 711 | 29.6 | 3.7 |
| **B** | 20 seeds × 8 states × 2 methods, pop300 | 320 | 1,423 | 59.3 | 7.4 |
| **C** | A + 10 seeds × 8 states pop100 ablation | 240 | 780 | 32.5 | 4.1 |
| **D** | 10 seeds × 8 states × 4 methods (A + Lexi2 + per-output-probability lexicase) | 320 | 1,004 | 41.8 | 5.2 |
| **E** | Same as D but 20 seeds | 640 | 2,008 | 83.7 | 10.5 |

Breakdown of the serial hours by arm (to show where the budget goes):

| Scenario | Lexicase-family (1.83 h × runs) | Tournament (7.06 h × runs) | pop100 (0.86 h × runs) |
|---|---:|---:|---:|
| A | 146 h (80 runs) | 565 h (80 runs) | — |
| B | 293 h (160 runs) | 1,130 h (160 runs) | — |
| C | 146 h (80 runs) | 565 h (80 runs) | 69 h (80 runs) |
| D | 439 h (240 runs) | 565 h (80 runs) | — |
| E | 879 h (480 runs) | 1,130 h (160 runs) | — |

Tournament is 79% of the serial cost of every scenario that includes it. Assumption: Lexi2 and the per-output-probability lexicase variant are implemented as lexicase-family selections with the same per-run cost as epsilon-lexicase pop300 (same population size, same evaluation pipeline).

---

## Step 4 — Deadline feasibility

- Today: **2026-08-19**
- Deadline: **2026-11-30**
- Days remaining: **103**
- Assumed buffer for analysis, figures, writing: **14 days** (2 weeks) → experiments must finish by **2026-11-16**, i.e. **89 compute days** are available.

| Scenario | Serial days | Fits serially? | Slack after buffer | Parallel days @ N=8 | Fits parallel? |
|---|---:|---|---:|---:|---|
| A | 29.6 | Yes | 59 days | 3.7 | Yes |
| B | 59.3 | Yes | 30 days | 7.4 | Yes |
| C | 32.5 | Yes | 56 days | 4.1 | Yes |
| D | 41.8 | Yes | 47 days | 5.2 | Yes |
| E | 83.7 | Yes, but tight | **~5 days** | 10.5 | Yes |

**Verdict:**

- All five scenarios fit within the window **when run in parallel at N = 8**, with at least 78 days of slack.
- Even fully serial, all five fit — but **E is the risk case**: 83.7 compute days against 89 available leaves only ~5 days of slack before the analysis buffer. Any rerun of failed/partial runs, machine downtime, or slower-than-mean seeds (tournament runs up to 13.9 h, ~2× the mean) would push E past the deadline serially.
- If E is the target, run it in parallel (or trim to scenario D at 20 seeds / different arms). At N = 8 it is a ~10.5-day job.

---

## Assumptions and caveats

1. **Re-runs use the same configuration as the completed runs**: noise model on, `ibm_fez` backend, hardware targets (fidelity/gates/depth), same machine class. Any change (e.g., noisier backend, higher fidelity targets, different population sizes) invalidates these numbers.
2. **Measured times are wall-clock and already include CPU contention.** The original batches ran 2–8 experiments concurrently on the same 10-core M4, so each run's `total_seconds` is inflated relative to a clean serial run. The serial projections are therefore **conservative upper bounds** (true serial times would be somewhat lower); the parallel projections at N=8 approximate the machine's observed behavior.
3. **Parallel estimates assume idealized linear speedup** (no overhead, no memory contention) at N = 8 concurrent runs. Real speedup will be slightly less than linear; treat parallel days as a lower bound.
4. **New selection arms (Lexi2, per-output-probability lexicase) are assumed to cost the same per run as epsilon-lexicase pop300.** They are lexicase-family selections at the same population size; if their evaluation/selection logic is heavier, add the difference.
5. **Mean run times embed the observed converged/failed mix.** The mix barely matters for tournament and shifts lexicase means by ≤15%, so projections are robust to that uncertainty.
6. Scenario B/E double the seed count using the *current* seed set (5 per state) as the calibration basis; new seeds are assumed to draw from the same runtime distribution (early-stop between 15–43 generations, mean ~19–21).
7. Two weeks of post-experiment buffer is assumed; adjust the verdict by the same number of days you actually need.
