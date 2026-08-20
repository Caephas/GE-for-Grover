#!/usr/bin/env python3
"""Assemble PAPER_DATA.md from existing experiment files (read-only, no re-runs)."""

from __future__ import annotations

import ast
import glob
import json
import os
import platform
import re
import statistics
from collections import Counter
from importlib.metadata import version

import numpy as np
import pandas as pd
from scipy import stats

ROOT = os.path.dirname(os.path.abspath(__file__))
STATES = ["000", "001", "010", "011", "100", "101", "110", "111"]
SUCCESS = 0.95
CONV = 0.90
WINDOW = 15
OUT = os.path.join(ROOT, "PAPER_DATA.md")

CONFIG_ASSIGN = re.compile(r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.+?)(\s*#.*)?$")


def agg_path(selection: str, pop: int, state: str) -> str:
    return os.path.join(ROOT, "experiments", selection, f"pop{pop}", "noise",
                       f"state_{state}", f"AGGREGATE_{state}.json")


def load_agg(selection: str, pop: int, state: str) -> dict | None:
    p = agg_path(selection, pop, state)
    if os.path.exists(p):
        return json.load(open(p))
    if pop == 100 and selection == "epsilon_lexicase":
        p2 = os.path.join(ROOT, "experiments_epsilon_lexicase_noise_pop100",
                          f"state_{state}", f"AGGREGATE_{state}.json")
        if os.path.exists(p2):
            return json.load(open(p2))
    return None


def diagnostics(selection: str, pop: int) -> list[pd.DataFrame]:
    runs = []
    for f in sorted(glob.glob(os.path.join(ROOT, "experiments", selection, f"pop{pop}",
                                           "noise", "state_*", "run_*", "diagnostics_*.csv"))):
        runs.append(pd.read_csv(f))
    return runs


def match_hardware_file(hw: dict, per_run: list) -> dict | None:
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


def hardware_files(selection: str, pop: int, state: str) -> list[dict]:
    out = []
    for f in sorted(glob.glob(os.path.join(
            ROOT, "experiments", selection, f"pop{pop}", "noise",
            f"state_{state}", "**", "hof_*_ibm_hardware_data.json"), recursive=True)):
        try:
            hw = json.load(open(f))
        except Exception:
            continue
        hw["_path"] = f
        hw["_mtime"] = os.path.getmtime(f)
        out.append(hw)
    return sorted(out, key=lambda h: h["_mtime"])


def newest_hardware(selection: str, pop: int, state: str, per_run: list) -> tuple[dict | None, list]:
    """Return (newest matched hardware file, list of all matched files)."""
    matched = []
    for hw in hardware_files(selection, pop, state):
        r = match_hardware_file(hw, per_run)
        if r is not None:
            matched.append((hw, r))
    if not matched:
        return None, []
    newest = max(matched, key=lambda t: t[0]["_mtime"])
    return newest, matched


def fnum(v, nd=4):
    return "N/A" if v is None else f"{v:.{nd}f}"


def stop_tally(per_run: list) -> dict:
    def norm(reason: str) -> str:
        reason = (reason or "").strip()
        if not reason:
            return "Unknown"
        for sep in (" at ", ": "):
            if sep in reason:
                reason = reason.split(sep, 1)[0]
        return reason or "Unknown"
    return dict(Counter(norm(r.get("stop_reason")) for r in per_run))


def main_table(selection: str, pop: int, label: str) -> list[str]:
    lines = []
    lines.append(f"### {label} (one row per state, {selection}, pop{pop})")
    lines.append("")
    lines.append("| State | Best sim fid | Seed | Transpiled D/G/2Q | Raw D/G | HW p_marked | HW seed | HW seed sim fid | HW job_id | HW timestamp | Success (k/5) | Mean±std fid | Mean stop gen | Stop reasons |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    total_k = 0
    for state in STATES:
        agg = load_agg(selection, pop, state)
        if agg is None:
            lines.append(f"| {state} | MISSING AGGREGATE | | | | | | | | | | | | |")
            continue
        per = agg["per_run"]
        best = max(per, key=lambda r: (r["fidelity"], -r["two_qubit_gates"], -r["depth"]))
        fids = [r["fidelity"] for r in per]
        k = sum(f >= SUCCESS for f in fids)
        total_k += k
        hw, matched = newest_hardware(selection, pop, state, per)
        if hw:
            hfile, hrun = hw
            hw_p = fnum(hfile.get("p_marked_hw"))
            hw_seed = hrun["seed"]
            hw_sim = fnum(hrun["fidelity"])
            hw_job = hfile.get("job_id", "?")
            hw_ts = str(hfile.get("timestamp", ""))[:19]
        else:
            hw_p = hw_seed = hw_sim = "N/A"
            hw_job = hw_ts = "no hof file on disk"
        lines.append(
            f"| {state} | {fnum(best['fidelity'])} | {best['seed']} | "
            f"{best['depth']}/{best['gate_count']}/{best['two_qubit_gates']} | "
            f"{best['raw_depth']}/{best['raw_gate_count']} | {hw_p} | {hw_seed} | {hw_sim} | "
            f"{hw_job} | {hw_ts} | {k}/5 | "
            f"{fnum(statistics.mean(fids))}±{fnum(statistics.stdev(fids) if len(fids) > 1 else 0.0)} | "
            f"{fnum(statistics.mean([r['early_stopped_gen'] for r in per]), 1)} | "
            f"{json.dumps(stop_tally(per))} |")
        if len(matched) > 1:
            olds = ", ".join(f"{os.path.basename(os.path.dirname(h['_path']))}: {fnum(h.get('p_marked_hw'))} "
                             f"({h.get('timestamp','')[:10]})" for h, _ in matched[:-1])
            lines.append(f"  _note: {state} has additional older matched hardware file(s): {olds}_")
    lines.append("")
    lines.append(f"Overall converged runs (fidelity >= {SUCCESS}): **{total_k}/40** "
                 f"({total_k / 40 * 100:.0f}%)")
    lines.append("")
    return lines


def section_h_config() -> list[str]:
    nb = json.load(open(os.path.join(ROOT, "ibm_lexicase_transpiled_111.ipynb")))
    vals: dict = {}
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        lines = list(cell["source"])
        i = 0
        while i < len(lines):
            line = lines[i]
            m = CONFIG_ASSIGN.match(line)
            if not m:
                i += 1
                continue
            name, rhs = m.group(1), m.group(2).strip()
            if rhs.endswith("{") and rhs.count("{") > rhs.count("}"):
                buf = [rhs]
                while i + 1 < len(lines) and sum(l.count("{") for l in buf) > sum(l.count("}") for l in buf):
                    i += 1
                    buf.append(lines[i].strip())
                rhs = " ".join(buf)
            if name in ("POPULATION_SIZE", "MAX_GENERATIONS", "NUMBER_OF_RUNS", "RUN_SEEDS",
                        "TOURNAMENT_SIZE", "GATE_PENALTY_WEIGHT", "SUCCESS_THRESHOLD", "NUM_SHOTS",
                        "MAX_EXPECTED_GATES", "MAX_EXPECTED_DEPTH", "USE_NOISE_MODEL", "ELITE_SIZE",
                        "P_CROSSOVER", "P_MUTATION", "HALLOFFAME_SIZE", "CODON_SIZE", "MAX_TREE_DEPTH",
                        "MIN_INIT_DEPTH", "MAX_INIT_DEPTH", "CODON_CONSUMPTION", "GENOME_REPRESENTATION",
                        "EARLY_STOPPING_MODE", "MIN_GENERATIONS_BEFORE_STOPPING",
                        "FIDELITY_SUCCESS_THRESHOLD", "GATE_COUNT_TARGET", "DEPTH_TARGET",
                        "EARLY_STOPPING_PATIENCE", "MIN_IMPROVEMENT_DELTA", "METRIC_WEIGHTS",
                        "EARLY_STOPPING_STRATEGY", "MOVING_AVERAGE_WINDOW", "USE_RELATIVE_IMPROVEMENT",
                        "CHECKPOINT_FREQUENCY", "RESUME_FROM_CHECKPOINT", "USE_TRANSFER_LEARNING"):
                try:
                    vals[name] = ast.literal_eval(rhs)
                except Exception:
                    pass
            i += 1
    v = lambda k: vals.get(k)
    L = []
    L.append("### H. Experimental configuration")
    L.append("")
    L.append("**Evolution:** population size %s; max generations %s; %s runs per state; seeds %s." % (
        v("POPULATION_SIZE"), v("MAX_GENERATIONS"), v("NUMBER_OF_RUNS"), v("RUN_SEEDS")))
    L.append("Crossover probability %s; mutation probability %s; elite size %s; HOF size %s; "
             "codon size %s; max tree depth %s; init depth %s-%s; codon consumption %s; "
             "genome representation %s." % (
        v("P_CROSSOVER"), v("P_MUTATION"), v("ELITE_SIZE"), v("HALLOFFAME_SIZE"), v("CODON_SIZE"),
        v("MAX_TREE_DEPTH"), v("MIN_INIT_DEPTH"), v("MAX_INIT_DEPTH"), v("CODON_CONSUMPTION"),
        v("GENOME_REPRESENTATION")))
    L.append("Checkpoint frequency %s; resume-from-checkpoint %s; transfer learning %s." % (
        v("CHECKPOINT_FREQUENCY"), v("RESUME_FROM_CHECKPOINT"), v("USE_TRANSFER_LEARNING")))
    L.append("")
    L.append("**Selection:** epsilon-lexicase (epsilon via Median Absolute Deviation, `epsilon_method=\"mad\"`) "
             "over 3 per-objective test cases: fidelity (p_marked), gate efficiency (1 - gates/MAX_EXPECTED_GATES, "
             "MAX=%s), depth efficiency (1 - depth/MAX_EXPECTED_DEPTH, MAX=%s); tournament baseline "
             "`selTournament` with tournament size %s selecting on the scalar fitness." % (
        v("MAX_EXPECTED_GATES"), v("MAX_EXPECTED_DEPTH"), v("TOURNAMENT_SIZE")))
    L.append("")
    L.append("**Fitness:** scalar `fitness = 10*miss + (1 - p_marked) + lambda * gate_count`, "
             "`miss = 1 if p_marked < %s else 0`, lambda = GATE_PENALTY_WEIGHT = %s; "
             "shots = %s. Fidelity success threshold %s." % (
        v("SUCCESS_THRESHOLD"), v("GATE_PENALTY_WEIGHT"), v("NUM_SHOTS"), v("SUCCESS_THRESHOLD")))
    L.append("")
    L.append("**Early stopping:** enabled=%s, mode=%s, strategy=%s; min generations before stopping=%s; "
             "targets: fidelity>=%s, gate_count<=%s, depth<=%s; patience %s; min improvement %s; "
             "metric weights %s; moving-average window=%s; relative improvement=%s." % (
        True, v("EARLY_STOPPING_MODE"), v("EARLY_STOPPING_STRATEGY"),
        v("MIN_GENERATIONS_BEFORE_STOPPING"), v("FIDELITY_SUCCESS_THRESHOLD"), v("GATE_COUNT_TARGET"),
        v("DEPTH_TARGET"), v("EARLY_STOPPING_PATIENCE"), v("MIN_IMPROVEMENT_DELTA"), v("METRIC_WEIGHTS"),
        v("MOVING_AVERAGE_WINDOW"), v("USE_RELATIVE_IMPROVEMENT")))
    L.append("")
    L.append("**Backend / simulation:** IBM Quantum `ibm_fez` (156 qubits), fetched live via "
             "`QiskitRuntimeService` (channel ibm_cloud); %s shots; noise model = `AerSimulator.from_backend(backend)` "
             "built from the **live backend calibration at kernel start** (i.e., calibration is live, not a frozen "
             "snapshot; the July epsilon-lexicase runs and the August tournament runs therefore used different "
             "calibrations). Ideal simulation = `QasmSimulator`. Transpilation: `transpile(..., optimization_level=3, "
             "seed_transpiler=run_seed)` in-loop; hardware re-transpiles with `generate_preset_pass_manager(..., "
             "optimization_level=3, seed_transpiler=deployed_run_seed)`." % v("NUM_SHOTS"))
    L.append("")
    L.append("**Grammar** (`grammars/grover.bnf`): 3 qubits / 3 classical bits; program = Initialize + HadamardAll + "
             "GroverIterations + Measure; iteration = OracleBlock | DiffuserBlock; oracle block is injected via "
             "`inject_oracle` into `## Begin Oracle ... ## End Oracle` markers (a no-op when the phenotype lacks the "
             "marker). Gate set: single-qubit x, y, z, h, s, sdg, t, tdg, id; two-qubit cx, cy, cz, swap; three-qubit "
             "ccx, cswap; parameterized rx, ry, rz, u, rxx, ryy, rzz, rzx with angles in "
             "{0, pi/4, pi/2, pi, 3pi/2, 2pi, 0.5, 1.3, 2.7, 0.314, 1.5708, 3.1415}; standard 3-qubit diffuser block "
             "is fixed in the grammar.")
    L.append("")
    L.append("**Software versions (report environment):** Python %s; qiskit %s; qiskit-aer %s; "
             "qiskit-ibm-runtime %s; numpy %s; pandas %s; scipy %s; matplotlib %s; deap %s; grape_bds %s. "
             "Notebook sets `PYTHONHASHSEED=0` (only fully effective when set before kernel launch)." % (
        platform.python_version(), version("qiskit"), version("qiskit-aer"), version("qiskit-ibm-runtime"),
        version("numpy"), version("pandas"), version("scipy"), version("matplotlib"), version("deap"),
        version("grape_bds")))
    L.append("")
    return L


def main() -> None:
    L: list[str] = []
    L.append("# PAPER_DATA — Grammatical Evolution for Quantum Algorithms (Grover)")
    L.append("")
    L.append("Assembled %s from existing `experiments/` trees, aggregates, hardware JSONs and diagnostics. "
             "No experiments were re-run." % pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))
    L.append("")
    L.append("**Definitions used throughout:** success = run fidelity >= %s; converged = peak fidelity >= %s; "
             "sim fidelity = per-run final re-evaluated fidelity in AGGREGATE (unless noted); "
             "hardware p_marked = p(|state>) from ibm_fez, 10,000 shots, matched to a per_run entry via "
             "raw_fitness + raw gates/depth." % (SUCCESS, CONV))
    L.append("")

    L += main_table("epsilon_lexicase", 300, "A. Main results (epsilon-lexicase, pop=300)")
    L.append("\n---\n")
    L += main_table("tournament", 300, "B. Tournament baseline (pop=300)")
    L.append("\n---\n")

    # ---------------- Section C ----------------
    L.append("### C. Head-to-head summary (pop=300)")
    L.append("")
    L.append("| State | Lex success | Tour success | Lex best fid | Tour best fid | Lex D/2Q | Tour D/2Q |")
    L.append("|---|---|---|---|---|---|---|")
    lk = tk = 0
    for state in STATES:
        a = load_agg("epsilon_lexicase", 300, state)
        b = load_agg("tournament", 300, state)
        def row(agg):
            per = agg["per_run"]
            best = max(per, key=lambda r: (r["fidelity"], -r["two_qubit_gates"], -r["depth"]))
            k = sum(r["fidelity"] >= SUCCESS for r in per)
            return k, best["fidelity"], best["seed"], best["depth"], best["two_qubit_gates"]
        k1, f1, s1, d1, q1 = row(a)
        k2, f2, s2, d2, q2 = row(b)
        lk += k1; tk += k2
        L.append(f"| {state} | {k1}/5 | {k2}/5 | {fnum(f1)} | {fnum(f2)} | {d1}/{q1} | {d2}/{q2} |")
    L.append("")
    L.append(f"Overall converged: lexicase **{lk}/40 ({lk/40*100:.0f}%)** vs tournament **{tk}/40 "
             f"({tk/40*100:.0f}%)** (run fidelity >= {SUCCESS}).")
    L.append("")

    # ---------------- Section D ----------------
    L.append("### D. Population ablation (epsilon-lexicase, pop=100 vs pop=300)")
    L.append("")
    L.append("| State | Success pop100 | Success pop300 | std fid pop100 | std fid pop300 |")
    L.append("|---|---|---|---|---|")
    k100 = k300 = 0
    bim100, bim300 = [], []
    for state in STATES:
        a100 = load_agg("epsilon_lexicase", 100, state)
        a300 = load_agg("epsilon_lexicase", 300, state)
        def stat(agg):
            per = agg["per_run"]
            fids = [r["fidelity"] for r in per]
            return sum(f >= SUCCESS for f in fids), statistics.stdev(fids) if len(fids) > 1 else 0.0
        k1, s1 = stat(a100); k2, s2 = stat(a300)
        k100 += k1; k300 += k2
        if s1 > 0.15: bim100.append(state)
        if s2 > 0.15: bim300.append(state)
        L.append(f"| {state} | {k1}/5 | {k2}/5 | {fnum(s1)} | {fnum(s2)} |")
    L.append("")
    L.append(f"Overall convergence: **{k100}/40 ({k100/40*100:.0f}%)** at pop=100 vs "
             f"**{k300}/40 ({k300/40*100:.0f}%)** at pop=300 (fidelity >= {SUCCESS}).")
    L.append(f"Bimodal states (std > 0.15): pop100 = {bim100 or 'none'}; pop300 = {bim300 or 'none'}.")
    L.append("")

    # ---------------- Section E ----------------
    L.append("### E. Mechanism analysis numbers")
    L.append("")
    lex, tour = diagnostics("epsilon_lexicase", 300), diagnostics("tournament", 300)
    def grp(runs):
        return [(df, "converged" if df.fidelity_max.max() >= CONV else "failed") for df in runs]
    lex_g, tour_g = grp(lex), grp(tour)
    L.append("**Diversity (mean unique behaviors, gens 0-15; % of population = /300):**")
    L.append("")
    L.append("| Group | Lexicase (n) | % of pop | Tournament (n) | % of pop |")
    L.append("|---|---|---|---|---|")
    for g in ("converged", "failed", "all"):
        lx = [df[df.generation <= WINDOW].unique_behaviors.mean() for df, gg in lex_g if g == "all" or gg == g]
        tt = [df[df.generation <= WINDOW].unique_behaviors.mean() for df, gg in tour_g if g == "all" or gg == g]
        L.append(f"| {g} | {np.mean(lx):.1f} (n={len(lx)}) | {np.mean(lx)/3:.1f}% | "
                 f"{np.mean(tt):.1f} (n={len(tt)}) | {np.mean(tt)/3:.1f}% |")
    L.append("")
    L.append("Gen-0 diversity: lexicase %.1f vs tournament %.1f — the two arms do NOT share initial "
             "populations despite identical seeds (environment difference between sweeps); treat raw diversity "
             "differences as confounded and use gen-0-normalized trajectories." % (
        np.mean([df.unique_behaviors.iloc[0] for df in lex]),
        np.mean([df.unique_behaviors.iloc[0] for df in tour])))
    L.append("")
    lex_f = [df for df, gg in lex_g if gg == "failed"]
    tour_f = [df for df, gg in tour_g if gg == "failed"]
    lpk = [df.fidelity_max.max() for df in lex_f]
    tpk = [df.fidelity_max.max() for df in tour_f]
    p = stats.mannwhitneyu(lpk, tpk, alternative="two-sided").pvalue
    L.append("**Failed-run peak fidelity (failed = peak < %s):**" % CONV)
    L.append("")
    L.append("| Metric | Lexicase (n=%d) | Tournament (n=%d) |" % (len(lpk), len(tpk)))
    L.append("|---|---|---|")
    for thr in (0.6, 0.7, 0.8):
        L.append(f"| Fraction crossing >= {thr} | {np.mean([p >= thr for p in lpk])*100:.0f}% | "
                 f"{np.mean([p >= thr for p in tpk])*100:.0f}% |")
    L.append(f"| Mean peak fidelity | {np.mean(lpk):.4f} | {np.mean(tpk):.4f} |")
    L.append(f"| Median peak fidelity | {np.median(lpk):.4f} | {np.median(tpk):.4f} |")
    L.append(f"| Mann-Whitney U p (two-sided) | {p:.4f} | (n={len(lpk)} vs {len(tpk)}) |")
    L.append("")
    L.append(f"**Coverage evidence:** lexicase failed runs never exceeded a peak fidelity of "
             f"**{max(lpk):.4f}** (i.e., never reached ~0.6), consistent with 'never reached the basin' "
             f"rather than premature convergence. Tournament failures reach 0.6-0.87 in "
             f"{np.mean([p >= 0.6 for p in tpk])*100:.0f}% of cases then stall (scalar gate-penalty tradeoff).")
    L.append("")

    # ---------------- Section F ----------------
    L.append("### F. Transpile / evolution-vs-transpiler numbers")
    L.append("")
    L.append("**Opt-0 (raw, pre-transpile) vs opt-3 (transpiled) for the deployed best circuit per state "
             "(epsilon-lexicase, pop=300):**")
    L.append("")
    L.append("| State | Raw D/G | Transpiled D/G | Depth reduction | Gate reduction |")
    L.append("|---|---|---|---|---|")
    for state in STATES:
        agg = load_agg("epsilon_lexicase", 300, state)
        best = max(agg["per_run"], key=lambda r: (r["fidelity"], -r["two_qubit_gates"], -r["depth"]))
        L.append(f"| {state} | {best['raw_depth']}/{best['raw_gate_count']} | "
                 f"{best['depth']}/{best['gate_count']} | "
                 f"{(1 - best['depth']/best['raw_depth'])*100:.0f}% | "
                 f"{(1 - best['gate_count']/best['raw_gate_count'])*100:.0f}% |")
    L.append("")
    L.append("**Transpile-seed sensitivity** (20 seed_transpiler values, real ibm_fez target, opt-3; "
             "see transpile_seed_sensitivity.csv): the 8 deployed best circuits are all **seed-stable** "
             "(min = median = max for every state). The July-deployed circuit for state 111 (run 4, seed 33537) "
             "is the one seed-sensitive circuit found: 7g/3d at seed 33537 vs 34g/23d at seed 0/70300 on the "
             "current target (the July hardware file recorded 37g/24d with the wrong stale seed 70300). "
             "State 011's deployed circuit is seed-stable but target-sensitive: recorded in-loop 5g/2d (July) "
             "vs 17g/12d transpiled today — i.e., layout depended on that day's calibration. Implication: "
             "evolution produces short raw circuits; the transpiler adds most of the deployed cost, and a small "
             "number of circuits are sensitive to transpile seed/calibration.")
    L.append("")

    # ---------------- Section G ----------------
    L.append("### G. Figure inventory")
    L.append("")
    root_figs = sorted(glob.glob(os.path.join(ROOT, "*.png")) + glob.glob(os.path.join(ROOT, "*.pdf")))
    L.append("**Analysis figures (project root):**")
    L.append("")
    L.append("| File | Type | Resolution | Description |")
    L.append("|---|---|---|---|")
    desc = {
        "fig_diversity_converged_vs_stalled.png": "Epsilon-lexicase pop300: fidelity + unique-behaviors trajectories, converged vs never-reached runs.",
        "fig_diversity_converged_vs_stalled.pdf": "Vector version of the same figure.",
        "fig_diversity_lexicase_vs_tournament.png": "Lexicase vs tournament pop300: fidelity, raw diversity, and gen-0-normalized diversity trajectories (4 groups).",
        "fig_diversity_lexicase_vs_tournament.pdf": "Vector version of the same figure.",
        "fig_failed_fidelity_lexicase_vs_tournament.png": "Failed-run fidelity trajectories + peak-fidelity ECDF, lexicase vs tournament.",
        "fig_failed_fidelity_lexicase_vs_tournament.pdf": "Vector version of the same figure.",
    }
    for f in root_figs:
        name = os.path.basename(f)
        if name.endswith(".pdf"):
            res = "vector (print-ready)"
        else:
            from PIL import Image
            dpi = Image.open(f).info.get("dpi", (None, None))[0]
            res = f"{dpi:.0f} dpi (below 300 - regenerate for print)" if dpi and dpi < 300 else f"{dpi} dpi"
        L.append(f"| `{name}` | {'PDF' if name.endswith('.pdf') else 'PNG'} | {res} | {desc.get(name, '')} |")
    L.append("")
    L.append("**Print-resolution versions:** `paper_figures/` contains 300-dpi PNGs and vector PDFs of the three "
             "analysis figures (regenerated via `make_paper_figures.py` from the saved CSVs — no experiments "
             "re-run).")
    L.append("")
    circuits = sorted(
        glob.glob(os.path.join(ROOT, "experiments", "*", "*", "noise", "state_*", "run_*", "circuit_*_*.png"))
        + glob.glob(os.path.join(ROOT, "experiments_epsilon_lexicase_noise_pop100", "state_*", "run_*",
                                 "circuit_*_*.png"))
    )
    L.append(f"**Circuit diagrams** ({len(circuits)} PNG files, all 150 dpi, in run folders):")
    L.append("")
    arms = {}
    for f in circuits:
        arm = os.path.relpath(os.path.dirname(os.path.dirname(os.path.dirname(f))), ROOT)
        arms.setdefault(arm, 0)
        arms[arm] += 1
    for arm, n in sorted(arms.items()):
        L.append(f"- `{arm}`: {n} circuit images (`circuit_raw_<state>_run<n>.png`, `circuit_transpiled_<state>_run<n>.png`)")
    L.append("")
    L.append("Deployed best-run circuit images per state (epsilon-lexicase pop300; also available for "
             "tournament and pop100 in the same layout):")
    L.append("")
    L.append("| State | Best run | Raw circuit | Transpiled circuit |")
    L.append("|---|---|---|---|")
    for state in STATES:
        agg = load_agg("epsilon_lexicase", 300, state)
        best = max(agg["per_run"], key=lambda r: (r["fidelity"], -r["two_qubit_gates"], -r["depth"]))
        d = f"experiments/epsilon_lexicase/pop300/noise/state_{state}/run_{best['run_id']}_seed_{best['seed']}"
        L.append(f"| {state} | run {best['run_id']} (seed {best['seed']}) | "
                 f"`{d}/circuit_raw_{state}_run{best['run_id']}.png` | "
                 f"`{d}/circuit_transpiled_{state}_run{best['run_id']}.png` |")
    L.append("")

    # ---------------- Section H ----------------
    L += section_h_config()

    # ---------------- Caveats ----------------
    L.append("### Notes / caveats")
    L.append("")
    L.append("- The epsilon-lexicase (July) and tournament (August) sweeps ran under different environments: "
             "gen-0 unique-behaviors differ per (state, seed) despite identical seeds and initialization code. "
             "Raw cross-method diversity comparisons are confounded; use the gen-0-normalized figure.")
    L.append("- Hardware results for states 000-011 are from July pre-patch runs (matched to the best-fidelity "
             "circuit by raw_fitness, but transpiled with the then-stale RANDOM_SEED; for these states the "
             "transpiled metrics in the hof files match the in-loop metrics). States 100, 101, 110, 111 have "
             "August re-deployments with the deployed run's own seed; 111/101 values are the corrected ones "
             "(0.9742 / 0.9827).")
    L.append("- Tournament states 100/110 hardware (0.9720 / 0.9750, seed 47182) were recovered from jobs "
             "d9r56tftfhrs73dr76ig / d9r1tthdsedc73ag263g after the original notebook runs timed out locally; "
             "these results are stored in the tournament run folders. The lexicase state-110 July result "
             "(0.9767, job d9j4ifibr2fc73e5er6g) was restored after an earlier misattribution, and the "
             "misplaced tournament copy in the lexicase state-100 folder was quarantined "
             "(`.misattributed_tournament`).")
    L.append("- `transpile_seed_sensitivity.csv` (168 rows) holds the 20-seed sweep of the deployed best circuits; "
             "`results_table.csv` holds the one-row-per-state consolidated table.")
    L.append("- Success counts use the per-run final fidelity from AGGREGATE (75% / 55% for lexicase/tournament "
             "pop300); diagnostics peak fidelity gives 78% / 57% (one extra run each).")
    L.append("")

    with open(OUT, "w") as f:
        f.write("\n".join(L))
    print(f"wrote {OUT} ({len(L)} lines)")


if __name__ == "__main__":
    main()
