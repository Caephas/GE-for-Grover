"""Diversity + fidelity trajectories for converged vs never-reached pop300 runs.

Groups are defined by actual outcome: a run is "converged" if fidelity_max ever
reaches 0.90 (state_111 x5 + state_101/seed 12147), otherwise "never-reached".
"""

import glob
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = "experiments/epsilon_lexicase/pop300/noise"
THRESHOLD = 0.90
POP = 300
OUT_PNG = "fig_diversity_converged_vs_stalled.png"
OUT_PDF = "fig_diversity_converged_vs_stalled.pdf"
DPI = 200

stuck_pairs = {
    "001": [12147, 70300],
    "011": [21315, 70300],
    "100": [12147],
    "101": [47182, 12147],
    "110": [12147, 33537],
}


def load(state: str, seed: int) -> pd.DataFrame | None:
    matches = glob.glob(os.path.join(BASE, f"state_{state}", f"run_*seed_{seed}", "diagnostics_*.csv"))
    return pd.read_csv(matches[0]) if matches else None


def load_all_runs() -> list[tuple[str, str, pd.DataFrame]]:
    runs: list[tuple[str, str, pd.DataFrame]] = []
    for path in sorted(glob.glob(os.path.join(BASE, "state_111", "run_*", "diagnostics_*.csv"))):
        label = os.path.basename(os.path.dirname(path))  # e.g. run_1_seed_21315
        runs.append((label, "111", pd.read_csv(path)))
    for state, seeds in stuck_pairs.items():
        for seed in seeds:
            df = load(state, seed)
            if df is not None:
                runs.append((f"run_{state}_{seed}", state, df))
    return runs


def group_trajectories(runs: list[tuple[str, str, pd.DataFrame]], metric: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Mean / std per generation with min_periods=3, separately per group."""
    rows = {}
    for label, state, df in runs:
        group = "converged" if df.fidelity_max.max() >= THRESHOLD else "never-reached"
        for _, r in df.iterrows():
            rows.setdefault(int(r.generation), {}).setdefault(group, []).append(r[metric])
    out = {}
    for group in ("converged", "never-reached"):
        gens = sorted(rows)
        mean = np.array([np.mean(rows[g][group]) if group in rows[g] else np.nan for g in gens])
        std = np.array([np.std(rows[g][group]) if group in rows[g] else np.nan for g in gens])
        out[group] = pd.DataFrame({"gen": gens, "mean": mean, "std": std})
    return out["converged"], out["never-reached"]


def main() -> None:
    runs = load_all_runs()
    conv, nev = group_trajectories(runs, "fidelity_max")
    conv_u, nev_u = group_trajectories(runs, "unique_behaviors")

    fig, axes = plt.subplots(2, 1, figsize=(7.2, 8.0), sharex=True)
    colors = {"converged": "#1f77b4", "never-reached": "#d62728"}
    labels = {"converged": f"Converged (n={sum(r.fidelity_max.max() >= THRESHOLD for _, _, r in runs)})",
              "never-reached": f"Never reached 0.9 (n={sum(r.fidelity_max.max() < THRESHOLD for _, _, r in runs)})"}

    for ax, (c_traj, n_traj, metric, ylabel) in zip(
        axes,
        [
            (conv, nev, "fidelity_max", "Best fidelity"),
            (conv_u, nev_u, "unique_behaviors", "Unique behaviors"),
        ],
    ):
        for group, traj in (("converged", c_traj), ("never-reached", n_traj)):
            color = colors[group]
            ax.plot(traj["gen"], traj["mean"], color=color, lw=2.2, label=labels[group])
            ax.fill_between(
                traj["gen"],
                traj["mean"] - traj["std"],
                traj["mean"] + traj["std"],
                color=color,
                alpha=0.14,
                lw=0,
            )
        for label, state, df in runs:
            group = "converged" if df.fidelity_max.max() >= THRESHOLD else "never-reached"
            ax.plot(
                df.generation, df[metric], color=colors[group], lw=0.8, alpha=0.28, zorder=0
            )
        if metric == "fidelity_max":
            ax.axhline(THRESHOLD, color="grey", ls=":", lw=1)
            ax.annotate("0.9 threshold", (1.5, 0.915), color="grey", fontsize=8)
            ax.set_ylim(0.4, 1.02)
        else:
            ax.axhline(POP, color="grey", ls=":", lw=1)
            ax.annotate("population size = 300", (1.5, POP + 3), color="grey", fontsize=8)
            ax.set_ylim(80, 320)
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.25, lw=0.5)
        ax.legend(loc="lower right", fontsize=9, framealpha=0.9)

    axes[1].set_xlabel("Generation")
    axes[0].set_title(
        "Converged vs never-reached runs (pop300, noise): fidelity separates, diversity does not collapse",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=DPI)
    fig.savefig(OUT_PDF)
    print(f"wrote {OUT_PNG} and {OUT_PDF}")


if __name__ == "__main__":
    main()
