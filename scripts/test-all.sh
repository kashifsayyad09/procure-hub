#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "== frontend: typecheck";  (cd "$ROOT/frontend" && npm run typecheck)
echo "== frontend: lint";       (cd "$ROOT/frontend" && npm run lint)
echo "== frontend: tests";      (cd "$ROOT/frontend" && npm test)
echo "== frontend: build";      (cd "$ROOT/frontend" && npm run build)
for svc in auth-service purchase-request-service; do
  DIR="$ROOT/backend/services/$svc"
  PY="$DIR/.venv/bin/python"; [ -x "$PY" ] || PY="${PYTHON:-python3}"
  echo "== $svc: lint";   (cd "$DIR" && "$PY" -m ruff check .)
  echo "== $svc: tests";  (cd "$DIR" && "$PY" -m pytest -q)
done
