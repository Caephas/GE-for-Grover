# Reconstruction and control-failure audit

No evolution or hardware job was run. This audit reads stored run artifacts and performs local transpilation only.

## 1. Task A reconstruction path

The archived Task A implementation built each phenotype, instantiated a fresh `generate_preset_pass_manager(target=frozen_target, optimization_level=3, seed_transpiler=run_seed)`, and retried up to eight times, accepting the first circuit whose gate count, depth, and 2Q count matched the stored run. It processed 240 champions and its archived output recorded **9 mismatches**, including the same eight Lexi2 runs identified here. Therefore Task A did not reconstruct all 240 champions with matching circuit metrics.

| State | Seed | Stored G/D/2Q | Reconstructed G/D/2Q | Matched in 8 attempts |
|---|---:|---:|---:|---|
| 000 | 80248 | 68/47/11 | 22/11/3 | False |
| 001 | 70300 | 62/42/10 | 23/15/4 | False |
| 011 | 70300 | 66/45/10 | 39/26/7 | False |
| 101 | 47182 | 65/44/12 | 65/45/14 | False |
| 101 | 12147 | 63/43/10 | 29/16/3 | False |
| 110 | 70300 | 62/43/10 | 56/40/12 | False |
| 111 | 74135 | 72/48/11 | 63/39/10 | False |
| 111 | 67154 | 52/34/9 | 78/52/14 | False |

All eight Lexi2 runs remain unmatched under the Task A retry path. The first task-A attempt already fixes the result because level-3 transpilation with a fixed seed is deterministic in this environment.

## 2. Determinism test

Three unmatched circuits were transpiled five times in one process and five times in fresh interpreter processes with the same fixed seed.

| State | Seed | G/D/2Q | Unique same-process circuits | Unique fresh-process circuits |
|---|---:|---:|---:|---:|
| 000 | 80248 | 22/11/3 | 1 | 1 |
| 001 | 70300 | 23/15/4 | 1 | 1 |
| 111 | 67154 | 78/52/14 | 1 | 1 |

Each circuit produced one unique metric/layout/operation-signature across all five repeats in each mode. The stored metrics therefore came from a transpilation context that the saved phenotype plus run seed does not reproduce; repeating the same fixed-seed call does not recover it.

# EXPLORATORY: control-arm failure diagnostics

There are 28 control task failures. 2 had at least one individual that met all three targets in some generation while the final scalar-HOF champion did not:

| State | Seed | First target-meeting generation |
|---|---|---|
| 011 | 91197 | 0 |
| 111 | 67154 | 42 |

Final-generation population and champion details:

| State | Seed | Final gen | Max-fid ind. fid | Max-fid ind. G | Max-fid ind. D | Max-fid ind. 2Q | Target ever | First target gen | Champion fid | Champion G | Champion D | Champion 2Q |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 000 | 47182 | 99 | 0.9725 | 33 | 19 | 6 | False |  | 0.9722 | 29 | 15 | 6 |
| 000 | 70300 | 99 | 0.9516 | 65 | 44 | 13 | False |  | 0.4948 | 27 | 16 | 5 |
| 000 | 74135 | 99 | 0.9696 | 41 | 23 | 6 | False |  | 0.4940 | 7 | 4 | 0 |
| 000 | 80248 | 99 | 0.9107 | 145 | 109 | 29 | False |  | 0.5290 | 72 | 49 | 13 |
| 000 | 91197 | 99 | 0.9766 | 22 | 14 | 5 | False |  | 0.9766 | 22 | 14 | 5 |
| 000 | 29440 | 99 | 0.9552 | 25 | 14 | 4 | False |  | 0.9552 | 25 | 14 | 4 |
| 001 | 12147 | 99 | 0.9757 | 26 | 15 | 5 | False |  | 0.9786 | 21 | 14 | 4 |
| 001 | 67154 | 99 | 0.9773 | 26 | 16 | 5 | False |  | 0.9750 | 23 | 13 | 5 |
| 001 | 80248 | 99 | 0.9055 | 95 | 61 | 16 | False |  | 0.4900 | 32 | 19 | 6 |
| 001 | 29440 | 99 | 0.9343 | 105 | 70 | 18 | False |  | 0.4885 | 21 | 13 | 5 |
| 010 | 74135 | 99 | 0.9662 | 43 | 22 | 7 | False |  | 0.9657 | 35 | 22 | 8 |
| 010 | 29440 | 99 | 0.9685 | 30 | 19 | 7 | False |  | 0.9704 | 29 | 18 | 7 |
| 011 | 91197 | 99 | 0.9745 | 23 | 12 | 5 | True | 0 | 0.9757 | 22 | 12 | 5 |
| 011 | 29440 | 99 | 0.9684 | 39 | 21 | 7 | False |  | 0.9713 | 31 | 16 | 6 |
| 100 | 80248 | 99 | 0.9740 | 25 | 16 | 5 | False |  | 0.9754 | 24 | 15 | 5 |
| 100 | 29440 | 99 | 0.9716 | 34 | 18 | 6 | False |  | 0.9707 | 31 | 16 | 6 |
| 101 | 47182 | 99 | 0.8917 | 101 | 67 | 18 | False |  | 0.6625 | 59 | 36 | 8 |
| 110 | 21315 | 99 | 0.9752 | 25 | 16 | 5 | False |  | 0.9774 | 24 | 16 | 5 |
| 110 | 70300 | 99 | 0.8666 | 140 | 88 | 23 | False |  | 0.4839 | 51 | 30 | 8 |
| 110 | 74135 | 99 | 0.8342 | 112 | 81 | 21 | False |  | 0.7621 | 70 | 46 | 11 |
| 110 | 67154 | 99 | 0.7475 | 222 | 156 | 39 | False |  | 0.5271 | 64 | 44 | 12 |
| 110 | 29440 | 99 | 0.9585 | 52 | 31 | 10 | False |  | 0.9670 | 43 | 25 | 8 |
| 111 | 47182 | 99 | 0.9309 | 107 | 72 | 19 | False |  | 0.5428 | 54 | 36 | 8 |
| 111 | 70300 | 99 | 0.9506 | 60 | 39 | 9 | False |  | 0.4800 | 63 | 44 | 13 |
| 111 | 67154 | 99 | 0.9740 | 25 | 15 | 5 | True | 42 | 0.9758 | 22 | 12 | 4 |
| 111 | 80248 | 99 | 0.8971 | 104 | 69 | 16 | False |  | 0.7610 | 70 | 46 | 10 |
| 111 | 91197 | 99 | 0.9753 | 25 | 16 | 5 | False |  | 0.9773 | 23 | 13 | 5 |
| 111 | 29440 | 99 | 0.9724 | 28 | 16 | 5 | False |  | 0.9766 | 24 | 14 | 5 |

The complete values are also in `control_failure_population_diagnostics.csv`.
