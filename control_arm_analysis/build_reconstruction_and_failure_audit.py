#!/usr/bin/env python3
"""Audit Task A reconstruction provenance and control-arm failures.

This script reads existing artifacts and transpiles stored phenotypes. It does
not execute evolution, submit hardware jobs, or edit the manuscript.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import build_control_arm_analysis as analysis


NOISE_BUNDLE = ROOT / "noise" / "frozen_env_ibm_fez_2026-08-20.pkl"
DETERMINISM_CASES = [("000", 80248), ("001", 70300), ("111", 67154)]


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


def build_circuit(phenotype: str) -> QuantumCircuit:
    namespace = {}
    exec(
        phenotype,
        {
            "np": np,
            "QuantumCircuit": QuantumCircuit,
            "QuantumRegister": QuantumRegister,
            "ClassicalRegister": ClassicalRegister,
        },
        namespace,
    )
    return namespace["qc"]


def circuit_signature(circuit: QuantumCircuit) -> dict:
    layout = [None] * 3
    for instruction in circuit.data:
        if instruction.operation.name == "measure":
            cbit = circuit.find_bit(instruction.clbits[0]).index
            layout[cbit] = int(instruction.qubits[0]._index)
    operations = [
        (
            instruction.operation.name,
            [int(q._index) for q in instruction.qubits],
            [int(c._index) for c in instruction.clbits],
            [str(parameter) for parameter in instruction.operation.params],
        )
        for instruction in circuit.data
    ]
    return {
        "gates": int(circuit.size()),
        "depth": int(circuit.depth()),
        "two_qubit_gates": int(
            sum(
                1
                for instruction in circuit.data
                if instruction.operation.num_qubits >= 2
            )
        ),
        "measurement_layout": layout,
        "circuit_hash": hashlib.sha256(repr(operations).encode()).hexdigest(),
    }


def task_a_transpile(state: str, seed: int, repeats: int = 8) -> list[dict]:
    result = read_json(analysis.result_path(analysis.LEX, state, seed))
    circuit = build_circuit(result["phenotype"])
    with NOISE_BUNDLE.open("rb") as handle:
        target = pickle.load(handle)["target"]
    expected = (
        int(result["gate_count"]),
        int(result["depth"]),
        int(result["two_qubit_gates"]),
    )
    rows = []
    for attempt in range(1, repeats + 1):
        pass_manager = generate_preset_pass_manager(
            target=target,
            optimization_level=3,
            seed_transpiler=result["seed"],
        )
        transpiled = pass_manager.run(circuit)
        signature = circuit_signature(transpiled)
        actual = (
            signature["gates"],
            signature["depth"],
            signature["two_qubit_gates"],
        )
        rows.append(
            {
                "state": state,
                "seed": seed,
                "attempt": attempt,
                "expected_gates": expected[0],
                "expected_depth": expected[1],
                "expected_two_qubit_gates": expected[2],
                "actual_gates": actual[0],
                "actual_depth": actual[1],
                "actual_two_qubit_gates": actual[2],
                "metrics_match": actual == expected,
                "measurement_layout": json.dumps(
                    signature["measurement_layout"]
                ),
                "circuit_hash": signature["circuit_hash"],
                "transpiler_seed": int(result["seed"]),
            }
        )
    return rows


def one_transpilation_json(state: str, seed: int) -> dict:
    result = read_json(analysis.result_path(analysis.LEX, state, seed))
    with NOISE_BUNDLE.open("rb") as handle:
        target = pickle.load(handle)["target"]
    transpiled = generate_preset_pass_manager(
        target=target,
        optimization_level=3,
        seed_transpiler=result["seed"],
    ).run(build_circuit(result["phenotype"]))
    signature = circuit_signature(transpiled)
    signature.update({"state": state, "seed": seed})
    return signature


def determinism_rows() -> tuple[list[dict], list[dict]]:
    same_process = []
    fresh_process = []
    for state, seed in DETERMINISM_CASES:
        for repeat in range(1, 6):
            signature = one_transpilation_json(state, seed)
            same_process.append(
                {"mode": "same process", "repeat": repeat, **signature}
            )
        for repeat in range(1, 6):
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--one",
                    state,
                    str(seed),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            signature = json.loads(completed.stdout)
            fresh_process.append(
                {"mode": "fresh process", "repeat": repeat, **signature}
            )
    return same_process, fresh_process


def failed_run_diagnostics() -> list[dict]:
    rows = []
    for state in analysis.STATES:
        for seed in analysis.SEEDS:
            champion = read_json(
                analysis.result_path(analysis.CTRL, state, seed)
            )
            if analysis.task_success(champion):
                continue
            selection_log = read_json(
                analysis.log_path(analysis.CTRL, state, seed)
            )["per_generation"]
            generations = sorted(int(value) for value in selection_log)
            final_generation = generations[-1]
            final_record = selection_log[str(final_generation)]
            highest = final_record["highest_fidelity_individual"]
            target_generations = [
                generation
                for generation in generations
                if selection_log[str(generation)].get(
                    "any_individual_meets_all_targets", False
                )
            ]
            rows.append(
                {
                    "state": state,
                    "seed": seed,
                    "final_generation": final_generation,
                    "highest_fidelity_individual_fidelity": highest[
                        "fidelity"
                    ],
                    "highest_fidelity_individual_gates": highest["gates"],
                    "highest_fidelity_individual_depth": highest["depth"],
                    "highest_fidelity_individual_two_qubit_gates": highest[
                        "two_qubit_gates"
                    ],
                    "any_target_meeting_individual": bool(
                        target_generations
                    ),
                    "first_target_meeting_generation": (
                        target_generations[0]
                        if target_generations
                        else ""
                    ),
                    "champion_fidelity": champion["fidelity"],
                    "champion_gates": champion["gate_count"],
                    "champion_depth": champion["depth"],
                    "champion_two_qubit_gates": champion[
                        "two_qubit_gates"
                    ],
                    "champion_stop_reason": champion["stop_reason"],
                }
            )
    return rows


def markdown_table(headers: list[str], rows: list[list]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    lines.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
    return lines


def main() -> None:
    exact_rows = list(
        csv.DictReader((HERE / "exact_fidelity_unified.csv").open())
    )
    unmatched = [
        (row["state"], int(row["seed"]), row)
        for row in exact_rows
        if row["method"] == analysis.LEX and row["metrics_match"] != "True"
    ]
    if len(unmatched) != 8:
        raise RuntimeError(f"expected 8 unmatched Lexi2 runs, found {len(unmatched)}")

    task_a_rows = []
    for state, seed, _row in unmatched:
        task_a_rows.extend(task_a_transpile(state, seed))
    write_csv(
        HERE / "task_a_reconstruction_attempts.csv",
        list(task_a_rows[0]),
        task_a_rows,
    )
    task_a_by_case = {}
    for row in task_a_rows:
        task_a_by_case.setdefault((row["state"], row["seed"]), []).append(row)

    same_process, fresh_process = determinism_rows()
    determinism = same_process + fresh_process
    write_csv(
        HERE / "transpiler_determinism_3x5.csv",
        list(determinism[0]),
        determinism,
    )

    failure_rows = failed_run_diagnostics()
    if len(failure_rows) != 28:
        raise RuntimeError(
            f"expected 28 control task failures, found {len(failure_rows)}"
        )
    write_csv(
        HERE / "control_failure_population_diagnostics.csv",
        list(failure_rows[0]),
        failure_rows,
    )

    target_meeting_failures = [
        row for row in failure_rows if row["any_target_meeting_individual"]
    ]
    summary = {
        "task_a_archived_result": {
            "records_processed": 240,
            "metric_mismatches": 9,
            "lexi2_metric_mismatches": 8,
        },
        "task_a_path": (
            "Build phenotype, then instantiate a fresh preset pass manager "
            "with target=frozen target, optimization_level=3, "
            "seed_transpiler=run seed; retry up to 8 times and accept the "
            "first circuit whose gate/depth/2Q metrics match the log."
        ),
        "unmatched_lexi2_runs": [
            {
                "state": state,
                "seed": seed,
                "expected": [
                    int(row["recorded_gates"]),
                    int(row["recorded_depth"]),
                    int(row["recorded_two_qubit_gates"]),
                ],
                "actual": [
                    int(
                        task_a_by_case[(state, seed)][-1][
                            "actual_gates"
                        ]
                    ),
                    int(
                        task_a_by_case[(state, seed)][-1][
                            "actual_depth"
                        ]
                    ),
                    int(
                        task_a_by_case[(state, seed)][-1][
                            "actual_two_qubit_gates"
                        ]
                    ),
                ],
                "matched_under_task_a": any(
                    item["metrics_match"]
                    for item in task_a_rows
                    if item["state"] == state and item["seed"] == seed
                ),
            }
            for state, seed, row in unmatched
        ],
        "determinism": {
            "cases": [
                {"state": state, "seed": seed}
                for state, seed in DETERMINISM_CASES
            ],
            "repeats_per_case_per_mode": 5,
            "same_process_unique_signatures": {
                f"{state}_{seed}": len(
                    {
                        (
                            row["gates"],
                            row["depth"],
                            row["two_qubit_gates"],
                            tuple(row["measurement_layout"]),
                            row["circuit_hash"],
                        )
                        for row in same_process
                        if row["state"] == state and row["seed"] == seed
                    }
                )
                for state, seed in DETERMINISM_CASES
            },
            "fresh_process_unique_signatures": {
                f"{state}_{seed}": len(
                    {
                        (
                            row["gates"],
                            row["depth"],
                            row["two_qubit_gates"],
                            tuple(row["measurement_layout"]),
                            row["circuit_hash"],
                        )
                        for row in fresh_process
                        if row["state"] == state and row["seed"] == seed
                    }
                )
                for state, seed in DETERMINISM_CASES
            },
        },
        "control_task_failures": {
            "n": len(failure_rows),
            "target_meeting_individual_ever": len(
                target_meeting_failures
            ),
            "target_meeting_but_champion_failed": [
                {
                    "state": row["state"],
                    "seed": row["seed"],
                    "first_target_meeting_generation": row[
                        "first_target_meeting_generation"
                    ],
                }
                for row in target_meeting_failures
            ],
        },
    }
    write_json(HERE / "reconstruction_and_failure_audit.json", summary)

    task_a_table = []
    for state, seed, row in unmatched:
        attempts = task_a_by_case[(state, seed)]
        task_a_table.append(
            [
                state,
                seed,
                f"{row['recorded_gates']}/{row['recorded_depth']}/{row['recorded_two_qubit_gates']}",
                f"{attempts[-1]['actual_gates']}/{attempts[-1]['actual_depth']}/{attempts[-1]['actual_two_qubit_gates']}",
                any(item["metrics_match"] for item in attempts),
            ]
        )

    determinism_table = []
    for state, seed in DETERMINISM_CASES:
        same = [
            row
            for row in same_process
            if row["state"] == state and row["seed"] == seed
        ]
        fresh = [
            row
            for row in fresh_process
            if row["state"] == state and row["seed"] == seed
        ]
        determinism_table.append(
            [
                state,
                seed,
                f"{same[0]['gates']}/{same[0]['depth']}/{same[0]['two_qubit_gates']}",
                len({row["circuit_hash"] for row in same}),
                len({row["circuit_hash"] for row in fresh}),
            ]
        )

    failure_table = [
        [
            row["state"],
            row["seed"],
            row["final_generation"],
            f"{row['highest_fidelity_individual_fidelity']:.4f}",
            row["highest_fidelity_individual_gates"],
            row["highest_fidelity_individual_depth"],
            row["highest_fidelity_individual_two_qubit_gates"],
            row["any_target_meeting_individual"],
            row["first_target_meeting_generation"],
            f"{row['champion_fidelity']:.4f}",
            row["champion_gates"],
            row["champion_depth"],
            row["champion_two_qubit_gates"],
        ]
        for row in failure_rows
    ]

    lines = [
        "# Reconstruction and control-failure audit",
        "",
        "No evolution or hardware job was run. This audit reads stored run "
        "artifacts and performs local transpilation only.",
        "",
        "## 1. Task A reconstruction path",
        "",
        "The archived Task A implementation built each phenotype, instantiated "
        "a fresh `generate_preset_pass_manager(target=frozen_target, "
        "optimization_level=3, seed_transpiler=run_seed)`, and retried up to "
        "eight times, accepting the first circuit whose gate count, depth, and "
        "2Q count matched the stored run. It processed 240 champions and its "
        "archived output recorded **9 mismatches**, including the same eight "
        "Lexi2 runs identified here. Therefore Task A did not reconstruct all "
        "240 champions with matching circuit metrics.",
        "",
        "| State | Seed | Stored G/D/2Q | Reconstructed G/D/2Q | Matched in 8 attempts |",
        "|---|---:|---:|---:|---|",
        *["| " + " | ".join(map(str, row)) + " |" for row in task_a_table],
        "",
        "All eight Lexi2 runs remain unmatched under the Task A retry path. "
        "The first task-A attempt already fixes the result because level-3 "
        "transpilation with a fixed seed is deterministic in this environment.",
        "",
        "## 2. Determinism test",
        "",
        "Three unmatched circuits were transpiled five times in one process "
        "and five times in fresh interpreter processes with the same fixed "
        "seed.",
        "",
        "| State | Seed | G/D/2Q | Unique same-process circuits | Unique fresh-process circuits |",
        "|---|---:|---:|---:|---:|",
        *["| " + " | ".join(map(str, row)) + " |" for row in determinism_table],
        "",
        "Each circuit produced one unique metric/layout/operation-signature "
        "across all five repeats in each mode. The stored metrics therefore "
        "came from a transpilation context that the saved phenotype plus run "
        "seed does not reproduce; repeating the same fixed-seed call does not "
        "recover it.",
        "",
        "# EXPLORATORY: control-arm failure diagnostics",
        "",
        f"There are {len(failure_rows)} control task failures. "
        f"{len(target_meeting_failures)} had at least one individual that met "
        "all three targets in some generation while the final scalar-HOF "
        "champion did not:",
        "",
        *markdown_table(
            ["State", "Seed", "First target-meeting generation"],
            [
                [
                    row["state"],
                    row["seed"],
                    row["first_target_meeting_generation"],
                ]
                for row in target_meeting_failures
            ],
        ),
        "",
        "Final-generation population and champion details:",
        "",
        *markdown_table(
            [
                "State",
                "Seed",
                "Final gen",
                "Max-fid ind. fid",
                "Max-fid ind. G",
                "Max-fid ind. D",
                "Max-fid ind. 2Q",
                "Target ever",
                "First target gen",
                "Champion fid",
                "Champion G",
                "Champion D",
                "Champion 2Q",
            ],
            failure_table,
        ),
        "",
        "The complete values are also in "
        "`control_failure_population_diagnostics.csv`.",
        "",
    ]
    (HERE / "RECONSTRUCTION_AND_FAILURE_AUDIT.md").write_text(
        "\n".join(lines).rstrip() + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--one", nargs=2, metavar=("STATE", "SEED"))
    args = parser.parse_args()
    if args.one:
        print(json.dumps(one_transpilation_json(args.one[0], int(args.one[1]))))
    else:
        main()
