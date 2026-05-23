# Design: Debug Panel

**Date:** 2026-04-26  
**Status:** Approved  
**Scope:** A toggleable right-side debug panel accessible from all pages, showing a live daemon log stream and a structured status snapshot.

---

## Goal

Add a **⬡ debug** button to the left sidebar (above the daemon status indicator). Clicking it opens a 270px right-side panel that persists across all route navigations. Clicking again closes it. The panel has two tabs: **logs** (live daemon log stream) and **status** (structured health snapshot).

---

## Files Changed

| File | Action | Responsibility |
|---|---|---|
| `daemon/src/brn_daemon/log_buffer.py` | **Create** | In-memory circular log buffer + custom logging handler |
| `daemon/src/brn_daemon/routes/debug_routes.py` | **Create** | `GET /logs` and `GET /debug/status` endpoints |
| `daemon/src/brn_daemon/main.py` | **Modify** | Wire log buffer handler into `logging.basicConfig`; register debug router |
| `ui/src/api/types.ts` | **Modify** | Add `LogLine` and `DebugStatus` TypeScript interfaces |
| `ui/src/api/client.ts` | **Modify** | Add `api.getLogs()` and `api.getDebugStatus()` |
| `ui/src/components/shared/DebugPanel.tsx` | **Create** | Tabbed panel component (logs + status tabs) |
| `ui/src/App.tsx` | **Modify** | Add `debugOpen` state, debug button in sidebar, render `<DebugPanel>` |

---

## Daemon — Log Buffer

### `log_buffer.py`

A module-level circular buffer of 500 log records. A custom `logging.Handler` subclass writes every log record into it. Exposed as a singleton so all modules share it.

```python
# Key interface:
class LogBuffer:
    MAX_LINES = 500
    def append(self, record: logging.LogRecord) -> None: ...
    def get(self, level: str | None = None, limit: int = 100) -> list[dict]: ...
    # Returns dicts: {ts: "HH:MM:SS", level: "INFO"|"WARNING"|"ERROR", msg: str}

log_buffer = LogBuffer()  # module-level singleton
```

Level normalisation:
- `logging.DEBUG` → `"DEBUG"`
- `logging.INFO` → `"INFO"`
- `logging.WARNING` → `"WARNING"`
- `logging.ERROR` / `logging.CRITICAL` → `"ERROR"`

### `main.py` changes

After `logging.basicConfig(...)`, add the buffer handler:

```python
from brn_daemon.log_buffer import log_buffer, LogBufferHandler
logging.getLogger().addHandler(LogBufferHandler(log_buffer))
```

---

## Daemon — Debug Routes

### `GET /logs`

Query params:
- `level` (optional): filter to `"WARNING"` or `"ERROR"` — omit for all
- `limit` (optional, default 100, max 500): number of lines to return

Response:
```json
{
  "lines": [
    { "ts": "12:01:03", "level": "INFO", "msg": "daemon started ok" },
    { "ts": "12:01:11", "level": "WARNING", "msg": "ocr sparse, skipping" },
    { "ts": "12:01:22", "level": "ERROR", "msg": "gateway timeout 30s" }
  ]
}
```

Always returns the **most recent** `limit` lines (tail, not head).

### `GET /debug/status`

Checks gateway reachability via `httpx` with a 3s timeout to `{gateway_url}/actuator/health`. Reads chroma collection counts. Returns last error from the log buffer (most recent ERROR-level line).

Response:
```json
{
  "daemon": {
    "status": "capturing",
    "capture_count_today": 42,
    "last_captured_at": "2026-04-26T12:01:10",
    "paused": false
  },
  "gateway": {
    "url": "http://localhost:8888",
    "reachable": true,
    "model": "GPT_4_1"
  },
  "chroma": {
    "activity_memories": 1204,
    "note_memories": 131
  },
  "last_error": {
    "ts": "12:01:22",
    "msg": "gateway timeout 30s"
  }
}
```

`last_error` is `null` if no ERROR-level lines in the buffer.

---

## UI — Types

### `ui/src/api/types.ts` additions

```typescript
export interface LogLine {
  ts: string       // "HH:MM:SS"
  level: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG'
  msg: string
}

export interface DebugStatus {
  daemon: {
    status: string
    capture_count_today: number
    last_captured_at: string | null
    paused: boolean
  }
  gateway: {
    url: string
    reachable: boolean
    model: string
  }
  chroma: {
    activity_memories: number
    note_memories: number
  }
  last_error: { ts: string; msg: string } | null
}
```

### `ui/src/api/client.ts` additions

```typescript
getLogs: (level?: string, limit?: number) => {
  const q = new URLSearchParams()
  if (level) q.set('level', level)
  if (limit) q.set('limit', String(limit))
  return get<{ lines: LogLine[] }>(`/logs?${q}`)
},
getDebugStatus: () => get<DebugStatus>('/debug/status'),
```

---

## UI — DebugPanel Component

### `ui/src/components/shared/DebugPanel.tsx`

Self-contained component. Props: none (reads no external state — all data fetched internally).

**Logs tab behaviour:**
- Polls `api.getLogs(undefined, 100)` every 2s via `useQuery({ refetchInterval: 2000 })`
- Renders lines newest-at-bottom, auto-scrolls to bottom on new lines (scroll pinned unless user has scrolled up)
- Level filter pills: `inf` / `wrn` / `err` — toggled client-side (no re-fetch, filter the in-memory result)
- Clear button: clears displayed lines client-side only (does not call any endpoint — just empties local state until next poll)
- Colour coding: INFO → `var(--text-dim)`, WARNING → `var(--amber)`, ERROR → `var(--red)`

**Status tab behaviour:**
- Polls `api.getDebugStatus()` every 5s via `useQuery({ refetchInterval: 5000 })`
- Sections: Daemon, Gateway, Chroma, Last Error
- Gateway `reachable: true` → green dot; `false` → red dot
- `last_error: null` → show `—` in muted text

**Panel header:**
- Title: `⬡ debug` in accent colour
- Dot: green if daemon status is `capturing`, amber if `paused`, red if unreachable
- `✕ close` button on the right — calls `onClose` prop (passed from `App.tsx`)

**Width:** 270px fixed, `shrink-0`.

---

## UI — App.tsx Changes

Three additions to `App.tsx`:

1. **State:** `const [debugOpen, setDebugOpen] = useState(false)`

2. **Sidebar button** — inserted between the nav list and the `<DaemonStatus>` block:
```tsx
<button onClick={() => setDebugOpen(o => !o)} /* styled as debug-btn */>
  ⬡ debug
</button>
```
Styling: when `debugOpen`, accent background + accent text; when closed, muted background + muted text.

3. **Panel rendering** — inside the content `<div>`, alongside `<main>`:
```tsx
<div className="flex flex-col flex-1 min-w-0 overflow-hidden">
  <StatsBar />
  <div className="flex flex-1 min-h-0 overflow-hidden">
    <main className="flex-1 overflow-auto">
      <Routes>…</Routes>
    </main>
    {debugOpen && <DebugPanel onClose={() => setDebugOpen(false)} />}
  </div>
</div>
```

The `DebugPanel` sits at the same level as `<main>`, so it spans the full height below the `StatsBar` and is unaffected by route changes.

---

## Behaviour Summary

| Action | Result |
|---|---|
| Click ⬡ debug (closed) | Panel opens, button highlights, logs tab shown |
| Click ⬡ debug (open) | Panel closes, button returns to muted |
| Click ✕ in panel header | Panel closes |
| Navigate to different route | Panel stays open |
| Toggle level filter pill | Filters rendered lines client-side, no re-fetch |
| Click clear | Clears rendered lines until next 2s poll |
| Switch to status tab | Loads /debug/status, polls every 5s |

---

## Out of Scope

- Persisting debug panel open/closed state across app restarts
- Searching/filtering log lines by text
- Log line expand-on-click for full message
- Exporting logs to file
- WebSocket / SSE streaming (polling every 2s is sufficient)
