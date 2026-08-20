#!/usr/bin/env bash
# Phase 4 VM environment setup (run on the GCP VM).
# Installs uv + Python 3.11, creates /opt/grover, installs the exact pinned
# dependencies from requirements.txt, and verifies imports.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

sudo apt-get update -y
sudo apt-get install -y curl ca-certificates build-essential

# Install uv (same toolchain used locally; provides pinned Python 3.11).
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

sudo mkdir -p /opt/grover/logs /opt/grover/noise
sudo chown "$(id -u):$(id -g)" /opt/grover
cd /opt/grover

uv python install 3.11
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -r requirements.txt

/opt/grover/.venv/bin/python - <<'PY'
import qiskit, qiskit_aer, qiskit_ibm_runtime, deap, grape, numpy, pandas, matplotlib
print("imports OK | qiskit", qiskit.__version__,
      "| aer", qiskit_aer.__version__,
      "| runtime", qiskit_ibm_runtime.__version__,
      "| deap", deap.__version__, "| numpy", numpy.__version__)
PY

echo "VM setup complete"
