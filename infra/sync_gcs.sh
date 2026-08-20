#!/usr/bin/env bash
# Token-safe GCS sync for the sweep results.
#
# Security rule: the IBM token lives ONLY in ~/.config/grover/ibm_env.sh on the
# VM (mode 600). Nothing containing a token is ever written into the
# experiments tree, and this sync additionally excludes logs, env files,
# notebooks (which historically embedded a token), and local-only files.
set -euo pipefail

SRC="${1:-/opt/grover/experiments}"
BUCKET="${GCS_BUCKET:-gs://grover-sweep-results-grammatical-evolution}"
EXCLUDE='(.*\.log$|.*token.*|.*\.env.*|.*\.ipynb$|.*credentials.*|.*\.pkl$|.*\.png$)'

if command -v gsutil >/dev/null 2>&1; then
  gsutil -m rsync -r -x "$EXCLUDE" "$SRC" "$BUCKET/experiments"
  gsutil -m rsync -r -x "$EXCLUDE" /opt/grover/noise "$BUCKET/noise"
else
  gcloud storage rsync --recursive --exclude "$EXCLUDE" "$SRC" "$BUCKET/experiments"
  gcloud storage rsync --recursive --exclude "$EXCLUDE" /opt/grover/noise "$BUCKET/noise"
fi
echo "GCS sync OK -> $BUCKET ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
