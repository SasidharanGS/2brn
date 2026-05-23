# Design Document: 2brn as OpenClaude's Persistent Memory

**Version:** 1.0  
**Date:** 2026-04-25  
**Status:** Design / Long-term vision  
**Scope:** Making 2brn the permanent, evolving memory layer for all OpenClaude sessions — the "second brain" that makes the assistant feel like it truly knows you

---

## 1. The vision

Right now, every OpenClaude session starts from zero. The assistant is brilliant but amnesiac — it can help you build anything, but it doesn't remember that you built it, why you built it the way you did, or what you learned along the way.

The vision is simple: **OpenClaude should feel like a senior colleague who has been working alongside you for years.** Someone who remembers the decisions you made, knows which projects you care about, understands your working patterns, and can surface relevant context without being asked.

2brn is uniquely positioned to be this memory layer because it already:
- Watches your screen continuously (activity memories)
- Reads and indexes all your Joplin notes (note memories)
- Generates daily journals that narrate your work life
- Stores structured decisions and session summaries (Design Doc 1)

This design document describes how to make all of that knowledge **actively available** to OpenClaude in a way that improves over time.

---

## 2. What "persistent memory" means in practice

Persistent memory is not a single feature — it is a **system of interconnected layers** that together make OpenClaude increasingly context-aware:

| Layer | What it is | Where it lives |
|-------|-----------|----------------|
| **Episodic** | "What happened" — individual session notes, daily journals, activity timeline | Joplin + ChromaDB |
| **Semantic** | "What I know" — Joplin notes, decisions, learnings, project docs | Joplin + ChromaDB |
| **Procedural** | "How I work" — patterns, preferences, recurring decisions, anti-patterns | CLAUDE.md + distilled notes |
| **Working** | "What's happening right now" — current activity, recent sessions, today's journal | 2brn daemon SQLite |

The **2brn MCP server** (Design Doc 2) provides OpenClaude with real-time access to the working and episodic layers. This document focuses on what's needed on top of that to achieve the full vision.

---

## 3. The memory lifecycle

Memory is not static. Good persistent memory goes through four stages:

```
CAPTURE → STORE → DISTIL → RETRIEVE
```

### 3.1 Capture (already mostly built)
- 2brn daemon: continuous screen capture + inference (✅ built)
- JoplinWatcher: note indexing into ChromaDB (✅ built)  
- Session notes in Joplin (Design Doc 1 — to be built)
- `/remember` skill: explicit memory writes mid-session (✅ built)
- Daily journals in Joplin (✅ built)

### 3.2 Store (mostly built)
- SQLite for structured activity data (✅ built)
- ChromaDB for semantic search (✅ built)
- Joplin for human-readable notes (✅ built)
- Monthly "Memories" notes for rough session markers (✅ built, partially)

**Gap:** Session notes (Design Doc 1) need to be built. Everything else is done.

### 3.3 Distil (needs building — the most important gap)
Raw capture is noisy. Distillation converts noise into signal:
- Daily → weekly summary notes in Joplin
- Project-specific "what I know" notes that get updated over time
- An evolving "about me" note that CLAUDE.md links to
- Identifying recurring patterns: "you always use FastAPI for Python services", "you prefer direct logic over abstractions"

**This is the key missing piece.** Without distillation, the memory system grows but doesn't get smarter.

### 3.4 Retrieve (Design Doc 2 covers this)
- 2brn MCP tools for OpenClaude to query memory at session start and mid-session
- CLAUDE.md instructions that make retrieval automatic

---

## 4. The distillation system

### 4.1 Nightly memory distillation (automated)

A scheduled job (runs daily at, say, 23:00) that:

1. **Reads today's data:**
   - All activities from `activities` table for today
   - Today's session notes from Joplin (via JoplinWatcher index)
   - Today's `/remember` calls from `session-decisions.jsonl`
   - Today's captures and inference results

2. **Calls JLL GPT Gateway with a structured prompt:**
   ```
   You are updating a personal knowledge base for Sasidharan Govindan.
   
   Today's data:
   - Activities: [list of summaries]
   - Session notes: [list of session summaries]
   - Explicit memories: [list from /remember calls]
   
   Update the following note sections:
   1. Add 1-3 bullet points to "Learnings — YYYY-MM" for genuinely new knowledge
   2. Add 1-2 bullet points to "Decisions — YYYY-MM" for decisions made
   3. Flag any patterns worth noting (e.g., repeated context-switching, productive streaks)
   
   Return JSON: { learnings: [...], decisions: [...], patterns: [...] }
   ```

3. **Writes results to Joplin** via Web Clipper:
   - Appends to "Learnings — YYYY-MM" note
   - Appends to "Decisions — YYYY-MM" note (if new decisions not already captured)
   - Appends to a new "Patterns — YYYY" note

4. **These notes are picked up by JoplinWatcher** on next poll → embedded into ChromaDB → searchable in future sessions

### 4.2 Weekly project digest (automated)

Every Sunday, a scheduled job:
1. Gathers all session notes + activity data for the week, grouped by project
2. For each active project, updates a "Project Status — {name}" note in Joplin:
   ```markdown
   ## Week of 2026-04-21
   - **2brn:** Completed TanStack Query migration, full Obsidian Glass redesign,
     24-issue code review resolved. Branch `feat/implementation` ready to merge.
   - **SDA:** No activity this week.
   - **JLL Gateway:** 1 debugging session on embeddings format.
   ```
3. These notes are the answer to "what's the current status of X?" — they accumulate history week by week

### 4.3 CLAUDE.md auto-updater (semi-automated)

The `~/.openclaude/CLAUDE.md` is the highest-leverage memory file — OpenClaude reads it at the start of every session. Today it contains static preferences.

The vision: **CLAUDE.md evolves based on patterns 2brn observes.**

Examples of auto-updates:
- 2brn observes you always run `nvm --version` before Node commands → already in CLAUDE.md ✅
- 2brn observes you always use `uv run` for Python → add to CLAUDE.md
- A session produces a decision about a new architectural pattern → distillation adds it to CLAUDE.md's "Key decisions" section
- You spend 80% of sessions on 2brn and SDA → those projects get promoted in the "Current Active Projects" section

**How:** The nightly distillation job produces a structured diff of CLAUDE.md changes. OpenClaude presents these to you (the user) for approval before writing. You're never surprised by what's in your own CLAUDE.md.

This is the `claude-md-management:revise-claude-md` skill already in your plugins — but triggered automatically by 2brn's distillation, not just manually.

---

## 5. The "about me" knowledge graph

Over time, the memory system builds an implicit model of who you are, how you work, and what you know. This is surfaced as a set of Joplin notes that get updated by the distillation system:

### 5.1 "Working patterns" note
```markdown
# Working Patterns — Sasidharan Govindan
*Auto-updated by 2brn distillation. Last updated: 2026-04-25*

## Peak focus windows
- Most productive: 09:00–12:00 (consistent across 3 months)
- Context-switches after 12:00 to communication/meetings

## Code preferences
- Python: async throughout, uv for environment management
- TypeScript: strict mode, typed API clients
- Commits: "why" not "what" in commit messages
- KISS principle: direct logic, no unnecessary abstractions

## Common patterns
- Always triggers nvm before Node commands
- Runs pytest after every Python change
- Uses Playwright MCP for UI verification
```

### 5.2 "Project knowledge" notes (one per project)
```markdown
# 2brn — What I Know
*Auto-updated by 2brn distillation. Last updated: 2026-04-25*

## Current status
Branch feat/implementation has 23 commits ahead of main.
Last session: Obsidian Glass UI redesign (complete).

## Key architectural decisions
- Electron 31 + Python FastAPI daemon (port 7842)
- JLL GPT Gateway for all LLM calls (non-OpenAI embeddings format)
- ChromaDB for semantic search (activity_memories + note_memories)
- TanStack Query for UI data fetching (staleTime: 30s)
- Joplin as notes layer (polling via JoplinWatcher every 60s)

## Known gotchas
- Electron spawn: use .venv/bin/python3, not system Python
- pnpm v10: onlyBuiltDependencies needed for Electron
- Journal unique constraint: (date, COALESCE(label, ''))
- nvm lazy-init: always run nvm --version before Node commands
```

These notes are:
- Read by OpenClaude at session start (via `search_notes` MCP tool)
- Updated by the distillation system when new knowledge is generated
- Embedded in ChromaDB for semantic search

---

## 6. The "second brain" chat experience

With all layers active, the 2brn chat UI (already built) becomes significantly more powerful:

### Current state
User: "What was I working on this morning?"
2brn: Searches `activity_memories` ChromaDB → returns summaries from screen captures

### Future state (with session notes + distillation)
User: "What was I working on this morning?"
2brn: Searches `activity_memories` + `note_memories` (session notes, project notes, journals) → returns:
- The activity summaries (screen-level)
- The session note ("you fixed 24 code review issues in the 2brn daemon")
- The morning journal ("focused deep work session, no interruptions")
- Relevant decisions made ("decided to use range bounds instead of date() for index performance")

The answer is richer, more contextual, and grounded in both passive observation and explicit memory.

---

## 7. Privacy and trust model

As the memory system becomes more comprehensive, privacy becomes more important.

### What 2brn stores about you
- Screen activity (inferred, not raw) — stored locally in `~/.2brn/`
- Joplin notes — stored in Joplin's local SQLite
- Session notes — stored in Joplin
- CLAUDE.md — stored in `~/.openclaude/`

**Nothing leaves your machine except:**
- Inference prompts to JLL GPT Gateway (contains OCR text summaries, not raw screenshots)
- Chat queries to JLL GPT Gateway (contains activity summaries + note excerpts)

### What OpenClaude sends to JLL Gateway
When OpenClaude calls 2brn MCP tools and uses the results in a conversation, the context (activity summaries, note excerpts) is included in the conversation payload sent to the JLL GPT Gateway.

**Mitigation:** App exclusions ensure sensitive apps (1Password, banking) are never captured. Only inferred summaries — not raw OCR text — are included in MCP tool responses.

### User control
- CLAUDE.md updates require human approval before writing
- Distillation outputs are visible in Joplin before they're embedded
- The session tracking (Design Doc 1) can be disabled per-session with a flag
- The 2brn daemon can be paused at any time from the UI

---

## 8. Integration map — how the three systems connect

```
                    ┌─────────────────────────────────────────────┐
                    │              OpenClaude Session               │
                    │                                               │
                    │  [CLAUDE.md] → pre-loaded context             │
                    │  [2brn MCP] → real-time queries               │
                    │  [Joplin MCP] → note read/write               │
                    └───────────────┬─────────────────────────────┘
                                    │ calls
                    ┌───────────────▼─────────────────────────────┐
                    │           2brn MCP Server                     │
                    │  get_current_context  search_activity         │
                    │  get_timeline        get_journal              │
                    │  search_notes        get_recent_decisions     │
                    └───────────────┬─────────────────────────────┘
                                    │ HTTP
                    ┌───────────────▼─────────────────────────────┐
                    │           2brn Daemon (port 7842)             │
                    │                                               │
                    │  SQLite ←──── captures, activities, journals  │
                    │  ChromaDB ←── activity_memories               │
                    │            ←── note_memories                  │
                    └─────────────────┬───────────────────────────┘
                                      │ reads/writes
          ┌───────────────────────────▼──────────────────────────┐
          │                    Joplin SQLite                       │
          │  • Daily journals (written by JournalMirror)           │
          │  • Session notes (written by session-to-joplin.sh)     │
          │  • /remember entries (written by skill)                │
          │  • Decisions, Learnings, Patterns (written by distil)  │
          │  • Project knowledge notes (written by weekly digest)  │
          │  • Working patterns note (written by distil)           │
          │  • CLAUDE.md diff suggestions (reviewed by user)       │
          └──────────────────────────────────────────────────────┘
                                      │ polled every 60s by JoplinWatcher
                                      ▼
                    ┌─────────────────────────────────────────────┐
                    │          ChromaDB note_memories               │
                    │  All Joplin notes → chunked → embedded        │
                    │  Searchable via 2brn MCP + 2brn chat UI       │
                    └─────────────────────────────────────────────┘

          ┌─────────────────────────────────────────────────────┐
          │          Stop Hook → session-to-joplin.sh            │
          │  Each session end → structured note → Joplin         │
          └─────────────────────────────────────────────────────┘

          ┌─────────────────────────────────────────────────────┐
          │          Nightly distillation (23:00 scheduled)      │
          │  Today's data → JLL Gateway → Learnings/Decisions/   │
          │  Patterns notes in Joplin → embedded by JoplinWatcher│
          └─────────────────────────────────────────────────────┘
```

---

## 9. Implementation roadmap

This is a long-term system. Build it incrementally, each phase delivering real value on its own.

### Phase 1 — Foundation (Design Doc 1 + Design Doc 2) — ~2 days
- Session tracking: every session → Joplin note
- 2brn MCP server: 4 core tools (current context, timeline, journal, productivity)
- Register MCP globally
- Add session startup protocol to CLAUDE.md

**Value delivered:** OpenClaude knows what you've been working on at session start. No more re-explaining.

### Phase 2 — Semantic search — ~1 day
- Add `/notes/search` to 2brn daemon
- Implement `search_activity` + `search_notes` tools in MCP
- Test "what was I building last week?" end-to-end

**Value delivered:** OpenClaude can answer questions about your history accurately.

### Phase 3 — Decisions layer — ~half day
- Implement `get_recent_decisions` MCP tool
- Wire `/remember` to accumulator file → session notes
- Test "what decisions have I made about X?"

**Value delivered:** No more re-debating settled questions.

### Phase 4 — Nightly distillation — ~1 day
- Add `distillation` scheduled job to 2brn daemon (23:00 daily)
- LLM call to JLL Gateway: today's data → Learnings/Decisions/Patterns
- Write results to Joplin
- Verify JoplinWatcher picks them up

**Value delivered:** Memory system gets smarter automatically. Weekly digest starts building project status notes.

### Phase 5 — CLAUDE.md evolution — ~1 day
- Weekly digest produces CLAUDE.md diff suggestions
- Present to user for approval (via 2brn chat UI or OpenClaude session)
- Auto-apply approved diffs

**Value delivered:** OpenClaude's pre-loaded context keeps improving without manual CLAUDE.md maintenance.

### Phase 6 — Project knowledge notes — ~half day
- Weekly digest writes/updates "Project knowledge" notes per project
- These become the primary answer to "what's the current status of X?"

**Value delivered:** Full "second brain" experience — OpenClaude feels like it has been working on your projects with you.

---

## 10. Success criteria

The system is working when:

1. **At session start,** OpenClaude references something from your last session without being told about it
2. **Mid-session,** "continue where I left off" works without any context dump from you
3. **Cross-project,** "what's the status of the SDA work?" returns an accurate, up-to-date answer
4. **Historical,** "when did I decide to use TanStack Query?" returns the exact session note and rationale
5. **Patterns,** CLAUDE.md's "Working patterns" section accurately reflects how you actually work
6. **Growth,** the memory system noticeably improves over weeks — early sessions require more explanation than sessions after a month of use

---

## 11. Files to create / modify (full roadmap view)

| File | Phase | Purpose |
|------|-------|---------|
| `~/.openclaude/hooks/session-to-joplin.sh` | 1 | Session capture |
| `~/.openclaude/settings.json` | 1 | Hook wiring |
| `~/tools/2brn-mcp-server/` | 1–3 | MCP server (see Design Doc 2) |
| `daemon/src/brn_daemon/routes/notes_routes.py` | 2 | `/notes/search` endpoint |
| `daemon/src/brn_daemon/distillation.py` | 4 | Nightly distillation job |
| `daemon/src/brn_daemon/main.py` | 4 | Register distillation scheduler |
| `~/.openclaude/CLAUDE.md` | 1, 5 | Session protocol + auto-updates |
| `docs/design/persistent-memory.md` (this doc) | 0 | ✓ done |
