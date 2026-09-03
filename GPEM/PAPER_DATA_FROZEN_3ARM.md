# PAPER_DATA — Frozen 10-seed, three arms (ε-lexicase, Lexi2, tournament)

Assembled 2026-09-02 from the frozen batch: 240 runs = 10 seeds × 8 states × 3 arms, pop 300, max 100 gens, all under `noise/frozen_env_ibm_fez_2026-08-20.pkl` (no live calibration). Lexi2 runs live in `experiments_frozen_10seed_lexi2/`. Converged = `Hardware targets achieved` stop reason; full-100 = `completed_all_generations`. 2Q counts are the corrected transpiled values. Hardware (ibm_fez, 10k shots): all three arms deployed on 2026-09-02 (8 deployed circuits per arm; Lexi2 deployed after its sweep completed).

### Overall (per arm, n=80)

| Metric | ε-lexicase | Lexi2 | tournament |
|---|---|---|---|
| Converged (early stop) | **79/80 (98.8%)** | **55/80 (68.8%)** | **75/80 (93.8%)** |
| Ran full 100 | 1 | 25 | 5 |
| Final fidelity mean ± SD | 0.9770 ± 0.0096 | 0.9066 ± 0.1587 | 0.9728 ± 0.0264 |
| Gens-to-stop mean (median), all runs | 28.4 (25) | 58.3 (46) | 33.6 (24) |

### A. $\varepsilon$-lexicase per-state results (pop=300, 10 seeds)

| State | Best sim fid | Seed | Transpiled D/G/2Q | Raw D/G | HW p_marked | Success (k/10) | Mean±std fid | Mean stop gen |
|---|---|---|---|---|---|---|---|---|
| 000 | 0.9898 | 47182 | 1/3/0 | 20/43 | 0.9918 | 10/10 | 0.9803±0.0054 | 23.3 |
| 001 | 0.9901 | 12147 | 2/4/0 | 14/28 | 0.9910 | 10/10 | 0.9796±0.0068 | 25.2 |
| 010 | 0.9818 | 33537 | 5/8/1 | 19/41 | 0.9731 | 10/10 | 0.9781±0.0024 | 26.8 |
| 011 | 0.9801 | 47182 | 4/8/1 | 16/29 | 0.9733 | 10/10 | 0.9770±0.0025 | 27.1 |
| 100 | 0.9881 | 29440 | 5/8/0 | 20/43 | 0.9806 | 10/10 | 0.9785±0.0085 | 31.1 |
| 101 | 0.9895 | 80248 | 3/6/0 | 14/28 | 0.9853 | 10/10 | 0.9754±0.0113 | 30.0 |
| 110 | 0.9859 | 33537 | 2/6/0 | 19/42 | 0.9840 | 9/10 | 0.9750±0.0177 | 36.3 |
| 111 | 0.9814 | 12147 | 10/19/3 | 30/62 | 0.9304 | 10/10 | 0.9720±0.0123 | 27.6 |

### B. Lexi2 per-state results (pop=300, 10 seeds)

| State | Best sim fid | Seed | Transpiled D/G/2Q | Raw D/G | HW p_marked | Success (k/10) | Mean±std fid | Mean stop gen |
|---|---|---|---|---|---|---|---|---|
| 000 | 0.9834 | 47182 | 2/5/0 | 23/45 | 0.9696 | 7/10 | 0.9448±0.1018 | 54.9 |
| 001 | 0.9819 | 33537 | 7/12/2 | 16/32 | 0.9766 | 8/10 | 0.9349±0.1367 | 48.5 |
| 010 | 0.9851 | 80248 | 3/5/0 | 21/43 | 0.9798 | 9/10 | 0.9783±0.0029 | 47.4 |
| 011 | 0.9887 | 91197 | 2/5/0 | 33/59 | 0.9800 | 5/10 | 0.8898±0.1843 | 67.5 |
| 100 | 0.9869 | 29440 | 3/6/0 | 25/48 | 0.9815 | 8/10 | 0.9764±0.0075 | 60.4 |
| 101 | 0.9820 | 21315 | 3/7/0 | 23/45 | 0.9793 | 5/10 | 0.8305±0.1983 | 66.7 |
| 110 | 0.9805 | 21315 | 6/11/1 | 28/53 | 0.9726 | 8/10 | 0.8860±0.1955 | 49.0 |
| 111 | 0.9876 | 21315 | 3/7/0 | 24/46 | 0.9700 | 5/10 | 0.8119±0.2229 | 71.9 |

### C. tournament per-state results (pop=300, 10 seeds)

| State | Best sim fid | Seed | Transpiled D/G/2Q | Raw D/G | HW p_marked | Success (k/10) | Mean±std fid | Mean stop gen |
|---|---|---|---|---|---|---|---|---|
| 000 | 0.9895 | 80248 | 1/3/0 | 19/43 | 0.9894 | 10/10 | 0.9810±0.0045 | 19.8 |
| 001 | 0.9881 | 80248 | 2/5/0 | 19/42 | 0.9833 | 10/10 | 0.9743±0.0088 | 25.1 |
| 010 | 0.9846 | 80248 | 3/5/0 | 19/42 | 0.9818 | 9/10 | 0.9765±0.0062 | 35.2 |
| 011 | 0.9797 | 70300 | 15/22/5 | 19/41 | 0.9239 | 8/10 | 0.9721±0.0083 | 39.6 |
| 100 | 0.9883 | 80248 | 2/4/0 | 19/44 | 0.9844 | 10/10 | 0.9753±0.0102 | 27.3 |
| 101 | 0.9819 | 47182 | 5/8/2 | 13/27 | 0.9658 | 10/10 | 0.9739±0.0093 | 30.0 |
| 110 | 0.9793 | 12147 | 6/10/2 | 11/25 | 0.9687 | 10/10 | 0.9769±0.0022 | 39.4 |
| 111 | 0.9794 | 67154 | 5/8/2 | 12/26 | 0.9680 | 8/10 | 0.9524±0.0717 | 52.4 |

### D. Three-arm head-to-head (deployed best-of-10 per state)

| State | Lex fid (D/2Q) | Lexi2 fid (D/2Q) | Tour fid (D/2Q) |
|---|---|---|---|
| 000 | 0.9898 (1/0) | 0.9834 (2/0) | 0.9895 (1/0) |
| 001 | 0.9901 (2/0) | 0.9819 (7/2) | 0.9881 (2/0) |
| 010 | 0.9818 (5/1) | 0.9851 (3/0) | 0.9846 (3/0) |
| 011 | 0.9801 (4/1) | 0.9887 (2/0) | 0.9797 (15/5) |
| 100 | 0.9881 (5/0) | 0.9869 (3/0) | 0.9883 (2/0) |
| 101 | 0.9895 (3/0) | 0.9820 (3/0) | 0.9819 (5/2) |
| 110 | 0.9859 (2/0) | 0.9805 (6/1) | 0.9793 (6/2) |
| 111 | 0.9814 (10/3) | 0.9876 (3/0) | 0.9794 (5/2) |


### E. Failure composition (full-100 runs)

| Arm | Converged | Fidelity fail (<0.95) | Size fail (fid≥0.95, big circuit) | Stopping-rule miss |
|---|---|---|---|---|
| $\varepsilon$-lexicase | 79 | 1 | 0 | 0 |
| Lexi2 | 55 | 14 | 9 | 2 |
| tournament | 75 | 1 | 4 | 0 |

### F. Figure inventory (paper_figures/frozen_10seed/)

fig01 fidelity by state/arm; fig02 gens-to-stop ECDF; fig03 convergence trajectories; fig04 circuit cost; fig05 hardware validation (2 arms); fig06 success heatmap; fig07 paired ε-lex vs tournament; fig08 failed trajectories (3 panels); fig09/fig10 paired/effect-size stats (2 arms); fig11 deployed circuits (24); fig12 paired ε-lex vs Lexi2; fig13 outcome composition; fig14 deployed quality; fig15 pairwise Cliff's δ forest; fig16 Lexi2 tiebreak/ε diagnostics.

### G. Configuration

10 seeds (21315, 47182, 12147, 33537, 70300, 74135, 67154, 80248, 91197, 29440), 8 states, pop 300, max 100 gens, frozen bundle, option-(a) early stopping, λ-free deployment (fidelity → transpiled 2Q → gates → depth). Lexi2: MAD ε per case per generation over the 8 output-state probabilities; size tiebreak (2Q → gates → depth) fires on 83.3% of selections on average. Software pins as in FROZEN_SWEEP_NOTES.md.
