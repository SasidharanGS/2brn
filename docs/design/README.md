# 2brn × OpenClaude Integration — Master Overview

**Version:** 1.0  
**Date:** 2026-04-25  
**Status:** Approved design, pending implementation  
**Owner:** Sasidharan Govindan

---

## What we are building

Three interconnected systems that together make OpenClaude a context-aware assistant with persistent memory of everything you do:

| System | Design Doc | One-liner |
|--------|-----------|-----------|
| **Session Tracking** | `session-tracking.md` | Every OpenClaude session → structured Joplin note automatically |
| **2brn MCP Server** | `2brn-mcp-server.md` | 2brn exposes 7 tools so OpenClaude can query your activity, journals, and notes |
| **Persistent Memory** | `persistent-memory.md` | 2brn distils everything into evolving knowledge that improves OpenClaude over time |

These are not independent features. Each one enables the next:

```
Session Tracking  →  feeds data into  →  2brn MCP Server  →  which powers  →  Persistent Memory
```

Without session tracking, the MCP server has no session-level knowledge.  
Without the MCP server, persistent memory has no retrieval path into OpenClaude.  
Without persistent memory distillation, the system accumulates noise but never gets smarter.

---

## The overall architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OpenClaude (every session)                           │
│                                                                               │
│  CLAUDE.md (pre-loaded context) ──► Session startup: call get_current_context│
│  2brn MCP tools (7 tools) ────────► query activity, journals, notes on demand │
│  Joplin MCP tools (6 tools) ──────► read/write notes directly                │
│  Stop hook ────────────────────────► writes session note to Joplin at end     │
│  PreToolUse hook ──────────────────► writes session-state.json at start       │
└────────────────────┬────────────────────────────────────────────────────────┘
                     │ HTTP calls
┌────────────────────▼────────────────────────────────────────────────────────┐
│                    2brn MCP Server  ~/tools/2brn-mcp-server/                 │
│   get_current_context  search_activity  get_timeline  get_productivity        │
│   get_journal  search_notes  get_recent_decisions                             │
└────────────────────┬────────────────────────────────────────────────────────┘
                     │ proxies to
┌────────────────────▼────────────────────────────────────────────────────────┐
│                    2brn Daemon  (port 7842)                                   │
│                                                                               │
│  SQLite ──────── captures, activities, journals                               │
│  ChromaDB ─────  activity_memories  (screen activity)                        │
│               ─  note_memories      (all Joplin notes)                       │
│  Scheduler ───── journal @14:00/@20:30, distillation @23:00, weekly digest   │
└─────────────┬───────────────────────────────────────────────────────────────┘
              │ reads/writes
┌─────────────▼───────────────────────────────────────────────────────────────┐
│                       Joplin  (local SQLite)                                  │
│                                                                               │
│  Daily Journals ──────── written by JournalMirror (2brn)                     │
│  Session Notes ───────── written by session-to-joplin.sh (Stop hook)         │
│  /remember entries ───── written by skill mid-session                        │
│  Decisions YYYY-MM ────── written by /remember + nightly distillation        │
│  Learnings / Patterns ─── written by nightly distillation                    │
│  Project Status notes ─── written by weekly digest                           │
│  Working patterns note ─── written by distillation, reviewed by user         │
│  Project knowledge notes ─ written by weekly digest                          │
└─────────────┬───────────────────────────────────────────────────────────────┘
              │ polled every 60s by JoplinWatcher
              ▼
       ChromaDB note_memories  ────► all Joplin notes searchable via
                                     2brn chat UI + 2brn MCP search tools
```

---

## What already exists (no work needed)

| Component | Status |
|-----------|--------|
| 2brn daemon (SQLite + ChromaDB + FastAPI) | ✅ Built |
| Screen capture + inference pipeline | ✅ Built |
| JoplinWatcher (60s poll → embed notes) | ✅ Built |
| Daily journals to Joplin (JournalMirror) | ✅ Built |
| Joplin MCP server (6 tools) | ✅ Built |
| `/remember` skill | ✅ Built |
| Monthly "Memories" markers | ✅ Built (but Stop hook not wired — see gap below) |
| 2brn chat UI with RAG (activity + notes) | ✅ Built |
| TanStack Query / Obsidian Glass UI | ✅ Built (this session) |

---

## Known gaps to fix before building new features

These are pre-existing issues discovered during design research:

| Gap | File | Fix |
|----|------|-----|
| **Stop hook not wired** — `save-memory.sh` exists but `settings.json` only runs `printf '\a'` | `~/.openclaude/settings.json` | Wire `session-to-joplin.sh` in Phase 1 |
| **`chat.py` metadata mismatch** — RAG prompt tries `metadata.get('file','?')` but Joplin chunks use `title`/`notebook` keys | `daemon/src/brn_daemon/chat.py` | Fix key names in `build_rag_prompt` |
| **`zod` unused** in Joplin MCP server | `~/tools/joplin-mcp-server/package.json` | Minor — remove in cleanup pass |

---

## Recommended build order

Each phase is independently valuable. Stopping after any phase still leaves you better off than before.

---

### Phase 1 — Session Tracking MVP (~4 hours)
**Unlocks:** "What was I working on last Tuesday?" becomes answerable

- [ ] Fix `settings.json` Stop hook — wire in the new `session-to-joplin.sh`
- [ ] Write `~/.openclaude/hooks/session-to-joplin.sh`:
  - Reads `session-state.json` (start time, repo, branch, starting git SHA)
  - Runs `git diff --name-only <start_sha>..HEAD` for changed files
  - Runs `git log --oneline <start_sha>..HEAD` for commits
  - Calls JLL Gateway for 2–3 sentence summary (falls back gracefully if unavailable)
  - Formats Markdown note body (see `session-tracking.md §4`)
  - Posts to Joplin "OpenClaude Sessions" notebook via Web Clipper
  - Also writes the monthly "Memories" marker (backward compat)
- [ ] Add `PreToolUse` hook to `settings.json` — writes `~/.openclaude/session-state.json` on first tool use
- [ ] Fix `chat.py` metadata bug (`file` → `title`/`notebook` for Joplin chunks)
- [ ] Verify: run a session, confirm note appears in Joplin with correct content
- [ ] Verify: JoplinWatcher picks up the note on next 60s poll → searchable in 2brn chat

**Design doc:** `docs/design/session-tracking.md`

---

### Phase 2 — 2brn MCP Server core (~1 day)
**Unlocks:** OpenClaude automatically knows what you've been working on at session start

- [ ] Scaffold `~/tools/2brn-mcp-server/` (TypeScript, MCP SDK, same pattern as joplin-mcp-server)
- [ ] Implement `get_current_context` tool (most important — called at every session start)
- [ ] Implement `get_timeline` tool
- [ ] Implement `get_productivity_snapshot` tool
- [ ] Implement `get_journal` tool
- [ ] Register in `~/.openclaude/settings.json` globally (not just 2brn repo)
- [ ] Add session startup protocol to `~/.openclaude/CLAUDE.md`
- [ ] Test: start a session, verify OpenClaude references recent work without being told

**Design doc:** `docs/design/2brn-mcp-server.md`

---

### Phase 3 — Semantic search tools (~half day)
**Unlocks:** "What do I know about X?" works across all notes + activity history

- [ ] Add `/notes/search` endpoint to 2brn daemon (`daemon/src/brn_daemon/routes/notes_routes.py`)
- [ ] Register new router in `daemon/src/brn_daemon/main.py`
- [ ] Implement `search_activity` MCP tool
- [ ] Implement `search_notes` MCP tool (semantic, not keyword — this is different from Joplin MCP)
- [ ] Test: "what was I building last week?" returns accurate results via MCP

**Design doc:** `docs/design/2brn-mcp-server.md §3.2`

---

### Phase 4 — Decisions layer (~half day)
**Unlocks:** "What did I decide about X?" — no more re-debating settled questions

- [ ] Modify `/remember` skill to also append to `~/.openclaude/session-decisions.jsonl`
- [ ] Session-to-joplin.sh reads `session-decisions.jsonl` → folds into session note "Key decisions" section → clears file
- [ ] Implement `get_recent_decisions` MCP tool (searches Decisions notes + session notes)
- [ ] Test: make a decision mid-session via `/remember`, verify it appears in session note and is queryable

**Design doc:** `docs/design/session-tracking.md §6`, `2brn-mcp-server.md §3.7`

---

### Phase 5 — Nightly distillation (~1 day)
**Unlocks:** Memory system gets smarter automatically without any manual effort

- [ ] Create `daemon/src/brn_daemon/distillation.py` — `DistillationJob` class
- [ ] Job logic: gather today's activities + session notes + /remember calls → JLL Gateway prompt → structured JSON → write to Joplin (Learnings, Decisions, Patterns notes)
- [ ] Add `distillation_daily@23:00` to APScheduler in `daemon/src/brn_daemon/main.py`
- [ ] Verify JoplinWatcher picks up distillation output → embedded in ChromaDB
- [ ] Test: after running, check "Learnings — YYYY-MM" note updated with today's new knowledge

**Design doc:** `docs/design/persistent-memory.md §4.1`

---

### Phase 6 — Weekly project digest (~half day)
**Unlocks:** "What's the current status of X?" always returns an accurate, up-to-date answer

- [ ] Add `weekly_digest@Sunday 22:00` to APScheduler
- [ ] Logic: group week's session notes by repo → per-project status paragraph → update "Project Status — {name}" Joplin notes
- [ ] Test: "what's the status of the SDA work?" → accurate answer from project status note

**Design doc:** `docs/design/persistent-memory.md §4.2`

---

### Phase 7 — CLAUDE.md evolution (~1 day)
**Unlocks:** Pre-loaded OpenClaude context improves automatically, reflecting how you actually work

- [ ] Distillation job produces CLAUDE.md diff proposals (structured JSON of additions/changes)
- [ ] New 2brn chat UI panel: "Suggested CLAUDE.md updates" — shows diffs, user approves/rejects
- [ ] On approval: write via 2brn daemon endpoint → `~/.openclaude/CLAUDE.md`
- [ ] Test: observe a pattern (e.g., you always use uv sync before running tests), verify it appears as a suggestion

**Design doc:** `docs/design/persistent-memory.md §4.3`

---

## Dependency map

```
Phase 1 (Session Tracking)
    └── enables → Phase 4 (Decisions layer — needs session-decisions.jsonl)
    └── enables → Phase 5 (Distillation — needs session notes to process)
    └── enables → Phase 6 (Weekly digest — needs session notes per project)

Phase 2 (MCP core tools)
    └── enables → Phase 3 (Semantic search tools — needs MCP server scaffold)
    └── enables → Phase 4 (Decisions tool — needs MCP server scaffold)
    └── enables → Phase 7 (CLAUDE.md evolution — needs MCP retrieval path)

Phase 5 (Distillation)
    └── enables → Phase 6 (Weekly digest — shares distillation infrastructure)
    └── enables → Phase 7 (CLAUDE.md evolution — uses distillation output)
```

Phases 1 and 2 are independent and can be built in parallel.  
Phases 3 and 4 require Phase 2.  
Phases 5, 6, 7 require Phase 1 (need session notes to distil).

---

## What success looks like

| After Phase | OpenClaude experience |
|-------------|----------------------|
| Phase 1 | You can ask 2brn chat "what was I doing Tuesday morning?" and get a session-level answer |
| Phase 2 | OpenClaude opens a session and references your recent work without you explaining it |
| Phase 3 | "What do I know about TanStack Query?" returns a synthesised answer from notes + history |
| Phase 4 | "What did we decide about the journal schema?" returns the exact decision + date |
| Phase 5 | Learnings and decisions accumulate automatically; memory improves without effort |
| Phase 6 | "What's the status of SDA?" is always accurate |
| Phase 7 | Every few weeks, CLAUDE.md gets smarter about who you are and how you work |

---

## Design documents

All three detailed design documents live in `docs/design/`:

- [`session-tracking.md`](session-tracking.md) — Full spec for Phase 1 + Phase 4
- [`2brn-mcp-server.md`](2brn-mcp-server.md) — Full spec for Phase 2 + Phase 3 + Phase 4 (decisions tool)
- [`persistent-memory.md`](persistent-memory.md) — Full spec for Phase 5 + Phase 6 + Phase 7 + overall vision

---

## Key constraints

- **No LLM intelligence in 2brn** — 2brn uses JLL GPT Gateway for its own inference (journals, activity summaries, distillation). OpenClaude is never used as 2brn's intelligence layer. This boundary is intentional and preserved in all phases.
- **Local-first** — All data stays on your machine / JLL infrastructure. Nothing goes to third-party clouds.
- **Graceful degradation** — Every integration point degrades cleanly if 2brn daemon is offline, Joplin is closed, or the gateway is unreachable. OpenClaude always starts; 2brn always captures.
- **Additive only** — Each phase adds capability without changing existing behaviour. Phase 1 does not break the daily journals. Phase 2 does not change how 2brn captures screens.
