#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs_hardware

ORDER=$(./.venv/bin/python - <<'PY'
import random
import secrets

pairs = [
    (method, state)
    for method in ("epsilon_lexicase", "tournament")
    for state in ("000", "001", "010", "011", "100", "101", "110", "111")
]
seed = secrets.randbits(32)
random.Random(seed).shuffle(pairs)
print(f"# randomized order seed: {seed}")
for method, state in pairs:
    print(f"{method} {state}")
PY
)

printf '%s\n' "$ORDER" | while read -r sel st; do
  case "$sel" in
    \#*|"") continue ;;
  esac
  echo "=== $(date -u +%FT%TZ) | $sel | state $st ==="
  ./.venv/bin/python redeploy_hardware.py --state "$st" --selection "$sel" --pop 300 --yes
done

echo "=== ALL DEPLOYMENTS DONE $(date -u +%FT%TZ) ==="
