# STATS_3ARM — Frozen batch: ε-lexicase vs Lexi2 vs tournament

240 runs (10 seeds × 8 states × 3 arms). α = 0.05; pairwise p-values reported raw with Holm-Bonferroni correction over the three arm pairs. No experiments re-run.

## 1. Convergence

| Arm | Converged/80 | % |
|---|---|---|
| $\varepsilon$-lexicase | 79/80 | 98.8% |
| Lexi2 | 55/80 | 68.8% |
| tournament | 75/80 | 93.8% |

| Pair | Fisher p (raw) | Holm-adjusted | Significant (adj < 0.05) |
|---|---|---|---|
| $\varepsilon$-lexicase vs Lexi2 | 0.0000 | 0.0000 | yes |
| $\varepsilon$-lexicase vs tournament | 0.2098 | 0.2098 | no |
| Lexi2 vs tournament | 0.0001 | 0.0001 | yes |

## 2. Final fidelity

- Kruskal-Wallis across arms: H = 9.65, p = 0.0080

| Pair | MWU U | p (raw) | Cliff's δ (95% CI) |
|---|---|---|---|
| $\varepsilon$-lexicase vs Lexi2 | 4015.5 | 0.0054 | +0.255 ([+0.081, +0.422]) |
| $\varepsilon$-lexicase vs tournament | 3938.5 | 0.0118 | +0.231 ([+0.055, +0.402]) |
| Lexi2 vs tournament | 3016.0 | 0.5311 | -0.058 ([-0.239, +0.125]) |

Means ± SD: ε-lexicase 0.9770 ± 0.0096; Lexi2 0.9066 ± 0.1587; tournament 0.9728 ± 0.0264. Lexi2's lower mean is driven by hard-state failures (|101⟩/|110⟩/|111⟩).

## 3. Generations to stop

| Arm | Converged runs mean (median) | All runs mean (median; full = 100) |
|---|---|---|
| $\varepsilon$-lexicase | 27.5 (25) | 28.4 (25) |
| Lexi2 | 39.8 (36) | 58.3 (46) |
| tournament | 29.2 (23) | 33.6 (24) |

## 4. Circuit quality (run-level best per state × seed)

| Arm | Transpiled gates median | Depth median | 2Q median | Deployed best-of-10: gates/depth/2Q (mean across states) |
|---|---|---|---|---|
| $\varepsilon$-lexicase | 10 | 5 | 2 | 7.8/4.0/0.6 |
| Lexi2 | 17 | 10 | 3 | 7.2/3.6/0.4 |
| tournament | 10 | 6 | 2 | 8.1/4.9/1.4 |

## 5. Failure composition (full-100 runs)

| Arm | Full-100 | Fidelity fail | Size fail | Stopping miss |
|---|---|---|---|---|
| $\varepsilon$-lexicase | 1 | 1 | 0 | 0 |
| Lexi2 | 25 | 14 | 9 | 2 |
| tournament | 5 | 1 | 4 | 0 |

Lexi2's dominant failure mode on hard states is fidelity (never reaches 0.95), unlike ε-lexicase/tournament where failures are overwhelmingly size-target misses.

## 6. Hardware validation (ibm_fez, 10,000 shots, deployed best-of-10)

| Arm | Mean HW p(marked) | Mean |sim − HW| | Max |delta| | Worst state |
|---|---|---|---|---|
| $\varepsilon$-lexicase | 0.9762 | 0.0104 | 0.0510 | |111⟩ |
| Lexi2 | 0.9762 | 0.0083 | 0.0176 | |111⟩ |
| tournament | 0.9707 | 0.0132 | 0.0558 | |011⟩ |

## Methods

- Fisher exact (convergence), Kruskal-Wallis + Mann-Whitney U + Cliff's δ with 10,000 resample bootstrap CI (seed 20260902); Holm-Bonferroni over the 3 arm pairs.
- Pairing: ε-lexicase vs tournament share gen-0 per (state, seed) (byte-verified); Lexi2 shares the same init code/seeds, so paired comparisons vs either arm are valid by construction (gen-0 hash-verified for state 000/seed 21315 in the smoke validation).
