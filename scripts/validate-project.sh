#!/usr/bin/env bash
# Checks the repository layout and that no secrets or build output are present.
set -euo pipefail
cd "$(dirname "$0")/.."
for f in Design.md Skill.md docker-compose.yml .env.example README.md PHASE_STATUS.md CHANGELOG.md frontend/package.json; do
  [ -e "$f" ] || { echo "MISSING: $f"; exit 1; }
done
[ ! -e .env ] || echo "WARNING: .env exists locally and must not be packaged"
if grep -rEl "AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC )?PRIVATE KEY" --exclude-dir=node_modules --exclude-dir=dist . ; then echo "Possible secret found"; exit 1; fi
if find . -type d -empty -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "./.git/*" | grep -q .; then echo "Empty directories found"; exit 1; fi
echo "Project layout OK"
