#!/usr/bin/env bash
# Local 80-run lexi8_random control-arm launcher (frozen-noise batch, M4).
#
# Matrix: 10 seeds x 8 states x 1 arm (lexi8_random), pop300, 100 max
# generations. Every run loads the same frozen noise and target bundle.
# Outputs are kept separate from Lexi2 and the other historical arms.
#
# Resume: the dispatcher skips any run whose run_result marker exists.
set -euo pipefail
cd "$(dirname "$0")/.."

NOISE_FILE="$PWD/noise/frozen_env_ibm_fez_2026-08-20.pkl"
SEEDS="21315,47182,12147,33537,70300,74135,67154,80248,91197,29440"

echo "frozen noise : $NOISE_FILE"
echo "seeds        : $SEEDS"
echo "outdir       : $PWD/experiments_frozen_10seed_lexi8_random"
echo "launching dispatcher (concurrency 4; extra args append/override)"

exec caffeinate -i -m -s ./.venv/bin/python infra/run_sweep.py \
  --concurrency 4 \
  --arms lexi8_random \
  --states 000,001,010,011,100,101,110,111 \
  --seeds "$SEEDS" \
  --population 300 \
  --generations 100 \
  --outdir "$PWD/experiments_frozen_10seed_lexi8_random" \
  --logdir "$PWD/logs_frozen_10seed_lexi8_random" \
  --noise-file "$NOISE_FILE" \
  --sync-every 0 \
  "$@"
