# STATS_SUPPLEMENT — Frozen 10-seed batch: ε-lexicase (3-case) vs tournament

Source: `experiments_frozen_10seed/` (160 runs: 10 seeds × 8 states × 2 arms, pop 300, max 100 generations, frozen noise + target bundle) and the 16 `hof_1_ibm_hardware_data.json` jobs. **No experiments or hardware jobs were run to produce this file.** Final fidelity = `run_result.json` final re-evaluated fidelity; converged = `Hardware targets achieved` stop reason. α = 0.05, two-sided. Software: scipy 1.15.1, numpy 2.2.2.

## 1. Primary paired analysis

Paired difference = ε-lexicase final fidelity − tournament final fidelity for each (state, seed); 80 pairs.

| Metric | Value |
|---|---|
| Median paired difference | **+0.0019** |
| Mean paired difference | +0.0042 |
| Wins / losses / ties | **52 / 26 / 2** |
| Wilcoxon signed-rank, non-zero pairs | W = 1066.0, n = 78, **p = 0.0181** → significant: yes |
| Wilcoxon signed-rank, all 80 (ties by default method) | W = 1066.0, p = 0.0181 |

**Result:** ε-lexicase wins 52/80 pairs (26 losses, 2 ties); median advantage +0.0019; Wilcoxon p = 0.0181 on the 78 non-zero pairs.

### 1a. Per-state win breakdown

| State | Lex wins /10 | Tour wins /10 | Ties | Mean diff | Binomial p (two-sided) |
|---|---|---|---|---|---|
| $\ket{000}$ | 5 | 3 | 2 | -0.0006 | 1.0000 |
| $\ket{001}$ | 8 | 2 | 0 | +0.0052 | 0.1094 |
| $\ket{010}$ | 5 | 5 | 0 | +0.0016 | 1.0000 |
| $\ket{011}$ | 5 | 5 | 0 | +0.0049 | 1.0000 |
| $\ket{100}$ | 7 | 3 | 0 | +0.0032 | 0.3438 |
| $\ket{101}$ | 7 | 3 | 0 | +0.0015 | 0.3438 |
| $\ket{110}$ | 7 | 3 | 0 | -0.0018 | 0.3438 |
| $\ket{111}$ | 8 | 2 | 0 | +0.0196 | 0.1094 |

No single state is significant at α = 0.05 after a per-state two-sided binomial test (n = 10 seeds per state; the test has low power at this n).

### 1b. Robustness to state clustering

**Per-state sign tests** (table in 1a): no state is individually significant (n = 10 seeds per state; max p = 0.109 for |001⟩ and |111⟩).

**State-block permutation test.** Units are the 8 states; the statistic is the sum of per-state mean paired differences. Under the null, the sign of each state's entire 10-seed block is flipped (all 2⁸ = 256 assignments, exact).

**Per-pair sign-flip permutation** (100,000 draws, seed 20260827) on the mean paired difference (Σ diff = +0.3349); the mean is sensitive to a few large differences.

**Aggregate sign test** on the 78 non-tied pairs (52 wins vs 26): assumes pairs independent (the pseudo-replication caveat it is intended to check).

**Sensitivity to the single most extreme pair** (tournament |111⟩ seed 91197, difference +0.2091): excluding it, wins 51/26/2, median +0.0018, Wilcoxon p = 0.0270 (n = 77), per-pair permutation p = 0.2572.

| Check | Statistic | p | Verdict (α = 0.05) |
|---|---|---|---|
| State-block permutation (exact, 256 assignments) | Σᵢ meanᵢ(diff) = +0.0335 | 0.0547 | borderline (just above threshold) |
| Per-pair sign-flip permutation (mean) | Σ diff = +0.3349 | 0.1268 | not significant |
| Aggregate sign test (independent-pairs assumption) | 52 vs 26 | 0.0043 | significant |
| Wilcoxon, excluding the extreme pair | W = 1066.0, n = 77 | 0.0270 | significant |
| Per-state binomial (worst case) | 8/10 wins (|001⟩, |111⟩) | 0.1094 | not significant |

**Result:** the paired advantage is robust in rank- and sign-based terms (Wilcoxon p = 0.018, and p = 0.027 excluding the extreme pair; 52/26/2 win split, aggregate sign-test p = 0.0043), but it is small and state-dependent: no state is individually significant at n = 10, and the conservative state-block permutation is borderline (p = 0.0547) while the mean-based per-pair permutation is not significant (p = 0.1268). The headline should be phrased as a small, concentrated advantage rather than a uniform effect over 80 independent pairs.

## 2. Supporting effect-size evidence

| Test | Statistic | p | Effect |
|---|---|---|---|
| Mann-Whitney U (final fidelity, 80 vs 80) | U = 3938.5 | **p = 0.0118** → significant: yes | ε-lexicase higher |
| Cliff's δ | **+0.2308** | 95% bootstrap CI [+0.0533, +0.4028] | CI excludes 0: yes |

**Result:** MWU p = 0.0118; Cliff's δ = +0.231 (small effect), 95% CI [+0.0533, +0.4028] excludes zero (10,000 bootstrap resamples, seed 20260827).

## 3. Variance — formal tests

| Arm | Final-fidelity SD (ddof=1) |
|---|---|
| ε-lexicase | 0.0096 |
| tournament | 0.0264 |
| SD ratio (tournament / ε-lexicase) | **2.75** |

- **Brown-Forsythe** (Levene with medians, center='median'): W = 0.56, df = (1, 158), **p = 0.4551** → significant at α = 0.05: no.
- **Bootstrap 95% CI on the SD ratio** (10,000 resamples, seed 20260827): **[0.58, 5.83]** → excludes 1: no.

**Result:** the 2.75× SD ratio is **descriptive, not formally significant** — Brown-Forsythe p = 0.4551 and the SD-ratio 95% CI [0.58, 5.83] includes 1. The elevated overall ratio is driven by |111⟩ (5.8×) and, secondarily, |010⟩ (2.6×) and |011⟩ (3.3×); the per-state flags are descriptive. (|110⟩ is the reverse: ε-lex SD 0.0177 vs tournament 0.0022.)

### Per-state SD ratio

| State | SD ε-lex | SD tour | Ratio tour/lex | Flag ≥1.5 |
|---|---|---|---|---|
| $\ket{000}$ | 0.0054 | 0.0045 | 0.83 |  |
| $\ket{001}$ | 0.0068 | 0.0088 | 1.30 |  |
| $\ket{010}$ | 0.0024 | 0.0062 | 2.56 | **yes** |
| $\ket{011}$ | 0.0025 | 0.0083 | 3.30 | **yes** |
| $\ket{100}$ | 0.0085 | 0.0102 | 1.21 |  |
| $\ket{101}$ | 0.0113 | 0.0093 | 0.83 |  |
| $\ket{110}$ | 0.0177 | 0.0022 | 0.12 |  |
| $\ket{111}$ | 0.0123 | 0.0717 | 5.84 | **yes** |

Tournament is ≥1.5× more variable in: $\ket{010}$ (2.6×), $\ket{011}$ (3.3×), $\ket{111}$ (5.8×). (|110⟩ is the reverse: ε-lex SD 0.0177 vs tournament 0.0022, driven by the single ε-lexicase non-converged run there.)

## 4. |111⟩ deployment counterfactual (ε-lexicase, offline)

Candidate pool: the 10 per-seed best circuits saved on disk for |111⟩ ε-lexicase (`run_result.json` per run; HOF size = 1, so the per-run best is the run's HOF candidate). Final-population checkpoints were not parsed (they were not part of the deployment pool).

| Seed | Sim fidelity | Transpiled g/d/2Q | Rule (a) pick | Rule (b) pick |
|---|---|---|---|---|
| 12147 | 0.9814 | 19/10/3 | **a** |  |
| 80248 | 0.9812 | 8/5/2 |  |  |
| 29440 | 0.9798 | 8/4/1 |  | **b** |
| 47182 | 0.9793 | 8/4/2 |  |  |
| 21315 | 0.9786 | 19/12/3 |  |  |
| 70300 | 0.9781 | 16/8/2 |  |  |
| 33537 | 0.9779 | 19/12/4 |  |  |
| 91197 | 0.9580 | 18/10/3 |  |  |
| 74135 | 0.9550 | 13/8/2 |  |  |
| 67154 | 0.9504 | 10/4/0 |  |  |

- Tolerance for near-top-fidelity: **within 0.01 of max sim fidelity (0.9814)** → 7 eligible candidates.

| Rule | Selection key | Chosen seed | Sim fidelity | Transpiled g/d/2Q |
|---|---|---|---|---|
| (a) deployed λ-free (fid → 2Q → depth, full pool) | max fidelity | 12147 | 0.9814 | 19/10/3 |
| (b) size-aware, near-top-fidelity (2Q → gates → depth) | min 2Q → gates → depth | 29440 | 0.9798 | 8/4/1 |

Rule (b) selects a **different, smaller circuit** (seed 29440: 8g/4d/2Q=1 vs deployed 19g/10d/2Q=3) at a sim-fidelity cost of 0.0016.
The rule-(b) pick (seed 29440) has **no hardware result on disk** (only the deployed seed 12147 was run on ibm_fez). Its simulated properties are reported above; no new hardware job was run.

**Result:** a size-aware selection over the existing candidates would have replaced the deployed depth-10 circuit (HW p(marked) 0.9304) with the seed-29440 circuit (8g/4d/2Q=1, sim fidelity 0.9798), i.e. the deployed |111⟩ pick was avoidably bloated by the pure fidelity-first rule.

## 5. Circuit-quality summary (existing data, run-level best per state × seed)

| Metric | ε-lex median | Tour median | Wilcoxon p (paired) |
|---|---|---|---|
| Transpiled depth | 5 | 6 | 0.1879 |
| Transpiled 2Q gates | 2 | 2 | 0.1245 |

| Substantially larger tournament circuit | Count (/80) |
|---|---|
| tournament depth > ε-lexicase | 39 |
| tournament depth ≥ 2× ε-lexicase | **14** |
| tournament 2Q > ε-lexicase | 34 |
| tournament 2Q ≥ ε-lexicase + 2 | **21** |

**Deployed best-of-10 per state (λ-free rule):**

| State | Lex D/2Q | Tour D/2Q |
|---|---|---|
| $\ket{000}$ | 1/0 | 1/0 |
| $\ket{001}$ | 2/0 | 2/0 |
| $\ket{010}$ | 5/1 | 3/0 |
| $\ket{011}$ | 4/1 | 15/5 |
| $\ket{100}$ | 5/0 | 2/0 |
| $\ket{101}$ | 3/0 | 5/2 |
| $\ket{110}$ | 2/0 | 6/2 |
| $\ket{111}$ | 10/3 | 5/2 |

Tournament's deployed circuit is ≥2× the ε-lexicase depth for |011⟩ (15 vs 4) and |110⟩ (6 vs 2); no deployed tournament circuit exceeds ε-lexicase 2Q by ≥2. At run level, tournament produces a ≥2×-depth circuit in 14/80 pairs and a 2Q ≥ +2 circuit in 17/80.

## 6. The 6 non-converged runs

| Arm | State | Seed | Peak fidelity | Peak gen | Final fidelity | Final g/d/2Q | Fidelity ≥0.95 at peak? | Classification |
|---|---|---|---|---|---|---|---|---|
| epsilon_lexicase | 110 | 29440 | 0.9716 | 99 | 0.9255 | 35/18/6 | yes | size-target miss |
| tournament | 010 | 29440 | 0.9780 | 60 | 0.9780 | 26/14/5 | yes | size-target miss |
| tournament | 011 | 70300 | 0.9797 | 99 | 0.9797 | 22/15/5 | yes | size-target miss |
| tournament | 011 | 74135 | 0.9790 | 29 | 0.9766 | 25/14/5 | yes | size-target miss |
| tournament | 111 | 74135 | 0.9785 | 98 | 0.9785 | 22/10/3 | yes | size-target miss |
| tournament | 111 | 91197 | 0.7489 | 90 | 0.7489 | 68/45/3 | no | fidelity failure |

**Result:** of the 6 non-converged runs, **5 met fidelity ≥ 0.95 at their peak but missed the hardware size targets** (gates ≤ 20, depth ≤ 15) and **1 genuinely failed on fidelity** (tournament |111⟩ seed 91197, peak 0.7489). The residual failure mode in this batch is size, not fidelity.

## Methods and assumptions

- **Wilcoxon signed-rank** (non-zero pairs): tests whether paired differences are symmetric about 0; requires paired observations; ties dropped (2 of 80). Default zero-handling variant reported alongside (p = 0.0181 both ways here).
- **Per-state binomial sign test**: per-state wins ~ Binomial(10, 0.5) under the null; assumes seeds independent within state; low power at n = 10.
- **State-block permutation**: exact over all 2⁸ sign assignments of per-state mean differences; treats states as blocks, so it does not assume 80 independent pairs. Resolution 1/256. Statistic = sum of per-state mean differences (outlier-sensitive).
- **Per-pair permutation**: 100,000 random sign flips of the paired differences; statistic = sum of differences (mean-based, outlier-sensitive); assumes label exchangeability within each pair; states enter as fixed blocks.
- **Aggregate sign test**: binomial on the non-tied pair win count; assumes pairs independent (presented as the pseudo-replication-aware comparison).
- **Sensitivity check**: all paired statistics recomputed with the single extreme pair (tournament |111⟩ seed 91197) removed.
- **Mann-Whitney U**: unpaired; treats the 80 per-arm run results as independent draws (complement to the paired tests; the same 10 seeds recur across states — a known limitation of the unpaired view).
- **Cliff's δ CI**: 10,000 paired-resample bootstrap, percentile 2.5–97.5.
- **Brown-Forsythe**: Levene with medians, robust to non-normality; independent samples.
- **SD-ratio bootstrap CI**: 10,000 independent resamples of each arm, percentile 2.5–97.5.
- All bootstrap/permutation draws use seed 20260827.
- Reproducibility check: 52/26/2, Wilcoxon ≈0.018, MWU ≈0.012, Cliff's δ ≈ +0.23 (CI excludes 0), SDs 0.0096/0.0264 (ratio ≈2.75), per-state SD flags 010/011/111, depth ≥2× in 14/80, 2Q ≥+2 in 17/80, and the 5-vs-1 non-converged classification all reproduced exactly. **Flagged as not reproducing an implicit expectation:** the formal variance tests are NOT significant (Brown-Forsythe p = 0.455; SD-ratio CI includes 1), and the conservative state-block permutation is borderline (p = 0.0547) rather than clearly significant.
