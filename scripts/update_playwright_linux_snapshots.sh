#!/usr/bin/env bash
# Regenerate Playwright visual baselines on linux/amd64 (matches GitHub Actions CI).
#
# Usage: ./scripts/update_playwright_linux_snapshots.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash "$ROOT_DIR/scripts/run_playwright_linux.sh" test tests/ui-visual.spec.ts --update-snapshots

printf '\nLinux visual snapshots updated under frontend/tests/ui-visual.spec.ts-snapshots/*-linux.png\n'
