#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example. Edit the passwords and both secrets before starting services."; }
(cd frontend && npm ci)
for svc in auth-service purchase-request-service approval-service; do
  (cd "backend/services/$svc" && python3 -m venv .venv && .venv/bin/pip install -q -r requirements-dev.txt -e ../../shared)
done
echo "Frontend:  cd frontend && npm run dev"
echo "Backend, with Docker:  docker compose up -d --build"
