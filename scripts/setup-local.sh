#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example. Edit the passwords before starting MySQL."; }
(cd frontend && npm ci)
echo "Frontend ready. Run: cd frontend && npm run dev"
echo "Database (needs Docker): docker compose up -d mysql"
