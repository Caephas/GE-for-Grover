"""Lexicase vs tournament pop300: unique-behaviors trajectories + statistics.

Reads diagnostics CSVs only. Compares mean unique_behaviors over generations
between the two selection methods (all 8 states x 5 seeds), split into
converged (peak fidelity >= 0.90) vs failed runs. Reports raw diversity,
gen-0-adjusted diversity gain, late-vs-early gain, and Mann-Whitney U tests.
Writes fig_diversity_lexicase_vs_tournament.{png,pdf}.
"""

from __future__ import annotations

import glob
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

CONV_THRESHOLD = 0.90
WINDOW = 15  # common generation window (all runs have >= 16 rows)
OUT_PNG = "fig_diversity_lexicase_vs_tournament.png"
OUT_PDF = "fig_diversity_lexicase_vs_tournament.pdf"
DPI = 200


def load(method: str) -> list[pd.DataFrame]:
    runs = []
    for f in sorted(glob.glob(f"experiments/{method}/pop300/noise/state_*/run_*/diagnostics_*.csv")):
        runs.append(pd.read_csv(f))
    return runs


def classify(runs, threshold=CONV_THRESHOLD) -> list[tuple[pd.DataFrame, str]]:
    return [(df, "converged" if df.fidelity_max.max() >= threshold else "failed") for df in runs]


def group_traj(runs, metric: str) -> dict[str, pd.DataFrame]:
    rows: dict[int, dict[str, list]] = {}
    for df, grp in runs:
        for _, r in df.iterrows():
            rows.setdefault(int(r.generation), {}).setdefault(grp, []).append(r[metric])
    out = {}
    for grp in ("converged", "failed"):
        gens = sorted(rows)
        mean = np.array([np.mean(rows[g][grp]) if grp in rows[g] else np.nan for g in gens])
        std = np.array([np.std(rows[g][grp]) if grp in rows[g] else np.nan for g in gens])
        out[grp] = pd.DataFrame({"gen": gens, "mean": mean, "std": std})
    return out


def group_traj_delta(runs) -> dict[str, pd.DataFrame]:
    """Gen-0-normalized unique behaviors: mean(u - u0) per generation."""
    rows: dict[int, dict[str, list]] = {}
    for df, grp in runs:
        u0 = df.unique_behaviors.iloc[0]
        for _, r in df.iterrows():
            rows.setdefault(int(r.generation), {}).setdefault(grp, []).append(r.unique_behaviors - u0)
    out = {}
    for grp in ("converged", "failed"):
        gens = sorted(rows)
        mean = np.array([np.mean(rows[g][grp]) if grp in rows[g] else np.nan for g in gens])
        std = np.array([np.std(rows[g][grp]) if grp in rows[g] else np.nan for g in gens])
        out[grp] = pd.DataFrame({"gen": gens, "mean": mean, "std": std})
    return out


def mwu(name, lx, tt) -> None:
    p = stats.mannwhitneyu(lx, tt, alternative="two-sided").pvalue
    print(f"{name:44s} lex {np.mean(lx):7.2f} (n={len(lx):2d}) | tour {np.mean(tt):7.2f} "
          f"(n={len(tt):2d}) | p={p:.4g}")


def stats_report(lex_c, tour_c) -> None:
    def w(df): return df[df.generation <= WINDOW]

    print("=" * 100)
    print("DIVERSITY STATISTICS (pop300, gens 0-%d unless noted)" % WINDOW)
    print("=" * 100)
    print(f"converged runs (peak fid >= {CONV_THRESHOLD}): "
          f"lexicase {sum(1 for _, g in lex_c if g == 'converged')}/40, "
          f"tournament {sum(1 for _, g in tour_c if g == 'converged')}/40")
    print("\n-- raw mean unique_behaviors --")
    mwu("all runs", [w(df).unique_behaviors.mean() for df, _ in lex_c],
                    [w(df).unique_behaviors.mean() for df, _ in tour_c])
    for grp in ("converged", "failed"):
        mwu(f"{grp} runs",
            [w(df).unique_behaviors.mean() for df, g in lex_c if g == grp],
            [w(df).unique_behaviors.mean() for df, g in tour_c if g == grp])
    print("\n-- gen0-adjusted gain (mean(0-15) - u0) --")
    mwu("all runs",
        [w(df).unique_behaviors.mean() - df.unique_behaviors.iloc[0] for df, _ in lex_c],
        [w(df).unique_behaviors.mean() - df.unique_behaviors.iloc[0] for df, _ in tour_c])
    for grp in ("converged", "failed"):
        mwu(f"{grp} runs",
            [w(df).unique_behaviors.mean() - df.unique_behaviors.iloc[0] for df, g in lex_c if g == grp],
            [w(df).unique_behaviors.mean() - df.unique_behaviors.iloc[0] for df, g in tour_c if g == grp])
    print("\n-- late-minus-early gain (last5 - first5) --")

    def lme(df): return df.unique_behaviors.tail(5).mean() - df.unique_behaviors.head(5).mean()
    mwu("all runs", [lme(df) for df, _ in lex_c], [lme(df) for df, _ in tour_c])
    for grp in ("converged", "failed"):
        mwu(f"{grp} runs",
            [lme(df) for df, g in lex_c if g == grp],
            [lme(df) for df, g in tour_c if g == grp])
    print("\n-- gen-0 --")
    mwu("all runs",
        [df.unique_behaviors.iloc[0] for df, _ in lex_c],
        [df.unique_behaviors.iloc[0] for df, _ in tour_c])


def main() -> None:
    lex, tour = load("epsilon_lexicase"), load("tournament")
    lex_c, tour_c = classify(lex), classify(tour)
    stats_report(lex_c, tour_c)

    colors = {"lexicase": "#1f77b4", "tournament": "#d62728"}
    groups = [
        ("lexicase", "converged"), ("lexicase", "failed"),
        ("tournament", "converged"), ("tournament", "failed"),
    ]
    traj = {
        ("lexicase", "converged"): group_traj(lex_c, "unique_behaviors")["converged"],
        ("lexicase", "failed"): group_traj(lex_c, "unique_behaviors")["failed"],
        ("tournament", "converged"): group_traj(tour_c, "unique_behaviors")["converged"],
        ("tournament", "failed"): group_traj(tour_c, "unique_behaviors")["failed"],
    }
    fid = {
        ("lexicase", "converged"): group_traj(lex_c, "fidelity_max")["converged"],
        ("lexicase", "failed"): group_traj(lex_c, "fidelity_max")["failed"],
        ("tournament", "converged"): group_traj(tour_c, "fidelity_max")["converged"],
        ("tournament", "failed"): group_traj(tour_c, "fidelity_max")["failed"],
    }
    delta = group_traj_delta(lex_c), group_traj_delta(tour_c)
    delta_traj = {
        ("lexicase", "converged"): delta[0]["converged"],
        ("lexicase", "failed"): delta[0]["failed"],
        ("tournament", "converged"): delta[1]["converged"],
        ("tournament", "failed"): delta[1]["failed"],
    }

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.8), sharex=True)
    counts = {}
    for method, runs in (("lexicase", lex_c), ("tournament", tour_c)):
        for grp in ("converged", "failed"):
            counts[(method, grp)] = sum(1 for _, g in runs if g == grp)

    for ax, (data, ylabel, title) in zip(
        axes,
        [
            (fid, "Best fidelity", "Best fidelity"),
            (traj, "Unique behaviors (pop 300)", "Unique behaviors (raw)"),
            (delta_traj, "Δ unique behaviors vs gen 0", "Unique behaviors (gen-0 normalized)"),
        ],
    ):
        for method, grp in groups:
            t = data[(method, grp)]
            color = colors[method]
            ls = "-" if grp == "converged" else "--"
            ax.plot(t["gen"], t["mean"], color=color, ls=ls, lw=2.2,
                    label=f"{method} {grp} (n={counts[(method, grp)]})")
            ax.fill_between(t["gen"], t["mean"] - t["std"], t["mean"] + t["std"],
                            color=color, alpha=0.10, lw=0)
        ax.set_ylabel(ylabel)
        ax.set_xlabel("Generation")
        ax.grid(alpha=0.25, lw=0.5)
        ax.axhline(0, color="grey", lw=0.8, ls=":")
        ax.legend(fontsize=8.5, framealpha=0.9)
        ax.set_title(title, fontsize=11)
    axes[0].set_ylim(0.3, 1.02)
    axes[1].set_ylim(80, 320)
    fig.suptitle("Lexicase vs tournament, pop300, noise (8 states x 5 seeds): "
                 "fidelity separates the methods; diversity does not collapse in either",
                 fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(OUT_PNG, dpi=DPI)
    fig.savefig(OUT_PDF)
    print(f"\nwrote {OUT_PNG} and {OUT_PDF}")


if __name__ == "__main__":
    main()
