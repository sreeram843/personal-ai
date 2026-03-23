#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP_IMAGE="personal-ai-quality-gate:local"

cleanup() {
  docker image rm -f "$TEMP_IMAGE" >/dev/null 2>&1 || true
}

trap cleanup EXIT

run_step() {
  printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$1"
  shift
  "$@"
}

run_frontend_step() {
  local description="$1"
  local command="$2"
  printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$description"
  (
    cd "$ROOT_DIR/frontend"
    eval "$command"
  )
}

run_step "Validating docker compose" docker compose -f "$ROOT_DIR/docker-compose.yml" config >/dev/null
run_step "Running lightweight security checks" python "$ROOT_DIR/scripts/security_checks.py"
run_step "Compiling Python sources" python -m compileall "$ROOT_DIR/app" "$ROOT_DIR/api" "$ROOT_DIR/tests"
run_step "Running backend reliability tests" python -m pytest "$ROOT_DIR/tests"
run_frontend_step "Linting frontend" "npm run lint"
run_frontend_step "Building frontend" "npm run build"
run_frontend_step "Running Playwright visual and flow tests" "npm run test:ui"
run_step "Building backend container image" docker build --file "$ROOT_DIR/Dockerfile.backend" --tag "$TEMP_IMAGE" "$ROOT_DIR"
run_step "Running docker compose smoke test" bash "$ROOT_DIR/scripts/compose_smoke.sh"

printf '\n[%s] Quality gate passed\n' "$(date '+%H:%M:%S')"