#!/usr/bin/env bash
# Build CurAI for iOS and launch on a Simulator (or list available targets).
#
# Prerequisites:
#   - Full Xcode from the Mac App Store (not just Command Line Tools)
#   - xcode-select -s /Applications/Xcode.app/Contents/Developer
#   - Backend running locally, e.g. http://localhost:8000
#
# Usage:
#   ./scripts/ios_simulator_smoke.sh              # boot default simulator and run app
#   ./scripts/ios_simulator_smoke.sh --list       # list simulators / devices
#   ./scripts/ios_simulator_smoke.sh --target "iPhone 17"
#   ./scripts/ios_simulator_smoke.sh --cloud      # load production web app in WebView
#   ./scripts/ios_simulator_smoke.sh --cloud https://app.cura-i.com --target "iPhone 17"
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
API_URL="${VITE_API_BASE_URL:-http://localhost:8000}"
CLOUD_MODE=false
CLOUD_URL="https://app.cura-i.com"
LIST_ONLY=false
TARGET_NAME=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --list)
      LIST_ONLY=true
      shift
      ;;
    --target)
      TARGET_NAME="${2:-}"
      shift 2
      ;;
    --api-url)
      API_URL="${2:-}"
      shift 2
      ;;
    --cloud)
      CLOUD_MODE=true
      if [[ "${2:-}" == http* ]]; then
        CLOUD_URL="${2:-}"
        shift 2
      else
        shift
      fi
      ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

require_xcode() {
  if [[ ! -d /Applications/Xcode.app ]]; then
    echo "ERROR: Xcode is not installed." >&2
    echo "Install Xcode from the App Store, then run:" >&2
    echo "  sudo xcode-select -s /Applications/Xcode.app/Contents/Developer" >&2
    echo "  sudo xcodebuild -license accept" >&2
    exit 1
  fi

  local selected
  selected="$(xcode-select -p 2>/dev/null || true)"
  if [[ "$selected" != *"Xcode.app"* ]]; then
    echo "ERROR: xcode-select points to Command Line Tools, not Xcode." >&2
    echo "Run: sudo xcode-select -s /Applications/Xcode.app/Contents/Developer" >&2
    exit 1
  fi
}

check_backend() {
  local url="$1"
  if ! curl -fsS --max-time 3 "$url/auth/config" >/dev/null; then
    echo "WARNING: Backend not reachable at $url/auth/config" >&2
    echo "Start the API (e.g. docker compose up) or set VITE_API_BASE_URL." >&2
  else
    echo "Backend OK: $url"
  fi
}

main() {
  require_xcode

  cd "$FRONTEND_DIR"

  if [[ "$LIST_ONLY" == true ]]; then
    npx cap run ios --list
    exit 0
  fi

  if [[ "$CLOUD_MODE" == true ]]; then
    API_URL="$CLOUD_URL"
    export CAPACITOR_SERVER_URL="$CLOUD_URL"
    check_backend "$CLOUD_URL"
    echo "Cloud mode: WebView loads $CLOUD_URL (same-origin API + web Google Sign-In)."
    echo "Requires latest frontend deployed to production (git push + VM deploy)."
    echo "Building minimal bundle and syncing Capacitor server URL..."
    npm run build:capacitor
    CAPACITOR_SERVER_URL="$CLOUD_URL" npx cap sync ios
  else
    check_backend "$API_URL"
    echo "Building web bundle with VITE_API_BASE_URL=$API_URL"
    VITE_API_BASE_URL="$API_URL" npm run build:capacitor
    npx cap sync ios
  fi

  local cap_args=(run ios)
  if [[ -n "$TARGET_NAME" ]]; then
    cap_args+=(--target-name "$TARGET_NAME")
  fi

  echo "Launching on iOS (${TARGET_NAME:-default simulator})..."
  npx cap "${cap_args[@]}"
}

main "$@"
