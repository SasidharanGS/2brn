# Design: Gateway-Aware 2brn Startup Script

**Date:** 2026-04-25  
**Status:** Approved  
**Scope:** Single shell script that ensures the JLL GPT Gateway is running before opening the 2brn app.

---

## Problem

2brn's daemon depends on the JLL GPT Gateway (port 8888) for all LLM and embedding calls. Currently there is no single command to start the full stack — the gateway and 2brn must be launched manually and in the right order.

---

## Solution

A `start-2brn.sh` script at the repo root. One command starts everything correctly.

---

## Script: `start-2brn.sh`

**Location:** `2brn/start-2brn.sh`

### Configuration (top of script)

```bash
GATEWAY_JAR="/path/to/dev-platform-ai-gateway/build/libs/dev-platform-ai-gateway.jar"
APP_PATH=""   # empty = open -a "2brn"; or set to absolute .app path
GATEWAY_LOG="$HOME/.2brn/gateway.log"
GATEWAY_PID_FILE="$HOME/.2brn/gateway.pid"
GATEWAY_HEALTH_URL="http://127.0.0.1:8888/actuator/health"
GATEWAY_STARTUP_TIMEOUT=30   # seconds to wait for gateway to become healthy
```

### Flow

```
run start-2brn.sh
  │
  ├─ curl -sf GATEWAY_HEALTH_URL → HTTP 200?
  │
  ├─ YES → "Gateway already running" → skip to open app
  │
  └─ NO  → launch gateway JAR in background
            nohup java -jar $GATEWAY_JAR >> $GATEWAY_LOG 2>&1 &
            echo $! > $GATEWAY_PID_FILE
            │
            ├─ poll GATEWAY_HEALTH_URL every 2s up to GATEWAY_STARTUP_TIMEOUT
            ├─ each tick: print a dot for feedback
            ├─ timeout reached → print error message, exit 1
            └─ health returns 200 → "Gateway ready"
                │
                └─ open 2brn app
                   if APP_PATH set: open "$APP_PATH"
                   else:            open -a "2brn"
```

### Error handling

| Scenario | Behaviour |
|---|---|
| JAR not found at `GATEWAY_JAR` | Print clear error with the path, `exit 1` |
| Gateway doesn't become healthy within timeout | Print error pointing to `$GATEWAY_LOG`, `exit 1` |
| App not found | macOS `open` prints its own error; script exits with its code |
| Gateway already running | Skip silently, open app immediately |

---

## Files changed

| File | Action |
|---|---|
| `start-2brn.sh` | **New** — startup script |

No changes to daemon, Electron, or UI code.

---

## Out of scope

- Stopping the gateway on app quit (gateway is a long-running service; leave it running)
- Auto-building the app if no `.app` exists (build separately with `pnpm electron:build`)
- Windows/Linux support (macOS `open` command only)
- LaunchAgent / always-on gateway (can be added later if needed)
