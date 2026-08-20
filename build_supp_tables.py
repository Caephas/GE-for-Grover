"""Build SUPP_TABLES.md: LaTeX-ready supplementary tables from existing files.

Read-only: aggregates, diagnostics, hardware JSONs, calibration CSV.
No experiments are re-run.
"""

from __future__ import annotations

import csv
import glob
import json
import os
import re
import statistics
from collections import Counter

import numpy as np
import pandas as pd
from scipy import stats

ROOT = os.path.dirname(os.path.abspath(__file__))
SEEDS = [21315, 47182, 12147, 33537, 70300]
STATES = ["000", "001", "010", "011", "100", "101", "110", "111"]
SUCCESS = 0.95
CONV = 0.90
WINDOW = 15
OUT = os.path.join(ROOT, "SUPP_TABLES.md")

TOURNAMENT_CLAIMED = {
    "000": [0.977, 0.978, 0.980, 0.981, 0.578],
    "001": [0.987, 0.977, 0.969, 0.986, 0.507],
    "010": [0.978, 0.980, 0.501, 0.509, 0.497],
    "011": [0.978, 0.975, 0.550, 0.490, 0.958],
    "100": [0.506, 0.979, 0.962, 0.978, 0.487],
    "101": [0.489, 0.492, 0.967, 0.482, 0.547],
    "110": [0.481, 0.980, 0.977, 0.511, 0.483],
    "111": [0.961, 0.987, 0.485, 0.977, 0.500],
}


def load_agg(sel: str, state: str) -> dict:
    p = os.path.join(ROOT, "experiments", sel, "pop300", "noise", f"state_{state}",
                     f"AGGREGATE_{state}.json")
    return json.load(open(p))


def per_seed_fids(sel: str, state: str) -> dict[int, float]:
    agg = load_agg(sel, state)
    return {r["seed"]: r["fidelity"] for r in agg["per_run"]}


def norm_reason(reason: str) -> str:
    reason = (reason or "").strip()
    if not reason:
        return "Unknown"
    for sep in (" at ", ": "):
        if sep in reason:
            reason = reason.split(sep, 1)[0]
    return reason or "Unknown"


def stop_reasons(sel: str, state: str) -> Counter:
    agg = load_agg(sel, state)
    return Counter(norm_reason(r.get("stop_reason")) for r in agg["per_run"])


def match_hw_file(hw: dict, per_run: list) -> dict | None:
    fe = hw.get("fitness_evolution")
    for r in per_run:
        rf = r.get("raw_fitness")
        if not isinstance(fe, (int, float)) or not isinstance(rf, (int, float)):
            continue
        if abs(rf - fe) > 1e-6:
            continue
        if r.get("raw_gate_count") != hw.get("original_gates") or r.get("raw_depth") != hw.get("original_depth"):
            continue
        return r
    return None


def deployed_hw(sel: str, state: str) -> dict | None:
    per_run = load_agg(sel, state)["per_run"]
    matched = []
    for f in glob.glob(os.path.join(ROOT, "experiments", sel, "pop300", "noise",
                                    f"state_{state}", "**", "hof_*_ibm_hardware_data.json"), recursive=True):
        try:
            hw = json.load(open(f))
        except Exception:
            continue
        r = match_hw_file(hw, per_run)
        if r is not None:
            hw["_path"] = f
            hw["_mtime"] = os.path.getmtime(f)
            hw["_run"] = r
            matched.append(hw)
    if not matched:
        return None
    return max(matched, key=lambda h: h["_mtime"])


def latex_fid(v: float) -> str:
    s = f"{v:.3f}"
    return f"\\textbf{{{s}}}" if v >= SUCCESS else s


def mechanism_check() -> tuple[list[str], list[tuple]]:
    def load(method):
        return [pd.read_csv(f) for f in sorted(glob.glob(
            os.path.join(ROOT, "experiments", method, "pop300", "noise",
                         "state_*", "run_*", "diagnostics_*.csv")))]
    lex, tour = load("epsilon_lexicase"), load("tournament")
    def grp(runs):
        return [(df, "converged" if df.fidelity_max.max() >= CONV else "failed") for df in runs]
    lex_g, tour_g = grp(lex), grp(tour)
    lex_f = [df for df, gg in lex_g if gg == "failed"]
    tour_f = [df for df, gg in tour_g if gg == "failed"]
    lpk = [df.fidelity_max.max() for df in lex_f]
    tpk = [df.fidelity_max.max() for df in tour_f]
    p = stats.mannwhitneyu(lpk, tpk, alternative="two-sided").pvalue

    conv_l = [df[df.generation <= WINDOW].unique_behaviors.mean() for df, gg in lex_g if gg == "converged"]
    conv_t = [df[df.generation <= WINDOW].unique_behaviors.mean() for df, gg in tour_g if gg == "converged"]
    fail_l = [df[df.generation <= WINDOW].unique_behaviors.mean() for df, gg in lex_g if gg == "failed"]
    fail_t = [df[df.generation <= WINDOW].unique_behaviors.mean() for df, gg in tour_g if gg == "failed"]

    rows = [
        ("Diversity converged (\\% of pop)", "lex 70.3\\% / tour 79.2\\%",
         f"lex {np.mean(conv_l)/300*100:.1f}\\% (mean {np.mean(conv_l):.1f}/300) / "
         f"tour {np.mean(conv_t)/300*100:.1f}\\% (mean {np.mean(conv_t):.1f}/300)"),
        ("Diversity failed (\\% of pop)", "lex 66.9\\% / tour 76.4\\%",
         f"lex {np.mean(fail_l)/300*100:.1f}\\% (mean {np.mean(fail_l):.1f}/300) / "
         f"tour {np.mean(fail_t)/300*100:.1f}\\% (mean {np.mean(fail_t):.1f}/300)"),
        ("Failed crossing $\\geq$ 0.6", "lex 0\\% / tour 24\\%",
         f"lex {np.mean([x >= 0.6 for x in lpk])*100:.0f}\\% (n={len(lpk)}) / "
         f"tour {np.mean([x >= 0.6 for x in tpk])*100:.0f}\\% (n={len(tpk)})"),
        ("Failed mean peak fid", "lex 0.549 / tour 0.614",
         f"lex {np.mean(lpk):.4f} / tour {np.mean(tpk):.4f}"),
        ("Failed median peak fid", "lex 0.563 / tour 0.583",
         f"lex {np.median(lpk):.4f} / tour {np.median(tpk):.4f}"),
        ("Mann-Whitney p", "0.17", f"{p:.4f} (n={len(lpk)} vs {len(tpk)})"),
    ]
    # numeric OK checks
    checks = [
        (abs(np.mean(conv_l) / 3 - 70.3) < 0.06 and abs(np.mean(conv_t) / 3 - 79.2) < 0.06),
        (abs(np.mean(fail_l) / 3 - 66.9) < 0.06 and abs(np.mean(fail_t) / 3 - 76.4) < 0.06),
        (abs(np.mean([x >= 0.6 for x in lpk]) - 0.0) < 1e-9 and abs(np.mean([x >= 0.6 for x in tpk]) - 4 / 17) < 1e-9),
        (abs(np.mean(lpk) - 0.549) < 0.0006 and abs(np.mean(tpk) - 0.614) < 0.0006),
        (abs(np.median(lpk) - 0.563) < 0.0006 and abs(np.median(tpk) - 0.583) < 0.0006),
        (abs(p - 0.17) < 0.01),
    ]
    for i, (label, claimed, got) in enumerate(rows):
        rows[i] = (label, claimed, got, "OK" if checks[i] else "MISMATCH")
    detail = [
        f"converged n: lex {len(conv_l)} / tour {len(conv_t)}; failed n: lex {len(fail_l)} / tour {len(fail_t)}",
        f"failed peak max (lex): {max(lpk):.4f}; failed peak max (tour): {max(tpk):.4f}",
    ]
    return detail, rows


def main() -> None:
    L: list[str] = []
    L.append("# SUPP_TABLES — LaTeX-ready supplementary tables")
    L.append("")
    L.append("Assembled %s from existing aggregates, diagnostics, hardware JSONs and the calibration CSV. "
             "No experiments were re-run. Seed column order: 21315, 47182, 12147, 33537, 70300." % pd.Timestamp.now().strftime("%Y-%m-%d"))
    L.append("")

    # ---------------- 1. Lexicase per-seed fidelities ----------------
    L.append("## Table 1 — Epsilon-lexicase pop300 per-seed final fidelity")
    L.append("")
    L.append("\\begin{tabular}{lccccc}")
    L.append("\\hline")
    L.append("State & 21315 & 47182 & 12147 & 33537 & 70300 \\\\")
    L.append("\\hline")
    for state in STATES:
        f = per_seed_fids("epsilon_lexicase", state)
        cells = " & ".join(latex_fid(f[s]) for s in SEEDS)
        L.append(f"$\\ket{{{state}}}$ & {cells} \\\\")
    L.append("\\hline")
    L.append("\\end{tabular}")
    L.append("")
    L.append("*Values \\geq 0.95 in bold.*")
    L.append("")

    # ---------------- 2. Tournament verification ----------------
    L.append("## Table 2 — Tournament pop300 per-seed final fidelity (verified)")
    L.append("")
    mismatches = []
    borderline = []
    L.append("\\begin{tabular}{lccccc}")
    L.append("\\hline")
    L.append("State & 21315 & 47182 & 12147 & 33537 & 70300 \\\\")
    L.append("\\hline")
    for state in STATES:
        f = per_seed_fids("tournament", state)
        got = [f[s] for s in SEEDS]
        claimed = TOURNAMENT_CLAIMED[state]
        for i, (g, c) in enumerate(zip(got, claimed)):
            if abs(g - c) > 0.00051:
                mismatches.append((state, SEEDS[i], c, g, abs(g - c)))
            elif abs((g * 1000) % 1 - 0.5) < 1e-6:
                borderline.append((state, SEEDS[i], c, g, abs(g - c)))
        cells = " & ".join(latex_fid(v) for v in got)
        L.append(f"$\\ket{{{state}}}$ & {cells} \\\\")
    L.append("\\hline")
    L.append("\\end{tabular}")
    L.append("")
    if mismatches:
        L.append("**Verification: MISMATCHES FOUND** (claimed vs extracted):")
        for st, seed, c, g, d in mismatches:
            L.append(f"- state {st}, seed {seed}: claimed {c:.3f} vs extracted {g:.4f} (|diff|={d:.4f})")
    elif borderline:
        L.append("**Verification: no substantive mismatches.** "
                 + "; ".join(f"state {st}/seed {seed}: claimed {c:.3f}, exact {g:.4f}" for st, seed, c, g, _ in borderline)
                 + " — these sit exactly on the 3rd-decimal rounding boundary (half-way cases).")
    else:
        L.append("**Verification: all 8 states match the supplied values exactly (3-decimal rounding).**")
    L.append("")

    # ---------------- 3. Stop reasons ----------------
    L.append("## Table 3 — Stop-reason counts (per state, 5 runs; reasons normalized)")
    L.append("")
    cats = ["Hardware targets achieved", "Fidelity stagnant", "Hardware metrics stagnant",
            "completed_all_generations", "Unknown"]
    for sel, name in (("epsilon_lexicase", "epsilon-lexicase"), ("tournament", "tournament")):
        L.append(f"### {name} pop300")
        L.append("")
        L.append("\\begin{tabular}{l" + "c" * len(cats) + "}")
        L.append("\\hline")
        L.append("State & " + " & ".join(cats) + " \\\\")
        L.append("\\hline")
        for state in STATES:
            c = stop_reasons(sel, state)
            total = sum(c.values())
            if total != 5:
                L.append(f"$\\ket{{{state}}}$ & " + " & ".join(str(c.get(k, 0)) for k in cats) +
                         f" \\\\  % WARNING: counts sum to {total}")
            else:
                L.append(f"$\\ket{{{state}}}$ & " + " & ".join(str(c.get(k, 0)) for k in cats) + " \\\\")
        L.append("\\hline")
        L.append("\\end{tabular}")
        L.append("")

    # ---------------- 4. Hardware job metadata ----------------
    L.append("## Table 4 — Hardware job metadata (deployed best-fidelity circuit per state)")
    L.append("")
    L.append("\\begin{tabular}{lcccccl}")
    L.append("\\hline")
    L.append("Method & State & Seed & Job ID & Timestamp & Transpiled D/G & p\\_marked \\\\")
    L.append("\\hline")
    missing = []
    for sel, name in (("epsilon_lexicase", "epsilon-lexicase"), ("tournament", "tournament")):
        for state in STATES:
            hw = deployed_hw(sel, state)
            if hw is None:
                missing.append((name, state))
                L.append(f"{name} & $\\ket{{{state}}}$ & -- & missing & -- & -- & -- \\\\")
                continue
            run = hw["_run"]
            ts = str(hw.get("timestamp", ""))[:19]
            L.append(f"{name} & $\\ket{{{state}}}$ & {run['seed']} & \\texttt{{{hw.get('job_id')}}} & "
                     f"{ts} & {hw.get('transpiled_depth')}/{hw.get('transpiled_gates')} & "
                     f"{hw.get('p_marked_hw'):.4f} \\\\")
    L.append("\\hline")
    L.append("\\end{tabular}")
    L.append("")
    if missing:
        L.append("**Missing hardware files:** " + "; ".join(f"{m} {s}" for m, s in missing))
    L.append("")
    L.append("Provenance: lexicase |101> and |111> are August re-deployments with the deployed run's own seed; "
             "lexicase |110> was restored from its July job (d9j4ifibr2fc73e5er6g); tournament |100>/|110> were "
             "recovered from jobs d9r56tftfhrs73dr76ig / d9r1tthdsedc73ag263g. Remaining rows are the original "
             "July (lexicase) / August (tournament) runs.")
    L.append("")

    # ---------------- 5. Calibration comparison ----------------
    L.append("## Table 5 — ibm_fez calibration, July vs August sweep windows")
    L.append("")
    cal = {}
    with open(os.path.join(ROOT, "calibration_ibm_fez_july_vs_august.csv")) as f:
        for row in csv.DictReader(f):
            if row["section"] == "july_vs_august" and row["key"] in ("July window", "August window", "delta (Aug-Jul)"):
                cal.setdefault(row["metric"], {})[row["key"]] = row["value"]
    pretty = {
        "T1_median_us": "T1 median (us)",
        "T2_median_us": "T2 median (us)",
        "readout_error_median": "readout error median",
        "single_q_gate_error_median": "1Q gate error median (sx/x)",
        "two_q_gate_error_median": "2Q gate error median (ECR)",
        "two_q_gate_error_mean": "2Q gate error mean",
    }
    L.append("\\begin{tabular}{lccc}")
    L.append("\\hline")
    L.append("Metric & July & August & Delta \\\\")
    L.append("\\hline")
    for k, label in pretty.items():
        d = cal.get(k, {})
        L.append(f"{label} & {d.get('July window', '?')} & {d.get('August window', '?')} & "
                 f"{d.get('delta (Aug-Jul)', '?')} \\\\")
    L.append("\\hline")
    L.append("\\end{tabular}")
    L.append("")

    # ---------------- 6. Mechanism verification ----------------
    L.append("## Table 6 — Mechanism numbers: verification against source diagnostics")
    L.append("")
    L.append("\\begin{tabular}{llll}")
    L.append("\\hline")
    L.append("Metric & Claimed & Recomputed & Match \\\\")
    L.append("\\hline")
    mech_detail, mech_rows = mechanism_check()
    for label, claimed, got, match in mech_rows:
        L.append(f"{label} & {claimed} & {got} & {match} \\\\")
    L.append("\\hline")
    L.append("\\end{tabular}")
    L.append("")
    L.append("Recomputation detail:")
    for line in mech_detail:
        L.append(f"- {line}")
    L.append("")

    with open(OUT, "w") as f:
        f.write("\n".join(L))
    print(f"wrote {OUT} ({len(L)} lines)")
    print("tournament mismatches:", mismatches if mismatches else "none")


if __name__ == "__main__":
    main()
