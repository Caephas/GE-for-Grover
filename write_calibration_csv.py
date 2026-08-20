"""Write calibration_ibm_fez_july_vs_august.csv (read-only investigation artifact).

Pulls historical ibm_fez BackendProperties for the July (epsilon-lexicase) and
August (tournament) sweep windows, computes per-date medians, July-vs-August
window deltas, and the same-circuit simulated-fidelity deltas under each
period's reconstructed noise model. No experiments are re-run.
"""

from __future__ import annotations

import csv
import datetime
import json

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, ReadoutError, depolarizing_error, thermal_relaxation_error
from qiskit_ibm_runtime import QiskitRuntimeService

OUT = "calibration_ibm_fez_july_vs_august.csv"
DATES = ["2026-07-21", "2026-07-22", "2026-07-23", "2026-07-26",
         "2026-08-06", "2026-08-07", "2026-08-08", "2026-08-11"]
SNAPS_FOR_SIM = ["2026-07-21", "2026-07-26", "2026-08-07"]
CASES = [("epsilon_lexicase", "111"), ("epsilon_lexicase", "000"),
         ("tournament", "110"), ("tournament", "100")]


def qubit_map(q):
    return {n.name: n.value for n in q}


def median_stats(props):
    t1 = [qubit_map(q)["T1"] for q in props.qubits if qubit_map(q).get("T1")]
    t2 = [qubit_map(q)["T2"] for q in props.qubits if qubit_map(q).get("T2")]
    ro = [qubit_map(q)["readout_error"] for q in props.qubits if qubit_map(q).get("readout_error")]
    g1, g2 = [], []
    for g in props.gates:
        e = {par.name: par.value for par in g.parameters}.get("gate_error")
        if e is None:
            continue
        if len(g.qubits) == 1 and g.gate in ("sx", "x"):
            g1.append(e)
        elif len(g.qubits) == 2 and g.gate in ("ecr", "cz", "cx"):
            g2.append(e)
    return {
        "T1_median_us": np.median(t1),
        "T2_median_us": np.median(t2),
        "readout_error_median": np.median(ro),
        "single_q_gate_error_median": np.median(g1),
        "two_q_gate_error_median": np.median(g2),
        "two_q_gate_error_mean": np.mean(g2),
    }


def build_circuit(pheno):
    loc = {}
    exec(pheno, {"QuantumRegister": QuantumRegister, "ClassicalRegister": ClassicalRegister,
                 "QuantumCircuit": QuantumCircuit, "np": np}, loc)
    return loc["qc"]


def build_noise_model(props, used_q, used_edges):
    qm = {i: qubit_map(q) for i, q in enumerate(props.qubits)}
    gm = {}
    for g in props.gates:
        gm[(g.gate, tuple(g.qubits))] = {par.name: par.value for par in g.parameters}
    nm = NoiseModel()
    for q in used_q:
        e1 = qm[q].get("prob_meas1_prep0", qm[q].get("readout_error", 0.01))
        e0 = qm[q].get("prob_meas0_prep1", qm[q].get("readout_error", 0.01))
        nm.add_readout_error(ReadoutError([[1 - e0, e0], [e1, 1 - e1]]), [q])
    for q in used_q:
        t1, t2 = qm[q].get("T1"), qm[q].get("T2")
        if not t1 or not t2:
            continue
        t2 = min(t2, 2 * t1)
        for gname in ("sx", "x"):
            e = gm.get((gname, (q,)), {}).get("gate_error")
            dep = depolarizing_error(e, 1) if e else None
            ln = gm.get((gname, (q,)), {}).get("gate_length", 40) * 1e-9
            therm = thermal_relaxation_error(t1 * 1e-6, t2 * 1e-6, ln)
            err = dep.compose(therm) if dep is not None else therm
            nm.add_quantum_error(err, [gname], [q])
        nm.add_quantum_error(thermal_relaxation_error(t1 * 1e-6, t2 * 1e-6, 0), ["rz"], [q])
        nm.add_quantum_error(thermal_relaxation_error(t1 * 1e-6, t2 * 1e-6, 40e-9), ["id"], [q])
    for (a, b) in used_edges:
        key = ("ecr", (a, b))
        for cand in (("ecr", (b, a)), ("cz", (a, b)), ("cz", (b, a))):
            if cand in gm:
                key = cand
                break
        errs = gm.get(key, {})
        e = errs.get("gate_error", 0.003)
        ln = errs.get("gate_length", 600) * 1e-9
        dep = depolarizing_error(e, 2)
        ta = thermal_relaxation_error(qm[a].get("T1", 100e-6),
                                      min(qm[a].get("T2", 80e-6), 2 * qm[a].get("T1", 100e-6)), ln)
        tb = thermal_relaxation_error(qm[b].get("T1", 100e-6),
                                      min(qm[b].get("T2", 80e-6), 2 * qm[b].get("T1", 100e-6)), ln)
        nm.add_quantum_error(dep.compose(ta, [0]).compose(tb, [1]), [key[0]], [a, b])
    return nm


def main() -> None:
    svc = QiskitRuntimeService(channel="ibm_cloud")
    backend = svc.backend("ibm_fez")
    props = {ds: backend.properties(datetime=datetime.datetime.fromisoformat(ds + "T12:00:00"))
             for ds in DATES}

    rows = []
    # Section 1: per-snapshot medians
    for ds in DATES:
        s = median_stats(props[ds])
        for k, v in s.items():
            unit = "us" if k.startswith("T") else ""
            rows.append({"section": "per-snapshot medians", "key": ds, "metric": k,
                         "value": f"{v:.8g}", "unit": unit})

    # Section 2: July window vs August window
    jul = [median_stats(props[d]) for d in ("2026-07-21", "2026-07-22", "2026-07-23", "2026-07-26")]
    aug = [median_stats(props[d]) for d in ("2026-08-06", "2026-08-07", "2026-08-08")]
    for k in jul[0]:
        j = np.median([s[k] for s in jul])
        a = np.median([s[k] for s in aug])
        rel = (a - j) / j * 100 if j else float("nan")
        rows.append({"section": "july_vs_august", "key": "July window", "metric": k,
                     "value": f"{j:.8g}", "unit": ""})
        rows.append({"section": "july_vs_august", "key": "August window", "metric": k,
                     "value": f"{a:.8g}", "unit": ""})
        rows.append({"section": "july_vs_august", "key": "delta (Aug-Jul)", "metric": k,
                     "value": f"{a - j:+.8g}", "unit": ""})
        rows.append({"section": "july_vs_august", "key": "relative change", "metric": k,
                     "value": f"{rel:+.1f}%", "unit": ""})

    # Section 3: same-circuit simulated fidelity under each period's noise model
    for sel, state in CASES:
        agg = json.load(open(f"experiments/{sel}/pop300/noise/state_{state}/AGGREGATE_{state}.json"))
        best = max(agg["per_run"], key=lambda r: (r["fidelity"], -r["two_qubit_gates"], -r["depth"]))
        qc = build_circuit(best["phenotype"])
        tqc = transpile(qc, backend=backend, optimization_level=3, seed_transpiler=best["seed"])
        used_q = sorted({q._index for inst in tqc.data for q in inst.qubits})
        used_edges = sorted({tuple(sorted([q._index for q in inst.qubits]))
                             for inst in tqc.data if len(inst.qubits) == 2})
        means = {}
        for ds in SNAPS_FOR_SIM:
            nm = build_noise_model(props[ds], used_q, used_edges)
            sim = AerSimulator(noise_model=nm)
            pm = []
            for seed in range(10):
                r = sim.run(tqc, shots=10000, seed_simulator=1000 + seed).result()
                counts = {k[::-1]: v for k, v in r.get_counts().items()}
                pm.append(counts.get(state, 0) / 10000)
            means[ds] = np.mean(pm)
        label = f"{sel}/{state} ({tqc.size()}g/{tqc.depth()}d)"
        for ds in SNAPS_FOR_SIM:
            rows.append({"section": "simulated p_marked by noise model", "key": label,
                         "metric": ds, "value": f"{means[ds]:.4f}", "unit": "10k shots, mean of 10 seeds"})
        rows.append({"section": "simulated p_marked by noise model", "key": label,
                     "metric": "delta Aug7-Jul21", "value": f"{means[SNAPS_FOR_SIM[2]] - means[SNAPS_FOR_SIM[0]]:+.4f}", "unit": ""})
        rows.append({"section": "simulated p_marked by noise model", "key": label,
                     "metric": "delta Aug7-Jul26", "value": f"{means[SNAPS_FOR_SIM[2]] - means[SNAPS_FOR_SIM[1]]:+.4f}", "unit": ""})

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["section", "key", "metric", "value", "unit"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
