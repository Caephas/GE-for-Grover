# SURVIVOR_POOL_COMPARISON — post-case survivor-pool sizes: Lexi2 vs 3-objective ε-lexicase

**Question.** Are the post-case survivor pools comparably large in the Lexi2
(8 output-state probability cases) and 3-objective ε-lexicase arms? If yes, a
large post-case pool is not a product of Lexi2's 8-output case decomposition,
and the tiebreak rule (not the case structure) is the operative difference.

**Answer from existing logs: NOT COMPUTABLE for the 3-objective arm.** The
ε-lexicase runs did not log per-selection survivor-pool sizes, so no
distribution exists to compare against the Lexi2 one. Nothing is claimed about
comparability. Details and evidence below. No new runs were performed.

---

## 1. How the Lexi2 pool sizes were logged (the reference computation)

In `run_experiment.py`, the Lexi2 selector (`selLexi2Quantum`) records, per
generation and per run:

- `selections`: the number of parent selections (`k`, 299 per active run-generation),
- `tiebreak_fires`: how many selections ended with more than one post-case
  survivor,
- `post_case_pool_sizes`: the survivor-pool size **for the tiebreak-firing
  selections only** (selections that collapse to a single individual are
  recorded only implicitly, as `selections - tiebreak_fires` with pool size 1).

These are written to `lexi2_log_*.json` in each of the 80 Lexi2 runs. The full
(unconditional) pool-size distribution is therefore
`[1] * (selections - fires) + post_case_pool_sizes` per run-generation.

## 2. Lexi2 post-case pool-size distribution (80 runs, 1,418,157 selections)

Unconditional distribution over all selections (pool size 1 included):

| Statistic | Value |
|---|---|
| Selections | 1,418,157 |
| Mean pool size | 7.59 |
| Median pool size | 7 |
| SD | 5.24 |
| p1 / p5 / p25 | 1 / 1 / 3 |
| p75 / p95 / p99 | 11 / 17 / 22 |
| Max | 41 |
| Share with pool = 1 | 15.8% |
| Share with pool = 2 | 6.6% |
| Share with pool ≥ 3 | 77.7% |
| Share with pool ≥ 5 | 66.8% |
| Share with pool ≥ 10 | 34.0% |

Conditional on the tiebreak firing (pool > 1): mean 8.82, median 8.

Per-generation trajectory (10-generation blocks; full per-generation values in
`survivor_pool_lexi2_bygen.csv`):

| Generations | Selections | Mean pool size | Median pool size |
|---|---|---|---|
| 0–9 | 142,745 | 8.11 (mostly size 1 at gen 0: mean 1.02) | 7 |
| 10–19 | 200,054 | 9.17 | 9 |
| 20–29 | 190,500 | 9.53 | 9 |
| 30–39 | 149,600 | 9.32 | 9 |
| 40–49 | 116,863 | 8.95 | 8 |
| 50–59 | 98,330 | 8.63 | 8 |
| 60–69 | 82,831 | 8.41 | 8 |
| 70–79 | 74,193 | 8.23 | 8 |
| 80–89 | 72,544 | 8.36 | 8 |
| 90–99 | 67,119 | 7.88 | 7 |

The pool is large from early evolution onward: pool = 1 in 98.6% of selections
at generation 0, falling to ~45% by generation 2 and ~10% or less from
generation ~20; pools of ≥ 3 individuals decide ~78% of all selections and
pools of ≥ 10 ~34%.

## 3. The 3-objective ε-lexicase arm: what exists in the logs

Per-run artifacts for `epsilon_lexicase` runs are: `run_result_*.json`,
`run_metadata_*.json`, `early_stopping_*.json`, `diagnostics_*.csv`,
`circuit_*.png`, and per-individual `eval_gen*` records. None of them contains
post-case survivor-pool sizes:

- `diagnostics_*.csv` records population-level per-generation statistics only
  (`n_valid`, fidelity/gate/depth min–max–mean–std–median–MAD, unique
  behaviours, scalar fitness) — no per-selection counts.
- `run_metadata_*.json` records system/timing/config only.
- No `*log*.json` equivalent of `lexi2_log` exists under the ε-lexicase arm
  (verified by file search).

In the code, per-selection pool-size accumulation exists only in the Lexi2
selector and is gated on the selection method:

```python
if gen is not None and SELECTION_METHOD == "lexi2":
    entry["post_case_pool_sizes"].extend(post_case_pool_sizes)
```

The 3-objective selector (`selEpsilonLexicaseQuantum`) filters case by case and
then picks randomly among survivors, but never records the final candidate
count. Because the per-selection case order is shuffled with runtime RNG state
that is not logged, the pools cannot be reconstructed after the fact from the
per-individual `eval_gen*` records or any other on-disk artifact without
re-running evolution.

## 4. Plain statement

The requested side-by-side comparison cannot be made from existing logs: the
Lexi2 post-case pool-size distribution is large (median 7–9 from early
evolution, with pool ≥ 3 in ~78% of selections), but the 3-objective
ε-lexicase arm logged no equivalent per-selection pool sizes, so there is no
evidence from which to judge whether its pools are comparably large. The
question "is the large pool a product of Lexi2's 8-output decomposition?"
therefore remains unanswered by the current data. To answer it, the identical
`post_case_pool_sizes` accumulation would need to be added to
`selEpsilonLexicaseQuantum` (for `SELECTION_METHOD == "epsilon_lexicase"`) and
the runs repeated — a new experiment, not performed here.
