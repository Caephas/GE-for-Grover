#!/usr/bin/env python3
"""Re-run ONLY the hardware validation for a saved state, without re-running evolution.

Loads the 10 per-run results saved under
    <root>/{selection}/pop{pop}/noise/state_{state}/
where root is experiments_frozen_10seed for epsilon_lexicase/tournament and
experiments_frozen_10seed_lexi2 for lexi2. For lexi2 the notebook-sourced
config comes from the (identical-config) lexicase notebook.
(aggregate + per-run folders), picks the deployed circuit with the lambda-free
lexicographic rule (max fidelity, then min transpiled 2Q gates, then min
total transpiled gates, then min transpiled depth; matching the driver),
loads that run's persisted scored ISA circuit, verifies its checksum, layout,
and complete operation counts against stored metadata, and submits that exact
circuit to ibm_fez without re-transpiling.

Before submitting it prints a confirmation block (deployed seed, fidelity,
transpiled gate/depth vs the recorded in-loop values) and asks for y/N.
Use --yes to skip the prompt, or --verify-only to stop after the check.
"""

from __future__ import annotations

import argparse
import ast
import datetime
import json
import os
import re
import sys
from types import SimpleNamespace

import numpy as np
import matplotlib.pyplot as plt
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

from hardware_isa import load_scored_isa, verify_live_isa

NOTEBOOK_PREFIX = {"epsilon_lexicase": "lexicase", "tournament": "tournament",
                   "lexi2": "lexicase"}  # lexi2 has no notebook; same submission code/config
EXPERIMENT_ROOTS = {"epsilon_lexicase": "experiments_frozen_10seed",
                    "tournament": "experiments_frozen_10seed",
                    "lexi2": "experiments_frozen_10seed_lexi2"}
CONFIG_ASSIGN = re.compile(r"^([A-Z_][A-Z0-9_]*)\s*=\s*(.+?)(\s*#.*)?$")


def config_from_notebook(state: str, selection: str) -> dict:
    """Extract the handful of config values run_hof_on_ibm reads at runtime."""
    nb_path = f"ibm_{NOTEBOOK_PREFIX[selection]}_transpiled_{state}.ipynb"
    nb = json.load(open(nb_path))
    vals: dict = {}
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        for line in cell["source"]:
            m = CONFIG_ASSIGN.match(line)
            if not m:
                continue
            name, rhs = m.group(1), m.group(2).strip()
            if name in ("GATE_PENALTY_WEIGHT", "SUCCESS_THRESHOLD", "USE_NOISE_MODEL", "NUM_SHOTS"):
                try:
                    vals[name] = ast.literal_eval(rhs)
                except Exception:
                    pass
    return vals


def load_deployed_run(state: str, selection: str, pop: int) -> tuple[dict, str, dict]:
    state_dir = os.path.join(EXPERIMENT_ROOTS[selection], selection,
                             f"pop{pop}", "noise", f"state_{state}")
    agg_path = os.path.join(state_dir, f"AGGREGATE_{state}.json")
    agg = json.load(open(agg_path))
    per_run = [r for r in agg.get("per_run", []) if isinstance(r, dict)]
    if len(per_run) != 10:
        print(f"  ⚠ expected 10 runs, found {len(per_run)} in {agg_path}")

    print(f"\nSaved per-run results ({state_dir}):")
    print(f"  {'run_id':>6} {'seed':>7} {'fidelity':>9} {'in-loop g/d/2Q':>18} {'raw gates/depth':>16}")
    for r in sorted(per_run, key=lambda x: x["run_id"]):
        run_dir = os.path.join(state_dir, f"run_{r['run_id']}_seed_{r['seed']}")
        exists = "OK" if os.path.isdir(run_dir) else "MISSING!"
        print(f"  {r['run_id']:>6} {r['seed']:>7} {r['fidelity']:>9.4f} "
              f"{r.get('gate_count')}g/{r.get('depth')}d/{r.get('two_qubit_gates')}q{'':>9} "
              f"{r.get('raw_gate_count')}g/{r.get('raw_depth')}d  [{exists}]")

    best = max(per_run, key=lambda r: (
        r["fidelity"], -r["two_qubit_gates"], -r["gate_count"], -r["depth"]))
    run_dir = os.path.join(state_dir, f"run_{best['run_id']}_seed_{best['seed']}")
    if not os.path.isdir(run_dir):
        sys.exit(f"✗ deployed run folder missing: {run_dir}")
    return best, run_dir, agg


def build_circuit(phenotype: str) -> QuantumCircuit:
    loc = {}
    exec(phenotype, {
        "QuantumRegister": QuantumRegister,
        "ClassicalRegister": ClassicalRegister,
        "QuantumCircuit": QuantumCircuit,
        "np": np,
    }, loc)
    qc = loc.get("qc")
    if qc is None:
        raise ValueError("phenotype produced no 'qc'")
    return qc


class _StubEvaluator:
    def __init__(self, shots: int, log_dir: str):
        self.shots = shots
        self.log_dir = log_dir

    def decode_individual(self, ind):
        return ind.phenotype

    def execute_circuit(self, code: str):
        return build_circuit(code)


def extract_run_hof_on_ibm(state: str, selection: str, cfg: dict):
    """Load the patched run_hof_on_ibm from the notebook (cell 42) verbatim."""
    nb_path = f"ibm_{NOTEBOOK_PREFIX[selection]}_transpiled_{state}.ipynb"
    nb = json.load(open(nb_path))
    src = "".join(nb["cells"][42]["source"])
    ns = {
        "os": os, "re": re, "json": json,
        "datetime": datetime.datetime,  # notebook cell uses `from datetime import datetime`
        "USE_NOISE_MODEL": cfg["USE_NOISE_MODEL"],
        "TARGET_STATE": state,
        "RANDOM_SEED": None,  # replaced below with the deployed seed fallback
        "LOG_DIR": None,
        "GATE_PENALTY_WEIGHT": cfg["GATE_PENALTY_WEIGHT"],
        "SUCCESS_THRESHOLD": cfg["SUCCESS_THRESHOLD"],
        "QiskitRuntimeService": __import__("qiskit_ibm_runtime", fromlist=["QiskitRuntimeService"]).QiskitRuntimeService,
        "Sampler": __import__("qiskit_ibm_runtime", fromlist=["SamplerV2"]).SamplerV2,
        "generate_preset_pass_manager": __import__(
            "qiskit.transpiler.preset_passmanagers", fromlist=["generate_preset_pass_manager"]
        ).generate_preset_pass_manager,
        "plot_distribution": __import__("qiskit.visualization", fromlist=["plot_distribution"]).plot_distribution,
        "display": __import__("IPython.display", fromlist=["display"]).display,
        "plt": plt,
    }
    exec(src, ns)
    return ns["run_hof_on_ibm"]


def pre_submit_check(best: dict, selection: str) -> None:
    print("\n" + "=" * 70)
    print("PRE-SUBMIT VERIFICATION (no job queued yet)")
    print("=" * 70)
    print(f"Deployed run:       run {best['run_id']} (seed {best['seed']})")
    print(f"Recorded fidelity:  {best['fidelity']:.4f}")
    print(f"Raw circuit:        {best['raw_gate_count']} gates / {best['raw_depth']} depth")
    print(f"In-loop transpiled: {best['gate_count']} gates / {best['depth']} depth / "
          f"{best['two_qubit_gates']} 2Q (fitness-time, seed {best['seed']})")

    qc = build_circuit(best["phenotype"])
    from qiskit_ibm_runtime import QiskitRuntimeService

    backend = QiskitRuntimeService(channel="ibm_cloud").backend("ibm_fez")
    tqc = transpile(qc, backend=backend, optimization_level=3, seed_transpiler=best["seed"])
    g, d = tqc.size(), tqc.depth()
    match = (g == best["gate_count"] and d == best["depth"])
    print(f"Pre-check transpile: {g} gates / {d} depth at seed_transpiler={best['seed']} "
          f"-> {'MATCHES in-loop (intended circuit)' if match else '⚠ DIFFERS from in-loop!'}")
    print(f"    ops: {dict(tqc.count_ops())}")
    if not match:
        print("    WARNING: this would deploy a differently-transpiled circuit than was scored.")


def run_hardware(state: str, selection: str, pop: int, best: dict, run_dir: str, cfg: dict) -> None:
    run_hof_on_ibm = extract_run_hof_on_ibm(state, selection, cfg)

    ind = SimpleNamespace(
        phenotype=best["phenotype"],
        fitness=SimpleNamespace(values=(best["raw_fitness"],)),
    )
    hof = SimpleNamespace(items=[ind])
    evaluator = _StubEvaluator(shots=cfg["NUM_SHOTS"], log_dir=run_dir)

    out_path = os.path.join(run_dir, "hof_1_ibm_hardware_data.json")
    pre_mtime = os.path.getmtime(out_path) if os.path.exists(out_path) else None

    run_hof_on_ibm(
        evaluator,
        hof,
        target_state=state,
        log_dir=run_dir,
        seed_transpiler=best["seed"],
    )

    if not os.path.exists(out_path):
        sys.exit(f"✗ no hardware result saved at {out_path} "
                 f"(job may still be queued - check the IBM dashboard)")
    if pre_mtime is not None and os.path.getmtime(out_path) <= pre_mtime:
        sys.exit("✗ hardware result file was NOT updated - the local wait timed out while "
                 "the job was still queued/running. Retrieve it later via the IBM dashboard "
                 "or QiskitRuntimeService(channel='ibm_cloud').jobs().")
    hw = json.load(open(out_path))
    print("\n" + "=" * 70)
    print("NEW HARDWARE RESULT")
    print("=" * 70)
    print(f"  p_marked_hw:        {hw['p_marked_hw']:.4f}")
    print(f"  transpiled:         {hw['transpiled_gates']}g/{hw['transpiled_depth']}d "
          f"(seed-consistent: {'yes' if hw['transpiled_gates'] == best['gate_count'] else 'NO'})")
    print(f"  job_id:             {hw['job_id']}")
    print(f"  timestamp:          {hw['timestamp']}")
    print(f"  saved to:           {out_path}")


def verify_stored_circuit(state: str, selection: str, best: dict, run_dir: str):
    """Load the exact scored ISA and verify its recorded identifying fields."""
    circuit, metadata, qpy_path, metadata_path = load_scored_isa(
        run_dir, state, int(best["run_id"])
    )
    expected = {
        "target_state": state,
        "selection_method": selection,
        "seed": int(best["seed"]),
        "run_id": int(best["run_id"]),
        "gate_count": int(best["gate_count"]),
        "depth": int(best["depth"]),
        "two_qubit_gates": int(best["two_qubit_gates"]),
    }
    mismatches = {
        key: {"expected": value, "metadata": metadata.get(key)}
        for key, value in expected.items()
        if metadata.get(key) != value
    }
    if mismatches:
        raise ValueError(f"scored ISA metadata mismatch: {mismatches}")
    return circuit, metadata, qpy_path, metadata_path


def run_stored_hardware(
    state: str,
    selection: str,
    best: dict,
    run_dir: str,
    circuit,
    metadata: dict,
) -> None:
    """Submit the persisted scored ISA circuit without re-transpiling."""
    service = QiskitRuntimeService(channel="ibm_cloud")
    backend = service.backend("ibm_fez")
    verify_live_isa(circuit, backend)

    sampler = SamplerV2(mode=backend)
    sampler.options.default_shots = 10_000
    print(f"\nSubmitting stored scored ISA {metadata['qpy_sha256'][:12]}...")
    job = sampler.run([circuit])
    print(f"  Job ID: {job.job_id()}")
    result = job.result(timeout=3600)

    pub_result = result[0]
    try:
        counts = pub_result.data.cr.get_counts()
    except AttributeError:
        counts = pub_result.data.c.get_counts()
    counts = {bitstring[::-1]: count for bitstring, count in counts.items()}
    total = sum(counts.values())
    p_marked = counts.get(state, 0) / total if total else 0.0

    hw_data = {
        "individual_id": 1,
        "fitness_evolution": float(best.get("raw_fitness", 0.0)),
        "fitness_hardware": 10 * int(p_marked < 0.48) + (1 - p_marked),
        "backend": backend.name,
        "target_state": state,
        "counts": counts,
        "p_marked_hw": p_marked,
        "total_shots": total,
        "original_gates": best.get("raw_gate_count"),
        "original_depth": best.get("raw_depth"),
        "transpiled_gates": metadata["gate_count"],
        "transpiled_depth": metadata["depth"],
        "transpiled_2q": metadata["two_qubit_gates"],
        "job_id": job.job_id(),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scored_isa_qpy_sha256": metadata["qpy_sha256"],
        "scored_isa_metadata_path": os.path.join(
            run_dir,
            f"scored_isa_metadata_{state}_run{int(best['run_id'])}.json",
        ),
    }
    out_path = os.path.join(run_dir, "hof_1_ibm_hardware_data.json")
    with open(out_path, "w") as f:
        json.dump(hw_data, f, indent=2)
    print(f"  p(marked)={p_marked:.4f}")
    print(f"  saved to: {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", default="111", help="target state, e.g. 111 (default: 111)")
    ap.add_argument("--selection", default="epsilon_lexicase",
                    choices=["epsilon_lexicase", "tournament", "lexi2"])
    ap.add_argument("--pop", type=int, default=300)
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    ap.add_argument("--verify-only", action="store_true", help="print the pre-submit check and exit")
    args = ap.parse_args()

    if args.selection not in NOTEBOOK_PREFIX:
        sys.exit(f"unsupported selection: {args.selection}")

    print(f"=== REDEPLOY HARDWARE | state {args.state} | {args.selection} | pop{args.pop} ===")
    best, run_dir, _ = load_deployed_run(args.state, args.selection, args.pop)
    try:
        circuit, metadata, qpy_path, metadata_path = verify_stored_circuit(
            args.state, args.selection, best, run_dir
        )
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(f"✗ {exc}")
    print("\n" + "=" * 70)
    print("VERIFIED STORED SCORED ISA")
    print("=" * 70)
    print(f"  QPY:       {qpy_path}")
    print(f"  metadata:  {metadata_path}")
    print(f"  SHA-256:   {metadata['qpy_sha256']}")
    print(f"  layout:    {metadata['measurement_layout']}")
    print(f"  gates:     {metadata['gate_count']}")
    print(f"  depth:     {metadata['depth']}")
    print(f"  2Q gates:  {metadata['two_qubit_gates']}")
    print(f"  op counts: {metadata['operation_counts']}")
    print(f"\nResult will be saved to: {os.path.join(run_dir, 'hof_1_ibm_hardware_data.json')}")

    if args.verify_only:
        print("\n[--verify-only] exiting before submission.")
        return

    if not args.yes:
        ans = input("\nSubmit this circuit to ibm_fez now? [y/N]: ").strip().lower()
        if ans not in ("y", "yes"):
            print("Aborted - no job submitted.")
            return

    run_stored_hardware(
        args.state, args.selection, best, run_dir, circuit, metadata
    )


if __name__ == "__main__":
    main()
