#!/usr/bin/env bash
# start-2brn.sh — start JLL GPT Gateway if needed, then open the 2brn app.
#
# Configuration — edit these lines to match your environment:
GATEWAY_JAR="$HOME/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/openclaude_x_jllgpt_x_gateway/dev-platform-ai-gateway/build/libs/dev-platform-ai-gateway.jar"
GATEWAY_ENV="$HOME/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/openclaude_x_jllgpt_x_gateway/dev-platform-ai-gateway/.env"
APP_PATH=""   # Leave empty to use `open -a "2brn"`, or set to absolute .app path

# ── internals (no need to edit below) ───────────────────────────────────────
GATEWAY_HEALTH_URL="http://127.0.0.1:8888/actuator/health"
GATEWAY_LOG="$HOME/.2brn/gateway.log"
GATEWAY_PID_FILE="$HOME/.2brn/gateway.pid"
GATEWAY_STARTUP_TIMEOUT=30   # seconds

set -euo pipefail

# ── helper ───────────────────────────────────────────────────────────────────
gateway_healthy() {
  # Accept any HTTP response (including 401 Unauthorized) as "gateway is up".
  # curl -sf treats 4xx/5xx as failure (exit 22), so we use --write-out instead
  # and check only for a connection error (exit code 7 = cannot connect).
  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "$GATEWAY_HEALTH_URL" 2>/dev/null)
  [[ "$http_code" =~ ^[0-9]+$ && "$http_code" -ge 100 ]]
}

open_app() {
  if [[ -n "$APP_PATH" ]]; then
    open "$APP_PATH"
  else
    open -a "2brn"
  fi
}

# ── 1. check if gateway is already up ────────────────────────────────────────
if gateway_healthy; then
  echo "✓ Gateway already running on port 8888."
else
  # ── 2. validate JAR exists ─────────────────────────────────────────────────
  if [[ ! -f "$GATEWAY_JAR" ]]; then
    echo "✗ Gateway JAR not found at:" >&2
    echo "  $GATEWAY_JAR" >&2
    echo "  Build the gateway first or update GATEWAY_JAR in this script." >&2
    exit 1
  fi

  # ── 3. start gateway in background ─────────────────────────────────────────
  mkdir -p "$(dirname "$GATEWAY_LOG")"
  echo "→ Starting JLL GPT Gateway..."
  echo "  Logs: $GATEWAY_LOG"
  # Load gateway .env if it exists (provides AI_GATEWAY_API_TOKEN etc.)
  if [[ -f "$GATEWAY_ENV" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$GATEWAY_ENV"
    set +a
  fi
  nohup java -jar "$GATEWAY_JAR" >> "$GATEWAY_LOG" 2>&1 &
  echo $! > "$GATEWAY_PID_FILE"

  # ── 4. wait for gateway to become healthy ──────────────────────────────────
  elapsed=0
  printf "  Waiting for gateway"
  while ! gateway_healthy; do
    if (( elapsed >= GATEWAY_STARTUP_TIMEOUT )); then
      echo ""
      echo "✗ Gateway did not become healthy within ${GATEWAY_STARTUP_TIMEOUT}s." >&2
      echo "  Check the log for errors: $GATEWAY_LOG" >&2
      exit 1
    fi
    printf "."
    sleep 2
    (( elapsed += 2 ))
  done
  echo ""
  echo "✓ Gateway ready (took ${elapsed}s)."
fi

# ── 5. open 2brn ─────────────────────────────────────────────────────────────
echo "→ Opening 2brn..."
open_app
