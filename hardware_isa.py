"""Utilities for loading and verifying persisted scored ISA circuits.

Hardware submission scripts must submit the circuit that produced the saved
score, not a fresh transpilation. The experiment driver writes one QPY plus a
metadata JSON per run champion. These helpers enforce that contract.
"""

from __future__ import annotations

import hashlib
import json
import os
import random

from qiskit import qpy


def isa_signature(circuit) -> dict:
    """Return the fields verified before hardware submission."""
    operation_counts = {
        str(name): int(count)
        for name, count in sorted(circuit.count_ops().items())
    }
    measurement_layout = [None] * circuit.num_clbits
    for inst in circuit.data:
        if inst.operation.name == "measure":
            cbit = circuit.find_bit(inst.clbits[0]).index
            measurement_layout[cbit] = int(inst.qubits[0]._index)
    return {
        "gate_count": int(circuit.size()),
        "depth": int(circuit.depth()),
        "two_qubit_gates": sum(
            1 for inst in circuit.data if inst.operation.num_qubits >= 2
        ),
        "operation_counts": operation_counts,
        "measurement_layout": measurement_layout,
        "active_qubits": sorted({
            int(q._index)
            for inst in circuit.data
            if inst.operation.name != "barrier"
            for q in inst.qubits
        }),
    }


def load_scored_isa(run_dir: str, state: str, run_id: int):
    """Load and verify the persisted scored ISA circuit for one run."""
    qpy_path = os.path.join(run_dir, f"scored_isa_{state}_run{run_id}.qpy")
    metadata_path = os.path.join(
        run_dir, f"scored_isa_metadata_{state}_run{run_id}.json"
    )
    if not os.path.isfile(qpy_path):
        raise FileNotFoundError(
            f"missing scored ISA artifact: {qpy_path}. "
            "Re-run the experiment with the updated driver; re-transpilation "
            "at hardware submission is intentionally forbidden."
        )
    if not os.path.isfile(metadata_path):
        raise FileNotFoundError(f"missing scored ISA metadata: {metadata_path}")

    with open(metadata_path) as f:
        metadata = json.load(f)
    with open(qpy_path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    if digest != metadata.get("qpy_sha256"):
        raise ValueError(
            f"scored ISA checksum mismatch for {qpy_path}: "
            f"{digest} != {metadata.get('qpy_sha256')}"
        )

    with open(qpy_path, "rb") as f:
        circuits = qpy.load(f)
    if len(circuits) != 1:
        raise ValueError(f"{qpy_path} contains {len(circuits)} circuits; expected 1")
    circuit = circuits[0]
    actual = isa_signature(circuit)

    expected_keys = (
        "gate_count",
        "depth",
        "two_qubit_gates",
        "operation_counts",
        "measurement_layout",
        "active_qubits",
    )
    mismatches = {
        key: {"expected": metadata.get(key), "actual": actual[key]}
        for key in expected_keys
        if metadata.get(key) != actual[key]
    }
    if mismatches:
        raise ValueError(
            f"stored ISA does not match its scored metadata: {mismatches}"
        )
    return circuit, metadata, qpy_path, metadata_path


def verify_live_isa(circuit, backend) -> None:
    """Fail unless the stored ISA circuit is valid on the live backend."""
    operation_names = set(circuit.count_ops())
    live_operation_names = {op.name for op in backend.target.operations}
    unknown = operation_names - live_operation_names
    if unknown:
        raise ValueError(
            f"stored ISA uses operations absent from the live target: "
            f"{sorted(unknown)}"
        )

    coupling_map = backend.target.build_coupling_map()
    if coupling_map is None:
        return
    live_edges = {tuple(edge) for edge in coupling_map.get_edges()}
    for inst in circuit.data:
        if inst.operation.num_qubits < 2:
            continue
        edge = tuple(int(q._index) for q in inst.qubits)
        if edge not in live_edges and edge[::-1] not in live_edges:
            raise ValueError(
                f"stored ISA edge {edge} is absent from the live coupling map"
            )


def balanced_method_order(entries: list, method_key, rng: random.Random) -> list:
    """Interleave method buckets in random order instead of grouping methods."""
    buckets = {}
    for entry in entries:
        buckets.setdefault(method_key(entry), []).append(entry)
    for bucket in buckets.values():
        rng.shuffle(bucket)

    ordered = []
    while buckets:
        methods = list(buckets)
        rng.shuffle(methods)
        for method in methods:
            ordered.append(buckets[method].pop())
            if not buckets[method]:
                del buckets[method]
    return ordered
