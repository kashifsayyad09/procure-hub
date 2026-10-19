#!/usr/bin/env bash
# Usage: scripts/package-phase.sh 01   -> ../procurehub-phase-01.zip (one cumulative archive)
set -euo pipefail
N="${1:?phase number, e.g. 01}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$(dirname "$ROOT")/procurehub-phase-$N.zip"
rm -f "$OUT"
cd "$(dirname "$ROOT")"
zip -rq "$OUT" "$(basename "$ROOT")" \
  -x "*/node_modules/*" "*/dist/*" "*/.venv/*" "*/__pycache__/*" "*/.env" "*.tfstate*" "*/.terraform/*" "*.zip"
echo "$OUT"
