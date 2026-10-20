#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example. Edit the passwords and JWT_SECRET before starting services."; }
(cd frontend && npm ci)
(cd backend/services/auth-service && python3 -m venv .venv && .venv/bin/pip install -q -r requirements-dev.txt)
echo "Frontend:  cd frontend && npm run dev"
echo "Auth service (see backend/services/auth-service/README.md), or with Docker: docker compose up -d --build"
