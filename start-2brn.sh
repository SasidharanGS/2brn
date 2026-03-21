#!/usr/bin/env bash
# start-2brn.sh — open the 2brn app.
#
# Optional: if you run a local AI gateway (e.g. Ollama, LM Studio, a custom
# OpenAI-compatible server), start it here before launching 2brn.
#
# Configuration — edit these lines to match your environment:
APP_PATH=""   # Leave empty to use `open -a "2brn"`, or set to absolute .app path

# ── internals (no need to edit below) ───────────────────────────────────────

set -euo pipefail

open_app() {
  if [[ -n "$APP_PATH" ]]; then
    open "$APP_PATH"
  else
    open -a "2brn"
  fi
}

echo "→ Opening 2brn..."
open_app
