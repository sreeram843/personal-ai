#!/usr/bin/env bash
# Run Playwright tests on linux/amd64 in Docker so rendering matches Linux snapshots.
#
# Usage:
#   ./scripts/run_playwright_linux.sh test
#   ./scripts/run_playwright_linux.sh test tests/ui-visual.spec.ts --update-snapshots

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLAYWRIGHT_NODE_IMAGE="${PLAYWRIGHT_NODE_IMAGE:-node:20-bookworm-slim}"
PLAYWRIGHT_ARGS="${*:-test}"

docker run --platform linux/amd64 --rm \
  -v "$ROOT_DIR:/work" \
  -w /work/frontend \
  "$PLAYWRIGHT_NODE_IMAGE" \
  bash -lc "
    set -euo pipefail
    npm ci
    npx playwright install --with-deps chromium firefox webkit
    CI=1 npx playwright $PLAYWRIGHT_ARGS
  "
