#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "== frontend: typecheck";  (cd "$ROOT/frontend" && npm run typecheck)
echo "== frontend: lint";       (cd "$ROOT/frontend" && npm run lint)
echo "== frontend: tests";      (cd "$ROOT/frontend" && npm test)
echo "== frontend: build";      (cd "$ROOT/frontend" && npm run build)
AUTH="$ROOT/backend/services/auth-service"
PY="$AUTH/.venv/bin/python"; [ -x "$PY" ] || PY="${PYTHON:-python3}"
echo "== auth-service: lint";   (cd "$AUTH" && "$PY" -m ruff check .)
echo "== auth-service: tests";  (cd "$AUTH" && "$PY" -m pytest -q)
