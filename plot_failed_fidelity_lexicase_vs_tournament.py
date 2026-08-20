"""Failed-run fidelity trajectories: lexicase vs tournament (pop300).

Failed = peak fidelity_max < 0.90 (same split as the diversity analysis).
Panel 1: mean +/- std fidelity trajectory of failed runs per method.
Panel 2: ECDF of failed-run peak fidelity + crossing-fraction annotations.
"""

from __future__ import annotations

import glob

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

CONV = 0.90
OUT_PNG = "fig_failed_fidelity_lexicase_vs_tournament.png"
OUT_PDF = "fig_failed_fidelity_lexicase_vs_tournament.pdf"
DPI = 200


def load(method: str) -> list[pd.DataFrame]:
    return [pd.read_csv(f) for f in sorted(
        glob.glob(f"experiments/{method}/pop300/noise/state_*/run_*/diagnostics_*.csv"))]


def failed(runs):
    return [df for df in runs if df.fidelity_max.max() < CONV]


def traj(runs):
    rows = {}
    for df in runs:
        for _, r in df.iterrows():
            rows.setdefault(int(r.generation), []).append(r.fidelity_max)
    gens = sorted(rows)
    return pd.DataFrame({
        "gen": gens,
        "mean": [np.mean(rows[g]) for g in gens],
        "std": [np.std(rows[g]) for g in gens],
    })


def main() -> None:
    lex_f = failed(load("epsilon_lexicase"))
    tour_f = failed(load("tournament"))
    print(f"failed runs (peak < {CONV}): lexicase n={len(lex_f)}, tournament n={len(tour_f)}")

    t_l, t_t = traj(lex_f), traj(tour_f)
    for g in (0, 5, 10, 15):
        ml = t_l.loc[t_l.gen == g, "mean"].iloc[0]
        mt = t_t.loc[t_t.gen == g, "mean"].iloc[0]
        print(f"  gen {g:2d}: lex {ml:.4f} | tour {mt:.4f}")

    peaks_l = np.array([df.fidelity_max.max() for df in lex_f])
    peaks_t = np.array([df.fidelity_max.max() for df in tour_f])
    p = stats.mannwhitneyu(peaks_l, peaks_t, alternative="two-sided").pvalue
    print(f"peak fidelity: lex {peaks_l.mean():.4f} vs tour {peaks_t.mean():.4f} | MWU p={p:.4f}")

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))
    colors = {"lexicase": "#1f77b4", "tournament": "#d62728"}

    ax = axes[0]
    for method, t, color in (("lexicase", t_l, colors["lexicase"]),
                             ("tournament", t_t, colors["tournament"])):
        ax.plot(t["gen"], t["mean"], color=color, lw=2.4, label=method)
        ax.fill_between(t["gen"], t["mean"] - t["std"], t["mean"] + t["std"],
                        color=color, alpha=0.14, lw=0)
    for df, method in [(x, "lexicase") for x in lex_f] + [(x, "tournament") for x in tour_f]:
        ax.plot(df.generation, df.fidelity_max, color=colors[method], lw=0.7, alpha=0.22, zorder=0)
    ax.axhline(CONV, color="grey", ls=":", lw=1)
    ax.annotate(f"converged threshold = {CONV}", (1.5, CONV + 0.015), color="grey", fontsize=8)
    ax.axhline(0.6, color="grey", ls="--", lw=0.8)
    ax.annotate("0.6", (1.5, 0.608), color="grey", fontsize=8)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Best fidelity (failed runs)")
    ax.set_ylim(0.35, 0.92)
    ax.set_title("Fidelity trajectories of failed runs", fontsize=11)
    ax.grid(alpha=0.25, lw=0.5)
    ax.legend(fontsize=9)

    ax = axes[1]
    for method, peaks, color in (("lexicase", peaks_l, colors["lexicase"]),
                                 ("tournament", peaks_t, colors["tournament"])):
        xs = np.sort(peaks)
        ys = np.arange(1, len(xs) + 1) / len(xs)
        ax.plot(xs, ys, marker="o", ms=4, lw=1.8, color=color, label=method)
    for thr in (0.6, 0.7, 0.8):
        ax.axvline(thr, color="grey", ls="--", lw=0.8)
    fl = {thr: np.mean(peaks_l >= thr) * 100 for thr in (0.6, 0.7, 0.8)}
    ft = {thr: np.mean(peaks_t >= thr) * 100 for thr in (0.6, 0.7, 0.8)}
    txt = "\n".join([f">= {thr}: lex {fl[thr]:.0f}% | tour {ft[thr]:.0f}%" for thr in (0.6, 0.7, 0.8)])
    ax.text(0.03, 0.18, txt, transform=ax.transAxes, fontsize=9,
            bbox=dict(boxstyle="round", fc="white", ec="grey", alpha=0.9))
    ax.set_xlabel("Peak fidelity (failed runs)")
    ax.set_ylabel("Cumulative fraction")
    ax.set_title("Peak-fidelity ECDF of failed runs", fontsize=11)
    ax.grid(alpha=0.25, lw=0.5)
    ax.legend(fontsize=9)

    fig.suptitle("How failures differ: lexicase never approaches the basin (coverage); "
                 "tournament reaches 0.6-0.87 then stalls", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(OUT_PNG, dpi=DPI)
    fig.savefig(OUT_PDF)
    print(f"wrote {OUT_PNG} and {OUT_PDF}")


if __name__ == "__main__":
    main()
