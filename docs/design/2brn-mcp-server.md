# Design Document: 2brn MCP Server for OpenClaude

**Version:** 1.0  
**Date:** 2026-04-25  
**Status:** Design / Pre-implementation  
**Scope:** A TypeScript MCP server that gives OpenClaude real-time access to 2brn's activity data, notes, and productivity context

---

## 1. Problem Statement

Every time a new OpenClaude session starts, the assistant has no idea:
- What you were just working on
- What state the codebase is in
- What decisions you've already made
- Whether you've been focused or scattered all day

You have to re-explain context every single session. This is friction — and it compounds over time.

2brn has all of this. It has been watching your screen, running inference, writing journals, and indexing your Joplin notes. The knowledge exists. It just isn't connected to OpenClaude.

**Goal:** Build a 2brn MCP server that gives OpenClaude 6–8 high-value tools to query 2brn's data, making every session context-aware from the first message.

---

## 2. Design principles

1. **Read-only by default.** The MCP server reads from 2brn's SQLite DB and ChromaDB. It does not write to them — writing stays within the 2brn daemon's own control plane.
2. **Fast responses.** MCP tools are called synchronously during conversation. Every tool must respond in <500ms. No LLM calls inside MCP tools.
3. **Graceful degradation.** If the 2brn daemon is not running, tools return empty/null responses rather than crashing. OpenClaude should always be able to start a session.
4. **Minimal setup.** Registered in `.mcp.json` (same pattern as Joplin MCP). Runs as a Node.js process alongside the existing Joplin MCP.
5. **Complementary to Joplin MCP.** The Joplin MCP handles note read/write. This MCP handles activity data, screen captures, productivity state, and semantic search over both.

---

## 3. Tools to expose

### 3.1 `get_current_context` — Most-used tool
**Purpose:** One-shot "orient me" call. Returns a structured snapshot of what's happening right now and recently. OpenClaude would call this at the start of a session.

**Input:** `{ hours_back?: number }` (default: 4)

**Output:**
```json
{
  "daemon_status": "capturing",
  "current_productivity_state": "focused",
  "current_app": "Cursor",
  "capture_count_today": 1193,
  "recent_activities": [
    {
      "started_at": "2026-04-25T12:45:00Z",
      "summary": "Working on 2brn UI code review fixes in VS Code",
      "task_category": "work",
      "productivity_state": "focused"
    }
    // ... up to 10 most recent
  ],
  "today_journal": "You spent the morning deep in the 2brn codebase...",
  "focus_pct_today": 34
}
```

**Implementation:** Single aiosqlite query joining `captures` + `activities` for the last N hours, plus a quick journal lookup. No embedding calls.

---

### 3.2 `search_activity` — Semantic memory search
**Purpose:** "What do I know about X?" — searches both activity history and Joplin notes via ChromaDB.

**Input:** `{ query: string, date_from?: string, date_to?: string, limit?: number }`

**Output:**
```json
{
  "results": [
    {
      "source": "activity",
      "date": "2026-04-25",
      "app": "Cursor",
      "summary": "Fixing the inference queue OOM bug in main.py",
      "task_category": "work",
      "relevance_score": 0.92
    },
    {
      "source": "joplin_note",
      "date": "2026-04-25",
      "title": "2026-04-25 14:32 — 2brn — TanStack Query fix",
      "notebook": "OpenClaude Sessions",
      "excerpt": "Migrated the 2brn React UI from manual useState+useEffect...",
      "relevance_score": 0.88
    }
  ]
}
```

**Implementation:** Calls the 2brn daemon's existing `/chat` endpoint internally? No — the MCP server talks directly to ChromaDB to avoid going through the HTTP layer. This means the MCP server needs direct access to ChromaDB's `~/.2brn/chroma/` directory.

**Alternative:** Call `GET http://127.0.0.1:7842/activities?date=...` and do keyword search. Simpler, no direct ChromaDB dependency. Semantic search requires embedding, which requires the daemon. 

**Decision: Proxy to the 2brn daemon REST API** for all data. The MCP server is a thin adapter, not a new data layer. This keeps the architecture clean.

---

### 3.3 `get_timeline` — Activity stream for a date
**Purpose:** "What did I do today/yesterday?" — structured list of activities.

**Input:** `{ date?: string }` (default: today, format YYYY-MM-DD)

**Output:**
```json
{
  "date": "2026-04-25",
  "activities": [
    {
      "time": "14:32",
      "summary": "Working on TanStack Query migration",
      "task_category": "work",
      "productivity_state": "focused",
      "duration_minutes": 47
    }
    // ...
  ],
  "stats": {
    "total_captures": 1193,
    "total_activities": 89,
    "top_category": "work",
    "focus_pct": 34
  }
}
```

**Implementation:** `GET http://127.0.0.1:7842/activities?date={date}` + `GET /captures?date={date}`.

---

### 3.4 `get_productivity_snapshot` — Current state + today's stats
**Purpose:** Quick pulse check — useful for OpenClaude to know if you're in a flow state or scattered.

**Input:** none

**Output:**
```json
{
  "current_state": "focused",
  "current_app": "Cursor",
  "last_captured_at": "2026-04-25T14:47:00Z",
  "today": {
    "productive_pct": 34,
    "top_category": "work",
    "top_app": "Cursor",
    "total_hours_tracked": 6.2
  }
}
```

**Implementation:** `GET http://127.0.0.1:7842/status` + `GET /insights/daily?date=today`.

---

### 3.5 `get_journal` — Daily narrative
**Purpose:** "What does my journal say about today/a specific date?" — gives OpenClaude the human-readable narrative 2brn wrote.

**Input:** `{ date?: string, label?: "morning" | "evening" | null }`

**Output:**
```json
{
  "date": "2026-04-25",
  "morning": "The morning was spent deep in the 2brn codebase...",
  "evening": null,
  "full_day": null
}
```

**Implementation:** `GET http://127.0.0.1:7842/journal/{date}`. Returns all labels for the date.

---

### 3.6 `search_notes` — Joplin semantic search via 2brn
**Purpose:** Search your Joplin notes by natural language query. Wraps the existing 2brn chat RAG pipeline but returns structured results rather than a streamed answer.

**Input:** `{ query: string, notebook?: string, limit?: number }`

**Output:**
```json
{
  "notes": [
    {
      "title": "AI Gateway Setup",
      "notebook": "Projects",
      "excerpt": "The gateway proxies Azure OpenAI. Embeddings use a custom format...",
      "note_id": "abc123",
      "relevance": 0.91
    }
  ]
}
```

**Note:** This differs from the Joplin MCP's `search_notes` which does keyword search. This one does **semantic/vector search** via ChromaDB's `note_memories` collection. Both are useful — keyword for exact matches, semantic for concept search.

**Implementation:** POST to a new 2brn daemon endpoint `GET /notes/search?q={query}&limit={limit}` that queries ChromaDB directly.

**Requires new daemon endpoint** (small addition to the daemon).

---

### 3.7 `get_recent_decisions` — Decision history
**Purpose:** "What decisions have I made about X recently?" — surfaces structured decisions from session notes and `/remember` calls.

**Input:** `{ query?: string, days_back?: number }`

**Output:**
```json
{
  "decisions": [
    {
      "date": "2026-04-25",
      "decision": "Removed React.StrictMode — causes all useEffect to run twice in dev",
      "source": "session_note",
      "session": "2026-04-25 14:32 — 2brn — TanStack Query fix"
    },
    {
      "date": "2026-04-19",
      "decision": "Joplin chosen as deliberate notes app (AGPL, local-first)",
      "source": "joplin_note",
      "note": "Decisions — 2026-04"
    }
  ]
}
```

**Implementation:** Searches Joplin notes titled "Decisions — YYYY-MM" via the Joplin MCP's `search_notes`, plus session notes' "Key decisions" sections. This is primarily a Joplin text search, not ChromaDB.

---

## 4. Architecture

### 4.1 Where the MCP server lives

```
~/tools/2brn-mcp-server/          ← new directory, same pattern as joplin-mcp-server
  src/index.ts                     ← MCP server entry point
  src/client.ts                    ← HTTP client for 2brn daemon REST API
  src/tools/                       ← one file per tool
    current-context.ts
    search-activity.ts
    timeline.ts
    productivity.ts
    journal.ts
    search-notes.ts
    decisions.ts
  build/index.js                   ← compiled output
  package.json
  tsconfig.json
```

### 4.2 Registration in `.mcp.json`

Add alongside the existing Joplin server:
```json
{
  "mcpServers": {
    "joplin": { ... existing ... },
    "2brn": {
      "command": "/path/to/node",
      "args": ["/path/to/2brn-mcp-server/build/index.js"],
      "env": {
        "BRND_URL": "http://127.0.0.1:7842",
        "BRND_TIMEOUT_MS": "3000"
      }
    }
  }
}
```

**Note:** `.mcp.json` is at the repo root. For this MCP to be available across all projects (not just 2brn), it should also be registered in `~/.openclaude/settings.json`'s `mcpServers` or in a global `.mcp.json`. **Recommendation: global** — the 2brn context is always relevant regardless of which repo you're in.

### 4.3 Data flow

```
OpenClaude (user asks question)
        │
        ▼
[OpenClaude] calls MCP tool e.g. get_current_context()
        │
        ▼
[2brn MCP server] (Node.js process)
        │  HTTP GET http://127.0.0.1:7842/...
        ▼
[2brn daemon] (Python FastAPI, port 7842)
        │  queries
        ▼
[SQLite ~./2brn/2brn.db] + [ChromaDB ~./2brn/chroma/]
        │
        ▼ response flows back up
[MCP server] formats JSON → MCP tool result
        │
        ▼
[OpenClaude] has context, answers user question
```

### 4.4 New daemon endpoint needed: `/notes/search`

For `search_notes` tool, add to `daemon/src/brn_daemon/routes/`:

```python
@router.get("/notes/search")
async def search_notes(q: str = Query(...), limit: int = Query(5)):
    """Semantic search over Joplin note_memories ChromaDB collection."""
    from brn_daemon.main import app_state
    chroma = app_state.get("chroma_store")
    gateway = ...  # from app_state
    embedding = await gateway.embed(q)
    results = chroma.query_notes(embedding=embedding, n_results=limit)
    # format and return
```

This is a small addition (~30 lines) to the existing daemon.

---

## 5. How OpenClaude uses these tools

### Session start (automatic via CLAUDE.md instruction)

Add to `~/.openclaude/CLAUDE.md`:
```markdown
## Session Startup Protocol
At the start of every session, call `2brn__get_current_context` to understand
what the user has been working on. Use this to:
- Acknowledge recent work without asking them to repeat it
- Understand current productivity state
- Have relevant project context pre-loaded
```

This makes context-loading automatic — OpenClaude calls it as the first tool before responding to the first user message.

### Mid-session usage

OpenClaude can call these tools proactively when relevant:
- User asks "what did I decide about X?" → `get_recent_decisions(query="X")`
- User says "continue where I left off" → `get_current_context(hours_back=24)` + `search_activity(query="the task")`
- User asks about past work on a different project → `get_timeline(date="last-tuesday")` + `search_activity(query="project-name")`

### The "second brain" effect

With these tools, a session opening could look like:

**User:** "Let's continue the SDA work"

**OpenClaude (internally calls `get_current_context` + `search_activity("SDA microservices")`):**
> "Based on your recent activity, you were working on the SDA microservices migration yesterday. The last session (3 hours, 2 commits) focused on the folder backend stored procedures. Your journal notes you had a call with Shekhar at 3pm. You were in a focused state for about 40% of yesterday.
> 
> Want to pick up from the stored procedures, or is there a new direction?"

No re-explaining. No context dump from the user. The assistant already knows.

---

## 6. What requires the 2brn daemon to be running

| Tool | Requires daemon | Fallback |
|------|----------------|---------|
| `get_current_context` | Yes | Return "daemon offline, no recent activity data" |
| `search_activity` | Yes (for semantic) | Return empty results |
| `get_timeline` | Yes | Return empty |
| `get_productivity_snapshot` | Yes | Return nulls |
| `get_journal` | Yes | Return null |
| `search_notes` | Yes (for semantic) | Suggest using Joplin MCP `search_notes` for keyword search |
| `get_recent_decisions` | Partially (Joplin MCP covers this) | Fall back to Joplin keyword search |

The MCP server should always start successfully even if the daemon is down. Tool calls return structured "unavailable" responses rather than throwing.

---

## 7. Relationship to existing Joplin MCP

These two MCP servers are complementary:

| Joplin MCP | 2brn MCP |
|-----------|---------|
| Read/write Joplin notes directly | Query 2brn's activity data + semantic search |
| Keyword search | Vector/semantic search |
| Full note content | Summarised/excerpted |
| Note management (create, append) | Read-only activity context |
| Works without 2brn daemon | Requires 2brn daemon |

They solve different problems. Both should be registered globally.

---

## 8. Privacy considerations

The 2brn daemon captures everything — including sensitive apps. The MCP server exposes this to OpenClaude (which is sent to the your AI provider).

Mitigations already in place:
- App exclusions in 2brn settings (1Password, etc.)
- OCR is filtered through inference before storage — raw screenshots are not exposed via the API
- Only `summary` and `app_name` are surfaced, not raw `ocr_text`

**Recommendation:** The MCP tools should never expose `ocr_text` directly — only inferred summaries. This is already the case in the daemon API.

---

## 9. Implementation phases

### Phase 1 — Core tools (~1 day)
1. Create `~/tools/2brn-mcp-server/` with TypeScript scaffold
2. Implement: `get_current_context`, `get_timeline`, `get_productivity_snapshot`, `get_journal`
3. Register in global `.mcp.json`
4. Test: start session, verify OpenClaude can call tools
5. Add session startup instruction to `~/.openclaude/CLAUDE.md`

### Phase 2 — Semantic search (~half day)
6. Add `/notes/search` endpoint to 2brn daemon
7. Implement `search_activity` and `search_notes` tools
8. Test: "what was I working on last week?" via MCP

### Phase 3 — Decisions tool (~half day)
9. Implement `get_recent_decisions` using Joplin keyword search on decision notes
10. Wire up to session tracking (Design Doc 1) for session-note decisions

---

## 10. Files to create / modify

| File | Action | Purpose |
|------|--------|---------|
| `~/tools/2brn-mcp-server/src/index.ts` | Create | MCP server entry point |
| `~/tools/2brn-mcp-server/src/client.ts` | Create | HTTP client for daemon API |
| `~/tools/2brn-mcp-server/src/tools/*.ts` | Create | One per tool (6–7 files) |
| `~/tools/2brn-mcp-server/package.json` | Create | MCP SDK + TypeScript |
| `~/.openclaude/settings.json` or global `.mcp.json` | Modify | Register 2brn MCP globally |
| `daemon/src/brn_daemon/routes/notes_routes.py` | Create | `/notes/search` endpoint |
| `daemon/src/brn_daemon/main.py` | Modify | Register new router |
| `~/.openclaude/CLAUDE.md` | Modify | Add session startup protocol |
| `docs/design/2brn-mcp-server.md` (this doc) | Create | ✓ done |
