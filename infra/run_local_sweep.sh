#!/usr/bin/env bash
# Local 160-run sweep launcher (frozen-noise batch, M4).
#
# Matrix: 10 seeds x 8 states x 2 arms (epsilon_lexicase, tournament),
# pop300, 100 max generations, all runs loading the SAME frozen noise
# snapshot. Outputs go to experiments_frozen_10seed/ (tagged batch; the old
# live-calibration runs in experiments/ are never touched).
#
# The whole thing runs under `caffeinate -i -s`: -i prevents idle sleep and
# -s prevents system sleep while on AC power (the one that matters when the
# lid is closed). Keep the Mac plugged in for the whole sweep.
#
# Resume: the dispatcher skips any run whose run_result_<state>_run<id>.json
# marker already exists, so killing/restarting this script resumes the batch
# without redoing completed runs.
#
# Usage:
#   bash infra/run_local_sweep.sh            # full 160-run batch
#   bash infra/run_local_sweep.sh --concurrency 3   # override concurrency
set -euo pipefail
cd "$(dirname "$0")/.."

NOISE_FILE="$PWD/noise/frozen_env_ibm_fez_2026-08-20.pkl"
SEEDS="21315,47182,12147,33537,70300,74135,67154,80248,91197,29440"

echo "frozen noise : $NOISE_FILE"
echo "seeds        : $SEEDS"
echo "outdir       : $PWD/experiments_frozen_10seed"
echo "launching dispatcher (concurrency 4; extra args append/override)"

exec caffeinate -i -s ./.venv/bin/python infra/run_sweep.py \
  --concurrency 4 \
  --arms epsilon_lexicase,tournament \
  --states 000,001,010,011,100,101,110,111 \
  --seeds "$SEEDS" \
  --population 300 \
  --generations 100 \
  --outdir "$PWD/experiments_frozen_10seed" \
  --logdir "$PWD/logs_frozen_10seed" \
  --noise-file "$NOISE_FILE" \
  --sync-every 0 \
  "$@"
