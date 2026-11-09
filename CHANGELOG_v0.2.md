# v0.2

This release extends the frozen three-arm Grover-circuit study with the
pre-registered `lexi8_random` control arm and the completed follow-up
provenance, correction, and reporting work.

## Added

- Added the `lexi8_random` control arm: the same eight output-probability
  epsilon-lexicase cases as Lexi2, with uniform random selection when more than
  one candidate survives, and no size tiebreak.
- Added the pre-registered control-arm analysis plan and its committed
  addendum, including the mechanism comparison for population maximum fidelity
  and post-case survivor-pool size.
- Added the corrected Task A exact-fidelity rescoring script and per-run CSV
  exports. The calculation injects the target-specific Grover oracle, uses the
  frozen transpilation target and noise model, applies density-matrix
  evolution, and includes frozen readout confusion without shot sampling.
- Added `task_a_exact_per_run.csv` with all 240 v0.1 champions and
  `control_arm_per_run.csv` with all 160 Lexi2 and `lexi8_random` runs.
- Added the stored-ISA hardware submission path. Hardware jobs load and verify
  the persisted scored QPY circuit rather than re-transpiling at submission.

## Corrections

- Corrected tournament `|111>`, seed `91197` from the logged 2Q value of 3
  (`gate_ops.cx`) to 10. This is verified by an oracle-injected reconstruction
  matching the logged 68 gates and depth 45; the reconstructed circuit has
  `sx=28`, `rz=27`, `cz=10`, and `measure=3`. The provenance note is:
  `two_qubit_gates corrected from logged 3 (gate_ops.cx) to 10, verified by
  oracle-injected reconstruction matching logged gates and depth`.
- Fixed floating-point boundary ties in permutation comparisons by using
  `>= abs(observed) - 1e-12`. The exact state-block permutation now counts
  16/256 assignments, giving `p = 0.0625`.
- Corrected the stats supplement's 2Q comparison summary to use the computed
  count instead of stale hardcoded text. The current count of pairs with
  tournament 2Q at least two gates above epsilon-lexicase is 22/80.
