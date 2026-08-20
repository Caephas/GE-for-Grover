#!/usr/bin/env python3
"""Build a paper-ready results table from existing experiment outputs.

Read-only: scans AGGREGATE_*.json files (and optional hardware JSONs). Never
runs experiments. Safe to re-run while the tournament sweep is still going:
tournament rows appear only once a state's aggregate is complete (all
EXPECTED_RUNS entries in per_run); anything missing/partial is reported as
"still running / incomplete", never as a 0% success rate.

Outputs:
  results_table.csv            - one row per state x selection x population
  markdown table on stdout     - sorted by selection_method, then state
  summary on stdout            - totals, success rates, coverage-failure flags
"""

from __future__ import annotations

import csv
import json
import os
import re
import statistics
import sys
from collections import Counter

# --------------------------------------------------------------------------
# Tunable knobs
# --------------------------------------------------------------------------
SUCCESS_FIDELITY_THRESHOLD = 0.95   # fidelity >= this counts as a successful run
BIMODAL_STD_THRESHOLD = 0.15        # std above this flags a bimodal distribution
COVERAGE_SUCCESS_RATE = 0.60        # below this = coverage-failure flag
EXPECTED_RUNS = 5                   # runs required for a tournament state to be complete
EXPECTED_STATES = [f"{i:03b}" for i in range(8)]  # 000 .. 111

# Which arms to scan: (selection_method, population, aggregate globs).
# The pop100 ablation spans the canonical tree and the legacy variant dir.
ARMS = [
    ("epsilon_lexicase", 300, [
        "experiments/epsilon_lexicase/pop300/noise/state_*/AGGREGATE_*.json",
    ]),
    ("epsilon_lexicase", 100, [
        "experiments/epsilon_lexicase/pop100/noise/state_*/AGGREGATE_*.json",
        "experiments_epsilon_lexicase_noise_pop100/state_*/AGGREGATE_*.json",
    ]),
    ("tournament", 300, [
        "experiments/tournament/pop300/noise/state_*/AGGREGATE_*.json",
    ]),
]

HARDWARE_GLOB = "**/hof_*_ibm_hardware_data.json"
HARDWARE_FITNESS_TOL = 1e-6  # |fitness_evolution - raw_fitness| tolerance for matching

CSV_COLUMNS = [
    "state", "selection_method", "population_size", "population_source",
    "n_runs", "success_rate", "success_rate_pct",
    "best_fidelity", "best_run_seed", "best_depth", "best_gate_count",
    "best_two_qubit_gates", "best_raw_depth", "best_raw_gate_count",
    "mean_fidelity", "std_fidelity", "bimodal",
    "hardware_p_marked", "hardware_seed", "hardware_sim_fidelity",
    "stop_reasons", "mean_early_stop_gen",
]


def path_state(path: str) -> str | None:
    m = re.search(r"state_(\d{3})", path.replace("\\", "/"))
    return m.group(1) if m else None


def infer_population(path: str, agg: dict) -> tuple[int | None, str]:
    """Population from the aggregate (if present) else from the folder path."""
    pop = agg.get("population_size")
    if isinstance(pop, (int, float)) and int(pop) > 0:
        return int(pop), "aggregate"
    m = re.search(r"pop(\d+)", path.replace("\\", "/"))
    if m:
        return int(m.group(1)), "path"
    return None, "unknown"


def normalize_stop_reason(reason: str) -> str:
    """Collapse verbose reasons into coarse buckets, e.g.
    "Fidelity stagnant at 0.5068 (target: 0.95)" -> "Fidelity stagnant"
    "Hardware targets achieved: fidelity=0.974, ..." -> "Hardware targets achieved"
    """
    reason = (reason or "").strip()
    if not reason:
        return "Unknown"
    for sep in (" at ", ": "):
        if sep in reason:
            reason = reason.split(sep, 1)[0]
    return reason or "Unknown"


def scan_hardware() -> dict[tuple[str, str, int], list[dict]]:
    """Map (state, selection, population) -> raw hardware file entries.

    Each entry carries the fields needed to match it to a per_run record:
    fitness_evolution (== the run's raw_fitness) and the raw gate/depth counts.
    """
    out: dict[tuple[str, str, int], list[dict]] = {}
    for path in sorted(_rglob(HARDWARE_GLOB)):
        state = path_state(path)
        pm = re.search(r"pop(\d+)", path.replace("\\", "/"))
        pop = int(pm.group(1)) if pm else None
        if "tournament" in path:
            sel = "tournament"
        elif "epsilon_lexicase" in path:
            sel = "epsilon_lexicase"
        else:
            sel = None
        if not (state and pop and sel):
            _note(f"hardware file skipped (unparseable path): {path}")
            continue
        try:
            data = json.load(open(path))
        except (OSError, json.JSONDecodeError) as e:
            _note(f"hardware file unreadable: {path} ({e})")
            continue
        p = data.get("p_marked_hw", data.get("p_marked"))
        if not isinstance(p, (int, float)):
            _note(f"hardware file has no p_marked: {path}")
            continue
        key = (state, sel, pop)
        out.setdefault(key, []).append({
            "path": path,
            "p_marked": float(p),
            "fitness_evolution": data.get("fitness_evolution"),
            "original_gates": data.get("original_gates"),
            "original_depth": data.get("original_depth"),
        })
    return out


def match_hardware(hw_entries: list[dict], per_run: list) -> dict | None:
    """Match hardware entries to per_run records.

    A match requires fitness_evolution == raw_fitness (within tolerance) AND
    identical raw gate/depth counts. Returns the best (highest p_marked) match:
    {p_marked, seed, sim_fidelity, path}. None if nothing matches.
    """
    candidates = []
    for entry in hw_entries:
        fe = entry.get("fitness_evolution")
        for r in per_run:
            if not isinstance(r, dict):
                continue
            rf = r.get("raw_fitness")
            if not isinstance(rf, (int, float)) or not isinstance(fe, (int, float)):
                continue
            if abs(rf - fe) > HARDWARE_FITNESS_TOL:
                continue
            if (r.get("raw_gate_count") != entry.get("original_gates")
                    or r.get("raw_depth") != entry.get("original_depth")):
                continue
            candidates.append({
                "p_marked": entry["p_marked"],
                "seed": r.get("seed"),
                "sim_fidelity": r.get("fidelity"),
                "path": entry["path"],
            })
    if not candidates:
        return None
    return max(candidates, key=lambda c: c["p_marked"])


def _rglob(pattern: str) -> list[str]:
    import glob
    return sorted(glob.glob(pattern, recursive=True))


NOTES: list[str] = []


def _note(msg: str) -> None:
    NOTES.append(msg)


def make_row(file: str, arm_sel: str, arm_pop: int, hw: dict) -> dict | None:
    """Turn one aggregate file into a table row, or None (with a note) if bad."""
    try:
        agg = json.load(open(file))
    except (OSError, json.JSONDecodeError) as e:
        _note(f"unreadable aggregate (skipped): {file} ({e})")
        return None

    state = agg.get("target_state") or path_state(file)
    if not state:
        _note(f"aggregate has no target_state and path unparseable: {file}")
        return None

    sel = agg.get("selection_method") or arm_sel
    if sel != arm_sel:
        _note(f"selection mismatch in {file}: file says {sel!r}, arm says {arm_sel!r}")

    pop, pop_src = infer_population(file, agg)
    if pop is None:
        _note(f"population could NOT be determined: {file}")
        return None
    if pop != arm_pop:
        _note(f"population mismatch in {file}: inferred {pop}, arm says {arm_pop}")

    per_run = agg.get("per_run")
    if not isinstance(per_run, list) or not per_run:
        _note(f"aggregate missing per_run (skipped): {file}")
        return None

    # Tournament completeness gate: only fully-written aggregates become rows.
    if arm_sel == "tournament":
        n_present = len([r for r in per_run if isinstance(r, dict)])
        if n_present < EXPECTED_RUNS:
            _note(f"tournament aggregate incomplete ({n_present}/{EXPECTED_RUNS} runs): {file}")
            return None

    fidelities = [
        float(r["fidelity"])
        for r in per_run
        if isinstance(r, dict) and isinstance(r.get("fidelity"), (int, float))
    ]
    if len(fidelities) != len(per_run):
        _note(f"{file}: {len(per_run) - len(fidelities)} per_run entries missing fidelity")
    if not fidelities:
        _note(f"aggregate has no usable fidelities (skipped): {file}")
        return None

    n = len(fidelities)
    k = sum(f >= SUCCESS_FIDELITY_THRESHOLD for f in fidelities)

    # Lambda-free deployment rule: highest fidelity, then fewest transpiled 2Q gates, then lowest depth.
    best_i = max(
        range(len(fidelities)),
        key=lambda i: (fidelities[i],
                       -per_run[i].get("two_qubit_gates", 10**9),
                       -per_run[i].get("depth", 10**9)),
    )
    best = per_run[best_i] if isinstance(per_run[best_i], dict) else {}

    mean_fid = statistics.mean(fidelities)
    std_fid = statistics.stdev(fidelities) if n > 1 else 0.0
    bimodal = std_fid > BIMODAL_STD_THRESHOLD

    stop_reasons = Counter(
        normalize_stop_reason(r.get("stop_reason"))
        for r in per_run
        if isinstance(r, dict)
    )

    early_stops = [
        float(r["early_stopped_gen"])
        for r in per_run
        if isinstance(r, dict) and isinstance(r.get("early_stopped_gen"), (int, float))
    ]
    mean_stop = statistics.mean(early_stops) if early_stops else agg.get("mean_early_stop_gen")

    hw_match = match_hardware(hw.get((state, sel, pop), []), per_run)
    if hw.get((state, sel, pop)) and hw_match is None:
        paths = ", ".join(e["path"] for e in hw[(state, sel, pop)])
        _note(f"hardware file(s) could not be matched to any per_run entry "
              f"(state {state}, {sel}, pop{pop}): {paths}")

    return {
        "state": state,
        "selection_method": sel,
        "population_size": pop,
        "population_source": pop_src,
        "n_runs": n,
        "success_rate": f"{k}/{n}",
        "success_rate_pct": f"{100.0 * k / n:.1f}%",
        "best_fidelity": f"{max(fidelities):.4f}",
        "best_run_seed": best.get("seed", ""),
        "best_depth": best.get("depth", ""),
        "best_gate_count": best.get("gate_count", ""),
        "best_two_qubit_gates": best.get("two_qubit_gates", ""),
        "best_raw_depth": best.get("raw_depth", ""),
        "best_raw_gate_count": best.get("raw_gate_count", ""),
        "mean_fidelity": f"{mean_fid:.4f}",
        "std_fidelity": f"{std_fid:.4f}",
        "bimodal": bimodal,
        "hardware_p_marked": f"{hw_match['p_marked']:.4f}" if hw_match else "N/A",
        "hardware_seed": hw_match["seed"] if hw_match else "N/A",
        "hardware_sim_fidelity": f"{hw_match['sim_fidelity']:.4f}" if hw_match else "N/A",
        "stop_reasons": json.dumps(dict(stop_reasons), ensure_ascii=False),
        "mean_early_stop_gen": f"{mean_stop:.1f}" if isinstance(mean_stop, (int, float)) else "",
    }


def main() -> None:
    hw = scan_hardware()
    rows: list[dict] = []
    seen_keys: set[tuple[str, str, int]] = set()
    tournament_incomplete: list[tuple[str, str]] = []  # (state, note)

    for arm_sel, arm_pop, globs in ARMS:
        files = sorted({f for pattern in globs for f in _rglob(pattern)})
        found_states = set()
        for file in files:
            state = path_state(file)
            if state:
                found_states.add(state)
            row = make_row(file, arm_sel, arm_pop, hw)
            if row is None:
                continue
            key = (row["state"], row["selection_method"], row["population_size"])
            if key in seen_keys:
                _note(f"duplicate row suppressed for {key} (second file: {file})")
                continue
            seen_keys.add(key)
            rows.append(row)

        for state in EXPECTED_STATES:
            if state not in found_states:
                if arm_sel == "tournament":
                    tournament_incomplete.append((state, "no aggregate yet"))
                else:
                    _note(f"WARNING: state {state} missing from {arm_sel}/pop{arm_pop}")

    # Any partial tournament aggregate (exists but fewer than EXPECTED_RUNS runs)
    # is already noted by make_row; surface it here too, keyed by state.
    for note in list(NOTES):
        m = re.match(r"tournament aggregate incomplete \((\d+)/5 runs\): .*?state_(\d{3})", note)
        if m:
            entry = (m.group(2), f"partial ({m.group(1)}/5 runs)")
            if entry not in tournament_incomplete:
                tournament_incomplete.append(entry)

    rows.sort(key=lambda r: (r["selection_method"], r["state"]))
    write_csv(rows)
    print_markdown(rows)
    print_summary(rows, tournament_incomplete)
    print_notes()


def write_csv(rows: list[dict]) -> None:
    with open("results_table.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in CSV_COLUMNS})
    print(f"\nCSV written: results_table.csv ({len(rows)} rows)")


def print_markdown(rows: list[dict]) -> None:
    print("\n" + "=" * 110)
    print("RESULTS TABLE (state x selection x population)")
    print("=" * 110)
    cols = [
        ("state", "state"), ("selection_method", "selection"),
        ("population_size", "pop"), ("n_runs", "n"),
        ("success_rate", "success"), ("success_rate_pct", "succ%"),
        ("best_fidelity", "best_fid"), ("best_run_seed", "best_seed"),
        ("best_depth", "depth"), ("best_gate_count", "gates"),
        ("best_two_qubit_gates", "2Q"), ("best_raw_depth", "raw_d"),
        ("best_raw_gate_count", "raw_g"), ("mean_fidelity", "mean_fid"),
        ("std_fidelity", "std_fid"), ("hardware_p_marked", "hw_p"),
        ("hardware_seed", "hw_seed"), ("hardware_sim_fidelity", "hw_sim"),
        ("mean_early_stop_gen", "stop_gen"), ("stop_reasons", "stop_reasons"),
    ]
    header = "| " + " | ".join(h for _, h in cols) + " |"
    sep = "|" + "|".join("-" * (len(h) + 2) for _, h in cols) + "|"
    print(header)
    print(sep)
    for r in rows:
        cells = []
        for key, _ in cols:
            v = r.get(key, "")
            if key == "std_fidelity" and r.get("bimodal"):
                v = f"{v} (bimodal)"
            if key == "stop_reasons":
                v = v.replace("|", "\\|")
            cells.append(str(v))
        print("| " + " | ".join(cells) + " |")


def print_summary(rows: list[dict], tournament_incomplete: list[tuple[str, str]]) -> None:
    print("\n" + "=" * 110)
    print("SUMMARY")
    print("=" * 110)

    by_group: dict[tuple[str, int], list[dict]] = {}
    for r in rows:
        by_group.setdefault((r["selection_method"], r["population_size"]), []).append(r)

    print("\nTotal runs and overall success rate per (selection, population):")
    for (sel, pop), rs in sorted(by_group.items()):
        total = sum(r["n_runs"] for r in rs)
        ok = sum(int(r["success_rate"].split("/")[0]) for r in rs)
        print(f"  {sel:18s} pop{pop:<4d} : {total:3d} runs, overall success "
              f"{ok}/{total} ({100.0 * ok / total:.1f}%)")

    print("\nCoverage-failure flags (success rate < {:.0f}%):".format(COVERAGE_SUCCESS_RATE * 100))
    flagged = [
        r for r in rows
        if float(r["success_rate_pct"].rstrip("%")) < COVERAGE_SUCCESS_RATE * 100
    ]
    if flagged:
        for r in sorted(flagged, key=lambda r: (r["selection_method"], r["state"])):
            print(f"  state {r['state']} ({r['selection_method']}, pop{r['population_size']}): "
                  f"{r['success_rate']} = {r['success_rate_pct']}")
    else:
        print("  none")

    missing_tournament = [s for s in EXPECTED_STATES
                          if not any(r["selection_method"] == "tournament" and r["state"] == s for r in rows)]
    print("\nTournament: still running / incomplete (not counted as failures):")
    if missing_tournament or tournament_incomplete:
        for state in EXPECTED_STATES:
            if state not in missing_tournament:
                continue
            note = next((n for s, n in tournament_incomplete if s == state), "no aggregate yet")
            print(f"  state {state}: {note}")
    else:
        print("  none - all 8 states complete")


def print_notes() -> None:
    if NOTES:
        print("\n" + "=" * 110)
        print("PROBLEMS / WARNINGS")
        print("=" * 110)
        for n in NOTES:
            print(f"  - {n}")
    else:
        print("\nNo problems or warnings.")


if __name__ == "__main__":
    main()
