# Gateway-Aware 2brn Startup Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `start-2brn.sh` at the 2brn repo root — a single command that checks if the JLL GPT Gateway is running on port 8888, starts it in the background if not, waits for it to be healthy, then opens the 2brn app.

**Architecture:** A self-contained bash script with two configurable variables at the top (JAR path and app path). It health-checks the gateway via `curl`, spawns the JAR with `nohup` if needed, polls until healthy, then calls `open` to launch 2brn. No changes to daemon, Electron, or UI code.

**Tech Stack:** Bash, `curl`, `nohup`, `java -jar`, macOS `open`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `start-2brn.sh` | **Create** | Full startup orchestration script |

---

### Task 1: Create `start-2brn.sh` with gateway check and conditional launch

**Files:**
- Create: `start-2brn.sh`

This is a single-task feature — the script is small enough to write, test, and commit atomically.

- [ ] **Step 1: Create the script**

Create `/Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/start-2brn.sh` with the following content:

```bash
#!/usr/bin/env bash
# start-2brn.sh — start JLL GPT Gateway if needed, then open the 2brn app.
#
# Configuration — edit these two lines to match your environment:
GATEWAY_JAR="$HOME/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/openclaude_x_jllgpt_x_gateway/dev-platform-ai-gateway/build/libs/dev-platform-ai-gateway.jar"
APP_PATH=""   # Leave empty to use `open -a "2brn"`, or set to absolute .app path

# ── internals (no need to edit below) ───────────────────────────────────────
GATEWAY_HEALTH_URL="http://127.0.0.1:8888/actuator/health"
GATEWAY_LOG="$HOME/.2brn/gateway.log"
GATEWAY_PID_FILE="$HOME/.2brn/gateway.pid"
GATEWAY_STARTUP_TIMEOUT=30   # seconds

set -euo pipefail

# ── helper ───────────────────────────────────────────────────────────────────
gateway_healthy() {
  curl -sf "$GATEWAY_HEALTH_URL" > /dev/null 2>&1
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
```

- [ ] **Step 2: Make the script executable**

```bash
chmod +x start-2brn.sh
```

- [ ] **Step 3: Smoke-test — gateway already running**

First, make sure the gateway is running (start it manually if needed). Then run:

```bash
./start-2brn.sh
```

Expected output:
```
✓ Gateway already running on port 8888.
→ Opening 2brn...
```
And 2brn opens. If `APP_PATH` is empty and you haven't installed a `2brn.app` yet, `open` will print an error like `"2brn" cannot be found` — that's expected; the gateway check part works correctly.

- [ ] **Step 4: Smoke-test — gateway not running**

Stop the gateway (or temporarily point `GATEWAY_HEALTH_URL` to a port nothing is running on, e.g. `8889`). Then run:

```bash
./start-2brn.sh
```

Expected output (gateway on wrong port test):
```
→ Starting JLL GPT Gateway...
  Logs: /Users/<you>/.2brn/gateway.log
  Waiting for gateway..............
✗ Gateway did not become healthy within 30s.
  Check the log for errors: /Users/<you>/.2brn/gateway.log
```
(Script exits with code 1.)

With the correct JAR and gateway stopped for real:
```
→ Starting JLL GPT Gateway...
  Logs: /Users/<you>/.2brn/gateway.log
  Waiting for gateway.....
✓ Gateway ready (took 10s).
→ Opening 2brn...
```

- [ ] **Step 5: Smoke-test — bad JAR path**

Temporarily set `GATEWAY_JAR="/tmp/nonexistent.jar"` in the script, stop the gateway, then run:

```bash
./start-2brn.sh
```

Expected output:
```
✗ Gateway JAR not found at:
  /tmp/nonexistent.jar
  Build the gateway first or update GATEWAY_JAR in this script.
```
(Exit code 1.)

Restore `GATEWAY_JAR` to the correct path afterward.

- [ ] **Step 6: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add start-2brn.sh
git commit -m "$(cat <<'EOF'
feat: add start-2brn.sh — gateway-aware startup script

Checks if JLL GPT Gateway is running on port 8888 before opening
the app. Starts the gateway JAR in the background if not, waits
for /actuator/health, then opens 2brn. Logs to ~/.2brn/gateway.log.

Co-Authored-By: Claude Opus 4.6 <noreply@openclaude.dev>
EOF
)"
```

---

## Notes

- **Gateway log** is appended (not truncated) each run — tail it with `tail -f ~/.2brn/gateway.log` if you need to debug.
- **Gateway PID** is written to `~/.2brn/gateway.pid` so you can kill it manually: `kill $(cat ~/.2brn/gateway.pid)`.
- **`APP_PATH`** — once you build and install the `.app` (via `pnpm electron:build`), either install it to `/Applications/2brn.app` (then `open -a "2brn"` works with no config change) or set `APP_PATH="/path/to/2brn.app"` explicitly.
- **`set -euo pipefail`** — the script exits immediately on any unexpected error. The `gateway_healthy` and `open_app` functions are exempt because they're called inside `if` / `while` conditions.
