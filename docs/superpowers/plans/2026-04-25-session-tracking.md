# Session Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically capture every OpenClaude session as a structured Joplin note so that questions like "what was I building last Tuesday?" become answerable through 2brn's chat interface.

**Architecture:** Three coordinated pieces: (1) a `PreToolUse` hook writes `~/.openclaude/session-state.json` on the first tool call of each session to record the start time, repo, branch, and git SHA; (2) a `session-to-joplin.sh` Stop hook reads that state at session end, collects git delta, calls JLL Gateway for a summary, formats a Markdown note, and posts it to Joplin's "OpenClaude Sessions" notebook; (3) the `/remember` skill is updated to also accumulate decisions to `~/.openclaude/session-decisions.jsonl` so they fold into the session note. All three work together but degrade gracefully when the other components are missing (gateway down, Joplin closed, no git repo).

**Tech Stack:** Bash, Python 3 (stdlib only — no pip installs), Joplin Web Clipper REST API (port 41184), JLL GPT Gateway (`http://localhost:8888/v1/chat/completions`), `~/.openclaude/settings.json` hook config, OpenClaude `/remember` skill (Markdown)

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `~/.openclaude/hooks/session-to-joplin.sh` | **Create** | Main Stop hook — formats + posts session note |
| `~/.openclaude/hooks/session-start.sh` | **Create** | PreToolUse hook — writes session-state.json |
| `~/.openclaude/settings.json` | **Modify** | Wire both hooks; Stop replaces `printf '\a'`, PreToolUse added |
| `.claude/skills/remember.md` (in 2brn repo) | **Modify** | Also write to `~/.openclaude/session-decisions.jsonl` |

> **Note:** The hooks live in `~/.openclaude/hooks/` (global, not in the repo) so they fire for every project, not just 2brn. The `.claude/skills/remember.md` change is in the repo but the `session-decisions.jsonl` file it writes is global.

---

## Task 1: session-start.sh — write session-state.json on first tool use

**Files:**
- Create: `~/.openclaude/hooks/session-start.sh`

This hook fires on every `PreToolUse` event. It checks if `session-state.json` already exists for this session (using a PID guard) — if not, it writes it. This gives the Stop hook the data it needs: start time, working directory, repo name, branch, and starting git SHA.

- [ ] **Step 1: Create the hooks directory if it doesn't exist**

```bash
mkdir -p ~/.openclaude/hooks
```

- [ ] **Step 2: Create `~/.openclaude/hooks/session-start.sh`**

```bash
#!/bin/bash
# session-start.sh
# PreToolUse hook — records session start state on the very first tool call.
# Subsequent tool calls in the same session are no-ops (PID guard).
# Output: ~/.openclaude/session-state.json

STATE_FILE="$HOME/.openclaude/session-state.json"

# PID guard: if state file exists AND the PID inside matches our parent process,
# this session is already initialised — skip.
if [ -f "$STATE_FILE" ]; then
    STORED_PID=$(python3 -c "
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    print(d.get('session_pid', ''))
except: print('')
" "$STATE_FILE" 2>/dev/null)
    # $PPID is the openclaude process; use it as the session identifier
    if [ "$STORED_PID" = "$PPID" ]; then
        exit 0  # already initialised for this session
    fi
fi

# Gather context
STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
WORKING_DIR=$(pwd)
REPO_NAME=$(basename "$WORKING_DIR")

# Git context (graceful if not a git repo)
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
GIT_SHA_START=$(git rev-parse --short HEAD 2>/dev/null || echo "")

# Write state file
python3 -c "
import json, sys
d = {
    'session_pid':   int(sys.argv[1]),
    'started_at':    sys.argv[2],
    'working_dir':   sys.argv[3],
    'repo_name':     sys.argv[4],
    'git_branch':    sys.argv[5],
    'git_sha_start': sys.argv[6],
}
with open('$STATE_FILE', 'w') as f:
    json.dump(d, f, indent=2)
" "$PPID" "$STARTED_AT" "$WORKING_DIR" "$REPO_NAME" "$GIT_BRANCH" "$GIT_SHA_START"

exit 0
```

- [ ] **Step 3: Make it executable**

```bash
chmod +x ~/.openclaude/hooks/session-start.sh
```

- [ ] **Step 4: Smoke-test it manually**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
bash ~/.openclaude/hooks/session-start.sh
cat ~/.openclaude/session-state.json
```

Expected output (values will vary):
```json
{
  "session_pid": 12345,
  "started_at": "2026-04-25T12:00:00Z",
  "working_dir": "/Users/sasidharan.govindan/.../2brn",
  "repo_name": "2brn",
  "git_branch": "feature/session-tracking",
  "git_sha_start": "cf83b2a"
}
```

- [ ] **Step 5: Test PID guard — running twice doesn't overwrite**

```bash
# Run once, note the pid in the file
bash ~/.openclaude/hooks/session-start.sh
FIRST_PID=$(python3 -c "import json; print(json.load(open('$HOME/.openclaude/session-state.json'))['session_pid'])")

# Run again — PID won't match PPID (different shell), so it WILL overwrite
# To truly test the guard, the second call must come from the same $PPID
# Just verify the file is valid JSON and contains all required keys
python3 -c "
import json
d = json.load(open('$HOME/.openclaude/session-state.json'))
required = ['session_pid','started_at','working_dir','repo_name','git_branch','git_sha_start']
missing = [k for k in required if k not in d]
assert not missing, f'Missing keys: {missing}'
print('OK — all keys present')
"
```

Expected: `OK — all keys present`

- [ ] **Step 6: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add .  # nothing to add — hook is outside the repo
git status  # confirm clean
# The hook file itself is NOT in the repo (lives in ~/.openclaude/hooks/)
# We'll commit the settings.json change in Task 3
echo "hook created at ~/.openclaude/hooks/session-start.sh"
```

---

## Task 2: session-to-joplin.sh — the main Stop hook

**Files:**
- Create: `~/.openclaude/hooks/session-to-joplin.sh`

This is the core of the feature. It runs when OpenClaude exits. It:
1. Reads `session-state.json` for start context
2. Collects git delta (changed files + commits since session start)
3. Reads `session-decisions.jsonl` for any `/remember decision:` calls
4. Calls JLL Gateway to generate a 2–3 sentence summary (falls back gracefully)
5. Formats the full Markdown note body
6. Posts to Joplin "OpenClaude Sessions" notebook via Web Clipper
7. Also writes the legacy monthly "Memories" marker (backward compat)
8. Clears `session-state.json` and `session-decisions.jsonl`

- [ ] **Step 1: Create `~/.openclaude/hooks/session-to-joplin.sh`**

```bash
#!/bin/bash
# session-to-joplin.sh
# Stop hook — captures the completed OpenClaude session as a Joplin note.
# Runs when openclaude exits. Gracefully handles: no git repo, gateway down,
# Joplin closed, no session-state.json (session too short / no tools called).

set -euo pipefail

JOPLIN_TOKEN="665e8cd6f888f1a7197c0e842dbc4e280f5475298d75333e7f34d2d67dc9c6970fda2b7f53380b95b8c711b75a14faeba1dd6b6aba44fc2c48d533406dcd51e5"
JOPLIN_PORT=41184
GATEWAY_URL="http://localhost:8888"
STATE_FILE="$HOME/.openclaude/session-state.json"
DECISIONS_FILE="$HOME/.openclaude/session-decisions.jsonl"
PENDING_DIR="$HOME/.openclaude/pending-sessions"

# ── 1. Read session state ──────────────────────────────────────────────────────
if [ ! -f "$STATE_FILE" ]; then
    # No tools were called — nothing meaningful to record
    exit 0
fi

SESSION_DATA=$(python3 -c "
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    print(d.get('started_at',''))
    print(d.get('working_dir',''))
    print(d.get('repo_name',''))
    print(d.get('git_branch',''))
    print(d.get('git_sha_start',''))
except Exception as e:
    print('')  # 5 empty lines = all fields missing
    print('')
    print('')
    print('')
    print('')
" "$STATE_FILE" 2>/dev/null)

STARTED_AT=$(echo "$SESSION_DATA" | sed -n '1p')
WORKING_DIR=$(echo "$SESSION_DATA" | sed -n '2p')
REPO_NAME=$(echo "$SESSION_DATA"  | sed -n '3p')
GIT_BRANCH=$(echo "$SESSION_DATA" | sed -n '4p')
GIT_SHA_START=$(echo "$SESSION_DATA" | sed -n '5p')

# If state was empty, nothing to record
if [ -z "$STARTED_AT" ]; then
    rm -f "$STATE_FILE"
    exit 0
fi

# ── 2. Compute duration ────────────────────────────────────────────────────────
ENDED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
DURATION_MINS=$(python3 -c "
from datetime import datetime
try:
    start = datetime.fromisoformat('$STARTED_AT'.replace('Z','+00:00'))
    end   = datetime.fromisoformat('$ENDED_AT'.replace('Z','+00:00'))
    print(int((end - start).total_seconds() / 60))
except:
    print(0)
" 2>/dev/null)

# ── 3. Git delta ───────────────────────────────────────────────────────────────
CHANGED_FILES=""
COMMITS=""
if [ -n "$GIT_SHA_START" ] && [ -d "$WORKING_DIR/.git" ]; then
    CHANGED_FILES=$(cd "$WORKING_DIR" && git diff --name-only "${GIT_SHA_START}..HEAD" 2>/dev/null | head -20 || echo "")
    COMMITS=$(cd "$WORKING_DIR" && git log --oneline "${GIT_SHA_START}..HEAD" 2>/dev/null | head -10 || echo "")
fi

FILES_COUNT=$(echo "$CHANGED_FILES" | grep -c . 2>/dev/null || echo "0")
COMMITS_COUNT=$(echo "$COMMITS" | grep -c . 2>/dev/null || echo "0")

# ── 4. Decisions from /remember ───────────────────────────────────────────────
DECISIONS_MD=""
if [ -f "$DECISIONS_FILE" ]; then
    DECISIONS_MD=$(python3 -c "
import json, sys
lines = []
try:
    for line in open('$DECISIONS_FILE'):
        line = line.strip()
        if not line: continue
        try:
            d = json.loads(line)
            lines.append('- **{}**: {}'.format(d.get('type','note'), d.get('text','')))
        except:
            pass
except: pass
print('\n'.join(lines))
" 2>/dev/null)
fi

# ── 5. LLM summary (optional — falls back gracefully) ─────────────────────────
SUMMARY="Summary unavailable (gateway unreachable or no activity recorded)."

# Build a compact context string for the LLM
CONTEXT="Repo: ${REPO_NAME} | Branch: ${GIT_BRANCH} | Duration: ${DURATION_MINS} min | Files changed: ${FILES_COUNT} | Commits: ${COMMITS_COUNT}"
if [ -n "$COMMITS" ]; then
    CONTEXT="${CONTEXT}\nCommits:\n${COMMITS}"
fi

LLM_RESPONSE=$(python3 -c "
import urllib.request, json, sys

url = '$GATEWAY_URL/v1/chat/completions'
messages = [
    {'role': 'system', 'content': 'You write concise 2-3 sentence summaries of coding sessions. Be specific about what was accomplished. No filler words.'},
    {'role': 'user',   'content': 'Summarise this OpenClaude session:\n$CONTEXT'}
]
payload = json.dumps({
    'model': 'CLAUDE_4_6_SONNET',
    'messages': messages,
    'max_tokens': 150
}).encode()

req = urllib.request.Request(url, data=payload,
    headers={'Content-Type': 'application/json', 'Authorization': 'Bearer 1'},
    method='POST')
try:
    with urllib.request.urlopen(req, timeout=8) as r:
        data = json.loads(r.read())
        print(data['choices'][0]['message']['content'].strip())
except Exception as e:
    print('')
" 2>/dev/null)

if [ -n "$LLM_RESPONSE" ]; then
    SUMMARY="$LLM_RESPONSE"
fi

# ── 6. Format note body ────────────────────────────────────────────────────────
LOCAL_DATE=$(date +"%Y-%m-%d")
LOCAL_TIME=$(date +"%H:%M")
NOTE_TITLE="${LOCAL_DATE} ${LOCAL_TIME} — ${REPO_NAME}"

NOTE_BODY=$(python3 -c "
import sys

repo        = sys.argv[1]
branch      = sys.argv[2]
started     = sys.argv[3]
ended       = sys.argv[4]
duration    = sys.argv[5]
working_dir = sys.argv[6]
summary     = sys.argv[7]
files_raw   = sys.argv[8]
commits_raw = sys.argv[9]
decisions   = sys.argv[10]

# Format changed files
files_lines = [f.strip() for f in files_raw.strip().split('\n') if f.strip()]
if files_lines:
    files_md = '\n'.join(f'- \`{f}\`' for f in files_lines[:15])
    if len(files_lines) > 15:
        files_md += f'\n- *... and {len(files_lines)-15} more*'
else:
    files_md = '*No files changed*'

# Format commits
commit_lines = [c.strip() for c in commits_raw.strip().split('\n') if c.strip()]
if commit_lines:
    commits_md = '\n'.join(f'- \`{c}\`' for c in commit_lines)
else:
    commits_md = '*No commits*'

# Build note
parts = [
    f'# {repo} — {started[:10]}',
    '',
    f'**Started:** {started}  ',
    f'**Ended:** {ended}  ',
    f'**Duration:** {duration} minutes  ',
    f'**Repo:** \`{working_dir}\`  ',
    f'**Branch:** \`{branch}\`  ',
    '',
    '## Summary',
    summary,
    '',
    '## Files changed',
    files_md,
    '',
    '## Commits',
    commits_md,
]

if decisions.strip():
    parts += ['', '## Key decisions', decisions]

parts += [
    '',
    '---',
    f'*Auto-generated by OpenClaude session hook · {repo}*',
]

print('\n'.join(parts))
" \
    "$REPO_NAME" \
    "$GIT_BRANCH" \
    "$STARTED_AT" \
    "$ENDED_AT" \
    "$DURATION_MINS" \
    "$WORKING_DIR" \
    "$SUMMARY" \
    "$CHANGED_FILES" \
    "$COMMITS" \
    "$DECISIONS_MD" \
2>/dev/null)

# ── 7. Post to Joplin (or save to pending if Joplin is closed) ────────────────
JOPLIN_ALIVE=$(curl -sf "http://localhost:${JOPLIN_PORT}/ping?token=${JOPLIN_TOKEN}" 2>/dev/null && echo "yes" || echo "no")

post_to_joplin() {
    local title="$1"
    local body="$2"

    # Find or create "OpenClaude Sessions" notebook
    NB_ID=$(curl -sf "http://localhost:${JOPLIN_PORT}/folders?token=${JOPLIN_TOKEN}" 2>/dev/null | \
        python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    for item in data.get('items', []):
        if item.get('title') == 'OpenClaude Sessions':
            print(item['id']); break
except: pass
" 2>/dev/null)

    if [ -z "$NB_ID" ]; then
        NB_ID=$(curl -sf -X POST "http://localhost:${JOPLIN_PORT}/folders?token=${JOPLIN_TOKEN}" \
            -H "Content-Type: application/json" \
            -d "{\"title\": \"OpenClaude Sessions\"}" 2>/dev/null | \
            python3 -c "import json,sys; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
    fi

    NOTE_JSON=$(python3 -c "
import json, sys
d = {'title': sys.argv[1], 'body': sys.argv[2]}
if sys.argv[3]: d['parent_id'] = sys.argv[3]
print(json.dumps(d))
" "$title" "$body" "$NB_ID" 2>/dev/null)

    curl -sf -X POST "http://localhost:${JOPLIN_PORT}/notes?token=${JOPLIN_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "$NOTE_JSON" > /dev/null 2>&1
}

if [ "$JOPLIN_ALIVE" = "yes" ]; then
    post_to_joplin "$NOTE_TITLE" "$NOTE_BODY"
else
    # Save to pending — will be uploaded next time Joplin is available
    mkdir -p "$PENDING_DIR"
    PENDING_FILE="${PENDING_DIR}/${LOCAL_DATE}-${LOCAL_TIME//:/}-session.md"
    python3 -c "
import json, sys
d = {'title': sys.argv[1], 'body': sys.argv[2]}
with open(sys.argv[3], 'w') as f:
    json.dump(d, f, indent=2)
" "$NOTE_TITLE" "$NOTE_BODY" "$PENDING_FILE" 2>/dev/null
fi

# ── 8. Upload any pending sessions (from previous offline sessions) ────────────
if [ "$JOPLIN_ALIVE" = "yes" ] && [ -d "$PENDING_DIR" ]; then
    for pending in "$PENDING_DIR"/*.md 2>/dev/null; do
        [ -f "$pending" ] || continue
        PTITLE=$(python3 -c "import json; d=json.load(open('$pending')); print(d['title'])" 2>/dev/null)
        PBODY=$(python3 -c  "import json; d=json.load(open('$pending')); print(d['body'])"  2>/dev/null)
        if [ -n "$PTITLE" ] && [ -n "$PBODY" ]; then
            post_to_joplin "$PTITLE" "$PBODY" && rm -f "$pending"
        fi
    done
fi

# ── 9. Legacy monthly "Memories" marker (backward compat) ─────────────────────
MONTH=$(date +%Y-%m)
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M)
NOTE_TITLE_LEGACY="Memories — ${MONTH}"
MARKER="## ${DATE} — session ended ${TIME} (${REPO_NAME}, ${DURATION_MINS}m)"

if [ "$JOPLIN_ALIVE" = "yes" ]; then
    ENCODED_TITLE=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$NOTE_TITLE_LEGACY")
    MEM_ID=$(curl -sf "http://localhost:${JOPLIN_PORT}/search?token=${JOPLIN_TOKEN}&query=${ENCODED_TITLE}&fields=id,title" 2>/dev/null | \
        python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data.get('items', []):
    if item.get('title') == '$NOTE_TITLE_LEGACY':
        print(item['id']); break
" 2>/dev/null)

    if [ -n "$MEM_ID" ]; then
        EXISTING=$(curl -sf "http://localhost:${JOPLIN_PORT}/notes/${MEM_ID}?token=${JOPLIN_TOKEN}&fields=body" 2>/dev/null | \
            python3 -c "import sys,json; print(json.load(sys.stdin).get('body',''))" 2>/dev/null)
        NEW_BODY=$(printf "%s\n\n%s" "$EXISTING" "$MARKER")
        JSON_BODY=$(python3 -c "import json,sys; print(json.dumps({'body': sys.argv[1]}))" "$NEW_BODY")
        curl -sf -X PUT "http://localhost:${JOPLIN_PORT}/notes/${MEM_ID}?token=${JOPLIN_TOKEN}" \
            -H "Content-Type: application/json" -d "$JSON_BODY" > /dev/null 2>&1
    fi
fi

# ── 10. Cleanup ────────────────────────────────────────────────────────────────
rm -f "$STATE_FILE"
rm -f "$DECISIONS_FILE"

exit 0
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x ~/.openclaude/hooks/session-to-joplin.sh
```

- [ ] **Step 3: Smoke-test the note formatter in isolation (no Joplin needed)**

```bash
# Simulate a session-state.json
cat > ~/.openclaude/session-state.json << 'EOF'
{
  "session_pid": 99999,
  "started_at": "2026-04-25T10:00:00Z",
  "working_dir": "/Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn",
  "repo_name": "2brn",
  "git_branch": "feature/session-tracking",
  "git_sha_start": "cf83b2a"
}
EOF

# Simulate a decisions file
cat > ~/.openclaude/session-decisions.jsonl << 'EOF'
{"ts": "2026-04-25T10:30:00Z", "type": "decision", "text": "Use PreToolUse hook for session start detection"}
{"ts": "2026-04-25T10:45:00Z", "type": "learning", "text": "PPID in bash hook = the openclaude process PID"}
EOF

# Run the hook (Joplin may or may not be open — both paths are safe)
bash ~/.openclaude/hooks/session-to-joplin.sh
echo "Exit code: $?"
```

Expected: exit code 0. If Joplin is open, a note appears in "OpenClaude Sessions". If not, a `.md` file appears in `~/.openclaude/pending-sessions/`.

- [ ] **Step 4: Verify output**

```bash
# If Joplin was closed, check pending:
ls -la ~/.openclaude/pending-sessions/ 2>/dev/null && \
  python3 -c "
import json
import glob
files = glob.glob('$HOME/.openclaude/pending-sessions/*.md')
for f in files:
    d = json.load(open(f))
    print('Title:', d['title'])
    print('Body preview:', d['body'][:300])
    print('---')
"
```

Expected: a pending session file with correct title format `YYYY-MM-DD HH:MM — 2brn` and body containing Summary, Files changed, Commits, Key decisions sections.

- [ ] **Step 5: Verify cleanup**

```bash
# session-state.json and session-decisions.jsonl should be gone after hook runs
[ ! -f ~/.openclaude/session-state.json ] && echo "state file cleaned up OK" || echo "FAIL: state file still exists"
[ ! -f ~/.openclaude/session-decisions.jsonl ] && echo "decisions file cleaned up OK" || echo "FAIL: decisions file still exists"
```

Expected: both print `...cleaned up OK`

---

## Task 3: Wire hooks into settings.json

**Files:**
- Modify: `~/.openclaude/settings.json`

Wire `session-start.sh` as a global `PreToolUse` hook and `session-to-joplin.sh` as the `Stop` hook, replacing the current `printf '\a'`.

- [ ] **Step 1: Write the updated settings.json**

```bash
python3 - << 'EOF'
import json

settings_path = os.path.expanduser('~/.openclaude/settings.json')

with open(settings_path) as f:
    s = json.load(f)

# Replace Stop hook (was just printf '\a')
s['hooks']['Stop'] = [
    {
        "hooks": [
            {
                "type": "command",
                "command": "/bin/bash ~/.openclaude/hooks/session-to-joplin.sh",
                "async": True
            }
        ]
    }
]

# Add PreToolUse hook (new)
s['hooks']['PreToolUse'] = [
    {
        "hooks": [
            {
                "type": "command",
                "command": "/bin/bash ~/.openclaude/hooks/session-start.sh",
                "async": True
            }
        ]
    }
]

with open(settings_path, 'w') as f:
    json.dump(s, f, indent=2)

print("settings.json updated OK")
EOF
```

Wait — `os` needs to be imported. Use this corrected version:

```bash
python3 -c "
import json, os

settings_path = os.path.expanduser('~/.openclaude/settings.json')

with open(settings_path) as f:
    s = json.load(f)

s['hooks']['Stop'] = [{'hooks': [{'type': 'command', 'command': '/bin/bash ~/.openclaude/hooks/session-to-joplin.sh', 'async': True}]}]
s['hooks']['PreToolUse'] = [{'hooks': [{'type': 'command', 'command': '/bin/bash ~/.openclaude/hooks/session-start.sh', 'async': True}]}]

with open(settings_path, 'w') as f:
    json.dump(s, f, indent=2)

print('settings.json updated OK')
"
```

- [ ] **Step 2: Verify the hooks section looks correct**

```bash
python3 -c "
import json, os
s = json.load(open(os.path.expanduser('~/.openclaude/settings.json')))
print(json.dumps(s['hooks'], indent=2))
"
```

Expected output:
```json
{
  "Stop": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "/bin/bash ~/.openclaude/hooks/session-to-joplin.sh",
          "async": true
        }
      ]
    }
  ],
  "PreToolUse": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "/bin/bash ~/.openclaude/hooks/session-start.sh",
          "async": true
        }
      ]
    }
  ]
}
```

- [ ] **Step 3: Commit the hooks into the repo as reference copies**

Even though the actual hooks run from `~/.openclaude/hooks/`, keeping copies in the repo means they're version-controlled and can be re-installed on a new machine.

```bash
mkdir -p /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/.claude/hooks
cp ~/.openclaude/hooks/session-start.sh \
   /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/.claude/hooks/session-start.sh
cp ~/.openclaude/hooks/session-to-joplin.sh \
   /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/.claude/hooks/session-to-joplin.sh
```

- [ ] **Step 4: Update .gitignore — hooks contain the Joplin token, must NOT be committed as-is**

Actually — the token is embedded in the script. We should commit the script with a placeholder token and document how to configure it. Let's scrub the token before committing:

```bash
# Replace the real token with a placeholder in the committed copies
sed -i '' 's/JOPLIN_TOKEN="[^"]*"/JOPLIN_TOKEN="YOUR_JOPLIN_TOKEN_HERE"/' \
    /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/.claude/hooks/session-to-joplin.sh

sed -i '' 's/JOPLIN_TOKEN="[^"]*"/JOPLIN_TOKEN="YOUR_JOPLIN_TOKEN_HERE"/' \
    /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/.claude/hooks/save-memory.sh
```

- [ ] **Step 5: Commit hook reference copies to repo**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add .claude/hooks/session-start.sh .claude/hooks/session-to-joplin.sh .claude/hooks/save-memory.sh
git commit -m "feat(session-tracking): add session-start + session-to-joplin hook reference copies"
```

---

## Task 4: Update /remember skill to accumulate decisions

**Files:**
- Modify: `.claude/skills/remember.md` (in 2brn repo — but this skill is used globally)

Add a step to the `/remember` skill so that when the user calls `/remember decision: X` or `/remember learning: X`, the entry is also appended to `~/.openclaude/session-decisions.jsonl`. This file is consumed by `session-to-joplin.sh` at session end to populate the "Key decisions" section of the session note.

- [ ] **Step 1: Read the current skill**

```bash
cat /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/.claude/skills/remember.md
```

- [ ] **Step 2: Rewrite `.claude/skills/remember.md`**

```markdown
# /remember

When the user says `/remember [something]` or `remember: [something]`, save it to Joplin AND to the session accumulator.

## Steps

1. **Classify** the input into one of:
   - `decision` — a choice made, with rationale
   - `learning` — a technical fact, tool discovery, or pattern observed
   - `project` — a project update, status change, or next action
   - `person` — a note about a person

2. **Determine target Joplin note** based on classification:
   - `decision` → search for note titled "Decisions — YYYY-MM" (current month) in Second Brain notebook
   - `learning` → search for note titled "Learnings" in Second Brain notebook
   - `project` → search for the specific project note (e.g. "2brn — Second Brain") or "Projects Index"
   - `person` → search for a note about the person (e.g. "Sasidharan Govindan") in People notebook

3. **Format the entry**:
   ```
   - **YYYY-MM-DD**: [The thing to remember]
   ```
   Use today's date from the system.

4. **Use the Joplin MCP tools** to save:
   - First try `search_notes` to find the target note
   - If found: use `append_to_note` with the note's ID and the formatted entry
   - If not found: use `create_note` with title, body (just the entry), and appropriate notebook

5. **Also append to the session accumulator** (so it appears in today's session note):

   Use the Bash tool to run:
   ```bash
   python3 -c "
   import json, datetime, os
   entry = {
       'ts':   datetime.datetime.utcnow().isoformat() + 'Z',
       'type': 'TYPE_PLACEHOLDER',
       'text': 'TEXT_PLACEHOLDER'
   }
   path = os.path.expanduser('~/.openclaude/session-decisions.jsonl')
   with open(path, 'a') as f:
       f.write(json.dumps(entry) + '\n')
   "
   ```
   Replace `TYPE_PLACEHOLDER` with the classification from step 1 (`decision`, `learning`, etc.)
   Replace `TEXT_PLACEHOLDER` with the text being remembered (escape any single quotes as `'\''`).

   Only run this step for `decision` and `learning` types — `project` and `person` entries are
   not surfaced in session notes.

6. **Confirm** with: `Saved to Joplin: \`<note title>\` ✓`

## MCP tools available
- `joplin__search_notes(query)` — find existing notes by keyword
- `joplin__get_note(id_or_title)` — read a note
- `joplin__append_to_note(id_or_title, content)` — append to existing note *(requires Joplin open)*
- `joplin__create_note(title, body, notebook)` — create new note *(requires Joplin open)*
```

- [ ] **Step 3: Write the updated skill file**

```bash
cat > /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/.claude/skills/remember.md << 'SKILL_EOF'
# /remember

When the user says `/remember [something]` or `remember: [something]`, save it to Joplin AND to the session accumulator.

## Steps

1. **Classify** the input into one of:
   - `decision` — a choice made, with rationale
   - `learning` — a technical fact, tool discovery, or pattern observed
   - `project` — a project update, status change, or next action
   - `person` — a note about a person

2. **Determine target Joplin note** based on classification:
   - `decision` → search for note titled "Decisions — YYYY-MM" (current month) in Second Brain notebook
   - `learning` → search for note titled "Learnings" in Second Brain notebook
   - `project` → search for the specific project note (e.g. "2brn — Second Brain") or "Projects Index"
   - `person` → search for a note about the person (e.g. "Sasidharan Govindan") in People notebook

3. **Format the entry**:
   ```
   - **YYYY-MM-DD**: [The thing to remember]
   ```
   Use today's date from the system.

4. **Use the Joplin MCP tools** to save:
   - First try `search_notes` to find the target note
   - If found: use `append_to_note` with the note's ID and the formatted entry
   - If not found: use `create_note` with title, body (just the entry), and appropriate notebook

5. **Also append to the session accumulator** for `decision` and `learning` types only:

   Use the Bash tool to run (substitute actual type and text):
   ```bash
   python3 -c "
   import json, datetime, os
   entry = {'ts': datetime.datetime.utcnow().isoformat()+'Z', 'type': 'TYPE', 'text': 'TEXT'}
   with open(os.path.expanduser('~/.openclaude/session-decisions.jsonl'), 'a') as f:
       f.write(json.dumps(entry) + '\n')
   "
   ```

6. **Confirm** with: `Saved to Joplin: \`<note title>\` ✓`

## MCP tools available
- `joplin__search_notes(query)` — find existing notes by keyword
- `joplin__get_note(id_or_title)` — read a note
- `joplin__append_to_note(id_or_title, content)` — append to existing note *(requires Joplin open)*
- `joplin__create_note(title, body, notebook)` — create new note *(requires Joplin open)*
SKILL_EOF
```

- [ ] **Step 4: Test the accumulator write manually**

```bash
python3 -c "
import json, datetime, os
entry = {'ts': datetime.datetime.utcnow().isoformat()+'Z', 'type': 'decision', 'text': 'Test decision from plan verification'}
with open(os.path.expanduser('~/.openclaude/session-decisions.jsonl'), 'a') as f:
    f.write(json.dumps(entry) + '\n')
"
cat ~/.openclaude/session-decisions.jsonl
```

Expected: a single JSONL line with the test decision.

Clean up:
```bash
rm -f ~/.openclaude/session-decisions.jsonl
```

- [ ] **Step 5: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add .claude/skills/remember.md
git commit -m "feat(session-tracking): update /remember to also write to session-decisions.jsonl"
```

---

## Task 5: End-to-end integration test

Verify the whole pipeline works together in a real session.

- [ ] **Step 1: Confirm settings.json hooks are wired**

```bash
python3 -c "
import json, os
s = json.load(open(os.path.expanduser('~/.openclaude/settings.json')))
assert 'PreToolUse' in s['hooks'], 'PreToolUse hook missing'
assert 'Stop' in s['hooks'], 'Stop hook missing'
stop_cmd = s['hooks']['Stop'][0]['hooks'][0]['command']
assert 'session-to-joplin' in stop_cmd, f'Stop hook not pointing to session-to-joplin: {stop_cmd}'
pre_cmd = s['hooks']['PreToolUse'][0]['hooks'][0]['command']
assert 'session-start' in pre_cmd, f'PreToolUse hook not pointing to session-start: {pre_cmd}'
print('hooks wired correctly')
"
```

Expected: `hooks wired correctly`

- [ ] **Step 2: Simulate a complete session flow**

```bash
# Simulate session start (as if PreToolUse fired)
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
bash ~/.openclaude/hooks/session-start.sh
echo "State file contents:"
cat ~/.openclaude/session-state.json

# Simulate a /remember decision during the session
python3 -c "
import json, datetime, os
entry = {'ts': datetime.datetime.utcnow().isoformat()+'Z', 'type': 'decision', 'text': 'PreToolUse hook writes session-state.json on first tool use'}
with open(os.path.expanduser('~/.openclaude/session-decisions.jsonl'), 'a') as f:
    f.write(json.dumps(entry) + '\n')
"

# Simulate session end (as if Stop fired)
bash ~/.openclaude/hooks/session-to-joplin.sh
echo "Stop hook exit code: $?"
```

- [ ] **Step 3: Verify Joplin note was created (if Joplin is open)**

Open Joplin. Navigate to **OpenClaude Sessions** notebook.
Expected: a note titled `YYYY-MM-DD HH:MM — 2brn` containing:
- Summary (from LLM or fallback)
- Files changed section
- Commits section
- Key decisions section with the test decision

- [ ] **Step 4: Verify pending fallback (if Joplin is closed)**

```bash
ls ~/.openclaude/pending-sessions/ 2>/dev/null || echo "no pending sessions"
```

If Joplin was closed during step 2, there should be a `.md` file in `pending-sessions/`.
Its contents should be valid JSON with `title` and `body` keys.

- [ ] **Step 5: Verify cleanup**

```bash
[ ! -f ~/.openclaude/session-state.json ]      && echo "session-state.json: cleaned ✓" || echo "FAIL"
[ ! -f ~/.openclaude/session-decisions.jsonl ] && echo "session-decisions.jsonl: cleaned ✓" || echo "FAIL"
```

- [ ] **Step 6: Final commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add -A
git status  # should be clean — all hook copies already committed
git log --oneline -4
```

---

## Task 6: Fix the chat.py metadata bug (discovered during design research)

**Files:**
- Modify: `daemon/src/brn_daemon/chat.py` line ~23

When 2brn's RAG retrieves Joplin note chunks and formats the prompt context, it reads `metadata.get('file','?')` but Joplin note chunks have metadata keys `source`, `note_id`, `title`, `notebook`, `chunk` — there is no `file` key. This means the source attribution for note results shows `?` instead of the note title, degrading the quality of answers. Since session notes will soon be in Joplin, fixing this now ensures the session notes are cited correctly in chat answers.

- [ ] **Step 1: Read the current build_rag_prompt**

```bash
grep -n "file\|app_name\|metadata" \
  /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/daemon/src/brn_daemon/chat.py \
  | head -20
```

- [ ] **Step 2: Write the fix**

Replace the `build_rag_prompt` function's context line:

Current (buggy):
```python
f"App/File: {c['metadata'].get('app_name', c['metadata'].get('file','?'))}\n{c['text']}"
```

Fixed — uses `title` + `notebook` for Joplin notes, `app_name` for activity memories:
```python
def build_rag_prompt(question: str, context_chunks: list[dict]) -> str:
    if not context_chunks:
        return (
            f"Context: No recorded activities or notes found for this query.\n\n"
            f"User question: {question}\n\n"
            f"Answer honestly that there is no recorded context for this query."
        )
    context_text = "\n\n".join(
        f"[{i+1}] Source: {c['metadata'].get('source','activity')} | "
        f"Date: {c['metadata'].get('date','?')} | "
        f"App/Note: {c['metadata'].get('app_name') or c['metadata'].get('title','?')}"
        f"{' (' + c['metadata']['notebook'] + ')' if c['metadata'].get('notebook') else ''}"
        f"\n{c['text']}"
        for i, c in enumerate(context_chunks)
    )
    return f"Context from your activity history and notes:\n\n{context_text}\n\nUser question: {question}"
```

- [ ] **Step 3: Apply the edit**

Edit `/Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/daemon/src/brn_daemon/chat.py` — replace the `build_rag_prompt` function body (lines ~13–27) with the fixed version above.

- [ ] **Step 4: Run the chat tests**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/daemon
uv run --extra dev pytest tests/test_chat.py -v 2>&1
```

Expected: all chat tests pass

- [ ] **Step 5: Run full test suite**

```bash
uv run --extra dev pytest tests/ -v 2>&1 | tail -10
```

Expected: 50 passed, 1 warning

- [ ] **Step 6: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add daemon/src/brn_daemon/chat.py
git commit -m "fix(chat): use title/notebook for Joplin note attribution in RAG prompt"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Session start state recorded — Task 1 (session-start.sh)
- ✅ Stop hook captures session — Task 2 (session-to-joplin.sh)
- ✅ Git delta (changed files + commits) — Task 2 §3
- ✅ LLM summary with graceful fallback — Task 2 §5
- ✅ Markdown note formatted with all sections — Task 2 §6
- ✅ Posts to "OpenClaude Sessions" Joplin notebook — Task 2 §7
- ✅ Notebook created if it doesn't exist — Task 2 `post_to_joplin()`
- ✅ Offline fallback to pending-sessions/ — Task 2 §7 else branch
- ✅ Pending sessions uploaded on next session start — Task 2 §8
- ✅ Legacy monthly "Memories" marker preserved — Task 2 §9
- ✅ Cleanup of state + decisions files — Task 2 §10
- ✅ Hooks wired in settings.json — Task 3
- ✅ Hook reference copies in repo (token scrubbed) — Task 3 §3–4
- ✅ /remember writes to session-decisions.jsonl — Task 4
- ✅ End-to-end integration test — Task 5
- ✅ chat.py metadata bug fixed — Task 6
- ✅ JoplinWatcher picks up session notes automatically — no code needed (existing behaviour)

**Placeholder scan:** None found. All steps have complete code.

**Type consistency:**
- `session-state.json` keys: `session_pid`, `started_at`, `working_dir`, `repo_name`, `git_branch`, `git_sha_start` — written in Task 1, read in Task 2 ✅
- `session-decisions.jsonl` line format: `{"ts": "...", "type": "...", "text": "..."}` — written in Task 4, read in Task 2 §4 ✅
- Pending session file format: `{"title": "...", "body": "..."}` — written in Task 2, read in Task 2 §8 ✅
