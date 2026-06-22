#!/usr/bin/env bash
# Regenerate Playwright visual baselines on linux/amd64 (matches GitHub Actions CI).
#
# Usage: ./scripts/update_playwright_linux_snapshots.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

docker run --platform linux/amd64 --rm \
  -v "$ROOT_DIR:/work" \
  -w /work/frontend \
  node:20-bookworm-slim \
  bash -lc '
    set -euo pipefail
    npm ci
    npx playwright install --with-deps chromium firefox webkit
    CI=1 npx playwright test tests/ui-visual.spec.ts --update-snapshots
  '

printf '\nLinux visual snapshots updated under frontend/tests/ui-visual.spec.ts-snapshots/*-linux.png\n'
