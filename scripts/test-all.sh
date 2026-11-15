#!/usr/bin/env bash
# Runs every check. Backend commands use each service's .venv when it exists, otherwise $PYTHON or python3.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "== frontend: typecheck";  (cd "$ROOT/frontend" && npm run typecheck)
echo "== frontend: lint";       (cd "$ROOT/frontend" && npm run lint)
echo "== frontend: tests";      (cd "$ROOT/frontend" && npm test)
echo "== frontend: build";      (cd "$ROOT/frontend" && npm run build)
py() { local p="$1/.venv/bin/python"; [ -x "$p" ] && echo "$p" || echo "${PYTHON:-python3}"; }
echo "== shared: lint";         (cd "$ROOT/backend/shared" && "$(py "$ROOT/backend/services/auth-service")" -m ruff check .)
echo "== shared: tests";        (cd "$ROOT/backend/shared" && "$(py "$ROOT/backend/services/auth-service")" -m pytest -q)
for svc in auth-service purchase-request-service approval-service vendor-service quotation-service; do
  DIR="$ROOT/backend/services/$svc"; PY="$(py "$DIR")"
  echo "== $svc: lint";   (cd "$DIR" && "$PY" -m ruff check .)
  echo "== $svc: tests";  (cd "$DIR" && "$PY" -m pytest -q)
done
echo "== cross-service end-to-end (starts the five services as real processes)"
(cd "$ROOT/backend/tests" && "$(py "$ROOT/backend/services/auth-service")" -m ruff check . && "$(py "$ROOT/backend/services/auth-service")" -m pytest -q)
