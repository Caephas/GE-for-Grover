#!/usr/bin/env python3
"""Two-panel Lexi2 mechanism figure (paper Fig. 15 / fig16):

left:  size-tiebreak firing rate by generation (overall / converged /
       non-converged), from lexi2_tiebreak_firerate_bygen.csv;
right: mean and median post-case survivor-pool size by generation (all runs),
       from survivor_pool_lexi2_bygen.csv.

Reads existing CSVs only; no experiments run. Writes PDF+PNG into
paper_figures/frozen_10seed/ and copies the PDF into gpem_paper/figures/.
"""

from __future__ import annotations

import csv
import os
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

FIG_DIR = "paper_figures/frozen_10seed"
PAPER_FIG_DIR = "gpem_paper/figures"


def read_csv(path: str) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


def series(rows: list[dict], key: str) -> tuple[list[int], list[float]]:
    gs, vs = [], []
    for r in rows:
        gs.append(int(r["generation"]))
        v = r[key].strip()
        vs.append(float(v) if v not in ("", "-") else float("nan"))
    return gs, vs


def main() -> None:
    fire = read_csv("lexi2_tiebreak_firerate_bygen.csv")
    pool = read_csv("survivor_pool_lexi2_bygen.csv")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.6, 3.9))

    gs = [int(r["generation"]) for r in fire]
    ax1.plot(gs, series(fire, "overall_fire_rate")[1],
             color="#2e7d32", lw=1.7, label="overall (80 runs)")
    ax1.plot(gs, series(fire, "converged_fire_rate")[1],
             color="#1f77b4", lw=1.5, ls="--", label="converged (55 runs)")
    ax1.plot(gs, series(fire, "nonconverged_fire_rate")[1],
             color="#d62728", lw=1.5, ls=":", label="non-converged (25 runs)")
    ax1.set_xlabel("generation")
    ax1.set_ylabel("tiebreak-fire rate (per selection)")
    ax1.set_ylim(-0.02, 1.03)
    ax1.legend(frameon=False, fontsize=8.5, loc="center right")
    ax1.set_title("Size-tiebreak firing rate (80 runs)")

    g2 = [int(r["generation"]) for r in pool]
    ax2.plot(g2, [float(r["mean_pool_size_all"]) for r in pool],
             color="#2e7d32", lw=1.7, label="mean")
    ax2.plot(g2, [float(r["median_pool_size_all"]) for r in pool],
             color="#555555", lw=1.2, ls="--", label="median")
    ax2.set_xlabel("generation")
    ax2.set_ylabel("post-case survivor-pool size")
    ax2.set_ylim(0, 11)
    ax2.legend(frameon=False, fontsize=8.5, loc="center right")
    ax2.set_title("Post-case survivor-pool size (80 runs)")

    fig.suptitle("Lexi2 per-generation mechanism (Douglas logging)", y=1.03,
                 fontsize=11)
    fig.tight_layout()
    pdf = os.path.join(FIG_DIR, "fig16_lexi2_tiebreak_firerate.pdf")
    png = os.path.join(FIG_DIR, "fig16_lexi2_tiebreak_firerate.png")
    fig.savefig(pdf)
    fig.savefig(png, dpi=200)
    shutil.copy(pdf, os.path.join(PAPER_FIG_DIR, "fig16_lexi2_tiebreak_firerate.pdf"))
    print("wrote", pdf, png)


if __name__ == "__main__":
    main()
