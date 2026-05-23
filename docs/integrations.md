# 2brn Integration Reference

**Last updated:** 2026-04-19  
**Scope:** 2brn daemon ↔ Joplin ↔ openclaude (Super Productivity excluded — no integration built yet)

---

## Overview

2brn is a second brain system with two knowledge layers:

| Layer | What | Where |
|-------|------|-------|
| **Passive** | Screen captures → OCR → AI inference → structured activities | SQLite + ChromaDB (`activity_memories`) |
| **Deliberate** | Notes you write intentionally | **Joplin** (SQLite) + ChromaDB (`note_memories`) |

Both layers are unified in the **2brn chat UI** via RAG — a question like *"what did I decide about the AI gateway auth?"* searches screen activity AND your Joplin notes simultaneously.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  SCREEN (passive capture)                                     │
│  Screenshot every 60s → OCR → AI provider inference              │
│  → SQLite (activities) + ChromaDB (activity_memories)         │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  JOPLIN (deliberate notes)                                    │
│  ~/.config/joplin-desktop/database.sqlite                     │
│  18 notebooks, 131+ notes, 34+ tags                          │
└──────┬─────────────────────────────────┬─────────────────────┘
       │ read-only SQLite poll (60s)      │ Web Clipper API
       ▼                                  ▼ (when Joplin open)
┌─────────────────────┐    ┌─────────────────────────────────┐
│ joplin_watcher.py   │    │ openclaude MCP (joplin server)  │
│ Embeds notes into   │    │ search / read / write notes     │
│ ChromaDB            │    │ /remember skill                 │
│ note_memories       │    │ Stop hook → memory note         │
└──────┬──────────────┘    └─────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│  ChromaDB (~/.2brn/chroma/)                                  │
│  • activity_memories — screen capture embeddings             │
│  • note_memories     — Joplin note embeddings                │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  2brn CHAT UI (port 7842)                                    │
│  RAG: query → embed → search both collections → GPT stream  │
└──────────────────────────────────────────────────────────────┘
```

---

## Component Reference

### 1. `joplin_watcher.py` — Note Embedding

**File:** `daemon/src/brn_daemon/joplin_watcher.py`  
**Replaces:** `vault_watcher.py` (Dendron folder watcher, now unused)

**What it does:**
- On daemon startup: bulk-embeds all non-empty Joplin notes into `note_memories`
- Every 60 seconds: polls Joplin SQLite for notes updated since last poll, re-embeds changed ones

**Key design decisions:**
- **Read-only SQLite** — safe for concurrent access; never writes to Joplin DB directly
- **Polling not watching** — SQLite file-watching is unreliable; 60s poll is acceptable latency
- **Props block stripping** — strips Joplin serialization metadata (`id:`, `type_:`, etc.) from note bodies before embedding (left over from the Dendron → Joplin migration)
- **Title prepended** — each note's title is prepended to the body (`# Title\n\nbody`) so keyword searches hit the title even on non-title chunks
- **Stable doc IDs** — `joplin-{note_id}-{chunk_index}` — ChromaDB upsert is idempotent

**Joplin DB path:** `~/.config/joplin-desktop/database.sqlite`  
**ChromaDB collection:** `note_memories`  
**Chunk size:** 400 words, respecting heading boundaries

**Wired in:** `main.py` instantiates `JoplinWatcher(gateway=..., chroma_client=...)` in lifespan; bulk-embeds on startup, starts polling task.

---

### 2. Joplin MCP Server — openclaude ↔ Joplin

**Location:** `~/tools/joplin-mcp-server/`  
**Entry point:** `build/index.js` (compiled TypeScript)  
**Config:** `.mcp.json` at repo root

**What it does:** Gives openclaude live access to Joplin notes during sessions — search, read, create, append.

**Tools exposed:**

| Tool | Description | Requires Joplin open? |
|------|-------------|----------------------|
| `search_notes(query, limit?)` | Full-text search via SQLite FTS (falls back to LIKE) | ❌ No |
| `get_note(id_or_title)` | Read full note body + metadata | ❌ No |
| `list_notes(notebook?, limit?)` | List notes, optionally by notebook | ❌ No |
| `get_notebooks()` | List all notebooks with counts | ❌ No |
| `create_note(title, body, notebook?)` | Create new note via Web Clipper API | ✅ Yes |
| `append_to_note(id_or_title, content)` | Append markdown to existing note | ✅ Yes |

**Implementation:**
- Read tools use `sql.js` (pure WASM, no native compile) to read Joplin SQLite directly
- Write tools use Joplin's Web Clipper REST API (`localhost:41184`)
- `sql.js` loads the full DB into memory per call (~5MB, acceptable)

**Registration:**
```json
// .mcp.json
{
  "mcpServers": {
    "joplin": {
      "command": "/path/to/node",
      "args": ["/path/to/joplin-mcp-server/build/index.js"],
      "env": {
        "JOPLIN_DB_PATH": "/Users/<your-username>/.config/joplin-desktop/database.sqlite",
        "JOPLIN_TOKEN": "<web-clipper-token>",
        "JOPLIN_PORT": "41184"
      }
    }
  }
}
```

**Rebuild after changes:**
```bash
cd ~/tools/joplin-mcp-server
npm run build
```

---

### 3. `JournalMirror` — Daemon Journals → Joplin

**File:** `daemon/src/brn_daemon/journal.py` — class `JournalMirror`

**What it does:** After each journal generation (14:00 morning, 20:30 evening), creates or appends to a Joplin daily note so journals are browsable in Joplin alongside your deliberate notes.

**Note structure in Joplin:**
- **Title:** `Daily Journal — YYYY-MM-DD`
- **Notebook:** `Daily Journals` (auto-created if missing)
- **Body:** Appends sections:
  ```markdown
  ## Morning Journal (auto — 14:00)
  _Generated from 2brn activity_

  [journal prose here]

  ---
  ## Evening Journal (auto — 20:30)
  ...
  ```

**Fallback:** If Joplin Web Clipper is not running, mirror is skipped silently. Journal still saves to SQLite (2brn chat still works).

**Wired in:** `main.py` → `_generate_and_mirror()` calls `journal_mirror.append_to_daily_note()` after each successful journal generation.

**Journal schedule:**
| Job | Time | Time window | Label |
|-----|------|-------------|-------|
| Morning journal | 14:00 | 06:00–14:00 | "morning" |
| Evening journal | 20:30 | 14:00–20:30 | "evening" |
| Full day journal | 00:00 | full day | none |

---

### 4. `/remember` Skill — Explicit Knowledge Capture

**File:** `.claude/skills/remember.md`

**Invocation:** `/remember [something]` during any openclaude session.

**What it does:**
1. Classifies the input: `decision` / `learning` / `project` / `person`
2. Finds the right Joplin note via `joplin__search_notes`
3. Appends a dated bullet via `joplin__append_to_note`
4. Confirms to user: `Saved to Joplin: <note title> ✓`

**Target notes by classification:**
| Classification | Target note | Notebook |
|---|---|---|
| `decision` | `Decisions — YYYY-MM` | Second Brain |
| `learning` | `Learnings` | Second Brain |
| `project` | Specific project note (e.g. "2brn — Second Brain") | Project notebook |
| `person` | Person note (e.g. "John Smith") | Second Brain |

**Requires Joplin open** (uses Web Clipper write API for append/create).

---

### 5. Stop Hook — Session Memory Marker

**File:** `.claude/hooks/save-memory.sh`  
**Trigger:** Automatically when every openclaude session ends (`Stop` hook in `~/.openclaude/settings.json`)

**What it does:** Appends a one-line session marker to the current month's memory note in Joplin:
```markdown
## 2026-04-19 — session ended 21:35
```

**Target note:** `Memories — YYYY-MM` in `Second Brain` notebook (created if missing).

**Fallback:** If Joplin Web Clipper is not running, hook exits silently (no error shown to user).

---

## Joplin Notebook Structure

| Notebook | Contents | Created by |
|----------|---------|------------|
| `Personal` | Personal notes (career, 1:1s, reviews) | Migrated from OneNote |
| `Quick Notes` | Reference notes, learning snippets | Migrated from OneNote |
| `AgentHub` | AgentHub project notes | Migrated from OneNote |
| `SDA` | Smart Document Assistant notes | Migrated from OneNote |
| `PDS` | Project Delivery Services notes | Migrated from OneNote |
| `Agentlib Microservices` | Agentlib project notes | Migrated from OneNote |
| `AgentEval` | AgentEval project notes | Migrated from OneNote |
| `AgentHub ACE` | AgentHub ACE notes | Migrated from OneNote |
| `ANZ` | ANZ analytics project notes | Migrated from OneNote |
| `Azara Benchmarker` | Azara benchmarker notes | Migrated from OneNote |
| `Hackathon` | Hackathon notes | Migrated from OneNote |
| `Azure OpenAI Course` | Azure OpenAI learning notes | Migrated from OneNote |
| `Openclaude` | openclaude debugging + setup | Migrated from OneNote |
| `Leeches` | Chess AI personal project | Migrated from OneNote |
| `JTC Deduplication` | JTC dedup project | Migrated from OneNote |
| `Polish ML Project` | Polish ML project | Migrated from OneNote |
| `Team catchups` | Team catchup notes | Migrated from OneNote |
| `Second Brain` | Structural notes: decisions, learnings, memories, people, projects | Created by migration script |
| `Daily Journals` | Auto-generated daily journals from 2brn daemon | Created by `JournalMirror` |

---

## Data Flow: What Happens When You Write a Joplin Note

```
You type a note in Joplin
        │
        ▼
Joplin saves it to ~/.config/joplin-desktop/database.sqlite
        │
        ▼ (within 60 seconds)
joplin_watcher.py polls SQLite, detects updated_time changed
        │
        ▼
Note body chunked (400 words) → embedded via your AI provider
        │
        ▼
ChromaDB note_memories collection updated (upsert, stable doc IDs)
        │
        ▼
2brn chat UI now surfaces this note in RAG results
        │
        ▼ (same session, via MCP)
openclaude can search and read the note via joplin__search_notes / get_note
```

---

## Data Flow: What Happens at 14:00 (Morning Journal)

```
APScheduler fires journal_morning job
        │
        ▼
JournalGenerator.generate(time_window=("06:00","14:00"), label="morning")
Queries SQLite activities for morning window → builds GPT prompt → streams journal
        │
        ├──► Saves to SQLite journals table (always)
        │
        └──► JournalMirror.append_to_daily_note()
                │
                ▼ (if Joplin open)
             Joplin Web Clipper API
             GET/POST "Daily Journal — YYYY-MM-DD" in Daily Journals notebook
             Append ## Morning Journal section
                │
                ▼ (within 60s, via joplin_watcher.py poll)
             New/updated daily note embedded into ChromaDB note_memories
```

---

## Data Flow: What Happens at End of openclaude Session

```
openclaude Stop hook fires save-memory.sh
        │
        ▼ (if Joplin open)
Joplin Web Clipper API
Search for "Memories — YYYY-MM" in Second Brain
        │
        ├── Found: PUT /notes/{id} — append session marker line
        └── Not found: POST /notes — create new monthly memory note
```

---

## Web Clipper Configuration

| Setting | Value |
|---------|-------|
| Port | 41184 |
| Token | `665e8cd6...` (see `.mcp.json`) |
| Enable: | Joplin → Tools → Options → Web Clipper → Enable Web Clipper Service |

**Token storage:** Hardcoded in `.mcp.json` (MCP env) and `.claude/hooks/save-memory.sh`.  
**If token expires or changes:** Update both files and rebuild is not required (token is read at runtime).

---

## What Requires Joplin to Be Open

| Feature | Requires Joplin? |
|---------|-----------------|
| Screen capture + OCR + inference | ❌ Always runs |
| Embedding notes into ChromaDB | ❌ Polls SQLite directly |
| 2brn chat RAG (both collections) | ❌ Always works |
| Twice-daily journal to SQLite | ❌ Always runs |
| Journal mirrored to Joplin daily note | ✅ Web Clipper |
| openclaude `search_notes` / `get_note` | ❌ SQLite read |
| openclaude `create_note` / `append_to_note` | ✅ Web Clipper |
| `/remember` skill | ✅ Web Clipper |
| Stop hook memory marker | ✅ Web Clipper |

---

## Migration History

All notes were migrated from **Microsoft OneNote** (work account) → Joplin on **2026-04-19**.

**Method:** Custom Python script (`scripts/dendron_to_joplin_api.py`) using Joplin Web Clipper API.  
**Intermediate step:** Notes were first exported from OneNote via Playwright + onenote.com to Dendron vault (`notes/`), then imported to Joplin via API.

**Migration script:** `scripts/dendron_to_joplin_api.py`  
- Creates notebooks, imports all notes with metadata
- Resolves `[[wikilinks]]` → Joplin `[Title](:/note-id)` format
- Applies tags
- Re-runs safely (deletes and re-creates target notebooks)

**Wikilink conversion:**
- Dendron `[[note.slug]]` → Joplin `[Note Title](:/joplin-note-id)`
- Unresolved links (target didn't exist) → `` `[[slug]]` `` (visible but inert)

---

## Key Files Changed / Added

| File | Change | Purpose |
|------|--------|---------|
| `daemon/src/brn_daemon/joplin_watcher.py` | **New** | Polls Joplin SQLite, embeds into note_memories |
| `daemon/src/brn_daemon/journal.py` | **Modified** | `JournalMirror` now writes to Joplin API |
| `daemon/src/brn_daemon/main.py` | **Modified** | Uses `JoplinWatcher`, removed vault path |
| `daemon/src/brn_daemon/vault_watcher.py` | **Superseded** | Kept but no longer wired in (Dendron era) |
| `~/tools/joplin-mcp-server/` | **New** | Node.js MCP server for Joplin |
| `.mcp.json` | **Modified** | Registers Joplin MCP server |
| `.claude/hooks/save-memory.sh` | **Modified** | Now posts to Joplin API |
| `.claude/skills/remember.md` | **Modified** | Uses `joplin__*` MCP tools |
| `scripts/dendron_to_joplin_api.py` | **New** | One-time migration script |
| `scripts/dendron_to_joplin.py` | **New** | JEX generator (alternative approach, kept for reference) |
| `notes/` | **New** | Dendron vault (source of migration, not actively used post-migration) |

---

## Operational Notes

### Rebuilding the Joplin MCP server after changes
```bash
cd ~/tools/joplin-mcp-server
npm run build
# Then restart openclaude for MCP to reload
```

### Re-running the migration (if needed)
```bash
# Ensure Joplin is open with Web Clipper enabled
python3 scripts/dendron_to_joplin_api.py
# Script deletes existing target notebooks first, then re-imports
```

### Checking daemon health
```bash
cd daemon
uv run --extra dev pytest tests/ -v          # 42 tests, all should pass
curl http://localhost:7842/status             # daemon health check
```

### Forcing a full re-embed of all Joplin notes
```bash
# Restart the daemon — bulk_embed_all() runs on every startup
cd daemon && uv run python -m brn_daemon.main
```

---

## Not Yet Implemented

| Feature | Description | Notes |
|---------|-------------|-------|
| Super Productivity integration | Log tasks, track time from openclaude | No integration built yet — SP has no MCP server |
| Weekly CLAUDE.md auto-update | openclaude agent reads memories → rewrites user context | Designed in `notes/2026-04-18-second-brain-full-design.md` Part 5 |
| Memory extraction agent | Nightly openclaude agent extracts decisions/learnings from journals → writes to Memories notes | Designed in design doc Part 4 |
| Joplin mobile sync | Notes written on phone syncing to same DB | Depends on Joplin sync config (OneDrive/Nextcloud) — not configured |
