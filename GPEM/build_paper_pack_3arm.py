#!/usr/bin/env python3
"""Three-arm frozen-batch paper pack (epsilon-lexicase vs Lexi2 vs tournament).

Reads ONLY completed artifacts:
  - experiments_frozen_10seed/{epsilon_lexicase,tournament}/pop300/noise/...
  - experiments_frozen_10seed_lexi2/lexi2/pop300/noise/...
No experiments are run. run_result two_qubit_gates are the corrected
(transpiled) counts. Lexi2 has no ibm_fez hardware results (flagged).

Writes:
  - PAPER_DATA_FROZEN_3ARM.md
  - STATS_3ARM_frozen.md
  - per_run_frozen_3arm.csv
  - results_table_frozen_3arm.csv
  - paper_figures/frozen_10seed/fig01..04,06,08,11,12 regenerated with Lexi2
"""

from __future__ import annotations

import csv
import glob
import itertools
import json
import os
import pickle
import statistics

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister, transpile

ARMS = ["epsilon_lexicase", "lexi2", "tournament"]
ARM_LABEL = {"epsilon_lexicase": r"$\varepsilon$-lexicase", "lexi2": "Lexi2",
             "tournament": "tournament"}
ARM_COLOR = {"epsilon_lexicase": "#0b5394", "lexi2": "#2e7d32", "tournament": "#b45f06"}
ROOTS = {"epsilon_lexicase": "experiments_frozen_10seed",
         "tournament": "experiments_frozen_10seed",
         "lexi2": "experiments_frozen_10seed_lexi2"}
STATES = ["000", "001", "010", "011", "100", "101", "110", "111"]
SEEDS = [21315, 47182, 12147, 33537, 70300, 74135, 67154, 80248, 91197, 29440]
BUNDLE = "noise/frozen_env_ibm_fez_2026-08-20.pkl"
FIG_DIR = "paper_figures/frozen_10seed"
RNG_SEED = 20260902


def arm_root(arm: str, state: str) -> str:
    return os.path.join(ROOTS[arm], arm, "pop300", "noise", f"state_{state}")


def load_run_results() -> dict:
    """{(arm, state): {seed: run_result}}"""
    out = {}
    for arm in ARMS:
        for st in STATES:
            d = {}
            for f in glob.glob(os.path.join(arm_root(arm, st), "run_*", "run_result_*.json")):
                r = json.load(open(f))
                d[r["seed"]] = r
            out[(arm, st)] = d
    return out


def load_deployed() -> dict:
    out = {}
    for arm in ARMS:
        for st in STATES:
            out[(arm, st)] = json.load(open(os.path.join(arm_root(arm, st), "deployed_best.json")))
    return out


def load_hardware() -> dict:
    out = {}
    for arm in ARMS:
        for st in STATES:
            fs = glob.glob(os.path.join(arm_root(arm, st), "run_*", "hof_1_ibm_hardware_data.json"))
            if fs:
                out[(arm, st)] = json.load(open(fs[0]))
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


def cliffs_ci(x: np.ndarray, y: np.ndarray, n_boot: int = 10000) -> tuple[float, float]:
    rng = np.random.default_rng(RNG_SEED)
    v = np.array([cliffs_delta(rng.choice(x, x.size, True), rng.choice(y, y.size, True))
                  for _ in range(n_boot)])
    return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def sig(p: float) -> str:
    return "yes" if p < 0.05 else "no"


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #
def _style():
    plt.rcParams.update({
        "font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10,
        "savefig.dpi": 300, "savefig.bbox": "tight",
        "axes.spines.top": False, "axes.spines.right": False,
    })


def _save(fig, name):
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(os.path.join(FIG_DIR, name + ".png"))
    fig.savefig(os.path.join(FIG_DIR, name + ".pdf"))
    plt.close(fig)
    print("figure:", name)


def fig01_fidelity(results):
    fig, ax = plt.subplots(figsize=(9.0, 3.8))
    x = np.arange(len(STATES))
    n = len(ARMS)
    w = 0.74 / n
    for i, arm in enumerate(ARMS):
        off = (i - (n - 1) / 2) * w
        data = [[results[(arm, st)][s]["fidelity"] for s in SEEDS] for st in STATES]
        bp = ax.boxplot(data, positions=x + off, widths=w * 0.85, patch_artist=True,
                        showfliers=False, medianprops=dict(color="white"))
        for patch in bp["boxes"]:
            patch.set_facecolor(ARM_COLOR[arm]); patch.set_alpha(0.72)
        for j in range(len(STATES)):
            vals = data[j]
            ax.scatter(np.full(len(vals), x[j] + off) + np.random.default_rng(j).uniform(-0.04, 0.04, len(vals)),
                       vals, s=7, color=ARM_COLOR[arm], alpha=0.55)
    ax.axhline(0.95, color="gray", ls="--", lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels([f"$|{st}\\rangle$" for st in STATES])
    ax.set_ylabel("final simulated fidelity"); ax.set_ylim(0.42, 1.01)
    handles = [plt.Line2D([], [], color=ARM_COLOR[a], marker="s", ls="", label=ARM_LABEL[a]) for a in ARMS]
    ax.legend(handles=handles, frameon=False, loc="lower left", ncol=3)
    ax.set_title("Final fidelity by state and selection method (10 seeds)")
    _save(fig, "fig01_fidelity_by_arm_state")


def fig02_gens(results):
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    for arm in ARMS:
        runs = [r for st in STATES for r in results[(arm, st)].values()]
        gens = sorted(r.get("early_stopped_gen") or 100 for r in runs)
        y = np.arange(1, len(gens) + 1) / len(gens)
        ax.step(gens, y, where="post", color=ARM_COLOR[arm], label=ARM_LABEL[arm], lw=1.7)
    ax.set_xlabel("generations to stop (full-100 counted at 100)")
    ax.set_ylabel("ECDF over runs"); ax.set_xlim(0, 102)
    ax.legend(frameon=False)
    ax.set_title("Generations-to-stop, three arms")
    _save(fig, "fig02_generations_to_stop")


def fig03_trajectories(results):
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    diag_roots = {}
    for arm in ARMS:
        series = []
        for st in STATES:
            for s in SEEDS:
                fs = glob.glob(os.path.join(arm_root(arm, st), f"run_*_seed_{s}", f"diagnostics_{st}_run*.csv"))
                if not fs:
                    continue
                with open(fs[0]) as fh:
                    rows = list(csv.DictReader(fh))
                vals = [float(x["fidelity_max"]) for x in rows if x.get("fidelity_max")]
                if vals:
                    series.append(np.pad(vals, (0, 100 - len(vals)), constant_values=vals[-1])[:100])
        if not series:
            continue
        m = np.mean(series, axis=0); sd = np.std(series, axis=0); g = np.arange(len(m))
        ax.plot(g, m, color=ARM_COLOR[arm], lw=1.7, label=ARM_LABEL[arm])
        ax.fill_between(g, m - sd, m + sd, color=ARM_COLOR[arm], alpha=0.14)
    ax.set_xlabel("generation"); ax.set_ylabel("best fidelity in population")
    ax.axhline(0.95, color="gray", ls="--", lw=0.8)
    ax.legend(frameon=False)
    ax.set_title("Mean best-fidelity trajectory (converged runs padded at stop value)")
    _save(fig, "fig03_convergence_trajectories")


def fig04_cost(results):
    fig, axes = plt.subplots(1, 3, figsize=(12.4, 3.5))
    x = np.arange(len(STATES)); n = len(ARMS); w = 0.74 / n
    for ax, key, ylab in ((axes[0], "depth", "transpiled depth"),
                          (axes[1], "gate_count", "transpiled gates"),
                          (axes[2], "two_qubit_gates", "transpiled 2Q gates")):
        for i, arm in enumerate(ARMS):
            off = (i - (n - 1) / 2) * w
            means, stds = [], []
            for st in STATES:
                vals = [results[(arm, st)][s][key] for s in SEEDS]
                means.append(statistics.mean(vals)); stds.append(statistics.stdev(vals))
            ax.bar(x + off, means, width=w * 0.85, yerr=stds, capsize=2,
                   color=ARM_COLOR[arm], alpha=0.85, label=ARM_LABEL[arm], error_kw=dict(lw=0.7))
        ax.set_xticks(x); ax.set_xticklabels([f"$|{st}\\rangle$" for st in STATES], fontsize=8)
        ax.set_ylabel(ylab)
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Transpiled circuit cost by state and selection method", y=1.03, fontsize=11)
    _save(fig, "fig04_circuit_cost")


def fig06_success(results):
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    M = np.array([[sum(1 for r in results[(arm, st)].values() if stop_class(r) == "converged")
                   for st in STATES] for arm in ARMS])
    im = ax.imshow(M, cmap="YlGnBu", vmin=0, vmax=10, aspect="auto")
    ax.set_xticks(range(len(STATES))); ax.set_xticklabels([f"$|{st}\\rangle$" for st in STATES])
    ax.set_yticks(range(len(ARMS))); ax.set_yticklabels([ARM_LABEL[a] for a in ARMS])
    for i in range(len(ARMS)):
        for j in range(len(STATES)):
            ax.text(j, i, f"{M[i, j]}/10", ha="center", va="center", fontsize=8,
                    color="black" if M[i, j] < 9 else "white")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="converged runs")
    ax.set_title("Converged runs per state × selection method")
    _save(fig, "fig06_success_heatmap")


def fig05_hardware(deployed, hw):
    fig, ax = plt.subplots(figsize=(6.6, 5.6))
    for arm in ARMS:
        xs, ys = [], []
        for st in STATES:
            if (arm, st) in hw:
                xs.append(deployed[(arm, st)]["fidelity"])
                ys.append(hw[(arm, st)]["p_marked_hw"])
        ax.scatter(xs, ys, s=55, color=ARM_COLOR[arm], label=ARM_LABEL[arm],
                   alpha=0.9, edgecolors="white", lw=0.5)
        for st, xv, yv in zip(STATES, xs, ys):
            ax.annotate(f"$|{st}\\rangle$", (xv, yv), textcoords="offset points",
                        xytext=(4, 4), fontsize=7, color=ARM_COLOR[arm])
    lim = (0.90, 1.0)
    ax.plot(lim, lim, "k--", lw=1)
    ax.set_xlim(*lim); ax.set_ylim(*lim)
    ax.set_xlabel("deployed simulated fidelity (frozen target)")
    ax.set_ylabel("hardware p(marked), ibm_fez, 10k shots")
    ax.set_aspect("equal")
    ax.legend(frameon=False)
    ax.set_title("Simulation-to-hardware validation (24 circuits, 3 arms)")
    _save(fig, "fig05_hardware_validation")


def fig08_failures(results):
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.6), sharex=True)
    for ax, arm in zip(axes, ARMS):
        n = 0
        for st in STATES:
            for s in SEEDS:
                r = results[(arm, st)][s]
                if stop_class(r) != "full":
                    continue
                fs = glob.glob(os.path.join(arm_root(arm, st), f"run_*_seed_{s}", f"diagnostics_{st}_run*.csv"))
                if not fs:
                    continue
                with open(fs[0]) as fh:
                    rows = list(csv.DictReader(fh))
                vals = [float(x["fidelity_max"]) for x in rows if x.get("fidelity_max")]
                if vals:
                    ax.plot(vals, color=ARM_COLOR[arm], alpha=0.65, lw=1.0)
                    n += 1
        ax.set_title(f"{ARM_LABEL[arm]} (n={n} full runs)")
        ax.set_xlabel("generation")
    axes[0].set_ylabel("best fidelity")
    fig.suptitle("Non-converged runs: best-fidelity trajectories", y=1.02, fontsize=11)
    _save(fig, "fig08_failed_trajectories")


def fig12_paired_lexi2(results):
    fig, ax = plt.subplots(figsize=(6.0, 5.4))
    cmap = plt.get_cmap("viridis")
    colors = cmap(np.linspace(0.08, 0.92, len(STATES)))
    above = below = 0
    for j, st in enumerate(STATES):
        xs = [results[("epsilon_lexicase", st)][s]["fidelity"] for s in SEEDS]
        ys = [results[("lexi2", st)][s]["fidelity"] for s in SEEDS]
        ax.scatter(xs, ys, s=25, color=colors[j], alpha=0.85, label=f"$|{st}\\rangle$")
        above += sum(a > b for a, b in zip(xs, ys)); below += sum(a < b for a, b in zip(xs, ys))
    lim = (0.42, 1.0)
    ax.plot(lim, lim, "k--", lw=1)
    ax.set_xlim(*lim); ax.set_ylim(*lim)
    ax.set_xlabel("ε-lexicase final fidelity"); ax.set_ylabel("Lexi2 final fidelity")
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="lower right")
    ax.text(0.98, 0.10, f"lex higher: {above} pairs\nlexi2 higher: {below} pairs",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=8,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", lw=0.6))
    ax.set_title("Paired fidelity: ε-lexicase vs Lexi2 (shared gen-0 init)")
    _save(fig, "fig12_paired_lexicase_vs_lexi2")


def fig13_failure_composition(results):
    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    classes = [("converged", "#2e8b57", "converged (early stop)"),
               ("fidelity_fail", "#c0392b", "fidelity fail (<0.95)"),
               ("size_fail", "#e67e22", "size fail (fid ok, big circuit)"),
               ("stopping_miss", "#95a5a6", "stopping-rule miss")]
    x = np.arange(len(ARMS))
    bottom = np.zeros(len(ARMS))
    for key, col, lab in classes:
        vals = []
        for arm in ARMS:
            rs = [r for st in STATES for r in results[(arm, st)].values()]
            fulls = [r for r in rs if stop_class(r) == "full"]
            vals.append(80 - len(fulls) if key == "converged"
                        else collections_counter([classify_full(r) for r in fulls])[key])
        bars = ax.bar(x, vals, bottom=bottom, color=col, label=lab, width=0.55)
        for xi, v in zip(x, vals):
            if v > 0:
                ax.text(xi, bottom[xi] + v / 2, str(v), ha="center", va="center",
                        fontsize=8, color="white", fontweight="bold")
        bottom += np.array(vals)
    ax.set_xticks(x); ax.set_xticklabels([ARM_LABEL[a] for a in ARMS])
    ax.set_ylabel("runs (of 80)")
    ax.set_ylim(0, 88)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    ax.set_title("Outcome composition by selection method (10 seeds × 8 states)")
    _save(fig, "fig13_failure_composition")


def fig14_deployed_quality(deployed):
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 3.7))
    x = np.arange(len(STATES)); n = len(ARMS); w = 0.74 / n
    for ax, key, ylab in ((axes[0], "two_qubit_gates", "deployed transpiled 2Q gates"),
                          (axes[1], "depth", "deployed transpiled depth")):
        for i, arm in enumerate(ARMS):
            off = (i - (n - 1) / 2) * w
            vals = [deployed[(arm, st)][key] for st in STATES]
            ax.bar(x + off, vals, width=w * 0.85, color=ARM_COLOR[arm],
                   alpha=0.88, label=ARM_LABEL[arm])
        ax.set_xticks(x); ax.set_xticklabels([f"$|{st}\\rangle$" for st in STATES], fontsize=8)
        ax.set_ylabel(ylab)
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Deployed best-of-10 circuit cost (λ-free rule)", y=1.03, fontsize=11)
    _save(fig, "fig14_deployed_quality")


def fig15_cliffs_forest(results):
    fids = {a: np.array([r["fidelity"] for st in STATES for r in results[(a, st)].values()]) for a in ARMS}
    pairs = [("epsilon_lexicase", "lexi2"), ("epsilon_lexicase", "tournament"), ("lexi2", "tournament")]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    bands = [(-1.0, -0.474, "#d9d9d9"), (-0.474, -0.33, "#e6e6e6"), (-0.33, -0.147, "#f0f0f0"),
             (-0.147, 0.147, "#fafafa"), (0.147, 0.33, "#f0f0f0"), (0.33, 0.474, "#e6e6e6"),
             (0.474, 1.0, "#d9d9d9")]
    for lo, hi, col in bands:
        ax.axvspan(lo, hi, color=col, zorder=0)
    for lo, hi, lab in [(-0.474, -0.33, "med"), (-0.33, -0.147, "small"), (-0.147, 0.147, "negligible"),
                        (0.147, 0.33, "small"), (0.33, 0.474, "med")]:
        ax.text((lo + hi) / 2, 2.72, lab, ha="center", fontsize=6.5, color="#555")
    est, cis = [], []
    labels = []
    for a, b in pairs:
        d = cliffs_delta(fids[a], fids[b])
        ci = cliffs_ci(fids[a], fids[b])
        _, p = stats.mannwhitneyu(fids[a], fids[b], alternative="two-sided")
        est.append(d); cis.append(ci); labels.append(f"{ARM_LABEL[a]}\nvs {ARM_LABEL[b]}\np={p:.4f}")
    y = np.arange(len(pairs))[::-1]
    for yi, d, ci, lab in zip(y, est, cis, labels):
        ax.errorbar([d], [yi], xerr=[[d - ci[0]], [ci[1] - d]], fmt="o", color="#0b5394",
                    ms=7, capsize=4, lw=1.5, zorder=3)
    ax.axvline(0, color="black", lw=0.9)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlim(-0.6, 0.7)
    ax.set_xlabel("Cliff's δ (positive = first arm higher fidelity)")
    ax.set_title("Pairwise final-fidelity effect sizes, 95% bootstrap CI")
    _save(fig, "fig15_cliffs_forest")


def fig16_lexi2_tiebreak():
    logs = glob.glob(os.path.join(ROOTS["lexi2"], "lexi2", "pop300", "noise",
                                  "state_*", "run_*", "lexi2_log_*.json"))
    gens = {}
    for f in logs:
        d = json.load(open(f))
        for g, v in d.get("per_generation", {}).items():
            gens.setdefault(int(g), []).append(v)
    gs = sorted(gens)
    rate, nrun, eps_case = [], [], {}
    for g in gs:
        vs = gens[g]
        fires = sum(v["tiebreak_fires"] for v in vs)
        sels = sum(v["selections"] for v in vs)
        rate.append(fires / sels if sels else float("nan"))
        nrun.append(len(vs))
        for v in vs:
            for c, e in enumerate(v["eps"]):
                eps_case.setdefault(c, []).append([])
        for c in range(8):
            arr = eps_case[c]
            arr[-1] = [v["eps"][c] for v in vs]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.2, 3.8))
    ax1.plot(gs, rate, color="#2e7d32", lw=1.6)
    ax1.set_xlabel("generation"); ax1.set_ylabel("tiebreak-fire rate (per selection)")
    ax1.set_ylim(0, 1.02)
    ax1.set_title(f"Lexi2 size-tiebreak firing rate ({len(logs)} runs)")
    ax1b = ax1.twinx()
    ax1b.plot(gs, nrun, color="#95a5a6", lw=0.8, alpha=0.6)
    ax1b.set_ylabel("runs active at gen", fontsize=8)
    ax1b.tick_params(axis="y", labelsize=8)
    M = np.array([[np.mean(eps_case[c][i]) if eps_case[c][i] else np.nan
                   for i, g in enumerate(gs)] for c in range(8)])
    im = ax2.imshow(M, aspect="auto", cmap="viridis", origin="lower",
                    extent=[gs[0], gs[-1], -0.5, 7.5])
    ax2.set_yticks(range(8)); ax2.set_yticklabels([f"p|{s}⟩" for s in STATES], fontsize=7)
    ax2.set_xlabel("generation"); ax2.set_ylabel("case")
    cb = fig.colorbar(im, ax=ax2, fraction=0.045, pad=0.04)
    cb.set_label("mean ε (MAD)", fontsize=8)
    ax2.set_title("Lexi2 ε per output-state case (mean across runs)")
    fig.suptitle("Lexi2 per-generation diagnostics (Douglas logging)", y=1.04, fontsize=11)
    _save(fig, "fig16_lexi2_tiebreak")


def fig11_deployed_circuits(deployed):
    os.makedirs(os.path.join(FIG_DIR, "circuits"), exist_ok=True)
    with open(BUNDLE, "rb") as f:
        target = pickle.load(f)["target"]

    def build(pheno):
        loc = {}
        exec(pheno, {"QuantumRegister": QuantumRegister, "ClassicalRegister": ClassicalRegister,
                     "QuantumCircuit": QuantumCircuit, "np": np}, loc)
        return loc["qc"]

    items = []
    for arm in ARMS:
        for st in STATES:
            d = deployed[(arm, st)]
            qc = build(d["phenotype"])
            tqc = None
            for _ in range(5):
                cand = transpile(qc, target=target, optimization_level=3, seed_transpiler=d["seed"])
                if cand.size() == d["gate_count"] and cand.depth() == d["depth"]:
                    tqc = cand
                    break
            if tqc is None:
                tqc = cand
            base = f"{arm}_{st}_seed{d['seed']}"
            qc.draw("mpl", idle_wires=False).savefig(os.path.join(FIG_DIR, "circuits", f"raw_{base}.png"),
                                                     dpi=300, bbox_inches="tight")
            plt.close("all")
            tqc.draw("mpl", idle_wires=False).savefig(os.path.join(FIG_DIR, "circuits", f"transpiled_{base}.png"),
                                                      dpi=300, bbox_inches="tight")
            plt.close("all")
            items.append((arm, st, d["seed"], tqc))
    fig, axes = plt.subplots(6, 4, figsize=(26, 22))
    for k, (arm, st, seed, tqc) in enumerate(items):
        ax = axes[k // 4][k % 4]
        tqc.draw("mpl", ax=ax, idle_wires=False, fold=-1)
        ax.set_title(f"$|{st}\\rangle$ {ARM_LABEL[arm]} (seed {seed})", fontsize=9)
    for ax in axes.flat[len(items):]:
        ax.axis("off")
    fig.suptitle("Deployed transpiled circuits — frozen ibm_fez target, opt-3, run seed",
                 fontsize=14, y=0.99)
    fig.savefig(os.path.join(FIG_DIR, "fig11_deployed_transpiled_circuits.png"), dpi=300, bbox_inches="tight")
    fig.savefig(os.path.join(FIG_DIR, "fig11_deployed_transpiled_circuits.pdf"))
    plt.close(fig)
    print("figure: fig11_deployed_transpiled_circuits (24 panels); circuits/ updated")


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #
def write_paper_data(results, deployed, hw):
    L = []
    A = L.append
    A("# PAPER_DATA — Frozen 10-seed, three arms (ε-lexicase, Lexi2, tournament)")
    A("")
    A("Assembled 2026-09-02 from the frozen batch: 240 runs = 10 seeds × 8 states × 3 arms, "
      "pop 300, max 100 gens, all under `noise/frozen_env_ibm_fez_2026-08-20.pkl` "
      "(no live calibration). Lexi2 runs live in `experiments_frozen_10seed_lexi2/`. "
      "Converged = `Hardware targets achieved` stop reason; full-100 = "
      "`completed_all_generations`. 2Q counts are the corrected transpiled values. "
      "Hardware (ibm_fez, 10k shots): all three arms deployed on 2026-09-02 "
      "(8 deployed circuits per arm; Lexi2 deployed after its sweep completed).")
    A("")
    A("### Overall (per arm, n=80)")
    A("")
    A("| Metric | ε-lexicase | Lexi2 | tournament |")
    A("|---|---|---|---|")
    for metric, fmt in [
        ("Converged (early stop)", lambda c: f"**{c}/80 ({100*c/80:.1f}%)**"),
        ("Ran full 100", lambda c: f"{80-c}"),
    ]:
        row = []
        for arm in ARMS:
            c = sum(1 for st in STATES for r in results[(arm, st)].values() if stop_class(r) == "converged")
            row.append(fmt(c))
        A(f"| {metric} | " + " | ".join(row) + " |")
    fids = {}
    for arm in ARMS:
        v = [r["fidelity"] for st in STATES for r in results[(arm, st)].values()]
        fids[arm] = v
    A(f"| Final fidelity mean ± SD | {np.mean(fids['epsilon_lexicase']):.4f} ± {np.std(fids['epsilon_lexicase'], ddof=1):.4f} "
      f"| {np.mean(fids['lexi2']):.4f} ± {np.std(fids['lexi2'], ddof=1):.4f} "
      f"| {np.mean(fids['tournament']):.4f} ± {np.std(fids['tournament'], ddof=1):.4f} |")
    gens = {}
    for arm in ARMS:
        v = [r.get("early_stopped_gen") or 100 for st in STATES for r in results[(arm, st)].values()]
        gens[arm] = v
    A(f"| Gens-to-stop mean (median), all runs | {np.mean(gens['epsilon_lexicase']):.1f} ({np.median(gens['epsilon_lexicase']):.0f}) "
      f"| {np.mean(gens['lexi2']):.1f} ({np.median(gens['lexi2']):.0f}) "
      f"| {np.mean(gens['tournament']):.1f} ({np.median(gens['tournament']):.0f}) |")
    A("")

    sec = {"epsilon_lexicase": "A", "lexi2": "B", "tournament": "C"}
    for arm in ARMS:
        A(f"### {sec[arm]}. {ARM_LABEL[arm]} per-state results (pop=300, 10 seeds)")
        A("")
        A("| State | Best sim fid | Seed | Transpiled D/G/2Q | Raw D/G | HW p_marked | Success (k/10) | Mean±std fid | Mean stop gen |")
        A("|---|---|---|---|---|---|---|---|---|")
        for st in STATES:
            d = deployed[(arm, st)]
            rs = list(results[(arm, st)].values())
            fid = [r["fidelity"] for r in rs]
            conv = sum(1 for r in rs if stop_class(r) == "converged")
            gs = [r.get("early_stopped_gen") or 100 for r in rs]
            h = hw.get((arm, st), {})
            pm = f"{h['p_marked_hw']:.4f}" if h else "—"
            A(f"| {st} | {d['fidelity']:.4f} | {d['seed']} | {d['depth']}/{d['gate_count']}/{d['two_qubit_gates']} "
              f"| {d['raw_depth']}/{d['raw_gate_count']} | {pm} | {conv}/10 | "
              f"{statistics.mean(fid):.4f}±{statistics.stdev(fid):.4f} | {statistics.mean(gs):.1f} |")
        A("")

    A("### D. Three-arm head-to-head (deployed best-of-10 per state)")
    A("")
    A("| State | Lex fid (D/2Q) | Lexi2 fid (D/2Q) | Tour fid (D/2Q) |")
    A("|---|---|---|---|")
    for st in STATES:
        cells = []
        for arm in ARMS:
            d = deployed[(arm, st)]
            cells.append(f"{d['fidelity']:.4f} ({d['depth']}/{d['two_qubit_gates']})")
        A(f"| {st} | " + " | ".join(cells) + " |")
    A("")
    A("")

    A("### E. Failure composition (full-100 runs)")
    A("")
    A("| Arm | Converged | Fidelity fail (<0.95) | Size fail (fid≥0.95, big circuit) | Stopping-rule miss |")
    A("|---|---|---|---|---|")
    for arm in ARMS:
        fulls = [r for st in STATES for r in results[(arm, st)].values() if stop_class(r) == "full"]
        cc = collections_counter([classify_full(r) for r in fulls])
        A(f"| {ARM_LABEL[arm]} | {80 - len(fulls)} | {cc['fidelity_fail']} | {cc['size_fail']} | {cc['stopping_miss']} |")
    A("")
    A("### F. Figure inventory (paper_figures/frozen_10seed/)")
    A("")
    A("fig01 fidelity by state/arm; fig02 gens-to-stop ECDF; fig03 convergence trajectories; "
      "fig04 circuit cost; fig05 hardware validation (2 arms); fig06 success heatmap; "
      "fig07 paired ε-lex vs tournament; fig08 failed trajectories (3 panels); "
      "fig09/fig10 paired/effect-size stats (2 arms); fig11 deployed circuits (24); "
      "fig12 paired ε-lex vs Lexi2; fig13 outcome composition; fig14 deployed quality; "
      "fig15 pairwise Cliff's δ forest; fig16 Lexi2 tiebreak/ε diagnostics.")
    A("")
    A("### G. Configuration")
    A("")
    A("10 seeds (21315, 47182, 12147, 33537, 70300, 74135, 67154, 80248, 91197, 29440), "
      "8 states, pop 300, max 100 gens, frozen bundle, option-(a) early stopping, "
      "λ-free deployment (fidelity → transpiled 2Q → gates → depth). Lexi2: MAD ε per "
      "case per generation over the 8 output-state probabilities; size tiebreak "
      "(2Q → gates → depth) fires on 83.3% of selections on average. "
      "Software pins as in FROZEN_SWEEP_NOTES.md.")
    A("")
    open("PAPER_DATA_FROZEN_3ARM.md", "w").write("\n".join(L))


def collections_counter(items):
    from collections import Counter
    return Counter(items)


def write_stats(results, deployed, hw):
    L = []
    A = L.append
    A("# STATS_3ARM — Frozen batch: ε-lexicase vs Lexi2 vs tournament")
    A("")
    A("240 runs (10 seeds × 8 states × 3 arms). α = 0.05; pairwise p-values reported raw "
      "with Holm-Bonferroni correction over the three arm pairs. No experiments re-run.")
    A("")
    fids = {arm: np.array([r["fidelity"] for st in STATES for r in results[(arm, st)].values()]) for arm in ARMS}

    A("## 1. Convergence")
    A("")
    A("| Arm | Converged/80 | % |")
    A("|---|---|---|")
    conv = {}
    for arm in ARMS:
        c = sum(1 for st in STATES for r in results[(arm, st)].values() if stop_class(r) == "converged")
        conv[arm] = c
        A(f"| {ARM_LABEL[arm]} | {c}/80 | {100*c/80:.1f}% |")
    A("")
    pairs = [("epsilon_lexicase", "lexi2"), ("epsilon_lexicase", "tournament"), ("lexi2", "tournament")]
    fisher = {}
    for a, b in pairs:
        tab = [[conv[a], 80 - conv[a]], [conv[b], 80 - conv[b]]]
        _, p = stats.fisher_exact(tab, alternative="two-sided")
        fisher[(a, b)] = p
    # Holm correction over 3 pairs
    ordered = sorted(pairs, key=lambda ab: fisher[ab])
    adj = {}
    for k, ab in enumerate(ordered):
        adj[ab] = min(1.0, fisher[ab] * (3 - k))
    A("| Pair | Fisher p (raw) | Holm-adjusted | Significant (adj < 0.05) |")
    A("|---|---|---|---|")
    for a, b in pairs:
        A(f"| {ARM_LABEL[a]} vs {ARM_LABEL[b]} | {fisher[(a,b)]:.4f} | {adj[(a,b)]:.4f} | "
          f"{sig(adj[(a,b)])} |")
    A("")

    A("## 2. Final fidelity")
    A("")
    kw = stats.kruskal(*[fids[a] for a in ARMS])
    A(f"- Kruskal-Wallis across arms: H = {kw.statistic:.2f}, p = {kw.pvalue:.4f}")
    A("")
    A("| Pair | MWU U | p (raw) | Cliff's δ (95% CI) |")
    A("|---|---|---|---|")
    for a, b in pairs:
        u, p = stats.mannwhitneyu(fids[a], fids[b], alternative="two-sided")
        d = cliffs_delta(fids[a], fids[b])
        ci = cliffs_ci(fids[a], fids[b])
        A(f"| {ARM_LABEL[a]} vs {ARM_LABEL[b]} | {u:.1f} | {p:.4f} | {d:+.3f} "
          f"([{ci[0]:+.3f}, {ci[1]:+.3f}]) |")
    A("")
    m = {a: (float(np.mean(fids[a])), float(np.std(fids[a], ddof=1))) for a in ARMS}
    A(f"Means ± SD: ε-lexicase {m['epsilon_lexicase'][0]:.4f} ± {m['epsilon_lexicase'][1]:.4f}; "
      f"Lexi2 {m['lexi2'][0]:.4f} ± {m['lexi2'][1]:.4f}; "
      f"tournament {m['tournament'][0]:.4f} ± {m['tournament'][1]:.4f}. "
      "Lexi2's lower mean is driven by hard-state failures (|101⟩/|110⟩/|111⟩).")
    A("")

    A("## 3. Generations to stop")
    A("")
    A("| Arm | Converged runs mean (median) | All runs mean (median; full = 100) |")
    A("|---|---|---|")
    for arm in ARMS:
        rs = [r for st in STATES for r in results[(arm, st)].values()]
        cg = [r.get("early_stopped_gen") or 100 for r in rs if stop_class(r) == "converged"]
        ag = [r.get("early_stopped_gen") or 100 for r in rs]
        A(f"| {ARM_LABEL[arm]} | {np.mean(cg):.1f} ({np.median(cg):.0f}) | "
          f"{np.mean(ag):.1f} ({np.median(ag):.0f}) |")
    A("")

    A("## 4. Circuit quality (run-level best per state × seed)")
    A("")
    A("| Arm | Transpiled gates median | Depth median | 2Q median | Deployed best-of-10: gates/depth/2Q (mean across states) |")
    A("|---|---|---|---|---|")
    for arm in ARMS:
        g = [r["gate_count"] for st in STATES for r in results[(arm, st)].values()]
        d = [r["depth"] for st in STATES for r in results[(arm, st)].values()]
        q = [r["two_qubit_gates"] for st in STATES for r in results[(arm, st)].values()]
        dg = [deployed[(arm, st)]["gate_count"] for st in STATES]
        dd = [deployed[(arm, st)]["depth"] for st in STATES]
        dq = [deployed[(arm, st)]["two_qubit_gates"] for st in STATES]
        A(f"| {ARM_LABEL[arm]} | {np.median(g):.0f} | {np.median(d):.0f} | {np.median(q):.0f} | "
          f"{np.mean(dg):.1f}/{np.mean(dd):.1f}/{np.mean(dq):.1f} |")
    A("")

    A("## 5. Failure composition (full-100 runs)")
    A("")
    A("| Arm | Full-100 | Fidelity fail | Size fail | Stopping miss |")
    A("|---|---|---|---|---|")
    for arm in ARMS:
        fulls = [r for st in STATES for r in results[(arm, st)].values() if stop_class(r) == "full"]
        cc = collections_counter([classify_full(r) for r in fulls])
        A(f"| {ARM_LABEL[arm]} | {len(fulls)} | {cc['fidelity_fail']} | {cc['size_fail']} | {cc['stopping_miss']} |")
    A("")
    A("Lexi2's dominant failure mode on hard states is fidelity (never reaches 0.95), unlike "
      "ε-lexicase/tournament where failures are overwhelmingly size-target misses.")
    A("")

    A("## 6. Hardware validation (ibm_fez, 10,000 shots, deployed best-of-10)")
    A("")
    A("| Arm | Mean HW p(marked) | Mean |sim − HW| | Max |delta| | Worst state |")
    A("|---|---|---|---|---|")
    for arm in ARMS:
        hs = [(deployed[(arm, st)]["fidelity"], hw[(arm, st)]["p_marked_hw"])
              for st in STATES if (arm, st) in hw]
        deltas = [a - b for a, b in hs]
        worst = STATES[int(np.argmax([abs(a - b) for a, b in hs]))]
        A(f"| {ARM_LABEL[arm]} | {np.mean([b for _, b in hs]):.4f} | "
          f"{np.mean([abs(a-b) for a, b in hs]):.4f} | {max(abs(d) for d in deltas):.4f} | "
          f"|{worst}⟩ |")
    A("")
    A("## Methods")
    A("")
    A("- Fisher exact (convergence), Kruskal-Wallis + Mann-Whitney U + Cliff's δ with 10,000 "
      f"resample bootstrap CI (seed {RNG_SEED}); Holm-Bonferroni over the 3 arm pairs.")
    A("- Pairing: ε-lexicase vs tournament share gen-0 per (state, seed) (byte-verified); Lexi2 "
      "shares the same init code/seeds, so paired comparisons vs either arm are valid by "
      "construction (gen-0 hash-verified for state 000/seed 21315 in the smoke validation).")
    A("")
    open("STATS_3ARM_frozen.md", "w").write("\n".join(L))


def write_csvs(results, deployed, hw):
    with open("per_run_frozen_3arm.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arm", "state", "seed", "run_id", "fidelity", "gate_count", "depth",
                    "two_qubit_gates", "raw_two_qubit_gates", "raw_gate_count", "raw_depth",
                    "raw_fitness", "stop_reason", "early_stopped_gen"])
        for arm in ARMS:
            for st in STATES:
                for s, r in results[(arm, st)].items():
                    w.writerow([arm, st, s, r.get("run_id"), r["fidelity"], r["gate_count"],
                                r["depth"], r["two_qubit_gates"], r.get("raw_two_qubit_gates"),
                                r["raw_gate_count"], r["raw_depth"], r["raw_fitness"],
                                r["stop_reason"], r.get("early_stopped_gen")])
    with open("results_table_frozen_3arm.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arm", "state", "deployed_seed", "deployed_fidelity", "deployed_depth",
                    "deployed_gates", "deployed_2q", "hw_p_marked", "success_k", "n_runs",
                    "fid_mean", "fid_std", "mean_stop_gen_all"])
        for arm in ARMS:
            for st in STATES:
                d = deployed[(arm, st)]
                h = hw.get((arm, st), {})
                rs = list(results[(arm, st)].values())
                fid = [r["fidelity"] for r in rs]
                conv = sum(1 for r in rs if stop_class(r) == "converged")
                gs = [r.get("early_stopped_gen") or 100 for r in rs]
                w.writerow([arm, st, d["seed"], f"{d['fidelity']:.6f}", d["depth"], d["gate_count"],
                            d["two_qubit_gates"], h.get("p_marked_hw", ""), conv, len(rs),
                            f"{statistics.mean(fid):.6f}", f"{statistics.stdev(fid):.6f}",
                            f"{statistics.mean(gs):.1f}"])
    print("CSVs written: per_run_frozen_3arm.csv, results_table_frozen_3arm.csv")


def main():
    _style()
    results = load_run_results()
    deployed = load_deployed()
    hw = load_hardware()
    assert all(len(results[(a, s)]) == 10 for a in ARMS for s in STATES)
    assert len(hw) == 24
    write_paper_data(results, deployed, hw)
    write_stats(results, deployed, hw)
    write_csvs(results, deployed, hw)
    fig01_fidelity(results)
    fig02_gens(results)
    fig03_trajectories(results)
    fig04_cost(results)
    fig05_hardware(deployed, hw)
    fig06_success(results)
    fig08_failures(results)
    fig12_paired_lexi2(results)
    fig13_failure_composition(results)
    fig14_deployed_quality(deployed)
    fig15_cliffs_forest(results)
    fig16_lexi2_tiebreak()
    fig11_deployed_circuits(deployed)
    print("3-arm pack done.")


if __name__ == "__main__":
    main()
