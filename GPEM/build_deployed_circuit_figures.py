#!/usr/bin/env python3
"""Draw the 16 deployed circuits (raw + transpiled) and a 4x4 panel figure.

Reads deployed_best.json per (state, arm), rebuilds each circuit from the
stored phenotype, transpiles with the FROZEN ibm_fez target at opt-3 with the
run seed (identical to in-loop transpilation), and draws:
  - paper_figures/frozen_10seed/circuits/raw_<arm>_<state>_seed<seed>.png
  - paper_figures/frozen_10seed/circuits/transpiled_<arm>_<state>_seed<seed>.png
  - paper_figures/frozen_10seed/fig11_deployed_transpiled_circuits.png/pdf

Sanity-checked: transpiled size/depth must equal the recorded deployed values.
"""

from __future__ import annotations

import json
import os
import pickle

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister, transpile

BUNDLE = "noise/frozen_env_ibm_fez_2026-08-20.pkl"
STATES = ["000", "001", "010", "011", "100", "101", "110", "111"]
ARMS = ["epsilon_lexicase", "tournament"]
ARM_TAG = {"epsilon_lexicase": r"$\varepsilon$-lex", "tournament": "tour"}
OUT_DIR = "paper_figures/frozen_10seed/circuits"
PANEL = "paper_figures/frozen_10seed/fig11_deployed_transpiled_circuits"


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


def main():
    with open(BUNDLE, "rb") as f:
        obj = pickle.load(f)
    target = obj["target"]
    assert target is not None, "bundle has no frozen target"

    os.makedirs(OUT_DIR, exist_ok=True)
    items = []
    for arm in ARMS:
        for st in STATES:
            d = json.load(open(f"experiments_frozen_10seed/{arm}/pop300/noise/state_{st}/deployed_best.json"))
            qc = build_circuit(d["phenotype"])

            # Reproduce the in-loop transpile; retry on the rare Qiskit 2.4.1
            # internal nondeterminism until the recorded metrics match.
            tqc = None
            for _ in range(5):
                cand = transpile(qc, target=target, optimization_level=3, seed_transpiler=d["seed"])
                if cand.size() == d["gate_count"] and cand.depth() == d["depth"]:
                    tqc = cand
                    break
            if tqc is None:
                raise RuntimeError(
                    f"could not reproduce recorded transpile for {arm} {st}: "
                    f"want {d['gate_count']}g/{d['depth']}d")

            base = f"{arm}_{st}_seed{d['seed']}"
            qc.draw("mpl", idle_wires=False).savefig(
                os.path.join(OUT_DIR, f"raw_{base}.png"), dpi=300, bbox_inches="tight")
            plt.close("all")
            tqc.draw("mpl", idle_wires=False).savefig(
                os.path.join(OUT_DIR, f"transpiled_{base}.png"), dpi=300, bbox_inches="tight")
            plt.close("all")
            items.append((arm, st, d["seed"], tqc))
            print(f"drew {base}: raw {qc.size()}g/{qc.depth()}d -> transpiled "
                  f"{tqc.size()}g/{tqc.depth()}d")

    # 4x4 panel of the deployed transpiled circuits
    fig, axes = plt.subplots(4, 4, figsize=(22, 15))
    for k, (arm, st, seed, tqc) in enumerate(items):
        ax = axes[k // 4][k % 4]
        tqc.draw("mpl", ax=ax, idle_wires=False, fold=-1)
        ax.set_title(f"$|{st}\\rangle$ {ARM_TAG[arm]} (seed {seed})", fontsize=10)
    fig.suptitle("Deployed transpiled circuits — frozen ibm_fez target, opt-3, seed = run seed",
                 fontsize=13, y=0.985)
    fig.savefig(PANEL + ".png", dpi=300, bbox_inches="tight")
    fig.savefig(PANEL + ".pdf")
    print(f"\npanel saved: {PANEL}.png/.pdf")
    print(f"32 circuit PNGs in {OUT_DIR}/")


if __name__ == "__main__":
    main()
