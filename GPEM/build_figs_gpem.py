#!/usr/bin/env python3
"""Regenerate the GPEM paper figures to match the current manuscript text.

This script only reads completed artifacts; no experiments are run and no
result is recomputed. It replots the figures that are included by
``gpem_paper/main.tex`` with:

  * the paper's swept terminology (method, Lexi^2, fixed, invocation rate,
    re-selection, small/compact, per-state comparison, no-lambda);
  * a canvas sized to the final printed width so in-figure text prints at
    >= 8 pt instead of being shrunk from a 10-26 in canvas;
  * no figure-level title when the LaTeX caption already states it.

Outputs are written (PNG + vector PDF) to ``paper_figures/frozen_10seed/`` and
the PDFs are copied to ``gpem_paper/figures/`` under the same file names, so
the existing ``\includegraphics`` calls keep resolving.

Data sources (read-only):
  experiments_frozen_10seed/{epsilon_lexicase,tournament}/pop300/noise/...
  experiments_frozen_10seed_lexi2/lexi2/pop300/noise/...
  logs_hardware_session_2026-09-02/*.json
  noise/frozen_env_ibm_fez_2026-08-20.pkl        (transpile target only)
  lexi2_tiebreak_firerate_bygen.csv
  survivor_pool_lexi2_bygen.csv
"""

from __future__ import annotations

import csv
import glob
import json
import os
import pickle
import shutil
import statistics
from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister, transpile

# --------------------------------------------------------------------------- #
# Shared configuration
# --------------------------------------------------------------------------- #
METHODS = ["epsilon_lexicase", "lexi2", "tournament"]
METHOD_LABEL = {
    "epsilon_lexicase": r"$\varepsilon$-lexicase",
    "lexi2": r"Lexi$^2$",
    "tournament": "tournament",
}
METHOD_SHORT = {
    "epsilon_lexicase": r"$\varepsilon$-lexicase",
    "lexi2": r"Lexi$^2$",
    "tournament": "tournament",
}
METHOD_COLOR = {
    "epsilon_lexicase": "#0b5394",
    "lexi2": "#2e7d32",
    "tournament": "#b45f06",
}
ROOTS = {
    "epsilon_lexicase": "experiments_frozen_10seed",
    "tournament": "experiments_frozen_10seed",
    "lexi2": "experiments_frozen_10seed_lexi2",
}
STATES = ["000", "001", "010", "011", "100", "101", "110", "111"]
SEEDS = [21315, 47182, 12147, 33537, 70300, 74135, 67154, 80248, 91197, 29440]
PAIRS = [
    ("epsilon_lexicase", "tournament"),
    ("epsilon_lexicase", "lexi2"),
    ("lexi2", "tournament"),
]

BUNDLE = "noise/frozen_env_ibm_fez_2026-08-20.pkl"
SESSION_DIR = "logs_hardware_session_2026-09-02"
FIG_DIR = "paper_figures/frozen_10seed"
PAPER_FIG_DIR = "gpem_paper/figures"
RNG_SEED = 20260902

# \textwidth of the compiled manuscript (372.0pt = 5.167in, measured from the
# build log). Printing a canvas of this width at \textwidth is a 1:1 mapping.
TEXTWIDTH_IN = 372.0 / 72.0


def _mm(n: float) -> float:
    """Printed width in inches for a factor n of \textwidth."""
    return round(TEXTWIDTH_IN * n, 3)


def _style() -> None:
    plt.rcParams.update({
        "font.size": 8,
        "axes.titlesize": 8.5,
        "axes.labelsize": 8,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "savefig.dpi": 300,
        "savefig.bbox": None,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def _save(fig, name: str) -> None:
    os.makedirs(FIG_DIR, exist_ok=True)
    os.makedirs(PAPER_FIG_DIR, exist_ok=True)
    pdf = os.path.join(FIG_DIR, name + ".pdf")
    fig.savefig(pdf)
    fig.savefig(os.path.join(FIG_DIR, name + ".png"), dpi=300)
    shutil.copy(pdf, os.path.join(PAPER_FIG_DIR, name + ".pdf"))
    plt.close(fig)
    print("wrote", pdf, "->", os.path.join(PAPER_FIG_DIR, name + ".pdf"))


# --------------------------------------------------------------------------- #
# Data loading (unchanged logic from the original builders)
# --------------------------------------------------------------------------- #
def arm_root(arm: str, state: str) -> str:
    return os.path.join(ROOTS[arm], arm, "pop300", "noise", f"state_{state}")


def load_results() -> dict:
    out = {}
    for arm in METHODS:
        for st in STATES:
            d = {}
            for f in glob.glob(os.path.join(arm_root(arm, st), "run_*",
                                            "run_result_*.json")):
                r = json.load(open(f))
                d[r["seed"]] = r
            out[(arm, st)] = d
    return out


def load_deployed() -> dict:
    out = {}
    for arm in METHODS:
        for st in STATES:
            out[(arm, st)] = json.load(
                open(os.path.join(arm_root(arm, st), "deployed_best.json")))
    return out


def load_matched_hw() -> dict:
    out = {}
    for f in glob.glob(os.path.join(SESSION_DIR, "*.json")):
        d = json.load(open(f))
        if d.get("circuit_kind") != "deployed":
            continue
        out[(d["arm"], d["target_state"])] = d
    assert len(out) == 24, f"expected 24 matched-session results, got {len(out)}"
    return out


def stop_class(r: dict) -> str:
    return ("full" if r["stop_reason"].startswith("completed_all_generations")
            else "converged")


def classify_full(r: dict) -> str:
    if r["fidelity"] < 0.95:
        return "fidelity_fail"
    if r["gate_count"] > 20 or r["depth"] > 15:
        return "size_fail"
    return "stopping_miss"


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


def trajectory(arm: str, st: str):
    """Per-generation best-in-population fidelity for one run (as a list)."""
    diag_col = f"p{st}_max" if arm == "lexi2" else "fidelity_max"
    for s in SEEDS:
        fs = glob.glob(os.path.join(arm_root(arm, st), f"run_*_seed_{s}",
                                    f"diagnostics_{st}_run*.csv"))
        if not fs:
            continue
        rows = list(csv.DictReader(open(fs[0])))
        vals = [float(r[diag_col]) for r in rows if r.get(diag_col)]
        if vals:
            yield vals


def read_csv(path: str) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #
def fig01_fidelity(results: dict) -> None:
    fig, ax = plt.subplots(figsize=(_mm(1.0), 3.5), layout="constrained")
    x = np.arange(len(STATES))
    n = len(METHODS)
    w = 0.74 / n
    for i, method in enumerate(METHODS):
        off = (i - (n - 1) / 2) * w
        data = [[results[(method, st)][s]["fidelity"] for s in SEEDS]
                for st in STATES]
        bp = ax.boxplot(data, positions=x + off, widths=w * 0.85,
                        patch_artist=True, showfliers=False,
                        medianprops=dict(color="white"))
        for patch in bp["boxes"]:
            patch.set_facecolor(METHOD_COLOR[method])
            patch.set_alpha(0.72)
        for j in range(len(STATES)):
            vals = data[j]
            ax.scatter(np.full(len(vals), x[j] + off)
                       + np.random.default_rng(j).uniform(-0.04, 0.04, len(vals)),
                       vals, s=4, color=METHOD_COLOR[method], alpha=0.55)
    ax.axhline(0.95, color="gray", ls="--", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"$|{st}\\rangle$" for st in STATES])
    ax.set_ylabel("final simulated fidelity")
    ax.set_ylim(0.40, 1.02)
    handles = [plt.Line2D([], [], color=METHOD_COLOR[m], marker="s", ls="",
                          label=METHOD_LABEL[m]) for m in METHODS]
    ax.legend(handles=handles, frameon=False, loc="lower left", ncol=3)
    _save(fig, "fig01_fidelity_by_arm_state")


def fig02_gens(results: dict) -> None:
    fig, ax = plt.subplots(figsize=(_mm(0.85), 3.0), layout="constrained")
    for method in METHODS:
        runs = [r for st in STATES for r in results[(method, st)].values()]
        gens = sorted(r.get("early_stopped_gen") or 100 for r in runs)
        y = np.arange(1, len(gens) + 1) / len(gens)
        ax.step(gens, y, where="post", color=METHOD_COLOR[method],
                label=METHOD_LABEL[method], lw=1.5)
    ax.set_xlabel("generations to stop (full-100 counted at 100)")
    ax.set_ylabel("ECDF over runs")
    ax.set_xlim(0, 102)
    ax.legend(frameon=False, loc="lower right")
    _save(fig, "fig02_generations_to_stop")


def fig03_trajectories() -> None:
    fig, ax = plt.subplots(figsize=(_mm(1.0), 3.5), layout="constrained")
    for method in METHODS:
        series = []
        for st in STATES:
            for vals in trajectory(method, st):
                series.append(np.pad(vals, (0, 100 - len(vals)),
                                     constant_values=vals[-1])[:100])
        assert series, f"no trajectories found for {method}"
        m = np.mean(series, axis=0)
        sd = np.std(series, axis=0)
        g = np.arange(len(m))
        ax.plot(g, m, color=METHOD_COLOR[method], lw=1.5,
                label=METHOD_LABEL[method])
        ax.fill_between(g, m - sd, m + sd, color=METHOD_COLOR[method],
                        alpha=0.14)
        print(f"  fig03 {method}: {len(series)} runs")
    ax.set_xlabel("generation")
    ax.set_ylabel("best fidelity in population")
    ax.axhline(0.95, color="gray", ls="--", lw=0.8)
    ax.legend(frameon=False, loc="lower right")
    _save(fig, "fig03_convergence_trajectories")


def fig05_hardware(deployed: dict, hw: dict) -> None:
    fig, ax = plt.subplots(figsize=(_mm(0.72), 3.5), layout="constrained")
    lim = (0.90, 1.0)
    # Only clear outliers are annotated: the main high-fidelity cluster
    # overlaps badly at print width.
    outlier_offsets = {
        ("lexi2", "101"): (7, 3),
        ("epsilon_lexicase", "111"): (-10, 7),
        ("lexi2", "011"): (8, 2),
        ("lexi2", "000"): (-31, -1),
        ("tournament", "011"): (-35, -6),
    }
    labeled = 0
    for method in METHODS:
        xs, ys, sts = [], [], []
        for st in STATES:
            xs.append(deployed[(method, st)]["fidelity"])
            ys.append(hw[(method, st)]["p_marked_hw"])
            sts.append(st)
        ax.scatter(xs, ys, s=26, color=METHOD_COLOR[method],
                   label=METHOD_LABEL[method], alpha=0.9,
                   edgecolors="white", lw=0.4)
        for st, xv, yv in zip(sts, xs, ys):
            if (method, st) in outlier_offsets:
                ax.annotate(f"$|{st}\\rangle$", (xv, yv),
                            textcoords="offset points",
                            xytext=outlier_offsets[(method, st)],
                            fontsize=8, color=METHOD_COLOR[method])
                labeled += 1
    ax.plot(lim, lim, "k--", lw=1)
    ax.set_xlim(*lim)
    ax.set_ylim(0.94, 1.0)
    ax.set_xlabel("deployed simulated fidelity (fixed target)")
    ax.set_ylabel("hardware p(marked), ibm_fez, 10k shots")
    ax.legend(frameon=False, loc="upper left")
    print(f"  fig05: labeled {labeled} outlier states")
    _save(fig, "fig05_hardware_validation")


def fig06_success(results: dict) -> None:
    fig, ax = plt.subplots(figsize=(_mm(0.9), 3.1), layout="constrained")
    M = np.array([[sum(1 for r in results[(m, st)].values()
                       if stop_class(r) == "converged") for st in STATES]
                  for m in METHODS])
    im = ax.imshow(M, cmap="YlGnBu", vmin=0, vmax=10, aspect="auto")
    ax.set_xticks(range(len(STATES)))
    ax.set_xticklabels([f"$|{st}\\rangle$" for st in STATES])
    ax.set_yticks(range(len(METHODS)))
    ax.set_yticklabels([METHOD_LABEL[m] for m in METHODS])
    for i in range(len(METHODS)):
        for j in range(len(STATES)):
            ax.text(j, i, f"{M[i, j]}/10", ha="center", va="center",
                    fontsize=8, color="black" if M[i, j] < 9 else "white")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="converged runs")
    _save(fig, "fig06_success_heatmap")


def fig07_paired_scatter(results: dict) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(_mm(1.0), 3.1),
                             layout="constrained")
    cmap = plt.get_cmap("viridis")
    colors = cmap(np.linspace(0.08, 0.92, len(STATES)))
    handles = []
    for ax, (a, b) in zip(axes, PAIRS):
        fa = {st: np.array([results[(a, st)][s]["fidelity"] for s in SEEDS])
              for st in STATES}
        fb = {st: np.array([results[(b, st)][s]["fidelity"] for s in SEEDS])
              for st in STATES}
        wins = losses = ties = 0
        for j, st in enumerate(STATES):
            xs, ys = fa[st], fb[st]
            sc = ax.scatter(xs, ys, s=12, color=colors[j], alpha=0.85,
                            edgecolors="none")
            if len(handles) < len(STATES):
                handles.append(sc)
            wins += int(np.sum(xs > ys))
            losses += int(np.sum(xs < ys))
            ties += int(np.sum(xs == ys))
        lim = (0.42, 1.0)
        ax.plot(lim, lim, "k--", lw=0.8)
        ax.set_xlim(*lim)
        ax.set_ylim(*lim)
        ax.set_xlabel(f"{METHOD_LABEL[a]} final fidelity")
        ax.set_ylabel(f"{METHOD_LABEL[b]} final fidelity")
        ax.set_title(f"{METHOD_LABEL[a]} vs {METHOD_LABEL[b]}")
        ax.text(0.03, 0.05,
                f"{METHOD_LABEL[a]}: {wins}\n{METHOD_LABEL[b]}: {losses}\n"
                f"ties: {ties}",
                transform=ax.transAxes, ha="left", va="bottom", fontsize=8,
                bbox=dict(boxstyle="round,pad=0.25", fc="white",
                          ec="gray", lw=0.5))
    fig.legend(handles, [f"$|{st}\\rangle$" for st in STATES],
               loc="outside lower center", ncol=8, frameon=False, fontsize=8,
               handletextpad=0.2, columnspacing=0.8)
    _save(fig, "fig07_paired_scatter")


def fig10_cliffs_delta(results: dict) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(_mm(1.0), 3.1), sharey=True,
                             layout="constrained")
    for ax, (a, b) in zip(axes, PAIRS):
        fa = np.concatenate([np.array([results[(a, st)][s]["fidelity"]
                                       for s in SEEDS]) for st in STATES])
        fb = np.concatenate([np.array([results[(b, st)][s]["fidelity"]
                                       for s in SEEDS]) for st in STATES])
        d = cliffs_delta(fa, fb)
        lo, hi = cliffs_ci(fa, fb)
        _, p = stats.mannwhitneyu(fa, fb, alternative="two-sided")
        rng = np.random.default_rng(RNG_SEED)
        boot = np.array([cliffs_delta(rng.choice(fa, fa.size, True),
                                      rng.choice(fb, fb.size, True))
                         for _ in range(10000)])
        ax.hist(boot, bins=80, color="#6b6b6b", alpha=0.7,
                edgecolor="white", lw=0.3)
        ax.axvline(d, color="#0b5394", lw=1.6)
        ax.axvline(lo, color="#b45f06", ls="--", lw=1.0)
        ax.axvline(hi, color="#b45f06", ls="--", lw=1.0)
        ax.set_title(f"{METHOD_LABEL[a]} vs {METHOD_LABEL[b]}\n"
                     f"$p$ = {p:.4f}\n"
                     f"CI [{lo:+.3f}, {hi:+.3f}]")
        ax.text(0.02, 0.95, f"observed $\\delta$ = {d:+.3f}",
                transform=ax.transAxes, ha="left", va="top", fontsize=8)
    axes[0].set_ylabel("count")
    fig.supxlabel("Cliff's $\\delta$ (bootstrap resamples)")
    _save(fig, "fig10_cliffs_delta")


def fig11_deployed_circuits(deployed: dict) -> None:
    with open(BUNDLE, "rb") as f:
        target = pickle.load(f)["target"]

    def build(pheno: str) -> QuantumCircuit:
        loc = {}
        exec(pheno, {"QuantumRegister": QuantumRegister,
                     "ClassicalRegister": ClassicalRegister,
                     "QuantumCircuit": QuantumCircuit,
                     "np": np}, loc)
        return loc["qc"]

    items = []
    for method in METHODS:
        for st in STATES:
            d = deployed[(method, st)]
            qc = build(d["phenotype"])
            tqc = None
            for _ in range(8):
                cand = transpile(qc, target=target, optimization_level=3,
                                 seed_transpiler=d["seed"])
                if cand.size() == d["gate_count"] and cand.depth() == d["depth"]:
                    tqc = cand
                    break
            if tqc is None:
                tqc = cand
            items.append((method, st, d["seed"], tqc))

    # 3 method blocks, each a 2 x 4 grid (one panel per state).
    fig, axes = plt.subplots(6, 4, figsize=(_mm(1.0), 8.4),
                             layout="constrained")
    for k, (method, st, seed, tqc) in enumerate(items):
        ax = axes[k // 4][k % 4]
        tqc.draw("mpl", ax=ax, idle_wires=False, fold=-1)
        ax.set_title(f"$|{st}\\rangle$\n{METHOD_LABEL[method]}", fontsize=8,
                     pad=1.5)
    for ax in axes.flat[len(items):]:
        ax.axis("off")
    # Qiskit annotates the global phase via pyplot.text(), which attaches to
    # whichever axes is current -- so all 24 labels pile up on the last panel.
    # Drop those display-only annotations.
    removed = 0
    for a in fig.axes:
        for t in list(a.texts):
            if t.get_text().startswith("Global Phase"):
                t.remove()
                removed += 1
    for t in list(fig.texts):
        if t.get_text().startswith("Global Phase"):
            t.remove()
            removed += 1
    print(f"  fig11: removed {removed} stacked global-phase labels")
    _save(fig, "fig11_deployed_transpiled_circuits")


def fig13_failure_composition(results: dict) -> None:
    fig, ax = plt.subplots(figsize=(_mm(0.8), 3.0), layout="constrained")
    classes = [("converged", "#2e8b57", "converged (early stop)"),
               ("fidelity_fail", "#c0392b", "fidelity fail (<0.95)"),
               ("size_fail", "#e67e22", "size fail (fid ok, large circuit)"),
               ("stopping_miss", "#95a5a6", "stopping-rule miss")]
    x = np.arange(len(METHODS))
    bottom = np.zeros(len(METHODS))
    per_method = {m: [] for m in METHODS}
    for key, col, lab in classes:
        vals = []
        for method in METHODS:
            rs = [r for st in STATES for r in results[(method, st)].values()]
            fulls = [r for r in rs if stop_class(r) == "full"]
            vals.append(80 - len(fulls) if key == "converged"
                        else Counter(classify_full(r) for r in fulls)[key])
        for method, v in zip(METHODS, vals):
            per_method[method].append(v)
        ax.bar(x, vals, bottom=bottom, color=col, label=lab, width=0.55)
        bottom += np.array(vals)
    for xi, method in enumerate(METHODS):
        ax.text(xi, bottom[xi] + 2, " / ".join(str(v) for v in per_method[method]),
                ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([METHOD_LABEL[m] for m in METHODS])
    ax.set_ylabel("runs (of 80)")
    ax.set_ylim(0, 104)
    ax.legend(frameon=False, fontsize=8, loc="upper center", ncol=2)
    _save(fig, "fig13_failure_composition")


def fig14_deployed_quality(deployed: dict) -> None:
    # Stacked rather than side by side so the eight state labels keep their
    # spacing at print width.
    fig, axes = plt.subplots(2, 1, figsize=(_mm(0.92), 4.2),
                             layout="constrained")
    x = np.arange(len(STATES))
    n = len(METHODS)
    w = 0.74 / n
    for ax, key, ylab in ((axes[0], "two_qubit_gates",
                           "deployed transpiled 2Q gates"),
                          (axes[1], "depth", "deployed transpiled depth")):
        for i, method in enumerate(METHODS):
            off = (i - (n - 1) / 2) * w
            vals = [deployed[(method, st)][key] for st in STATES]
            ax.bar(x + off, vals, width=w * 0.85,
                   color=METHOD_COLOR[method], alpha=0.88,
                   label=METHOD_LABEL[method])
        ax.set_xticks(x)
        ax.set_xticklabels([f"$|{st}\\rangle$" for st in STATES])
        ax.set_ylabel(ylab)
    axes[0].legend(frameon=False, fontsize=8, loc="upper left")
    _save(fig, "fig14_deployed_quality")


def fig16_lexi2_tiebreak_firerate() -> None:
    fire = read_csv("lexi2_tiebreak_firerate_bygen.csv")
    pool = read_csv("survivor_pool_lexi2_bygen.csv")
    n_runs = len(glob.glob(os.path.join(ROOTS["lexi2"], "lexi2", "pop300",
                                        "noise", "state_*", "run_*",
                                        "lexi2_log_*.json")))
    assert n_runs == 80, f"expected 80 Lexi2 runs, found {n_runs}"

    def series(rows, key):
        gs, vs = [], []
        for r in rows:
            gs.append(int(r["generation"]))
            v = r[key].strip()
            vs.append(float(v) if v not in ("", "-") else float("nan"))
        return gs, vs

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(_mm(0.9), 3.4),
                                   layout="constrained")

    ax1.plot(*series(fire, "overall_fire_rate"), color="#2e7d32", lw=1.5,
             label="overall (80 runs)")
    ax1.plot(*series(fire, "converged_fire_rate"), color="#1f77b4", lw=1.3,
             ls="--", label="converged (55 runs)")
    ax1.plot(*series(fire, "nonconverged_fire_rate"), color="#d62728", lw=1.3,
             ls=":", label="non-converged (25 runs)")
    ax1.set_xlabel("generation")
    ax1.set_ylabel("tiebreak-invocation rate (per selection)")
    ax1.set_ylim(-0.02, 1.03)
    ax1.legend(frameon=False, loc="lower right")
    ax1.set_title("Size-tiebreak invocation rate")

    g2, mean2 = series(pool, "mean_pool_size_all")
    _, med2 = series(pool, "median_pool_size_all")
    ax2.plot(g2, mean2, color="#2e7d32", lw=1.5, label="mean")
    ax2.plot(g2, med2, color="#555555", lw=1.1, ls="--", label="median")
    ax2.set_xlabel("generation")
    ax2.set_ylabel("post-case candidate-pool size")
    ax2.set_ylim(0, 11)
    ax2.legend(frameon=False, loc="lower right")
    ax2.set_title("Post-case candidate-pool size")

    print(f"  fig16 firerate: {n_runs} runs")
    _save(fig, "fig16_lexi2_tiebreak_firerate")


def main() -> None:
    _style()
    results = load_results()
    deployed = load_deployed()
    hw = load_matched_hw()

    fig01_fidelity(results)
    fig02_gens(results)
    fig03_trajectories()
    fig05_hardware(deployed, hw)
    fig06_success(results)
    fig07_paired_scatter(results)
    fig10_cliffs_delta(results)
    fig11_deployed_circuits(deployed)
    fig13_failure_composition(results)
    fig14_deployed_quality(deployed)
    fig16_lexi2_tiebreak_firerate()


if __name__ == "__main__":
    main()
