#!/usr/bin/env python3
"""Unify the pairwise Cliff's delta bootstrap CIs on one seed (20260827),
so Tables 10 and 11 of the GPEM paper report identical values for the shared
epsilon-lexicase vs. tournament comparison.

Convention (same as build_stats_supplement_frozen_final.py): independent
resampling with replacement of each arm's 80 final fidelities, 10,000 draws,
percentile 2.5-97.5. Reads ONLY per_run_frozen_3arm.csv; no experiments run.
"""

import csv

import numpy as np

SEED = 20260827
N_BOOT = 10000
ARMS = ["epsilon_lexicase", "lexi2", "tournament"]


def cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
    gt = np.sum(x[:, None] > y[None, :])
    lt = np.sum(x[:, None] < y[None, :])
    return float((gt - lt) / (x.size * y.size))


def main() -> None:
    fid = {a: [] for a in ARMS}
    for r in csv.DictReader(open("per_run_frozen_3arm.csv")):
        fid.setdefault(r["arm"], []).append(float(r["fidelity"]))
    x = {a: np.array(fid[a]) for a in ARMS}
    for a, b in [("epsilon_lexicase", "lexi2"),
                 ("epsilon_lexicase", "tournament"),
                 ("lexi2", "tournament")]:
        d = cliffs_delta(x[a], x[b])
        rng = np.random.default_rng(SEED)
        boot = np.array([cliffs_delta(rng.choice(x[a], x[a].size, True),
                                      rng.choice(x[b], x[b].size, True))
                         for _ in range(N_BOOT)])
        lo, hi = np.percentile(boot, [2.5, 97.5])
        print(f"{a} vs {b}: delta={d:+.4f}  CI=[{lo:+.4f}, {hi:+.4f}]")


if __name__ == "__main__":
    main()
