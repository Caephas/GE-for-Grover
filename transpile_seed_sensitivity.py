"""Quantify transpile-seed sensitivity for the 8 deployed pop300 best circuits.

Read-only diagnostic: for each state's best-fidelity run, rebuild its circuit
from the stored phenotype and transpile it to ibm_fez under 20 different
seed_transpiler values (optimization_level=3, the same settings the fitness
loop uses). Reports the gate-count / depth distribution per state so we can see
how much of the transpiled-size variance is seed lottery vs circuit property.
"""

from __future__ import annotations

import csv
import json
import statistics

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister, transpile

STATES = ["000", "001", "010", "011", "100", "101", "110", "111"]
BASE = "experiments/epsilon_lexicase/pop300/noise"
SEEDS = list(range(20))  # 20 seed_transpiler values for the lottery
OUT_CSV = "transpile_seed_sensitivity.csv"


def get_backend():
    from qiskit_ibm_runtime import QiskitRuntimeService

    service = QiskitRuntimeService(name="qgss-2025")
    return service.backend("ibm_fez")


def build_circuit(phenotype: str) -> QuantumCircuit:
    loc = {}
    exec(
        phenotype,
        {
            "QuantumRegister": QuantumRegister,
            "ClassicalRegister": ClassicalRegister,
            "QuantumCircuit": QuantumCircuit,
            "np": np,
        },
        loc,
    )
    return loc["qc"]


def main() -> None:
    backend = get_backend()
    print(f"backend: {backend.name} ({backend.num_qubits} qubits)")

    rows = []
    print(f"\n{'state':>5} {'seed':>6} {'raw_g':>5} {'raw_d':>5} {'at_deploy_g':>11} {'at_deploy_d':>11} "
          f"{'gates min':>9} {'gates med':>9} {'gates max':>9} {'depth min':>9} {'depth med':>9} {'depth max':>9}")
    for state in STATES:
        agg = json.load(open(f"{BASE}/state_{state}/AGGREGATE_{state}.json"))
        best = max(agg["per_run"], key=lambda r: (r["fidelity"], -r["two_qubit_gates"], -r["depth"]))
        qc = build_circuit(best["phenotype"])
        raw_g, raw_d = qc.size(), qc.depth()

        seeds = list(SEEDS)
        if best["seed"] not in seeds:
            seeds.append(best["seed"])

        gates, depths = [], []
        deploy_g = deploy_d = None
        for seed in seeds:
            tqc = transpile(qc, backend=backend, optimization_level=3, seed_transpiler=seed)
            g, d = tqc.size(), tqc.depth()
            gates.append(g)
            depths.append(d)
            rows.append({
                "state": state,
                "seed": seed,
                "is_deployed_seed": seed == best["seed"],
                "gates": g,
                "depth": d,
            })
            if seed == best["seed"]:
                deploy_g, deploy_d = g, d

        print(f"{state:>5} {best['seed']:>6} {raw_g:>5} {raw_d:>5} {deploy_g:>11} {deploy_d:>11} "
              f"{min(gates):>9} {statistics.median(gates):>9.0f} {max(gates):>9} "
              f"{min(depths):>9} {statistics.median(depths):>9.0f} {max(depths):>9}  "
              f"[in-loop was {best['gate_count']}g/{best['depth']}d]")

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["state", "seed", "is_deployed_seed", "gates", "depth"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {OUT_CSV} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
