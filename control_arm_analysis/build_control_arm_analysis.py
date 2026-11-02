#!/usr/bin/env python3
"""Pre-registered analysis of the lexi8_random control arm.

This script reads completed simulation artifacts only. It does not run
evolution, submit hardware jobs, modify the analysis plan, or touch tags.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import pickle
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister, transpile
from qiskit_aer import AerSimulator
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hardware_isa import load_scored_isa


OUT = Path(__file__).resolve().parent
FIG = OUT / "figures"

STATES = [f"{i:03b}" for i in range(8)]
SEEDS = [
    21315,
    47182,
    12147,
    33537,
    70300,
    74135,
    67154,
    80248,
    91197,
    29440,
]
LEX = "lexi2"
CTRL = "lexi8_random"
EPSILON = "epsilon_lexicase"
TOURNAMENT = "tournament"
ARM_ROOTS = {
    LEX: ROOT / "experiments_frozen_10seed_lexi2" / "lexi2" / "pop300" / "noise",
    CTRL: (
        ROOT
        / "experiments_frozen_10seed_lexi8_random"
        / "lexi8_random"
        / "pop300"
        / "noise"
    ),
    EPSILON: (
        ROOT
        / "experiments_frozen_10seed"
        / EPSILON
        / "pop300"
        / "noise"
    ),
    TOURNAMENT: (
        ROOT
        / "experiments_frozen_10seed"
        / TOURNAMENT
        / "pop300"
        / "noise"
    ),
}
ALL_METHODS = [EPSILON, TOURNAMENT, LEX, CTRL]
PAIR_METHODS = [LEX, CTRL]
NOISE_BUNDLE = ROOT / "noise" / "frozen_env_ibm_fez_2026-08-20.pkl"
BOOT_SEED = 20260827
BOOT_N = 10_000
FID_TARGET = 0.95
GATE_TARGET = 20
DEPTH_TARGET = 15


def read_json(path: Path):
    with path.open() as handle:
        return json.load(handle)


def write_json(path: Path, value) -> None:
    with path.open("w") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def paired_key(state: str, seed: int) -> tuple[str, int]:
    return state, seed


def run_dir(method: str, state: str, seed: int) -> Path:
    run_id = SEEDS.index(seed) + 1
    return (
        ARM_ROOTS[method]
        / f"state_{state}"
        / f"run_{run_id}_seed_{seed}"
    )


def result_path(method: str, state: str, seed: int) -> Path:
    run_id = SEEDS.index(seed) + 1
    return run_dir(method, state, seed) / f"run_result_{state}_run{run_id}.json"


def log_path(method: str, state: str, seed: int) -> Path:
    run_id = SEEDS.index(seed) + 1
    prefix = "lexi2" if method == LEX else method
    return run_dir(method, state, seed) / f"{prefix}_log_{state}_run{run_id}.json"


def diagnostics_path(method: str, state: str, seed: int) -> Path:
    run_id = SEEDS.index(seed) + 1
    return run_dir(method, state, seed) / f"diagnostics_{state}_run{run_id}.csv"


def task_success(result: dict, fidelity_key: str = "fidelity") -> bool:
    return bool(
        float(result[fidelity_key]) >= FID_TARGET
        and int(result["gate_count"]) <= GATE_TARGET
        and int(result["depth"]) <= DEPTH_TARGET
    )


def stop_family(result: dict) -> str:
    reason = result.get("stop_reason") or ""
    if reason.startswith("Hardware targets achieved"):
        return "early stop"
    success = task_success(result)
    if success:
        return "late success"
    if float(result["fidelity"]) < FID_TARGET:
        return "fidelity fail"
    return "size fail"


def cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
    """Cliff's delta for x relative to y."""
    greater = int(np.sum(x[:, None] > y[None, :]))
    less = int(np.sum(x[:, None] < y[None, :]))
    return (greater - less) / (x.size * y.size)


def state_cluster_bootstrap(
    x: np.ndarray,
    y: np.ndarray,
    *,
    statistic,
    rng_seed: int,
    draws: int,
) -> tuple[np.ndarray, float, float]:
    """Resample whole state blocks, preserving the ten paired seeds."""
    assert x.size == len(STATES) * len(SEEDS)
    assert y.size == x.size
    rng = np.random.default_rng(rng_seed)
    state_offsets = {
        state: np.arange(i * len(SEEDS), (i + 1) * len(SEEDS))
        for i, state in enumerate(STATES)
    }
    values = np.empty(draws, dtype=float)
    for i in range(draws):
        sampled_states = rng.choice(STATES, size=len(STATES), replace=True)
        idx = np.concatenate([state_offsets[state] for state in sampled_states])
        values[i] = statistic(x[idx], y[idx])
    lo, hi = np.percentile(values, [2.5, 97.5])
    return values, float(lo), float(hi)


def exact_mcnemar(only_lex: int, only_ctrl: int) -> float:
    discordant = only_lex + only_ctrl
    if discordant == 0:
        return 1.0
    return float(
        stats.binomtest(discordant - only_ctrl, discordant, 0.5).pvalue
    )


def paired_fidelity_summary(
    lex_values: np.ndarray,
    ctrl_values: np.ndarray,
    *,
    lex_meta: list[dict],
    ctrl_meta: list[dict],
    fidelity_key: str,
) -> dict:
    diff = ctrl_values - lex_values
    nonzero = diff[diff != 0]
    wilcoxon = stats.wilcoxon(nonzero, alternative="two-sided")
    observed_delta = float(cliffs_delta(ctrl_values, lex_values))
    draws, delta_lo, delta_hi = state_cluster_bootstrap(
        ctrl_values,
        lex_values,
        statistic=cliffs_delta,
        rng_seed=BOOT_SEED,
        draws=BOOT_N,
    )

    both = sum(
        task_success(lm, fidelity_key) and task_success(cm, fidelity_key)
        for lm, cm in zip(lex_meta, ctrl_meta)
    )
    only_lex = sum(
        task_success(lm, fidelity_key) and not task_success(cm, fidelity_key)
        for lm, cm in zip(lex_meta, ctrl_meta)
    )
    only_ctrl = sum(
        not task_success(lm, fidelity_key) and task_success(cm, fidelity_key)
        for lm, cm in zip(lex_meta, ctrl_meta)
    )
    neither = len(lex_meta) - both - only_lex - only_ctrl
    return {
        "n_pairs": int(lex_values.size),
        "lex_task_success": int(both + only_lex),
        "control_task_success": int(both + only_ctrl),
        "mcnemar_both_succeed": int(both),
        "mcnemar_only_lexi2": int(only_lex),
        "mcnemar_only_control": int(only_ctrl),
        "mcnemar_neither": int(neither),
        "mcnemar_exact_p": exact_mcnemar(int(only_lex), int(only_ctrl)),
        "lex_median_fidelity": float(np.median(lex_values)),
        "lex_mean_fidelity": float(np.mean(lex_values)),
        "control_median_fidelity": float(np.median(ctrl_values)),
        "control_mean_fidelity": float(np.mean(ctrl_values)),
        "median_paired_diff_control_minus_lexi2": float(np.median(diff)),
        "mean_paired_diff_control_minus_lexi2": float(np.mean(diff)),
        "pairs_control_higher": int(np.sum(diff > 0)),
        "pairs_lexi2_higher": int(np.sum(diff < 0)),
        "pairs_tied": int(np.sum(diff == 0)),
        "wilcoxon_statistic": float(wilcoxon.statistic),
        "wilcoxon_p": float(wilcoxon.pvalue),
        "wilcoxon_n_nonzero": int(nonzero.size),
        "wilcoxon_method": (
            "scipy.stats.wilcoxon, two-sided, zero_method=wilcox, "
            "scipy method=auto"
        ),
        "cliffs_delta_control_vs_lexi2": observed_delta,
        "cliffs_delta_ci95_state_cluster": [delta_lo, delta_hi],
        "bootstrap_draws": int(draws.size),
        "bootstrap_seed": BOOT_SEED,
    }


def qsummary(values: list[float]) -> dict:
    arr = np.asarray(values, dtype=float)
    q1, q2, q3 = np.percentile(arr, [25, 50, 75])
    return {
        "n": int(arr.size),
        "mean": float(np.mean(arr)),
        "median": float(q2),
        "q1": float(q1),
        "q3": float(q3),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "sd": float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0,
    }


_EXACT_SIMULATOR: AerSimulator | None = None
_READOUT_MATRICES: dict[int, np.ndarray] | None = None
_FROZEN_TARGET = None


def _init_exact_worker(noise_bundle_path: str) -> None:
    global _EXACT_SIMULATOR, _READOUT_MATRICES, _FROZEN_TARGET
    with open(noise_bundle_path, "rb") as handle:
        bundle = pickle.load(handle)
    _EXACT_SIMULATOR = AerSimulator(
        method="density_matrix", noise_model=bundle["noise_model"]
    )
    _EXACT_SIMULATOR.set_options(max_parallel_threads=1)
    _FROZEN_TARGET = bundle["target"]
    readouts = {}
    for error in bundle["noise_model"].to_dict()["errors"]:
        if (
            error.get("type") == "roerror"
            and error.get("operations") == ["measure"]
            and len(error.get("gate_qubits", [()])[0]) == 1
        ):
            qubit = int(error["gate_qubits"][0][0])
            readouts[qubit] = np.asarray(error["probabilities"], dtype=float)
    if len(readouts) != 156:
        raise RuntimeError(
            f"expected 156 single-qubit readout matrices, found {len(readouts)}"
        )
    _READOUT_MATRICES = readouts


def _exact_target_probability_with_readout(
    simulator: AerSimulator,
    circuit,
    measurement_layout: list[int],
    readout_matrices: dict[int, np.ndarray],
    target: str,
) -> float:
    """Exact noisy probabilities followed by the frozen readout confusion."""
    unmeasured = circuit.remove_final_measurements(inplace=False)
    unmeasured.save_probabilities(
        qubits=[int(q) for q in measurement_layout], label="probs"
    )
    result = simulator.run(unmeasured, shots=None).result()
    probabilities = np.asarray(result.data()["probs"], dtype=float)
    width = len(measurement_layout)
    target_probability = 0.0
    for input_index, probability in enumerate(probabilities):
        input_bits = f"{input_index:0{width}b}"[::-1]
        for output_index in range(2**width):
            output_bits = f"{output_index:0{width}b}"[::-1]
            if output_bits != target:
                continue
            confusion = 1.0
            for qubit, input_bit, output_bit in zip(
                measurement_layout, input_bits, output_bits
            ):
                confusion *= readout_matrices[int(qubit)][
                    int(input_bit), int(output_bit)
                ]
            target_probability += float(probability) * confusion
    return float(target_probability)


def _exact_rescore_one(job: dict) -> dict:
    if (
        _EXACT_SIMULATOR is None
        or _READOUT_MATRICES is None
        or _FROZEN_TARGET is None
    ):
        raise RuntimeError("exact worker was not initialized")

    local_vars = {}
    exec(
        job["phenotype"],
        {
            "np": np,
            "QuantumCircuit": QuantumCircuit,
            "QuantumRegister": QuantumRegister,
            "ClassicalRegister": ClassicalRegister,
        },
        local_vars,
    )
    circuit = local_vars.get("qc")
    if circuit is None:
        raise ValueError("phenotype did not define qc")
    expected_metrics = (
        int(job["recorded_gates"]),
        int(job["recorded_depth"]),
        int(job["recorded_two_qubit_gates"]),
    )
    transpiler_seed = int(job["seed"])
    transpiled = transpile(
        circuit,
        target=_FROZEN_TARGET,
        optimization_level=3,
        seed_transpiler=transpiler_seed,
    )
    reconstructed_metrics = (
        int(transpiled.size()),
        int(transpiled.depth()),
        sum(
            1
            for instruction in transpiled.data
            if instruction.operation.num_qubits >= 2
        ),
    )
    measurement_layout = [None] * 3
    for instruction in transpiled.data:
        if instruction.operation.name == "measure":
            cbit = transpiled.find_bit(instruction.clbits[0]).index
            measurement_layout[cbit] = int(instruction.qubits[0]._index)
    if any(qubit is None for qubit in measurement_layout):
        raise ValueError("transpiled circuit does not have a three-bit measurement layout")
    metrics_match = reconstructed_metrics == expected_metrics
    exact_fidelity = (
        _exact_target_probability_with_readout(
            _EXACT_SIMULATOR,
            transpiled,
            measurement_layout,
            _READOUT_MATRICES,
            job["state"],
        )
        if metrics_match
        else None
    )
    return {
        "method": job["method"],
        "state": job["state"],
        "seed": job["seed"],
        "exact_fidelity": exact_fidelity,
        "metrics_match": metrics_match,
        "recorded_metrics": expected_metrics,
        "reconstructed_metrics": reconstructed_metrics,
        "reconstructed_gates": int(transpiled.size()),
        "reconstructed_depth": int(transpiled.depth()),
        "reconstructed_two_qubit_gates": sum(
            1
            for instruction in transpiled.data
            if instruction.operation.num_qubits >= 2
        ),
        "measurement_layout": measurement_layout,
        "transpiler_seed": transpiler_seed,
    }


def _exact_rescore_control_qpy_one(job: dict) -> dict:
    if (
        _EXACT_SIMULATOR is None
        or _READOUT_MATRICES is None
        or _FROZEN_TARGET is None
    ):
        raise RuntimeError("exact worker was not initialized")
    circuit, metadata, _qpy_path, _metadata_path = load_scored_isa(
        job["run_dir"], job["state"], job["run_id"]
    )
    exact_fidelity = _exact_target_probability_with_readout(
        _EXACT_SIMULATOR,
        circuit,
        metadata["measurement_layout"],
        _READOUT_MATRICES,
        job["state"],
    )
    return {
        "method": CTRL,
        "state": job["state"],
        "seed": job["seed"],
        "exact_fidelity": exact_fidelity,
        "measurement_layout": metadata["measurement_layout"],
    }


def load_analysis_data() -> tuple[dict, dict]:
    results = {}
    loaded = {}
    for method in (LEX, CTRL):
        for state in STATES:
            for seed in SEEDS:
                path = result_path(method, state, seed)
                payload = read_json(path)
                results[(method, state, seed)] = payload
                loaded[(method, state, seed)] = path
    return results, loaded


def load_all_analysis_data() -> dict:
    results = {}
    for method in ALL_METHODS:
        for state in STATES:
            for seed in SEEDS:
                results[(method, state, seed)] = read_json(
                    result_path(method, state, seed)
                )
    return results


def integrity_check(results: dict) -> dict:
    expected = {(state, seed) for state in STATES for seed in SEEDS}
    control_files = list(
        ARM_ROOTS[CTRL].glob("state_*/run_*/run_result_*.json")
    )
    control_keys = {
        (result["target_state"], result["seed"])
        for (method, _state, _seed), result in results.items()
        if method == CTRL
    }
    lex_keys = {
        (result["target_state"], result["seed"])
        for (method, _state, _seed), result in results.items()
        if method == LEX
    }

    hash_mismatches = []
    for state in STATES:
        for seed in SEEDS:
            ctrl_dir = run_dir(CTRL, state, seed)
            lex_dir = run_dir(LEX, state, seed)
            control_hashes = read_json(ctrl_dir / "gen0_genome_hashes.json")
            lexi2_hashes = read_json(lex_dir / "gen0_genome_hashes.json")
            if control_hashes.get("hashes") != lexi2_hashes.get("hashes"):
                hash_mismatches.append(
                    {
                        "state": state,
                        "seed": seed,
                        "control_n": len(control_hashes.get("hashes", [])),
                        "lexi2_n": len(lexi2_hashes.get("hashes", [])),
                    }
                )

    isa_errors = []
    for state in STATES:
        run_id = 1
        for seed in SEEDS:
            directory = run_dir(CTRL, state, seed)
            result = results[(CTRL, state, seed)]
            try:
                _circuit, metadata, _qpy, _meta_path = load_scored_isa(
                    str(directory), state, run_id
                )
                for key in ("fidelity", "gate_count", "depth", "two_qubit_gates"):
                    if metadata.get("p_marked" if key == "fidelity" else key) != result.get(key):
                        raise ValueError(f"metadata/result mismatch for {key}")
            except Exception as exc:
                isa_errors.append(
                    {
                        "state": state,
                        "seed": seed,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            run_id += 1

    checks = {
        "control_run_result_file_count": len(control_files),
        "expected_grid_cells": len(expected),
        "control_unique_grid_cells": len(control_keys),
        "lexi2_unique_grid_cells": len(lex_keys),
        "states_x_seeds_exactly_match_lexi2": bool(
            control_keys == expected and lex_keys == expected
        ),
        "control_run_result_files_exactly_match_expected_grid": bool(
            len(control_files) == 80 and control_keys == expected
        ),
        "gen0_hash_comparisons": 80,
        "gen0_hash_mismatches": hash_mismatches,
        "scored_isa_files_checked": 80,
        "scored_isa_errors": isa_errors,
        "workers_per_run": 1,
        "workers_evidence": (
            "infra/run_sweep.py hardcodes --workers 1 in the sole child "
            "spawn command; the single completed sweep used that dispatcher"
        ),
    }
    checks["passed"] = bool(
        checks["control_run_result_file_count"] == 80
        and checks["states_x_seeds_exactly_match_lexi2"]
        and checks["control_run_result_files_exactly_match_expected_grid"]
        and not hash_mismatches
        and not isa_errors
        and checks["workers_per_run"] == 1
    )
    return checks


def per_state_rows(results: dict) -> tuple[list[dict], list[dict]]:
    success_rows = []
    failure_rows = []
    for state in STATES:
        lex_count = 0
        control_count = 0
        for seed in SEEDS:
            lex_count += int(task_success(results[(LEX, state, seed)]))
            control_count += int(task_success(results[(CTRL, state, seed)]))
        success_rows.append(
            {
                "state": state,
                "lexi2_task_success": lex_count,
                "control_task_success": control_count,
                "n_per_method": len(SEEDS),
                "control_minus_lexi2": control_count - lex_count,
            }
        )

        categories = {
            "early stop": 0,
            "late success": 0,
            "fidelity fail": 0,
            "size fail": 0,
        }
        for seed in SEEDS:
            categories[stop_family(results[(CTRL, state, seed)])] += 1
        failure_rows.append({"state": state, **categories, "total": len(SEEDS)})
    return success_rows, failure_rows


def size_rows(results: dict) -> list[dict]:
    rows = []
    for method in (LEX, CTRL):
        all_runs = [
            results[(method, state, seed)]
            for state in STATES
            for seed in SEEDS
        ]
        successful = [result for result in all_runs if task_success(result)]
        for population, metric in (("all runs", all_runs), ("task-success runs", successful)):
            rows.append(
                {
                    "method": method,
                    "population": population,
                    "n_runs": len(metric),
                    "median_gates": float(
                        np.median([r["gate_count"] for r in metric])
                    ),
                    "median_depth": float(
                        np.median([r["depth"] for r in metric])
                    ),
                    "median_two_qubit_gates": float(
                        np.median([r["two_qubit_gates"] for r in metric])
                    ),
                }
            )
    return rows


def mechanism_tables(results: dict) -> tuple[list[dict], list[dict], list[dict]]:
    fidelity_values = {method: {} for method in ALL_METHODS}
    pool_values = {LEX: {}, CTRL: {}}
    control_highest = {}

    for method in ALL_METHODS:
        for state in STATES:
            for seed in SEEDS:
                with diagnostics_path(method, state, seed).open(newline="") as handle:
                    for row in csv.DictReader(handle):
                        generation = int(row["generation"])
                        max_fidelity_column = (
                            f"p{state}_max"
                            if method in PAIR_METHODS
                            else "fidelity_max"
                        )
                        fidelity_values[method].setdefault(generation, []).append(
                            float(row[max_fidelity_column])
                        )

                if method in PAIR_METHODS:
                    payload = read_json(log_path(method, state, seed))
                    for generation_text, record in payload["per_generation"].items():
                        generation = int(generation_text)
                        pool_values[method].setdefault(generation, []).extend(
                            int(value)
                            for value in record.get("post_case_pool_sizes", [])
                        )
                        if method == CTRL:
                            highest = record.get("highest_fidelity_individual")
                            if highest is not None:
                                control_highest.setdefault(generation, []).append(
                                    {
                                        **highest,
                                        "any_individual_meets_all_targets": bool(
                                            record.get(
                                                "any_individual_meets_all_targets",
                                                False,
                                            )
                                        ),
                                    }
                                )

    fidelity_rows = []
    pool_rows = []
    for method in ALL_METHODS:
        for generation in sorted(fidelity_values[method]):
            summary = qsummary(fidelity_values[method][generation])
            fidelity_rows.append(
                {"method": method, "generation": generation, **summary}
            )
    for method in PAIR_METHODS:
        for generation in sorted(pool_values[method]):
            summary = qsummary(pool_values[method][generation])
            pool_rows.append({"method": method, "generation": generation, **summary})

    highest_rows = []
    for generation in sorted(control_highest):
        records = control_highest[generation]
        row = {"generation": generation, "n_runs": len(records)}
        for field in ("fidelity", "gates", "depth", "two_qubit_gates"):
            summary = qsummary([float(record[field]) for record in records])
            row[f"{field}_mean"] = summary["mean"]
            row[f"{field}_q1"] = summary["q1"]
            row[f"{field}_q3"] = summary["q3"]
        row["fraction_any_individual_meets_all_targets"] = float(
            np.mean(
                [
                    record["any_individual_meets_all_targets"]
                    for record in records
                ]
            )
        )
        highest_rows.append(row)
    return fidelity_rows, pool_rows, highest_rows


def exact_conditional_paired_ci(
    only_lex: int, only_control: int, n_pairs: int, confidence: float = 0.95
) -> tuple[float, float]:
    """Exact conditional CI for a paired risk difference.

    Conditional on the discordant pairs, the number favouring Lexi2 is
    binomial. A Clopper-Pearson interval for that within-discordance
    probability is mapped back to p(Lexi2) - p(control).
    """
    discordant = only_lex + only_control
    if discordant == 0:
        return 0.0, 0.0
    alpha = 1.0 - confidence
    pi_lower = (
        0.0
        if only_lex == 0
        else float(stats.beta.ppf(alpha / 2.0, only_lex, only_control + 1))
    )
    pi_upper = (
        1.0
        if only_control == 0
        else float(
            stats.beta.ppf(
                1.0 - alpha / 2.0, only_lex + 1, only_control
            )
        )
    )
    scale = discordant / n_pairs
    return scale * (2.0 * pi_lower - 1.0), scale * (2.0 * pi_upper - 1.0)


def paired_exact_summary(
    lex_values: np.ndarray,
    control_values: np.ndarray,
    lex_meta: list[dict],
    control_meta: list[dict],
) -> dict:
    diff = control_values - lex_values
    nonzero = diff[diff != 0]
    wilcoxon = stats.wilcoxon(nonzero, alternative="two-sided")
    both = sum(
        task_success(lex_item, "exact_fidelity")
        and task_success(control_item, "exact_fidelity")
        for lex_item, control_item in zip(lex_meta, control_meta)
    )
    only_lex = sum(
        task_success(lex_item, "exact_fidelity")
        and not task_success(control_item, "exact_fidelity")
        for lex_item, control_item in zip(lex_meta, control_meta)
    )
    only_control = sum(
        not task_success(lex_item, "exact_fidelity")
        and task_success(control_item, "exact_fidelity")
        for lex_item, control_item in zip(lex_meta, control_meta)
    )
    neither = len(lex_meta) - both - only_lex - only_control
    return {
        "n_pairs": len(lex_meta),
        "lex_task_success": int(both + only_lex),
        "control_task_success": int(both + only_control),
        "mcnemar_both_succeed": int(both),
        "mcnemar_only_lexi2": int(only_lex),
        "mcnemar_only_control": int(only_control),
        "mcnemar_neither": int(neither),
        "mcnemar_exact_p": exact_mcnemar(int(only_lex), int(only_control)),
        "lex_median_fidelity": float(np.median(lex_values)),
        "lex_mean_fidelity": float(np.mean(lex_values)),
        "control_median_fidelity": float(np.median(control_values)),
        "control_mean_fidelity": float(np.mean(control_values)),
        "median_paired_diff_control_minus_lexi2": float(np.median(diff)),
        "mean_paired_diff_control_minus_lexi2": float(np.mean(diff)),
        "pairs_control_higher": int(np.sum(diff > 0)),
        "pairs_lexi2_higher": int(np.sum(diff < 0)),
        "pairs_tied": int(np.sum(diff == 0)),
        "wilcoxon_statistic": float(wilcoxon.statistic),
        "wilcoxon_p": float(wilcoxon.pvalue),
        "wilcoxon_n_nonzero": int(nonzero.size),
        "cliffs_delta_control_vs_lexi2": float(
            cliffs_delta(control_values, lex_values)
        ),
    }


def four_arm_descriptives(
    results: dict,
) -> tuple[list[dict], list[dict], list[dict]]:
    overall_rows = []
    per_state_rows = []
    failure_rows = []
    for method in ALL_METHODS:
        runs = [
            results[(method, state, seed)]
            for state in STATES
            for seed in SEEDS
        ]
        successes = sum(task_success(result) for result in runs)
        overall_rows.append(
            {
                "method": method,
                "task_successes": int(successes),
                "n_runs": len(runs),
                "task_success_proportion": successes / len(runs),
            }
        )
        categories = {
            "early stop": 0,
            "late success": 0,
            "fidelity fail": 0,
            "size fail": 0,
        }
        for result in runs:
            categories[stop_family(result)] += 1
        failure_rows.append(
            {
                "method": method,
                **categories,
                "total": len(runs),
            }
        )
        for state in STATES:
            state_runs = [
                results[(method, state, seed)] for seed in SEEDS
            ]
            per_state_rows.append(
                {
                    "method": method,
                    "state": state,
                    "task_successes": sum(
                        task_success(result) for result in state_runs
                    ),
                    "n_runs": len(state_runs),
                }
            )
    return overall_rows, per_state_rows, failure_rows


def mechanism_selected_generations(
    fidelity_rows: list[dict],
    pool_rows: list[dict],
    generations: tuple[int, ...] = (5, 10, 20, 50),
) -> list[dict]:
    rows = []
    for method in ALL_METHODS:
        for generation in generations:
            fidelity = next(
                (
                    row
                    for row in fidelity_rows
                    if row["method"] == method
                    and row["generation"] == generation
                ),
                None,
            )
            pool = next(
                (
                    row
                    for row in pool_rows
                    if row["method"] == method
                    and row["generation"] == generation
                ),
                None,
            )
            rows.append(
                {
                    "method": method,
                    "generation": generation,
                    "population_max_fidelity_mean": (
                        fidelity["mean"] if fidelity else ""
                    ),
                    "population_max_fidelity_n_runs": (
                        fidelity["n"] if fidelity else 0
                    ),
                    "post_case_pool_size_mean": (
                        pool["mean"] if pool else ""
                    ),
                    "post_case_pool_size_n_selections": (
                        pool["n"] if pool else 0
                    ),
                    "post_case_pool_status": (
                        "available" if pool else "not logged in v0.1 artifact"
                    ),
                }
            )
    return rows


def exact_rescoring(results: dict) -> dict:
    jobs = []
    for method in PAIR_METHODS:
        for state in STATES:
            for seed in SEEDS:
                result = results[(method, state, seed)]
                jobs.append(
                    {
                        "method": method,
                        "state": state,
                        "seed": seed,
                        "phenotype": result["phenotype"],
                        "genome_hash": result["genome_hash"],
                        "recorded_gates": result["gate_count"],
                        "recorded_depth": result["depth"],
                        "recorded_two_qubit_gates": result[
                            "two_qubit_gates"
                        ],
                    }
                )
    workers = min(4, os.cpu_count() or 1)
    qpy_jobs = []
    for state in STATES:
        for run_id, seed in enumerate(SEEDS, 1):
            qpy_jobs.append(
                {
                    "state": state,
                    "seed": seed,
                    "run_id": run_id,
                    "run_dir": str(run_dir(CTRL, state, seed)),
                }
            )
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_exact_worker,
        initargs=(str(NOISE_BUNDLE),),
    ) as executor:
        records = list(executor.map(_exact_rescore_one, jobs, chunksize=1))
        qpy_records = list(
            executor.map(_exact_rescore_control_qpy_one, qpy_jobs, chunksize=1)
        )
    common = {
        (record["method"], record["state"], record["seed"]): record
        for record in records
    }
    control_qpy = {
        (record["state"], record["seed"]): record
        for record in qpy_records
    }
    return common, control_qpy


def plot_mechanism(fidelity_rows: list[dict], pool_rows: list[dict]) -> Path:
    colors = {LEX: "#1f77b4", CTRL: "#d95f02"}
    labels = {LEX: "Lexi$^2$", CTRL: "lexi8_random"}
    fig, axes = plt.subplots(2, 1, figsize=(7.0, 7.2), constrained_layout=True)

    for method in (LEX, CTRL):
        rows = sorted(
            (row for row in fidelity_rows if row["method"] == method),
            key=lambda row: row["generation"],
        )
        x = np.asarray([row["generation"] for row in rows])
        mean = np.asarray([row["mean"] for row in rows])
        q1 = np.asarray([row["q1"] for row in rows])
        q3 = np.asarray([row["q3"] for row in rows])
        axes[0].plot(x, mean, color=colors[method], linewidth=1.7, label=labels[method])
        axes[0].fill_between(x, q1, q3, color=colors[method], alpha=0.16)

    axes[0].set_xlabel("Generation")
    axes[0].set_ylabel("Population maximum target fidelity")
    axes[0].set_title("A  Population maximum fidelity")
    axes[0].set_ylim(0.0, 1.02)
    axes[0].legend(frameon=False)
    axes[0].grid(alpha=0.2)

    for method in (LEX, CTRL):
        rows = sorted(
            (row for row in pool_rows if row["method"] == method),
            key=lambda row: row["generation"],
        )
        x = np.asarray([row["generation"] for row in rows])
        mean = np.asarray([row["mean"] for row in rows])
        q1 = np.asarray([row["q1"] for row in rows])
        q3 = np.asarray([row["q3"] for row in rows])
        axes[1].plot(x, mean, color=colors[method], linewidth=1.7, label=labels[method])
        axes[1].fill_between(x, q1, q3, color=colors[method], alpha=0.16)

    axes[1].set_xlabel("Generation")
    axes[1].set_ylabel("Post-case pool size")
    axes[1].set_title("B  Non-singleton post-case pool size")
    axes[1].legend(frameon=False)
    axes[1].grid(alpha=0.2)

    for axis in axes:
        axis.tick_params(labelsize=8)

    path = FIG / "control_arm_mechanism.pdf"
    fig.savefig(path, format="pdf", bbox_inches="tight")
    plt.close(fig)
    return path


def format_float(value: float, digits: int = 6) -> str:
    return f"{value:.{digits}f}"


def markdown_table(headers: list[str], rows: list[list]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    lines.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
    return lines


def build_report(
    integrity: dict,
    stored_summary: dict,
    exact_summary: dict,
    success_rows: list[dict],
    failure_rows: list[dict],
    median_rows: list[dict],
    fidelity_rows: list[dict],
    pool_rows: list[dict],
    highest_rows: list[dict],
    sampled_minus_exact: dict,
    paired_rows: list[dict],
    four_arm_overall: list[dict],
    four_arm_by_state: list[dict],
    four_arm_failure: list[dict],
    mechanism_summary: list[dict],
    paired_success_delta: float,
    paired_success_ci: tuple[float, float],
    exact_path_rows: list[dict],
) -> None:
    metrics_match_total = sum(
        bool(row["metrics_match"]) for row in exact_path_rows
    )
    lexi2_metrics_matches = sum(
        bool(row["metrics_match"])
        for row in exact_path_rows
        if row["method"] == LEX
    )
    control_metrics_matches = sum(
        bool(row["metrics_match"])
        for row in exact_path_rows
        if row["method"] == CTRL
    )
    qpy_layout_matches = sum(
        row["qpy_layout_matches_reconstruction"] is True
        for row in exact_path_rows
        if row["method"] == CTRL
    )
    lines = [
        "# lexi8_random control-arm analysis",
        "",
        "Pre-registered analysis of the completed 80-run control sweep. "
        "All results below use existing artifacts only; no evolution or "
        "hardware job was run.",
        "",
        "## 0. Integrity checks",
        "",
        *markdown_table(
            ["Check", "Result"],
            [
                ["Control run_result files", integrity["control_run_result_file_count"]],
                ["States x seeds exactly match Lexi2", integrity["states_x_seeds_exactly_match_lexi2"]],
                ["gen-0 hash mismatches", len(integrity["gen0_hash_mismatches"])],
                ["Scored ISA QPY/metadata errors", len(integrity["scored_isa_errors"])],
                ["Workers per run", integrity["workers_per_run"]],
                ["Overall gate", "PASS" if integrity["passed"] else "FAIL"],
            ],
        ),
        "",
        "The worker check is structural: `infra/run_sweep.py` hardcodes "
        "`--workers 1` in the sole child-process spawn path.",
        "",
        "## 0.5 Exact-fidelity reconciliation",
        "",
        "The control-only exact values previously reported here are superseded. "
        "That path loaded the stored control ISA QPY, removed measurements, and "
        "saved probabilities before readout; Lexi2 was left at its sampled value. "
        "The two arms therefore did not share a scoring path, and only the control "
        "benefited from removal of readout error. Its sampled-minus-exact mean "
        "was -0.012204, compared with approximately +0.0015 for the earlier "
        "readout-inclusive Lexi2 Task A check.",
        "",
        "The common exact calculation is now: obtain the scored circuit, run "
        "`AerSimulator(method=\"density_matrix\")` on the fixed noise model, "
        "save pre-readout probabilities, then apply the frozen per-qubit readout "
        "confusion matrices. No shot sampling is used. For the phenotype-based "
        "comparison, both arms are reconstructed with the run seed and fixed "
        "target; a run is eligible only when the reconstructed gate, depth, and "
        "2Q counts equal the stored metrics. All 80 controls are additionally "
        "scored from their persisted QPY circuits.",
        "",
        *markdown_table(
            ["Method", "n", "Sampled minus exact: mean", "Median", "Min", "Max"],
            [
                [
                    method,
                    sampled_minus_exact[method]["n"],
                    f"{sampled_minus_exact[method]['mean']:+.6f}",
                    f"{sampled_minus_exact[method]['median']:+.6f}",
                    f"{sampled_minus_exact[method]['min']:+.6f}",
                    f"{sampled_minus_exact[method]['max']:+.6f}",
                ]
                for method in PAIR_METHODS
            ],
        ),
        "",
        "In this table the control summary uses all 80 stored QPY circuits; the "
        "Lexi2 summary uses the 68 phenotype reconstructions that reproduce the "
        "stored transpiled metrics. The paired comparison below uses the same "
        "68 phenotype-reconstructed pairs in both arms.",
        "",
        f"The unified Lexi2 sample-minus-exact mean is "
        f"{sampled_minus_exact[LEX]['mean']:+.6f}, comparable to the earlier "
        "Task A mean of approximately +0.0015.",
        "",
        "Unified exact-value paired comparison:",
        "",
        *markdown_table(
            ["Quantity", "Unified exact result"],
            [
                ["lexi8_random higher / Lexi2 higher / ties", f"{exact_summary['pairs_control_higher']} / {exact_summary['pairs_lexi2_higher']} / {exact_summary['pairs_tied']}"],
                ["Median paired difference (control - Lexi2)", f"{exact_summary['median_paired_diff_control_minus_lexi2']:+.6f}"],
                ["Wilcoxon W / p / non-zero n", f"{exact_summary['wilcoxon_statistic']:.1f} / {exact_summary['wilcoxon_p']:.6f} / {exact_summary['wilcoxon_n_nonzero']}"],
                ["Cliff's delta (control vs Lexi2)", f"{exact_summary['cliffs_delta_control_vs_lexi2']:+.6f}"],
            ],
        ),
        "",
        "The earlier 64/16 control advantage was not a finding about the methods. "
        "It was produced by omitting readout error for only the control arm. "
        "Applying readout confusion to both arms removes that systematic advantage.",
        f"The shared phenotype reconstruction matches the stored transpiled "
        f"metrics for {lexi2_metrics_matches}/80 Lexi2 runs and "
        f"{control_metrics_matches}/80 control runs, giving "
        f"{exact_summary['n_pairs']} complete pairs. The remaining pairs contain "
        "at least one endpoint whose transpiled circuit cannot be reconstructed "
        "from the saved phenotype with the current Qiskit pass manager; the older "
        "Lexi2 runs have no QPY. They are excluded from the paired exact "
        "comparison rather than silently substituting a different transpilation.",
        "",
        "The reconstructed gate/depth/2Q metrics matched the stored logged metrics "
        f"in {metrics_match_total}/160 "
        "runs. For the control's stored QPY, measurement layout matched the "
        f"common-path reconstruction in {qpy_layout_matches}/80 "
        "runs. Full per-run provenance is in `exact_fidelity_unified.csv`.",
        "",
        "## 1. Pre-registered analysis",
        "",
        "### 1.1 Primary: task success and exact McNemar",
        "",
        "Task success requires final fidelity >= 0.95, transpiled gates <= 20, "
        "and transpiled depth <= 15.",
        "",
        *markdown_table(
            ["Cell", "Count"],
            [
                ["Both succeed", stored_summary["mcnemar_both_succeed"]],
                ["Only Lexi2 succeeds", stored_summary["mcnemar_only_lexi2"]],
                ["Only lexi8_random succeeds", stored_summary["mcnemar_only_control"]],
                ["Neither succeeds", stored_summary["mcnemar_neither"]],
            ],
        ),
        "",
        f"Task-success totals: Lexi2 {stored_summary['lex_task_success']}/80, "
        f"lexi8_random {stored_summary['control_task_success']}/80. "
        f"Exact two-sided McNemar p = {stored_summary['mcnemar_exact_p']:.6f}.",
        "The exact test conditions on the discordant pairs and uses no normal "
        "approximation or continuity correction.",
        "",
    ]

    causal = (
        stored_summary["control_task_success"] > stored_summary["lex_task_success"]
        and stored_summary["mcnemar_exact_p"] < 0.05
    )
    if causal:
        lines.append(
            "Pre-registered interpretation: lexi8_random has significantly higher "
            "task success, so the size tiebreak may be described as causal for the "
            "Lexi2 task-success deficit."
        )
    else:
        lines.append(
            "Pre-registered interpretation: the condition for a causal claim is not "
            "met. Do not attribute the observed task-success difference to the size "
            "tiebreak."
        )

    lines.extend(
        [
            "",
            "### 1.2 Secondary: final fidelity and generations to stop",
            "",
            *markdown_table(
                ["Quantity", "Value"],
                [
                    ["Pairs", stored_summary["n_pairs"]],
                    ["lexi8_random higher / Lexi2 higher / ties", f"{stored_summary['pairs_control_higher']} / {stored_summary['pairs_lexi2_higher']} / {stored_summary['pairs_tied']}"],
                    ["Median paired difference (control - Lexi2)", f"{stored_summary['median_paired_diff_control_minus_lexi2']:+.6f}"],
                    ["Mean paired difference (control - Lexi2)", f"{stored_summary['mean_paired_diff_control_minus_lexi2']:+.6f}"],
                    ["Paired Wilcoxon W", f"{stored_summary['wilcoxon_statistic']:.1f}"],
                    ["Paired Wilcoxon p", f"{stored_summary['wilcoxon_p']:.6f}"],
                    ["Non-zero pairs used", stored_summary["wilcoxon_n_nonzero"]],
                    ["Cliff's delta (control vs Lexi2)", f"{stored_summary['cliffs_delta_control_vs_lexi2']:+.6f}"],
                    ["State-cluster bootstrap 95% CI", f"[{stored_summary['cliffs_delta_ci95_state_cluster'][0]:+.6f}, {stored_summary['cliffs_delta_ci95_state_cluster'][1]:+.6f}]"],
                ],
            ),
            "",
            "The Cliff's delta interval resamples the eight state blocks with "
            f"replacement, preserving all ten paired seeds within a sampled "
            f"state ({BOOT_N:,} draws, NumPy seed {BOOT_SEED}). A positive "
            "delta means lexi8_random has the higher fidelity. The Wilcoxon "
            "test is two-sided and uses scipy's default zero handling; this "
            "dataset has 80 non-zero paired differences.",
            "",
        ]
    )

    gens_by_method = {}
    for method in (LEX, CTRL):
        gens_by_method[method] = [
            int(result.get("early_stopped_gen") or 100)
            for result in [
                json.loads(result_path(method, state, seed).read_text())
                for state in STATES
                for seed in SEEDS
            ]
        ]
    lines.extend(
        markdown_table(
            ["Method", "Generations-to-stop mean", "Median", "IQR"],
            [
                [
                    method,
                    f"{np.mean(gens_by_method[method]):.3f}",
                    f"{np.median(gens_by_method[method]):.1f}",
                    f"[{np.percentile(gens_by_method[method], 25):.1f}, {np.percentile(gens_by_method[method], 75):.1f}]",
                ]
                for method in (LEX, CTRL)
            ],
        )
    )
    lines.extend(
        [
            "",
            "Generations-to-stop follows the existing v0.1 convention "
            "`early_stopped_gen or 100`.",
            "",
            "### 1.3 Mechanism",
            "",
            "Population maximum fidelity is read from `p<target>_max`. "
            "Post-case pool size is the shared `post_case_pool_sizes` field, "
            "which contains only non-singleton tiebreak pools in both methods.",
            "",
        ]
    )

    selected_generations = {0, 1, 2, 5, 10, 25, 50, 75, 99}
    mech_table = []
    for generation in sorted(selected_generations):
        row = [generation]
        for rows, method in (
            (fidelity_rows, LEX),
            (fidelity_rows, CTRL),
            (pool_rows, LEX),
            (pool_rows, CTRL),
        ):
            match = next(
                (
                    entry
                    for entry in rows
                    if entry["method"] == method
                    and entry["generation"] == generation
                ),
                None,
            )
            if match is None:
                row.extend(["NA", "NA"])
            else:
                row.extend(
                    [
                        f"{match['mean']:.3f}",
                        f"[{match['q1']:.3f}, {match['q3']:.3f}]",
                    ]
                )
        mech_table.append(row)
    lines.extend(
        markdown_table(
            [
                "Gen",
                "Lexi2 max-fid mean",
                "Lexi2 max-fid IQR",
                "Control max-fid mean",
                "Control max-fid IQR",
                "Lexi2 pool mean",
                "Lexi2 pool IQR",
                "Control pool mean",
                "Control pool IQR",
            ],
            mech_table,
        )
    )
    lines.extend(
        [
            "",
            "The full per-generation distributions are in the two mechanism CSV "
            "files. The vector PDF contains both panels and uses the method names "
            "Lexi2 and lexi8_random. Later-generation summaries are based only "
            "on runs still active at that generation; the `n` column in each CSV "
            "records the changing sample size.",
            "",
            "### 1.4 Robustness: exact density-matrix rescoring",
            "",
            "All 80 lexi8_random endpoints were re-scored from stored QPY. "
            f"The paired exact comparison uses the {exact_summary['n_pairs']} "
            "(state, seed) pairs for "
            "which both phenotype reconstructions reproduce the stored transpiled "
            "metrics and therefore share the same reconstruction path. Exact task "
            "success uses exact fidelity with the stored transpiled size metrics.",
            "",
            *markdown_table(
                ["Quantity", "Lexi2 sampled", "Lexi2 exact", "Control sampled", "Control exact"],
                [
                    ["Task success on comparable set", "see stored 80-run result", f"{exact_summary['lex_task_success']}/{exact_summary['n_pairs']}", "see stored 80-run result", f"{exact_summary['control_task_success']}/{exact_summary['n_pairs']}"],
                    ["Median final fidelity", f"{stored_summary['lex_median_fidelity']:.6f}", f"{exact_summary['lex_median_fidelity']:.6f}", f"{stored_summary['control_median_fidelity']:.6f}", f"{exact_summary['control_median_fidelity']:.6f}"],
                    ["Mean final fidelity", f"{stored_summary['lex_mean_fidelity']:.6f}", f"{exact_summary['lex_mean_fidelity']:.6f}", f"{stored_summary['control_mean_fidelity']:.6f}", f"{exact_summary['control_mean_fidelity']:.6f}"],
                ],
            ),
            "",
            "Exact-value paired comparison:",
            "",
            *markdown_table(
                ["Quantity", "Exact-value result"],
                [
                    ["McNemar cells (both / only Lexi2 / only control / neither)", f"{exact_summary['mcnemar_both_succeed']} / {exact_summary['mcnemar_only_lexi2']} / {exact_summary['mcnemar_only_control']} / {exact_summary['mcnemar_neither']}"],
                    ["Exact McNemar p", f"{exact_summary['mcnemar_exact_p']:.6f}"],
                    ["Control higher / Lexi2 higher / ties", f"{exact_summary['pairs_control_higher']} / {exact_summary['pairs_lexi2_higher']} / {exact_summary['pairs_tied']}"],
                    ["Median paired difference", f"{exact_summary['median_paired_diff_control_minus_lexi2']:+.6f}"],
                    ["Wilcoxon W / p / non-zero n", f"{exact_summary['wilcoxon_statistic']:.1f} / {exact_summary['wilcoxon_p']:.6f} / {exact_summary['wilcoxon_n_nonzero']}"],
                    ["Cliff's delta (control vs Lexi2)", f"{exact_summary['cliffs_delta_control_vs_lexi2']:+.6f}"],
                ],
            ),
            "",
            "The paired exact comparison is not the primary task-success test; "
            "the primary analysis remains based on the stored sampled endpoint.",
            "",
            "## 2. Descriptive tables",
            "",
            "### 2.1 Per-state task success",
            "",
            *markdown_table(
                ["State", "Lexi2", "lexi8_random", "Control - Lexi2"],
                [
                    [
                        row["state"],
                        f"{row['lexi2_task_success']}/10",
                        f"{row['control_task_success']}/10",
                        f"{row['control_minus_lexi2']:+d}",
                    ]
                    for row in success_rows
                ],
            ),
            "",
            "### 2.2 lexi8_random failure composition",
            "",
            *markdown_table(
                ["State", "Early stop", "Late success", "Fidelity fail", "Size fail", "Total"],
                [
                    [
                        row["state"],
                        row["early stop"],
                        row["late success"],
                        row["fidelity fail"],
                        row["size fail"],
                        row["total"],
                    ]
                    for row in failure_rows
                ],
            ),
            "",
            *markdown_table(
                ["Category", "Total"],
                [
                    [category, sum(row[category] for row in failure_rows)]
                    for category in (
                        "early stop",
                        "late success",
                        "fidelity fail",
                        "size fail",
                    )
                ],
            ),
            "",
            "Classification is mutually exclusive and uses the final stored "
            "champion: early stop, late task success, fidelity failure, or size "
            "failure.",
            "",
            "### 2.3 Run-level median circuit size",
            "",
            *markdown_table(
                ["Method", "Population", "n", "Gates", "Depth", "2Q"],
                [
                    [
                        row["method"],
                        row["population"],
                        row["n_runs"],
                        row["median_gates"],
                        row["median_depth"],
                        row["median_two_qubit_gates"],
                    ]
                    for row in median_rows
                ],
            ),
            "",
            "### 2.4 Control-only highest-fidelity-individual fields",
            "",
            "These fields are descriptive for lexi8_random only and are not used "
            "for between-method inference.",
            "",
            *markdown_table(
                ["Gen", "n", "Fid mean [IQR]", "Gates mean [IQR]", "Depth mean [IQR]", "2Q mean [IQR]", "Any meets all targets"],
                [
                    [
                        row["generation"],
                        row["n_runs"],
                        f"{row['fidelity_mean']:.3f} [{row['fidelity_q1']:.3f}, {row['fidelity_q3']:.3f}]",
                        f"{row['gates_mean']:.2f} [{row['gates_q1']:.2f}, {row['gates_q3']:.2f}]",
                        f"{row['depth_mean']:.2f} [{row['depth_q1']:.2f}, {row['depth_q3']:.2f}]",
                        f"{row['two_qubit_gates_mean']:.2f} [{row['two_qubit_gates_q1']:.2f}, {row['two_qubit_gates_q3']:.2f}]",
                        f"{row['fraction_any_individual_meets_all_targets']:.3f}",
                    ]
                    for row in highest_rows
                    if row["generation"] in selected_generations
                ],
            ),
            "",
            "The complete per-generation descriptive table is in "
            "`control_highest_fidelity_individual_by_generation.csv`.",
            "",
            "## EXPLORATORY (post hoc; not pre-registered)",
            "",
            "### E1. Paired task-success difference",
            "",
            f"Lexi2 minus lexi8_random task-success difference: "
            f"**{paired_success_delta:+.6f}** (5/80, or 6.25 percentage points). "
            f"Exact conditional 95% CI: "
            f"**[{paired_success_ci[0]:+.6f}, {paired_success_ci[1]:+.6f}]**. "
            "The interval conditions on the 17 Lexi2-only and 12 control-only "
            "discordant pairs and applies a Clopper-Pearson interval to their "
            "win probability.",
            "",
            "### E2. Four-method task success and failure composition",
            "",
            *markdown_table(
                ["Method", "Task successes", "n", "Proportion"],
                [
                    [
                        row["method"],
                        row["task_successes"],
                        row["n_runs"],
                        f"{row['task_success_proportion']:.3f}",
                    ]
                    for row in four_arm_overall
                ],
            ),
            "",
            *(
                lambda per_state: markdown_table(
                    ["State", *ALL_METHODS],
                    [
                        [
                            state,
                            *[
                                next(
                                    row["task_successes"]
                                    for row in four_arm_by_state
                                    if row["method"] == method
                                    and row["state"] == state
                                )
                                for method in ALL_METHODS
                            ],
                        ]
                        for state in STATES
                    ],
                )
            )(four_arm_by_state),
            "",
            *markdown_table(
                ["Method", "Early stop", "Late success", "Fidelity fail", "Size fail", "Total"],
                [
                    [
                        row["method"],
                        row["early stop"],
                        row["late success"],
                        row["fidelity fail"],
                        row["size fail"],
                        row["total"],
                    ]
                    for row in four_arm_failure
                ],
            ),
            "",
            "### E3. Mechanism summary at selected generations",
            "",
            *markdown_table(
                ["Method", "Gen", "Max-fid mean", "Runs", "Pool mean", "Selections"],
                [
                    [
                        row["method"],
                        row["generation"],
                        (
                            f"{row['population_max_fidelity_mean']:.6f}"
                            if row["population_max_fidelity_mean"] != ""
                            else "NA"
                        ),
                        row["population_max_fidelity_n_runs"],
                        (
                            f"{row['post_case_pool_size_mean']:.6f}"
                            if row["post_case_pool_size_mean"] != ""
                            else "NA"
                        ),
                        row["post_case_pool_size_n_selections"],
                    ]
                    for row in mechanism_summary
                ],
            ),
            "",
            "Population maximum fidelity is available for all four methods. "
            "Post-case pool size is available only for Lexi2 and lexi8_random; "
            "the v0.1 epsilon-lexicase and tournament artifacts did not log those "
            "pools, so no values are reconstructed or invented here.",
            "",
            "## Outputs",
            "",
            "- `integrity_check.json`",
            "- `control_arm_results.json`",
            "- `run_level_paired.csv`",
            "- `exact_fidelity_unified.csv`",
            "- `per_state_task_success.csv`",
            "- `control_failure_composition.csv`",
            "- `run_level_median_sizes.csv`",
            "- `four_arm_task_success.csv`",
            "- `four_arm_task_success_by_state.csv`",
            "- `four_arm_failure_composition.csv`",
            "- `mechanism_selected_generations.csv`",
            "- `mechanism_population_max_fidelity_by_generation.csv`",
            "- `mechanism_post_case_pool_size_by_generation.csv`",
            "- `control_highest_fidelity_individual_by_generation.csv`",
            "- `cliffs_delta_state_cluster_bootstrap.csv`",
            "- `figures/control_arm_mechanism.pdf`",
        ]
    )
    (OUT / "CONTROL_ARM_ANALYSIS.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    results, _loaded = load_analysis_data()
    integrity = integrity_check(results)
    write_json(OUT / "integrity_check.json", integrity)
    if not integrity["passed"]:
        raise SystemExit("Integrity checks failed; analysis stopped.")

    lex_meta = [
        results[(LEX, state, seed)]
        for state in STATES
        for seed in SEEDS
    ]
    ctrl_meta = [
        results[(CTRL, state, seed)]
        for state in STATES
        for seed in SEEDS
    ]
    lex_fid = np.asarray([result["fidelity"] for result in lex_meta], dtype=float)
    ctrl_fid = np.asarray([result["fidelity"] for result in ctrl_meta], dtype=float)

    stored_summary = paired_fidelity_summary(
        lex_fid,
        ctrl_fid,
        lex_meta=lex_meta,
        ctrl_meta=ctrl_meta,
        fidelity_key="fidelity",
    )

    common_exact, control_qpy_exact = exact_rescoring(results)
    exact_pair_coordinates = [
        (state, seed)
        for state in STATES
        for seed in SEEDS
        if common_exact[(LEX, state, seed)]["metrics_match"]
        and common_exact[(CTRL, state, seed)]["metrics_match"]
    ]
    exact_lex_values = np.asarray(
        [
            common_exact[(LEX, state, seed)]["exact_fidelity"]
            for state, seed in exact_pair_coordinates
        ],
        dtype=float,
    )
    exact_ctrl_values = np.asarray(
        [
            common_exact[(CTRL, state, seed)]["exact_fidelity"]
            for state, seed in exact_pair_coordinates
        ],
        dtype=float,
    )
    exact_lex_meta = [
        {
            **results[(LEX, state, seed)],
            "exact_fidelity": common_exact[(LEX, state, seed)][
                "exact_fidelity"
            ],
        }
        for state, seed in exact_pair_coordinates
    ]
    exact_ctrl_meta = [
        {
            **results[(CTRL, state, seed)],
            "exact_fidelity": common_exact[(CTRL, state, seed)][
                "exact_fidelity"
            ],
        }
        for state, seed in exact_pair_coordinates
    ]
    exact_summary = paired_exact_summary(
        exact_lex_values,
        exact_ctrl_values,
        exact_lex_meta,
        exact_ctrl_meta,
    )

    success_rows, failure_rows = per_state_rows(results)
    median_rows = size_rows(results)
    fidelity_rows, pool_rows, highest_rows = mechanism_tables(results)
    sampled_minus_exact = {
        LEX: qsummary(
            [
                results[(LEX, state, seed)]["fidelity"]
                - common_exact[(LEX, state, seed)]["exact_fidelity"]
                for state, seed in exact_pair_coordinates
            ]
        ),
        CTRL: qsummary(
            [
                results[(CTRL, state, seed)]["fidelity"]
                - control_qpy_exact[(state, seed)]["exact_fidelity"]
                for state in STATES
                for seed in SEEDS
            ]
        ),
    }

    all_results = load_all_analysis_data()
    four_arm_overall, four_arm_by_state, four_arm_failure = four_arm_descriptives(
        all_results
    )
    mechanism_summary = mechanism_selected_generations(fidelity_rows, pool_rows)
    paired_success_delta = (
        stored_summary["lex_task_success"]
        - stored_summary["control_task_success"]
    ) / 80.0
    paired_success_ci = exact_conditional_paired_ci(
        stored_summary["mcnemar_only_lexi2"],
        stored_summary["mcnemar_only_control"],
        80,
    )

    paired_rows = []
    for index, (state, seed) in enumerate(
        [(state, seed) for state in STATES for seed in SEEDS]
    ):
        lex_result = results[(LEX, state, seed)]
        ctrl_result = results[(CTRL, state, seed)]
        paired_rows.append(
            {
                "state": state,
                "seed": seed,
                "lexi2_fidelity": lex_result["fidelity"],
                "control_fidelity": ctrl_result["fidelity"],
                "paired_diff_control_minus_lexi2": ctrl_fid[index] - lex_fid[index],
                "lexi2_task_success": task_success(lex_result),
                "control_task_success": task_success(ctrl_result),
                "lexi2_gates": lex_result["gate_count"],
                "control_gates": ctrl_result["gate_count"],
                "lexi2_depth": lex_result["depth"],
                "control_depth": ctrl_result["depth"],
                "lexi2_two_qubit_gates": lex_result["two_qubit_gates"],
                "control_two_qubit_gates": ctrl_result["two_qubit_gates"],
                "lexi2_generations_to_stop": int(
                    lex_result.get("early_stopped_gen") or 100
                ),
                "control_generations_to_stop": int(
                    ctrl_result.get("early_stopped_gen") or 100
                ),
                "control_stop_family": stop_family(ctrl_result),
                "lexi2_phenotype_exact_fidelity": common_exact[
                    (LEX, state, seed)
                ]["exact_fidelity"],
                "control_phenotype_exact_fidelity": common_exact[
                    (CTRL, state, seed)
                ]["exact_fidelity"],
                "control_qpy_exact_fidelity": control_qpy_exact[
                    (state, seed)
                ]["exact_fidelity"],
                "common_path_pair_eligible": (
                    common_exact[(LEX, state, seed)]["metrics_match"]
                    and common_exact[(CTRL, state, seed)]["metrics_match"]
                ),
                "lexi2_sampled_minus_phenotype_exact": (
                    lex_result["fidelity"]
                    - common_exact[(LEX, state, seed)]["exact_fidelity"]
                    if common_exact[(LEX, state, seed)]["metrics_match"]
                    else None
                ),
                "control_sampled_minus_phenotype_exact": (
                    ctrl_result["fidelity"]
                    - common_exact[(CTRL, state, seed)]["exact_fidelity"]
                    if common_exact[(CTRL, state, seed)]["metrics_match"]
                    else None
                ),
                "control_sampled_minus_qpy_exact": (
                    ctrl_result["fidelity"]
                    - control_qpy_exact[(state, seed)]["exact_fidelity"]
                ),
                "lexi2_exact_task_success": (
                    bool(
                        common_exact[(LEX, state, seed)]["exact_fidelity"]
                        >= FID_TARGET
                        and int(lex_result["gate_count"]) <= GATE_TARGET
                        and int(lex_result["depth"]) <= DEPTH_TARGET
                    )
                    if common_exact[(LEX, state, seed)]["metrics_match"]
                    else None
                ),
                "control_exact_task_success": bool(
                    control_qpy_exact[(state, seed)]["exact_fidelity"]
                    >= FID_TARGET
                    and int(ctrl_result["gate_count"]) <= GATE_TARGET
                    and int(ctrl_result["depth"]) <= DEPTH_TARGET
                ),
                "lexi2_reconstructed_gates": common_exact[(LEX, state, seed)][
                    "reconstructed_gates"
                ],
                "control_reconstructed_gates": common_exact[(CTRL, state, seed)][
                    "reconstructed_gates"
                ],
                "lexi2_reconstructed_depth": common_exact[(LEX, state, seed)][
                    "reconstructed_depth"
                ],
                "control_reconstructed_depth": common_exact[(CTRL, state, seed)][
                    "reconstructed_depth"
                ],
            }
        )

    exact_path_rows = []
    for method in PAIR_METHODS:
        for state in STATES:
            for run_id, seed in enumerate(SEEDS, 1):
                result = results[(method, state, seed)]
                record = common_exact[(method, state, seed)]
                qpy_gates = ""
                qpy_depth = ""
                qpy_two_qubit_gates = ""
                qpy_measurement_layout = ""
                qpy_layout_matches_reconstruction = ""
                qpy_exact_fidelity = ""
                if method == CTRL:
                    _circuit, metadata, _qpy, _meta = load_scored_isa(
                        str(run_dir(method, state, seed)), state, run_id
                    )
                    qpy_exact_fidelity = control_qpy_exact[(state, seed)][
                        "exact_fidelity"
                    ]
                    qpy_gates = metadata["gate_count"]
                    qpy_depth = metadata["depth"]
                    qpy_two_qubit_gates = metadata["two_qubit_gates"]
                    qpy_measurement_layout = json.dumps(
                        metadata["measurement_layout"]
                    )
                    qpy_layout_matches_reconstruction = (
                        metadata["measurement_layout"]
                        == record["measurement_layout"]
                    )
                exact_path_rows.append(
                    {
                        "method": method,
                        "state": state,
                        "seed": seed,
                        "sampled_fidelity": result["fidelity"],
                        "exact_fidelity": record["exact_fidelity"],
                        "sampled_minus_exact": (
                            result["fidelity"] - record["exact_fidelity"]
                            if record["exact_fidelity"] is not None
                            else ""
                        ),
                        "metrics_match": record["metrics_match"],
                        "recorded_metrics": list(record["recorded_metrics"]),
                        "reconstructed_metrics": list(
                            record["reconstructed_metrics"]
                        ),
                        "control_qpy_exact_fidelity": qpy_exact_fidelity,
                        "control_sampled_minus_qpy_exact": (
                            result["fidelity"] - qpy_exact_fidelity
                            if qpy_exact_fidelity != ""
                            else ""
                        ),
                        "recorded_gates": result["gate_count"],
                        "reconstructed_gates": record["reconstructed_gates"],
                        "recorded_depth": result["depth"],
                        "reconstructed_depth": record["reconstructed_depth"],
                        "recorded_two_qubit_gates": result[
                            "two_qubit_gates"
                        ],
                        "reconstructed_two_qubit_gates": record[
                            "reconstructed_two_qubit_gates"
                        ],
                        "qpy_gates_for_control_comparison": qpy_gates,
                        "qpy_depth_for_control_comparison": qpy_depth,
                        "qpy_two_qubit_gates_for_control_comparison": (
                            qpy_two_qubit_gates
                        ),
                        "qpy_measurement_layout": qpy_measurement_layout,
                        "qpy_layout_matches_reconstruction": (
                            qpy_layout_matches_reconstruction
                        ),
                        "transpiler_seed": record["transpiler_seed"],
                    }
                )

    write_csv(
        OUT / "run_level_paired.csv",
        list(paired_rows[0]),
        paired_rows,
    )
    write_csv(
        OUT / "exact_fidelity_unified.csv",
        list(exact_path_rows[0]),
        exact_path_rows,
    )
    write_csv(
        OUT / "per_state_task_success.csv",
        list(success_rows[0]),
        success_rows,
    )
    write_csv(
        OUT / "control_failure_composition.csv",
        list(failure_rows[0]),
        failure_rows,
    )
    write_csv(
        OUT / "run_level_median_sizes.csv",
        list(median_rows[0]),
        median_rows,
    )
    write_csv(
        OUT / "mechanism_population_max_fidelity_by_generation.csv",
        list(fidelity_rows[0]),
        fidelity_rows,
    )
    write_csv(
        OUT / "mechanism_post_case_pool_size_by_generation.csv",
        list(pool_rows[0]),
        pool_rows,
    )
    write_csv(
        OUT / "control_highest_fidelity_individual_by_generation.csv",
        list(highest_rows[0]),
        highest_rows,
    )
    write_csv(
        OUT / "four_arm_task_success.csv",
        list(four_arm_overall[0]),
        four_arm_overall,
    )
    write_csv(
        OUT / "four_arm_task_success_by_state.csv",
        list(four_arm_by_state[0]),
        four_arm_by_state,
    )
    write_csv(
        OUT / "four_arm_failure_composition.csv",
        list(four_arm_failure[0]),
        four_arm_failure,
    )
    write_csv(
        OUT / "mechanism_selected_generations.csv",
        list(mechanism_summary[0]),
        mechanism_summary,
    )

    boot_draws = state_cluster_bootstrap(
        ctrl_fid,
        lex_fid,
        statistic=cliffs_delta,
        rng_seed=BOOT_SEED,
        draws=BOOT_N,
    )[0]
    write_csv(
        OUT / "cliffs_delta_state_cluster_bootstrap.csv",
        ["draw", "cliffs_delta_control_vs_lexi2"],
        [
            {"draw": i, "cliffs_delta_control_vs_lexi2": value}
            for i, value in enumerate(boot_draws)
        ],
    )

    mechanism_pdf = plot_mechanism(fidelity_rows, pool_rows)
    stored_summary["control_mean_fidelity"] = float(np.mean(ctrl_fid))
    combined = {
        "integrity": integrity,
        "stored_fidelity_analysis": stored_summary,
        "exact_density_matrix_analysis": exact_summary,
        "sampled_minus_exact_fidelity_distribution": sampled_minus_exact,
        "exploratory_paired_task_success": {
            "difference_lexi2_minus_control": paired_success_delta,
            "exact_conditional_95_ci": list(paired_success_ci),
            "method": (
                "Clopper-Pearson exact conditional interval for paired risk "
                "difference"
            ),
        },
        "exploratory_four_arm_task_success": four_arm_overall,
        "exploratory_four_arm_task_success_by_state": four_arm_by_state,
        "exploratory_four_arm_failure_composition": four_arm_failure,
        "exploratory_mechanism_selected_generations": mechanism_summary,
        "per_state_task_success": success_rows,
        "control_failure_composition": failure_rows,
        "run_level_median_sizes": median_rows,
        "mechanism_figure": str(mechanism_pdf.relative_to(ROOT)),
        "analysis_plan_sha256": hashlib.sha256(
            (ROOT / "ANALYSIS_PLAN_control_arm.md").read_bytes()
        ).hexdigest(),
    }
    write_json(OUT / "control_arm_results.json", combined)
    build_report(
        integrity,
        stored_summary,
        exact_summary,
        success_rows,
        failure_rows,
        median_rows,
        fidelity_rows,
        pool_rows,
        highest_rows,
        sampled_minus_exact,
        paired_rows,
        four_arm_overall,
        four_arm_by_state,
        four_arm_failure,
        mechanism_summary,
        paired_success_delta,
        paired_success_ci,
        exact_path_rows,
    )
    print(json.dumps(combined, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
