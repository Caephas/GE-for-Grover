#!/usr/bin/env python3
"""Reproduce the corrected Task A exact-fidelity calculation.

This reads existing v0.1 and control-arm run results. It does not run
evolution or submit hardware jobs.
"""

from __future__ import annotations

import csv
import json
import pickle
import re
from pathlib import Path

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel


ROOT = Path(__file__).resolve().parent
NOISE_BUNDLE = ROOT / "noise" / "frozen_env_ibm_fez_2026-08-20.pkl"
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
TASK_A_ROOTS = {
    "epsilon_lexicase": ROOT / "experiments_frozen_10seed" / "epsilon_lexicase",
    "lexi2": ROOT / "experiments_frozen_10seed_lexi2" / "lexi2",
    "tournament": ROOT / "experiments_frozen_10seed" / "tournament",
}
CONTROL_ROOTS = {
    "lexi2": ROOT / "experiments_frozen_10seed_lexi2" / "lexi2",
    "lexi8_random": (
        ROOT / "experiments_frozen_10seed_lexi8_random" / "lexi8_random"
    ),
}
TASK_A_MEANS = {
    "epsilon_lexicase": 0.00180039,
    "lexi2": 0.00147201,
    "tournament": 0.00197747,
}


def result_path(method: str, state: str, seed: int, roots: dict) -> Path:
    run_id = SEEDS.index(seed) + 1
    return (
        roots[method]
        / "pop300"
        / "noise"
        / f"state_{state}"
        / f"run_{run_id}_seed_{seed}"
        / f"run_result_{state}_run{run_id}.json"
    )


def oracle_code(state: str) -> str:
    lines = []
    for index, bit in enumerate(state):
        if bit == "0":
            lines.append(f"qc.x({index})")
    lines.extend(["qc.h(2)", "qc.mcx(list(range(2)), 2)", "qc.h(2)"])
    for index, bit in enumerate(state):
        if bit == "0":
            lines.append(f"qc.x({index})")
    return "\n".join(lines) + "\n"


def inject_oracle(code: str, state: str) -> str:
    return re.sub(
        r"(## Begin Oracle\n)(.*?)(## End Oracle\n)",
        lambda match: (
            match.group(1) + oracle_code(state) + match.group(3)
        ),
        code,
        flags=re.DOTALL,
    )


def build_circuit(code: str, state: str) -> QuantumCircuit:
    local_vars = {}
    exec(
        inject_oracle(code, state),
        {
            "QuantumRegister": QuantumRegister,
            "ClassicalRegister": ClassicalRegister,
            "QuantumCircuit": QuantumCircuit,
            "np": np,
        },
        local_vars,
    )
    return local_vars["qc"]


def two_qubit_count(circuit: QuantumCircuit) -> int:
    return sum(
        1
        for instruction in circuit.data
        if instruction.operation.num_qubits >= 2
    )


def reduced_noise_model(
    original: NoiseModel, physical_qubits: list[int]
) -> tuple[NoiseModel, dict[int, int]]:
    physical_map = {
        qubit: index for index, qubit in enumerate(physical_qubits)
    }
    reduced = NoiseModel()
    reduced._basis_gates = set(original._basis_gates)
    reduced._noise_instructions = set(original._noise_instructions)
    reduced._noise_qubits = set(range(3))
    reduced._default_quantum_errors = {}
    reduced._local_quantum_errors = {}
    reduced._default_readout_error = None
    reduced._local_readout_errors = {}
    reduced._custom_noise_passes = []

    for operation, errors in original._local_quantum_errors.items():
        mapped = {
            tuple(physical_map[qubit] for qubit in qubits): error
            for qubits, error in errors.items()
            if set(qubits) <= set(physical_qubits)
        }
        if mapped:
            reduced._local_quantum_errors[operation] = mapped

    for qubits, error in original._local_readout_errors.items():
        if qubits[0] in physical_map:
            reduced._local_readout_errors[
                (physical_map[qubits[0]],)
            ] = error
    return reduced, physical_map


def observed_probability(
    diagonal: np.ndarray, readout_matrices: list[np.ndarray]
) -> np.ndarray:
    observed = np.zeros(8)
    for actual, probability in enumerate(diagonal):
        if probability <= 0:
            continue
        for measured in range(8):
            value = probability
            for qubit in range(3):
                value *= readout_matrices[qubit][
                    (actual >> qubit) & 1,
                    (measured >> qubit) & 1,
                ]
            observed[measured] += value
    return observed


def calculate_exact(
    run_result: dict,
    state: str,
    target,
    original_noise_model: NoiseModel,
) -> dict:
    circuit = build_circuit(run_result["phenotype"], state)
    chosen = None
    for _ in range(8):
        chosen = generate_preset_pass_manager(
            target=target,
            optimization_level=3,
            seed_transpiler=run_result["seed"],
        ).run(circuit)
        if (
            chosen.size() == run_result["gate_count"]
            and chosen.depth() == run_result["depth"]
            and two_qubit_count(chosen)
            == run_result["two_qubit_gates"]
        ):
            break

    measurement_layout = [None] * 3
    for instruction in chosen.data:
        if instruction.operation.name == "measure":
            cbit = chosen.find_bit(instruction.clbits[0]).index
            measurement_layout[cbit] = int(instruction.qubits[0]._index)

    physical_map = {
        qubit: index for index, qubit in enumerate(measurement_layout)
    }
    reduced_circuit = QuantumCircuit(3, 3)
    for instruction in chosen.data:
        if instruction.operation.name == "measure":
            continue
        reduced_circuit.append(
            instruction.operation,
            [
                reduced_circuit.qubits[physical_map[int(qubit._index)]]
                for qubit in instruction.qubits
            ],
            [],
        )
    reduced_circuit.measure(range(3), range(3))
    reduced_model, _ = reduced_noise_model(
        original_noise_model, measurement_layout
    )

    density_circuit = reduced_circuit.remove_final_measurements(
        inplace=False
    )
    density_circuit.save_density_matrix()
    density_matrix = np.asarray(
        AerSimulator(
            method="density_matrix", noise_model=reduced_model
        )
        .run(density_circuit)
        .result()
        .data()["density_matrix"]
    )
    diagonal = np.clip(np.real(np.diag(density_matrix)), 0, None)
    readout_matrices = [
        original_noise_model._local_readout_errors[(qubit,)].probabilities
        for qubit in measurement_layout
    ]
    observed = observed_probability(diagonal, readout_matrices)

    return {
        "exact_fidelity": float(observed[int(state[::-1], 2)]),
        "reconstructed_gates": int(chosen.size()),
        "reconstructed_depth": int(chosen.depth()),
        "reconstructed_two_qubit_gates": two_qubit_count(chosen),
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def task_success(run_result: dict) -> bool:
    return bool(
        float(run_result["fidelity"]) >= 0.95
        and int(run_result["gate_count"]) <= 20
        and int(run_result["depth"]) <= 15
    )


def main() -> None:
    with NOISE_BUNDLE.open("rb") as handle:
        bundle = pickle.load(handle)
    target = bundle["target"]
    original_noise_model = bundle["noise_model"]

    task_a_rows = []
    by_method = {method: [] for method in TASK_A_ROOTS}
    for method in ("epsilon_lexicase", "lexi2", "tournament"):
        for state in STATES:
            for seed in SEEDS:
                result_file = result_path(
                    method, state, seed, TASK_A_ROOTS
                )
                run_result = json.loads(result_file.read_text())
                exact = calculate_exact(
                    run_result, state, target, original_noise_model
                )
                reconstruction_matches = (
                    exact["reconstructed_gates"]
                    == run_result["gate_count"]
                    and exact["reconstructed_depth"]
                    == run_result["depth"]
                    and exact["reconstructed_two_qubit_gates"]
                    == run_result["two_qubit_gates"]
                )
                row = {
                    "method": method,
                    "state": state,
                    "seed": seed,
                    "sampled_fidelity": run_result["fidelity"],
                    "exact_fidelity": exact["exact_fidelity"],
                    "stored_gates": run_result["gate_count"],
                    "stored_depth": run_result["depth"],
                    "stored_2q": run_result["two_qubit_gates"],
                    "reconstructed_gates": exact[
                        "reconstructed_gates"
                    ],
                    "reconstructed_depth": exact[
                        "reconstructed_depth"
                    ],
                    "reconstructed_2q": exact[
                        "reconstructed_two_qubit_gates"
                    ],
                    "reconstruction_matches": (
                        "true" if reconstruction_matches else "false"
                    ),
                }
                task_a_rows.append(row)
                by_method[method].append(row)

    task_a_path = ROOT / "task_a_exact_per_run.csv"
    write_csv(
        task_a_path,
        [
            "method",
            "state",
            "seed",
            "sampled_fidelity",
            "exact_fidelity",
            "stored_gates",
            "stored_depth",
            "stored_2q",
            "reconstructed_gates",
            "reconstructed_depth",
            "reconstructed_2q",
            "reconstruction_matches",
        ],
        task_a_rows,
    )

    control_rows = []
    task_a_lookup = {
        (row["method"], row["state"], int(row["seed"])): row
        for row in task_a_rows
    }
    control_exact = list(
        csv.DictReader(
            (ROOT / "control_arm_analysis" / "exact_fidelity_unified.csv").open()
        )
    )
    control_lookup = {
        (row["method"], row["state"], int(row["seed"])): row
        for row in control_exact
    }
    for method in ("lexi2", "lexi8_random"):
        for state in STATES:
            for seed in SEEDS:
                run_result = json.loads(
                    result_path(
                        method, state, seed, CONTROL_ROOTS
                    ).read_text()
                )
                if method == "lexi2":
                    source = task_a_lookup[(method, state, seed)]
                    exact_fidelity = float(source["exact_fidelity"])
                    reconstruction_matches = source[
                        "reconstruction_matches"
                    ]
                else:
                    source = control_lookup[(method, state, seed)]
                    exact_fidelity = float(
                        source["control_qpy_exact_fidelity"]
                    )
                    reconstruction_matches = (
                        "true"
                        if source["metrics_match"] == "True"
                        else "false"
                    )
                control_rows.append(
                    {
                        "method": method,
                        "state": state,
                        "seed": seed,
                        "final_sampled_fidelity": run_result["fidelity"],
                        "final_gates": run_result["gate_count"],
                        "final_depth": run_result["depth"],
                        "final_2q": run_result["two_qubit_gates"],
                        "stop_reason": run_result["stop_reason"],
                        "task_success": (
                            "true" if task_success(run_result) else "false"
                        ),
                        "exact_fidelity": exact_fidelity,
                        "reconstruction_matches": reconstruction_matches,
                    }
                )

    control_path = ROOT / "control_arm_per_run.csv"
    write_csv(
        control_path,
        [
            "method",
            "state",
            "seed",
            "final_sampled_fidelity",
            "final_gates",
            "final_depth",
            "final_2q",
            "stop_reason",
            "task_success",
            "exact_fidelity",
            "reconstruction_matches",
        ],
        control_rows,
    )

    print("Task A sampled-minus-exact means")
    for method in ("epsilon_lexicase", "lexi2", "tournament"):
        values = [
            float(row["sampled_fidelity"]) - float(row["exact_fidelity"])
            for row in by_method[method]
        ]
        print(
            method,
            f"recomputed={np.mean(values):+.8f}",
            f"transcript={TASK_A_MEANS[method]:+.8f}",
            "MATCH" if abs(np.mean(values) - TASK_A_MEANS[method]) < 5e-9
            else "MISMATCH",
        )


if __name__ == "__main__":
    main()
