#!/usr/bin/env python3
"""Build a chmod-600 environment file with the IBM credentials for the VM.

Reads the saved IBM Quantum account (~/.qiskit/qiskit-ibm.json) and writes a
file containing QISKIT_IBM_TOKEN / QISKIT_IBM_INSTANCE. The token is never
printed; the file is only ever transferred to the VM's environment (never
synced to GCS, never written into experiment output folders).
"""
import json
import os
import sys


def main() -> int:
    src = os.path.expanduser("~/.qiskit/qiskit-ibm.json")
    if not os.path.exists(src):
        print(f"error: {src} not found", file=sys.stderr)
        return 1
    with open(src) as f:
        data = json.load(f)
    entry = data.get("default-ibm-cloud") or data.get("default")
    if not entry or not entry.get("token"):
        print("error: no ibm_cloud account with a token found", file=sys.stderr)
        return 1
    out = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "/tmp/ibm_env.sh")
    content = (
        f"export QISKIT_IBM_TOKEN='{entry['token']}'\n"
        f"export QISKIT_IBM_INSTANCE='{entry.get('instance', '')}'\n"
    )
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(content)
    os.chmod(out, 0o600)
    print(f"wrote credentials env file: {out} (mode 600, token not printed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
