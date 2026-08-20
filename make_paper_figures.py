"""Render the analysis figures at print resolution into paper_figures/.

Re-plots from the saved experiment CSVs only (no experiments re-run).
Produces 300-dpi PNGs and vector PDFs for the three analysis figures.
"""

from __future__ import annotations

import os

import plot_diversity_converged_vs_stalled as m1
import plot_diversity_lexicase_vs_tournament as m2
import plot_failed_fidelity_lexicase_vs_tournament as m3


def main() -> None:
    os.makedirs("paper_figures", exist_ok=True)
    for mod in (m1, m2, m3):
        mod.DPI = 300
        mod.OUT_PNG = os.path.join("paper_figures", os.path.basename(mod.OUT_PNG))
        mod.OUT_PDF = os.path.join("paper_figures", os.path.basename(mod.OUT_PDF))
        mod.main()
    print("\npaper_figures/ ready (300-dpi PNG + vector PDF per figure)")


if __name__ == "__main__":
    main()
