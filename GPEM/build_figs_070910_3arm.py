#!/usr/bin/env python3
"""Regenerate fig07/fig09/fig10 as three-arm figures (frozen 10-seed batch).

Reads ONLY completed artifacts:
  - experiments_frozen_10seed/{epsilon_lexicase,tournament}/pop300/noise/...
  - experiments_frozen_10seed_lexi2/lexi2/pop300/noise/...
No experiments are run. run_result two_qubit_gates are the corrected
(transpiled) counts; these figures use final fidelity only.

Writes (PNG + PDF):
  - paper_figures/frozen_10seed/fig07_paired_scatter.pdf        (3 panels)
  - paper_figures/frozen_10seed/fig09_paired_diff_histogram.pdf (3 panels)
  - paper_figures/frozen_10seed/fig10_cliffs_delta.pdf          (3 panels)
"""

from __future__ import annotations

import glob
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

ARMS = ["epsilon_lexicase", "lexi2", "tournament"]
ARM_LABEL = {"epsilon_lexicase": r"$\varepsilon$-lexicase", "lexi2": "Lexi2",
             "tournament": "tournament"}
ROOTS = {"epsilon_lexicase": "experiments_frozen_10seed",
         "tournament": "experiments_frozen_10seed",
         "lexi2": "experiments_frozen_10seed_lexi2"}
STATES = ["000", "001", "010", "011", "100", "101", "110", "111"]
SEEDS = [21315, 47182, 12147, 33537, 70300, 74135, 67154, 80248, 91197, 29440]
FIG_DIR = "paper_figures/frozen_10seed"
RNG_SEED = 20260902
PAIRS = [("epsilon_lexicase", "tournament"),
         ("epsilon_lexicase", "lexi2"),
         ("lexi2", "tournament")]


def load_results() -> dict:
    out = {}
    for arm in ARMS:
        for st in STATES:
            d = {}
            for f in glob.glob(os.path.join(
                    ROOTS[arm], arm, "pop300", "noise", f"state_{st}",
                    "run_*", "run_result_*.json")):
                r = json.load(open(f))
                d[r["seed"]] = r
            out[(arm, st)] = d
    return out


def cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
    gt = np.sum(x[:, None] > y[None, :])
    lt = np.sum(x[:, None] < y[None, :])
    return float((gt - lt) / (x.size * y.size))


def cliffs_ci(x: np.ndarray, y: np.ndarray, n_boot: int = 10000):
    rng = np.random.default_rng(RNG_SEED)
    v = np.array([cliffs_delta(rng.choice(x, x.size, True),
                               rng.choice(y, y.size, True))
                  for _ in range(n_boot)])
    return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def median_ci(diffs: np.ndarray, n_boot: int = 10000):
    rng = np.random.default_rng(RNG_SEED)
    v = np.array([np.median(rng.choice(diffs, diffs.size, True))
                  for _ in range(n_boot)])
    return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def _save(fig, name):
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(os.path.join(FIG_DIR, name + ".png"), dpi=300,
                bbox_inches="tight")
    fig.savefig(os.path.join(FIG_DIR, name + ".pdf"), bbox_inches="tight")
    plt.close(fig)
    print("figure:", name)


def _style():
    plt.rcParams.update({
        "font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10,
        "savefig.dpi": 300, "savefig.bbox": "tight",
        "axes.spines.top": False, "axes.spines.right": False,
    })


def _fid_arrays(results, arm):
    return {st: np.array([results[(arm, st)][s]["fidelity"] for s in SEEDS])
            for st in STATES}


def fig07_paired_scatter(results):
    fig, axes = plt.subplots(1, 3, figsize=(18.0, 5.6))
    cmap = plt.get_cmap("viridis")
    colors = cmap(np.linspace(0.08, 0.92, len(STATES)))
    for ax, (a, b) in zip(axes, PAIRS):
        fa, fb = _fid_arrays(results, a), _fid_arrays(results, b)
        wins = losses = ties = 0
        for j, st in enumerate(STATES):
            xs, ys = fa[st], fb[st]
            ax.scatter(xs, ys, s=26, color=colors[j], alpha=0.85,
                       edgecolors="none", label=f"$|{st}\\rangle$")
            wins += int(np.sum(xs > ys))
            losses += int(np.sum(xs < ys))
            ties += int(np.sum(xs == ys))
        lim = (0.42, 1.0)
        ax.plot(lim, lim, "k--", lw=1)
        ax.set_xlim(*lim)
        ax.set_ylim(*lim)
        ax.set_xlabel(f"{ARM_LABEL[a]} final fidelity")
        ax.set_ylabel(f"{ARM_LABEL[b]} final fidelity")
        ax.legend(frameon=False, fontsize=8, ncol=2, loc="lower right")
        ax.text(0.02, 0.06,
                f"{ARM_LABEL[a]} higher: {wins}\n"
                f"{ARM_LABEL[b]} higher: {losses}\n"
                f"ties: {ties}",
                transform=ax.transAxes, ha="left", va="bottom", fontsize=8,
                bbox=dict(boxstyle="round,pad=0.3", fc="white",
                          ec="gray", lw=0.6))
        ax.set_title(f"{ARM_LABEL[a]} vs {ARM_LABEL[b]} (80 pairs)")
    fig.suptitle("Paired final fidelity, all arm pairs (shared gen-0 init)",
                 y=1.02, fontsize=12)
    _save(fig, "fig07_paired_scatter")


def fig09_paired_diff_histogram(results):
    fig, axes = plt.subplots(1, 3, figsize=(18.0, 4.4))
    for ax, (a, b) in zip(axes, PAIRS):
        fa, fb = _fid_arrays(results, a), _fid_arrays(results, b)
        diffs = np.concatenate([fa[st] - fb[st] for st in STATES])
        wins = int(np.sum(diffs > 0))
        losses = int(np.sum(diffs < 0))
        ties = int(np.sum(diffs == 0))
        med = float(np.median(diffs))
        lo, hi = median_ci(diffs)
        ax.hist(diffs, bins=36, color="#6b6b6b", alpha=0.75,
                edgecolor="white", lw=0.4)
        ax.axvline(0, color="black", ls="--", lw=1)
        ax.axvspan(lo, hi, color="#0b5394", alpha=0.12)
        ax.axvline(med, color="#0b5394", lw=1.8)
        ax.text(0.99, 0.95, f"median {med:+.4f}\n95% CI [{lo:+.4f}, {hi:+.4f}]",
                transform=ax.transAxes, ha="right", va="top", fontsize=8,
                bbox=dict(boxstyle="round,pad=0.3", fc="white",
                          ec="#0b5394", lw=0.8))
        ax.text(0.01, 0.95,
                f"{ARM_LABEL[a]} higher {wins}  |  "
                f"{ARM_LABEL[b]} higher {losses}  |  ties {ties}",
                transform=ax.transAxes, ha="left", va="top", fontsize=8)
        ax.set_xlabel(f"{ARM_LABEL[a]} $-$ {ARM_LABEL[b]} final fidelity "
                      "(80 paired runs)")
        ax.set_ylabel("pairs")
        ax.set_title(f"{ARM_LABEL[a]} vs {ARM_LABEL[b]}")
    fig.suptitle("Paired final-fidelity differences with median 95% CI "
                 "(bootstrap)", y=1.04, fontsize=12)
    _save(fig, "fig09_paired_diff_histogram")


def fig10_cliffs_delta(results):
    fig, axes = plt.subplots(1, 3, figsize=(18.0, 4.6), sharey=True)
    for ax, (a, b) in zip(axes, PAIRS):
        fa = np.concatenate([_fid_arrays(results, a)[st] for st in STATES])
        fb = np.concatenate([_fid_arrays(results, b)[st] for st in STATES])
        d = cliffs_delta(fa, fb)
        lo, hi = cliffs_ci(fa, fb)
        _, p = stats.mannwhitneyu(fa, fb, alternative="two-sided")
        rng = np.random.default_rng(RNG_SEED)
        boot = np.array([cliffs_delta(rng.choice(fa, fa.size, True),
                                      rng.choice(fb, fb.size, True))
                         for _ in range(10000)])
        ax.hist(boot, bins=80, color="#6b6b6b", alpha=0.7,
                edgecolor="white", lw=0.3)
        ax.axvline(d, color="#0b5394", lw=1.8,
                   label=f"observed $\\delta$ = {d:+.3f}")
        ax.axvline(lo, color="#b45f06", ls="--", lw=1.1)
        ax.axvline(hi, color="#b45f06", ls="--", lw=1.1)
        ax.set_xlabel("Cliff's $\\delta$ (bootstrap resamples)")
        ax.set_ylabel("count")
        ax.legend(frameon=False, fontsize=8)
        ax.set_title(f"{ARM_LABEL[a]} vs {ARM_LABEL[b]}\n"
                     f"MWU p = {p:.4f}; 95% CI [{lo:+.3f}, {hi:+.3f}]",
                     fontsize=10)
    fig.suptitle("Cliff's $\\delta$ bootstrap distributions, all arm pairs "
                 "(10,000 resamples)", y=1.04, fontsize=12)
    _save(fig, "fig10_cliffs_delta")


def main():
    _style()
    results = load_results()
    fig07_paired_scatter(results)
    fig09_paired_diff_histogram(results)
    fig10_cliffs_delta(results)


if __name__ == "__main__":
    main()
