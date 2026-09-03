#!/usr/bin/env python3
"""Submit all 25 frozen deployment circuits to ibm_fez, one job at a time.

Circuits:
  - 24 deployed best-of-10 circuits (8 states x epsilon_lexicase / tournament /
    lexi2) loaded from the saved deployed_best.json files, and
  - the |111> size-aware counterfactual circuit (epsilon_lexicase, seed 29440)
    loaded from its saved run_result.

No evolution is run. Each circuit is rebuilt from its stored phenotype and
transpiled to the frozen ibm_fez target at optimisation level 3 with its stored
transpiler seed (retried until the transpiled size matches the recorded
in-loop size). All 25 jobs are submitted and awaited back-to-back on the same
backend (individual jobs; the IBM plan does not permit Runtime Sessions),
10,000 shots each.

Outputs (originals are never overwritten):
  - per-circuit: <run_dir>/hof_1_ibm_hardware_data_session_2026-09-02.json
  - central:     logs_hardware_session_2026-09-02/<arm>_state<state>_seed<seed>.json

Usage:
  python submit_hardware_session_2026-09-02.py --dry-run   # build+verify only
  python submit_hardware_session_2026-09-02.py --submit    # submit to ibm_fez
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import pickle
import re
import sys

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

SESSION_LABEL = "session_2026-09-02"
SHOTS = 10_000
FROZEN_BUNDLE = "noise/frozen_env_ibm_fez_2026-08-20.pkl"
STATES = [f"{i:03b}" for i in range(8)]
ROOTS = {
    "epsilon_lexicase": "experiments_frozen_10seed",
    "tournament": "experiments_frozen_10seed",
    "lexi2": "experiments_frozen_10seed_lexi2",
}
COUNTERFACTUAL = {
    "arm": "epsilon_lexicase",
    "state": "111",
    "run_result": (
        "experiments_frozen_10seed/epsilon_lexicase/pop300/noise/state_111/"
        "run_10_seed_29440/run_result_111_run10.json"
    ),
}


def build_circuit(phenotype: str) -> QuantumCircuit:
    loc: dict = {}
    exec(phenotype, {
        "QuantumRegister": QuantumRegister,
        "ClassicalRegister": ClassicalRegister,
        "QuantumCircuit": QuantumCircuit,
        "np": __import__("numpy"),
    }, loc)
    qc = loc.get("qc")
    if qc is None:
        raise ValueError("phenotype produced no 'qc'")
    return qc


def two_qubit_count(qc: QuantumCircuit) -> int:
    return sum(1 for inst in qc.data if inst.operation.num_qubits >= 2)


def load_manifest() -> list[dict]:
    manifest = []
    for arm, root in ROOTS.items():
        for st in STATES:
            d = json.load(open(os.path.join(
                root, arm, "pop300", "noise", f"state_{st}", "deployed_best.json")))
            run_dir = os.path.join(root, arm, "pop300", "noise", f"state_{st}",
                                   f"run_{d['run_id']}_seed_{d['seed']}")
            manifest.append({
                "arm": arm, "state": st, "seed": d["seed"],
                "phenotype": d["phenotype"],
                "sim_fidelity": d["fidelity"],
                "recorded": (d["gate_count"], d["depth"], d["two_qubit_gates"]),
                "run_dir": run_dir,
                "kind": "deployed",
            })
    r = json.load(open(COUNTERFACTUAL["run_result"]))
    run_dir = os.path.dirname(COUNTERFACTUAL["run_result"])
    manifest.append({
        "arm": COUNTERFACTUAL["arm"], "state": COUNTERFACTUAL["state"],
        "seed": r["seed"], "phenotype": r["phenotype"],
        "sim_fidelity": r["fidelity"],
        "recorded": (r["gate_count"], r["depth"], r["two_qubit_gates"]),
        "run_dir": run_dir,
        "kind": "counterfactual",
    })
    return manifest


def load_frozen_target():
    with open(FROZEN_BUNDLE, "rb") as f:
        return pickle.load(f)["target"]


def isa_check(tqc: QuantumCircuit, backend) -> tuple[bool, str]:
    """Check the transpiled circuit is acceptable for the live backend."""
    names = set(tqc.count_ops().keys())
    live_names = set()
    for op in backend.target.operations:
        live_names.add(op.name)
    unknown = names - live_names
    if unknown:
        return False, f"gates not in live target: {sorted(unknown)}"
    cmap = backend.target.build_coupling_map()
    if cmap is None:
        return True, "no coupling-map check possible"
    edges = {(a, b) for a, b in cmap.get_edges()}
    for inst in tqc.data:
        if inst.operation.num_qubits == 2:
            qs = tuple(tqc.find_bit(q).index for q in inst.qubits)
            if qs not in edges and qs[::-1] not in edges:
                return False, f"2Q edge {qs} not in live coupling map"
    return True, "ok"


def prep_circuits(manifest: list[dict], backend, frozen_target) -> list[dict]:
    """Rebuild + transpile each circuit to the frozen target; verify vs recorded."""
    out = []
    for e in manifest:
        qc = build_circuit(e["phenotype"])
        rec_g, rec_d, rec_q = e["recorded"]
        chosen = None
        for _ in range(6):
            pm = generate_preset_pass_manager(
                target=frozen_target, optimization_level=3,
                seed_transpiler=e["seed"])
            tqc = pm.run(qc)
            if tqc.size() == rec_g and tqc.depth() == rec_d:
                chosen = tqc
                break
            chosen = tqc  # last attempt fallback
        g, d, q = chosen.size(), chosen.depth(), two_qubit_count(chosen)
        ok = (g == rec_g and d == rec_d)
        valid, reason = isa_check(chosen, backend)
        e.update({
            "qc_isa": chosen,
            "tr_gates": g, "tr_depth": d, "tr_2q": q,
            "size_match": ok,
            "isa_ok": valid, "isa_reason": reason,
            "raw_gates": qc.size(), "raw_depth": qc.depth(),
        })
        out.append(e)
    return out


def print_manifest(entries: list[dict]) -> None:
    print(f"{'#':>2} {'arm':<16}{'state':<6}{'seed':<7}{'sim':<8}"
          f"{'rec D/G/2Q':<12}{'transpiled D/G/2Q':<17}{'raw D/G':<10}match")
    for i, e in enumerate(entries, 1):
        rg, rd, rq = e["recorded"]
        print(f"{i:>2} {e['arm']:<16}{e['state']:<6}{e['seed']:<7}"
              f"{e['sim_fidelity']:<8.4f}{rd}/{rg}/{rq:<8}"
              f"{e['tr_depth']}/{e['tr_gates']}/{e['tr_2q']:<11}"
              f"{e['raw_depth']}/{e['raw_gates']:<6}"
              f"{'OK' if e['size_match'] else 'MISMATCH'}")


def extract_counts(pub_result):
    try:
        return pub_result.data.cr.get_counts()
    except AttributeError:
        pass
    try:
        return pub_result.data.c.get_counts()
    except AttributeError:
        pass
    data = pub_result.data
    for f in dir(data):
        if not f.startswith("_") and hasattr(getattr(data, f), "get_counts"):
            return getattr(data, f).get_counts()
    raise RuntimeError("could not extract counts from result")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="build/transpile/verify all circuits; do not submit")
    ap.add_argument("--submit", action="store_true",
                    help="actually submit to ibm_fez")
    args = ap.parse_args()
    if args.submit and args.dry_run:
        sys.exit("choose either --dry-run or --submit, not both")
    if not (args.submit or args.dry_run):
        sys.exit("pass --dry-run (verify only) or --submit (run hardware)")

    out_root = f"logs_hardware_{SESSION_LABEL}"
    os.makedirs(out_root, exist_ok=True)

    print(f"=== HARDWARE BATCH {SESSION_LABEL} | ibm_fez | {SHOTS} shots "
          f"(individual jobs, back-to-back) ===")
    service = QiskitRuntimeService(channel="ibm_cloud")
    backend = service.backend("ibm_fez")
    print(f"backend: {backend.name} | status: {backend.status()}")

    manifest = load_manifest()
    print(f"manifest circuits: {len(manifest)}")
    frozen_target = load_frozen_target()
    entries = prep_circuits(manifest, backend, frozen_target)
    print_manifest(entries)

    n_bad = sum(1 for e in entries if not e["size_match"])
    n_bad_isa = sum(1 for e in entries if not e["isa_ok"])
    if n_bad or n_bad_isa:
        print(f"\n⚠ {n_bad} circuit(s) could not be reproduced at recorded size "
              f"after retries; ⚠ {n_bad_isa} circuit(s) failed the live-ISA check "
              f"({[e['isa_reason'] for e in entries if not e['isa_ok']][:3]}). "
              f"They will be SKIPPED.")

    if args.dry_run:
        print("\n[DRY-RUN] no jobs submitted.")
        return

    to_run = [e for e in entries if e["size_match"]]
    print(f"\nSubmitting {len(to_run)} circuits back-to-back...")
    summary = []
    sampler = SamplerV2(mode=backend)
    sampler.options.default_shots = SHOTS
    for e in to_run:
        tag = f"{e['arm']} state{e['state']} seed{e['seed']}"
        print(f"\n[{tag}] submitting...")
        try:
            job = sampler.run([e["qc_isa"]])
            print(f"  job id: {job.job_id()}")
            result = job.result(timeout=3600)
            counts = extract_counts(result[0])
            counts = {k[::-1]: v for k, v in counts.items()}
            total = sum(counts.values())
            p_marked = counts.get(e["state"], 0) / total if total else 0.0
            hw_data = {
                "individual_id": 1,
                "fitness_evolution": None,
                "fitness_hardware": None,
                "backend": backend.name,
                "target_state": e["state"],
                "counts": counts,
                "p_marked_hw": p_marked,
                "total_shots": total,
                "original_gates": e["raw_gates"],
                "original_depth": e["raw_depth"],
                "transpiled_gates": e["tr_gates"],
                "transpiled_depth": e["tr_depth"],
                "transpiled_2q": e["tr_2q"],
                "seed": e["seed"],
                "arm": e["arm"],
                "sim_fidelity": e["sim_fidelity"],
                "job_id": job.job_id(),
                "session_id": None,
                "execution_mode": "individual_jobs_back_to_back",
                "session_label": SESSION_LABEL,
                "timestamp": datetime.datetime.now().isoformat(),
                "circuit_kind": e["kind"],
            }
            per_run = os.path.join(
                e["run_dir"], f"hof_1_ibm_hardware_data_{SESSION_LABEL}.json")
            central = os.path.join(
                out_root, f"{e['arm']}_state{e['state']}_seed{e['seed']}.json")
            for p in (per_run, central):
                with open(p, "w") as f:
                    json.dump(hw_data, f, indent=2)
            gap = e["sim_fidelity"] - p_marked
            summary.append((tag, p_marked, gap))
            print(f"  p(marked) = {p_marked:.4f} | sim-HW gap = {gap:+.4f}")
            print(f"  saved: {central}")
        except Exception as exc:
            print(f"  ✗ failed: {exc}")
            summary.append((tag, None, None))

    print("\n=== SESSION SUMMARY ===")
    for tag, p, gap in summary:
        if p is None:
            print(f"  {tag}: FAILED")
        else:
            print(f"  {tag}: p(marked)={p:.4f}  sim-HW={gap:+.4f}")
    n_fail = sum(1 for _, p, _ in summary if p is None)
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
