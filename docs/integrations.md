# 2brn Integration Reference

**Last updated:** 2026-05-23
**Scope:** how 2brn extends to external services via the plugin system, plus the optional first-party Joplin note-embedding integration.

---

## Overview

2brn is a second brain system with two knowledge layers:

| Layer | What | Where |
|-------|------|-------|
| **Passive** | Screen captures → OCR → AI inference → structured activities | SQLite + ChromaDB (`activity_memories`) |
| **Deliberate** | Notes you write intentionally | Any notes app you choose (e.g. Joplin) + optional embedding into ChromaDB (`note_memories`) |

Outbound integrations (mirror journals to Joplin, post to Slack, log to Notion, etc.) are **not hardcoded**. They are expressed as **plugins** — local MCP servers that 2brn launches over stdio — driven by **natural-language rules** that fire on internal events.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  SCREEN (passive capture, always on)                          │
│  Screenshot every 60s → OCR → LLM inference → activity        │
│  → SQLite (activities) + ChromaDB (activity_memories)         │
│  → emits  capture_inferred  event                             │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  NIGHTLY PIPELINE (21:00)                                     │
│  JournalGenerator → SQLite (journals)                         │
│  → emits  journal_generated  event                            │
│  BlogGenerator → SQLite (blog_posts)                          │
│  → emits  blog_generated  event                               │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  PLUGIN ORCHESTRATOR                                          │
│  EventBus  →  rule lookup  →  MCP tool call                   │
│             (rules parsed once at save time; no runtime LLM)  │
│                                                               │
│  ┌────────────────┐    ┌────────────────┐                   │
│  │ Plugin: joplin │    │ Plugin: slack  │  …                │
│  │ MCPClient over │    │ MCPClient over │                   │
│  │ stdio          │    │ stdio          │                   │
│  └────────────────┘    └────────────────┘                   │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  OPTIONAL: JOPLIN NOTE EMBEDDING (off by default)             │
│  joplin_watcher.py polls ~/.config/joplin-desktop/database.sqlite│
│  Chunks + embeds notes into ChromaDB note_memories            │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  2brn CHAT (port 7842)                                        │
│  RAG over activity_memories  +  note_memories  +  LLM stream  │
└──────────────────────────────────────────────────────────────┘
```

---

## The Plugin System

A **plugin** is a record in the `plugins` table that points at a local MCP server: `{name, command, args, env_keys}`. 2brn launches the command as a subprocess and speaks JSON-RPC over stdio. No network surface, no shared process.

A **rule** is a natural-language sentence tied to a plugin. At save time, 2brn classifies it once via the LLM into a structured form:

```python
{
  "trigger":       "journal_generated" | "blog_generated" | "capture_inferred"
                   | "daily_at_HH:MM" | "every_Xs" | "manual",
  "tool_name":     "<mcp-tool-name>",
  "args_template": { …with {placeholders}… },
}
```

The parsed form is cached in SQLite. At runtime the orchestrator does **not** call the LLM again — it renders placeholders and dispatches the tool call directly. Each execution is logged to `plugin_rule_executions` (capped at 500 rows per rule).

### Trigger vocabulary

| Trigger | Fires when | Payload (placeholders) |
|---|---|---|
| `journal_generated` | Nightly pipeline finishes a journal | `{date}`, `{journal_content}` |
| `blog_generated` | Nightly pipeline finishes a blog post | `{date}`, `{blog_content}` |
| `capture_inferred` | Inference completes for one capture | `{summary}`, `{task_category}`, `{productivity_state}`, `{app_name}`, `{timestamp}`, `{tags}` |
| `daily_at_HH:MM` | Cron schedule | `{date}`, `{time}` |
| `every_Xs` | Interval schedule | `{date}`, `{time}` |
| `manual` | "Run now" button | `{date}`, `{time}` |

### Tables

```sql
plugins
  id, name, command, args(JSON), env_keys(JSON), enabled,
  last_health_at, last_health_ok, last_health_error, created_at

plugin_rules
  id, plugin_id(FK), title, rule_text, enabled,
  trigger, tool_name, args_template(JSON),
  parse_status, parse_error, parsed_at, created_at

plugin_rule_executions
  id, rule_id(FK), started_at, ended_at,
  status('ok'|'error'|'timeout'), error, payload(JSON), result(JSON)
```

Secrets are **not** stored in SQLite. The plugin row holds only key names (e.g. `["JOPLIN_TOKEN"]`); values go to the OS keychain under `plugin.<name>.<KEY>` and fall back to env var `BRN_PLUGIN_<NAME>_<KEY>`.

### Daemon-side files

| File | Purpose |
|---|---|
| `daemon/src/brn_daemon/plugins/events.py` | `EventBus`, `EventNames` |
| `daemon/src/brn_daemon/plugins/mcp_client.py` | Stdlib-only JSON-RPC over stdio (`MCPClient`, `MCPClientPool`) |
| `daemon/src/brn_daemon/plugins/rule_parser.py` | NL → `ParsedRule`; `render_args()` for placeholder substitution |
| `daemon/src/brn_daemon/plugins/orchestrator.py` | `PluginOrchestrator`: subscribes to bus, schedules cron rules, dispatches tool calls, logs executions |
| `daemon/src/brn_daemon/routes/plugins_routes.py` | REST API |

### API surface

| Verb | Path | Purpose |
|---|---|---|
| `GET` | `/plugins` | List configured plugins + health |
| `POST` | `/plugins` | Add plugin (`name`, `command`, `args`, `env`) |
| `PUT` | `/plugins/{id}` | Edit / enable / disable |
| `DELETE` | `/plugins/{id}` | Delete plugin (cascades to rules + executions) |
| `GET` | `/plugins/{id}/tools` | Live `tools/list` against the running server |
| `GET` | `/plugin-rules?plugin_id=…` | List rules |
| `POST` | `/plugin-rules` | Add rule (LLM parses once at save) |
| `PUT` | `/plugin-rules/{id}` | Edit rule (re-parses on save) |
| `DELETE` | `/plugin-rules/{id}` | Delete rule |
| `POST` | `/plugin-rules/{id}/reparse` | Force LLM re-parse |
| `POST` | `/plugin-rules/{id}/run` | Manually trigger (uses `manual` payload) |
| `GET` | `/plugin-rules/{id}/executions?limit=` | Recent execution log |

### UI

`ui/src/components/Plugins.tsx` — split-pane page:
- **Left:** list of plugins with health dots
- **Right:** plugin detail, rule cards, rule editor with trigger/placeholder hint, advanced panel (env keys, available tools, delete)
- Each rule card has **edit / re-parse / run now / history / delete**.

---

## First-party Integration: Joplin Note Embedding (optional)

This is the only Joplin coupling left in the core daemon. It is **off by default** and pure consumer-side — it reads from Joplin, never writes.

**Toggle:** Settings → Joplin integration → "Enable note embedding".
**Config keys:** `joplin_enabled` (bool, default `false`), `joplin_db_path` (string, default empty → `~/.config/joplin-desktop/database.sqlite`).

**File:** `daemon/src/brn_daemon/joplin_watcher.py` (gated on `cfg.joplin_enabled` in `main.py`).

What it does (when enabled):
- On daemon startup: bulk-embeds every non-empty Joplin note into `note_memories`.
- Every 60s: polls Joplin SQLite for notes with a newer `updated_time`, re-embeds them.

Design notes:
- **Read-only SQLite poll** — safe for concurrent access; never opens a write handle.
- **Title prepended** to body before chunking so title-only keyword queries hit.
- **Chunk size:** 400 words at heading boundaries.
- **Stable doc IDs:** `joplin-{note_id}-{chunk_index}` (idempotent upsert).

Everything else that used to live in 2brn-core — mirroring journals back to Joplin, the `/remember` skill, the Stop hook, session memory markers — is now expressed as plugin rules against a Joplin MCP server (or any other notes service you wire in).

---

## Example: re-implementing the old "mirror journal to Joplin" with a plugin

Pre-plugin-system, the daemon had a hardcoded `JournalMirror` class. To get the same behaviour now:

1. **Install a Joplin MCP server** (e.g. `~/tools/joplin-mcp-server/`).
2. **Plugins → Add**:
   - Name: `joplin`
   - Command: `node`
   - Args: `/Users/me/tools/joplin-mcp-server/build/index.js`
   - Env: `JOPLIN_TOKEN=...`, `JOPLIN_PORT=41184`
3. **Add a rule** (paste plain English):

   > When my journal is generated, create a Joplin note in the "Journal" notebook titled with today's date and use the journal content as the body.

   The parser locks this to `{trigger: "journal_generated", tool_name: "create_note", args_template: {…}}`.

4. Optional: a second rule on `blog_generated` to mirror the dev-log.

If Joplin is closed when the event fires, the MCP server itself will fail to reach the Web Clipper and the orchestrator records an `error` execution. Captures and journals keep working — no crash, no data loss.

---

## What Requires Joplin to Be Open

| Feature | Requires Joplin app? |
|---|---|
| Screen capture + OCR + inference | ❌ Always runs |
| Nightly journal + blog generation | ❌ Always runs |
| Joplin note embedding into ChromaDB (when enabled) | ❌ Reads SQLite directly |
| 2brn chat RAG | ❌ Always works |
| A plugin rule that calls Joplin's Web Clipper API | ✅ Joplin must be open |

---

## Operational Notes

### Forcing a full re-embed of Joplin notes
Restart the daemon — `bulk_embed_all()` runs on every startup when `joplin_enabled=true`.

### Inspecting a rule's parsed form
```bash
curl http://localhost:7842/plugin-rules | jq '.[] | {id, trigger, tool_name, args_template, parse_status}'
```

### Forcing a re-parse after editing rule text
```bash
curl -X POST http://localhost:7842/plugin-rules/{id}/reparse
```

### Tail of recent executions for a rule
```bash
curl http://localhost:7842/plugin-rules/{id}/executions?limit=20 | jq
```

### Running the test suite
```bash
cd daemon
uv run --extra dev pytest tests/ -v
```

---

## Not Yet Implemented

| Feature | Notes |
|---|---|
| Plugin gallery / one-click install | Out of scope by design — plugins are configured manually for now |
| Multi-tool rules ("call A then B") | One rule maps to one tool call |
| Rule-side conditional logic | The trigger-side `app_name`/`task_category` placeholders are available; richer filtering would need a small DSL |
| Auto-discovery of installed MCP servers | Each plugin must be added explicitly in the Plugins UI |
