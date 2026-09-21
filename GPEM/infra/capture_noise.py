#!/usr/bin/env python3
"""Capture one ibm_fez noise-model snapshot for the whole sweep.

Writes the same noise model that AerSimulator.from_backend(backend) builds
(NoiseModel.from_backend(...)) to a pickle file (exact round-trip: the dict
form contains numpy arrays and complex matrices that plain JSON can't carry).
Runs during the sweep load it via `--noise-file PATH` or the
QISKIT_NOISE_MODEL_JSON env var, so all runs share one frozen calibration and
are reproducible.

Credentials come from QISKIT_IBM_TOKEN / QISKIT_IBM_INSTANCE or the saved
account. No hardware job is submitted.

Usage:
  python3 capture_noise.py --out /opt/grover/noise/noise_ibm_fez_2026-08-19.json
"""
import argparse
import pickle
import os
import sys
from datetime import datetime, timezone

from qiskit_aer.noise import NoiseModel
from qiskit_ibm_runtime import QiskitRuntimeService


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="noise_ibm_fez.pkl")
    ap.add_argument("--bundle-out", default=None,
                    help="write a frozen-env bundle pickle "
                         "{noise_model, target, ...} for the whole sweep")
    ap.add_argument("--noise-in", default=None,
                    help="existing frozen noise-model pickle to embed in the "
                         "bundle (keeps the exact same noise; otherwise built "
                         "live from the backend)")
    ap.add_argument("--backend", default="ibm_fez")
    args = ap.parse_args()

    token = os.environ.get("QISKIT_IBM_TOKEN")
    instance = os.environ.get("QISKIT_IBM_INSTANCE")
    if token:
        service = QiskitRuntimeService(channel="ibm_cloud", token=token,
                                       instance=instance or None)
    else:
        service = QiskitRuntimeService(channel="ibm_cloud")
    backend = service.backend(args.backend)

    nm = NoiseModel.from_backend(backend)
    if args.bundle_out:
        if args.noise_in:
            with open(args.noise_in, "rb") as f:
                nm = pickle.load(f)
        bundle = {
            "noise_model": nm,
            "target": backend.target,
            "backend": backend.name,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(args.bundle_out, "wb") as f:
            pickle.dump(bundle, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"captured frozen-env bundle -> {args.bundle_out} "
              f"({backend.target.num_qubits}-qubit target, noise from "
              f"{args.noise_in or 'live'} )")
        return 0

    with open(args.out, "wb") as f:
        pickle.dump(nm, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"captured noise model from {args.backend} "
          f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
