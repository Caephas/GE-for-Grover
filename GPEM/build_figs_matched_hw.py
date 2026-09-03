#!/usr/bin/env python3
"""Regenerate the paper hardware figure(s) from the matched-window session
(2026-09-02) logs, so every plotted/table hardware number in the paper refers to
the same calibration window.

Reads ONLY completed artifacts (session logs + deployed_best.json); no
experiments and no hardware jobs are run.
"""

from __future__ import annotations

import glob
import json
import os
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ARMS = ["epsilon_lexicase", "lexi2", "tournament"]
ARM_LABEL = {"epsilon_lexicase": r"$\varepsilon$-lexicase", "lexi2": "Lexi2",
             "tournament": "tournament"}
ARM_COLOR = {"epsilon_lexicase": "#0b5394", "lexi2": "#2e7d32", "tournament": "#b45f06"}
ROOTS = {"epsilon_lexicase": "experiments_frozen_10seed",
         "tournament": "experiments_frozen_10seed",
         "lexi2": "experiments_frozen_10seed_lexi2"}
STATES = ["000", "001", "010", "011", "100", "101", "110", "111"]
SESSION_DIR = "logs_hardware_session_2026-09-02"
FIG_DIR = "paper_figures/frozen_10seed"
PAPER_FIG_DIR = "gpem_paper/figures"


def load_matched_hw() -> dict:
    out = {}
    for f in glob.glob(os.path.join(SESSION_DIR, "*.json")):
        d = json.load(open(f))
        if d.get("circuit_kind") != "deployed":
            continue
        out[(d["arm"], d["target_state"])] = d
    assert len(out) == 24, f"expected 24 deployed session results, got {len(out)}"
    return out


def load_deployed_sim() -> dict:
    out = {}
    for arm in ARMS:
        for st in STATES:
            p = os.path.join(ROOTS[arm], arm, "pop300", "noise",
                             f"state_{st}", "deployed_best.json")
            out[(arm, st)] = json.load(open(p))["fidelity"]
    return out


def main() -> None:
    hw = load_matched_hw()
    sim = load_deployed_sim()

    fig, ax = plt.subplots(figsize=(6.6, 5.6))
    for arm in ARMS:
        xs, ys = [], []
        for st in STATES:
            xs.append(sim[(arm, st)])
            ys.append(hw[(arm, st)]["p_marked_hw"])
        ax.scatter(xs, ys, s=55, color=ARM_COLOR[arm], label=ARM_LABEL[arm],
                   alpha=0.9, edgecolors="white", lw=0.5)
        for st, xv, yv in zip(STATES, xs, ys):
            ax.annotate(f"$|{st}\\rangle$", (xv, yv), textcoords="offset points",
                        xytext=(4, 4), fontsize=7, color=ARM_COLOR[arm])
    lim = (0.90, 1.0)
    ax.plot(lim, lim, "k--", lw=1)
    ax.set_xlim(*lim)
    ax.set_ylim(*lim)
    ax.set_xlabel("deployed simulated fidelity (frozen target)")
    ax.set_ylabel("hardware p(marked), ibm_fez, 10k shots")
    ax.set_aspect("equal")
    ax.legend(frameon=False)
    ax.set_title("Simulation-to-hardware validation (24 circuits, 3 arms, "
                 "matched window 2026-09-02)")
    fig.tight_layout()
    pdf = os.path.join(FIG_DIR, "fig05_hardware_validation.pdf")
    png = os.path.join(FIG_DIR, "fig05_hardware_validation.png")
    fig.savefig(pdf)
    fig.savefig(png, dpi=200)
    shutil.copy(pdf, os.path.join(PAPER_FIG_DIR, "fig05_hardware_validation.pdf"))
    print("wrote", pdf, png)


if __name__ == "__main__":
    main()
