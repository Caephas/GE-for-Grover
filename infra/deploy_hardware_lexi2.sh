#!/usr/bin/env bash
# Deploy the 8 Lexi2 deployed best-of-10 circuits to ibm_fez (10,000 shots each).
# Reads experiments_frozen_10seed_lexi2/lexi2/pop300/noise/state_*/deployed_best.json.
set -u
cd "$(dirname "$0")/.."
mkdir -p logs_hardware_lexi2

ORDER=$(./.venv/bin/python - <<'PY'
import random
import secrets

states = ["000", "001", "010", "011", "100", "101", "110", "111"]
seed = secrets.randbits(32)
random.Random(seed).shuffle(states)
print(f"# randomized order seed: {seed}")
for state in states:
    print(state)
PY
)

printf '%s\n' "$ORDER" | while read -r st; do
  case "$st" in
    \#*|"") continue ;;
  esac
  echo "=== $(date -u +%FT%TZ) | lexi2 | state $st ==="
  ./.venv/bin/python redeploy_hardware.py --state "$st" --selection lexi2 --pop 300 --yes
done

echo "=== ALL LEXI2 DEPLOYMENTS DONE $(date -u +%FT%TZ) ==="
