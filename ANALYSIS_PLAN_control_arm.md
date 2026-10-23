Primary: task success (fid >= 0.95, gates <= 20, depth <= 15 at final generation),
Lexi² vs lexi8_random, paired by (state, seed); exact McNemar test.
Secondary: final fidelity, paired Wilcoxon signed-rank; Cliff's delta with
state-cluster bootstrap CI (10,000 resamples, seed 20260827); generations-to-stop.
Mechanism: post-case pool size and fidelity of the highest-fidelity individual by
generation, both arms.
Robustness: all fidelity comparisons repeated on exact density-matrix re-scoring.
Interpretation rule: tiebreak is called causal for the Lexi² deficit only if
lexi8_random task success is significantly higher than Lexi² (McNemar p < 0.05).

## Addendum (2026-10-23 19:36 UTC), committed before any control-arm results were inspected
Mechanism comparison, both arms: per-generation population maximum fidelity, taken
from p<target>_max in diagnostics_<state>_run<id>.csv, and post-case pool size,
from lexi2_log / lexi8_random_log. Plot mean and IQR by generation, both arms.
The v0.1 Lexi² artifacts do not record the size or target-success status of the
highest-fidelity individual; these fields are reported descriptively for
lexi8_random only and are not used for any between-arm inference.
