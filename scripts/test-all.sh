#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../frontend"
echo "== typecheck"; npm run typecheck
echo "== lint";      npm run lint
echo "== unit tests"; npm test
echo "== build";     npm run build
