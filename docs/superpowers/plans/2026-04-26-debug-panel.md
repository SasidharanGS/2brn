# Debug Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a toggleable right-side debug panel to the 2brn app showing a live daemon log stream and a structured health/status snapshot, accessible from all pages via a sidebar button.

**Architecture:** Three layers — (1) a daemon-side in-memory log buffer + two new API endpoints (`GET /logs`, `GET /debug/status`); (2) new TypeScript types and API client methods; (3) a `DebugPanel.tsx` React component with Logs and Status tabs, wired into `App.tsx` with a sidebar toggle button. The panel sits alongside `<main>` so it persists across route changes.

**Tech Stack:** Python (FastAPI, Pydantic, httpx, logging), React 19, TypeScript, @tanstack/react-query, Tailwind v3 CSS variables

---

## File Map

| File | Action |
|---|---|
| `daemon/src/brn_daemon/log_buffer.py` | Create — circular buffer + logging handler |
| `daemon/src/brn_daemon/routes/debug_routes.py` | Create — `/logs` and `/debug/status` endpoints |
| `daemon/src/brn_daemon/main.py` | Modify — wire buffer handler + register debug router |
| `daemon/tests/test_log_buffer.py` | Create — tests for log buffer |
| `daemon/tests/test_debug_routes.py` | Create — tests for debug endpoints |
| `ui/src/api/types.ts` | Modify — add `LogLine`, `DebugStatus` interfaces |
| `ui/src/api/client.ts` | Modify — add `getLogs`, `getDebugStatus` |
| `ui/src/components/shared/DebugPanel.tsx` | Create — tabbed panel component |
| `ui/src/App.tsx` | Modify — debug state, sidebar button, panel render |

---

### Task 1: Log buffer module

**Files:**
- Create: `daemon/src/brn_daemon/log_buffer.py`
- Create: `daemon/tests/test_log_buffer.py`

- [ ] **Step 1: Write the failing tests**

Create `/Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/daemon/tests/test_log_buffer.py`:

```python
import logging
from brn_daemon.log_buffer import LogBuffer, LogBufferHandler, log_buffer


def test_buffer_appends_and_gets():
    buf = LogBuffer()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello world", args=(), exc_info=None
    )
    buf.append(record)
    lines = buf.get()
    assert len(lines) == 1
    assert lines[0]["msg"] == "hello world"
    assert lines[0]["level"] == "INFO"
    assert len(lines[0]["ts"]) == 8  # "HH:MM:SS"


def test_buffer_level_filter():
    buf = LogBuffer()
    for level, msg in [
        (logging.INFO, "info msg"),
        (logging.WARNING, "warn msg"),
        (logging.ERROR, "error msg"),
    ]:
        record = logging.LogRecord(
            name="test", level=level, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None
        )
        buf.append(record)

    warnings_and_errors = buf.get(level="WARNING")
    assert len(warnings_and_errors) == 2
    assert all(l["level"] in ("WARNING", "ERROR") for l in warnings_and_errors)

    errors_only = buf.get(level="ERROR")
    assert len(errors_only) == 1
    assert errors_only[0]["level"] == "ERROR"


def test_buffer_limit():
    buf = LogBuffer()
    for i in range(20):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=f"msg {i}", args=(), exc_info=None
        )
        buf.append(record)
    lines = buf.get(limit=5)
    assert len(lines) == 5
    # Should return the most recent 5
    assert lines[-1]["msg"] == "msg 19"


def test_buffer_max_lines_circular():
    buf = LogBuffer()
    buf.MAX_LINES = 5  # shrink for test
    for i in range(10):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=f"msg {i}", args=(), exc_info=None
        )
        buf.append(record)
    lines = buf.get()
    assert len(lines) == 5
    # Oldest should be gone, newest retained
    msgs = [l["msg"] for l in lines]
    assert "msg 0" not in msgs
    assert "msg 9" in msgs


def test_buffer_level_normalisation():
    buf = LogBuffer()
    for level, expected in [
        (logging.DEBUG, "DEBUG"),
        (logging.INFO, "INFO"),
        (logging.WARNING, "WARNING"),
        (logging.ERROR, "ERROR"),
        (logging.CRITICAL, "ERROR"),
    ]:
        record = logging.LogRecord(
            name="test", level=level, pathname="", lineno=0,
            msg="x", args=(), exc_info=None
        )
        buf.append(record)
    lines = buf.get()
    levels = [l["level"] for l in lines]
    assert "DEBUG" in levels
    assert "INFO" in levels
    assert "WARNING" in levels
    assert levels.count("ERROR") == 2  # ERROR + CRITICAL both map to ERROR


def test_handler_writes_to_buffer():
    buf = LogBuffer()
    handler = LogBufferHandler(buf)
    logger = logging.getLogger("test_handler")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.info("via handler")
    logger.removeHandler(handler)
    lines = buf.get()
    assert any(l["msg"] == "via handler" for l in lines)


def test_module_level_singleton_exists():
    assert log_buffer is not None
    assert isinstance(log_buffer, LogBuffer)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/daemon
uv run --extra dev pytest tests/test_log_buffer.py -v
```

Expected: `ModuleNotFoundError: No module named 'brn_daemon.log_buffer'`

- [ ] **Step 3: Create `log_buffer.py`**

Create `/Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/daemon/src/brn_daemon/log_buffer.py`:

```python
import logging
from collections import deque
from datetime import datetime


class LogBuffer:
    MAX_LINES = 500

    def __init__(self) -> None:
        self._buf: deque[dict] = deque(maxlen=self.MAX_LINES)

    def append(self, record: logging.LogRecord) -> None:
        level = self._normalise(record.levelno)
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        self._buf.append({"ts": ts, "level": level, "msg": record.getMessage()})

    def get(self, level: str | None = None, limit: int = 100) -> list[dict]:
        lines = list(self._buf)
        if level == "WARNING":
            lines = [l for l in lines if l["level"] in ("WARNING", "ERROR")]
        elif level == "ERROR":
            lines = [l for l in lines if l["level"] == "ERROR"]
        return lines[-limit:]

    @staticmethod
    def _normalise(levelno: int) -> str:
        if levelno >= logging.ERROR:
            return "ERROR"
        if levelno >= logging.WARNING:
            return "WARNING"
        if levelno >= logging.INFO:
            return "INFO"
        return "DEBUG"


class LogBufferHandler(logging.Handler):
    def __init__(self, buf: LogBuffer) -> None:
        super().__init__()
        self._buf = buf

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._buf.append(record)
        except Exception:
            self.handleError(record)


# Module-level singleton — imported by routes and main.py
log_buffer = LogBuffer()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/daemon
uv run --extra dev pytest tests/test_log_buffer.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add daemon/src/brn_daemon/log_buffer.py daemon/tests/test_log_buffer.py
git commit -m "$(cat <<'EOF'
feat(daemon): add in-memory circular log buffer

500-line deque with LogBufferHandler. Level normalisation maps
CRITICAL→ERROR. Module-level singleton shared across all modules.

Co-Authored-By: Claude Opus 4.6 <noreply@openclaude.dev>
EOF
)"
```

---

### Task 2: Debug API endpoints

**Files:**
- Create: `daemon/src/brn_daemon/routes/debug_routes.py`
- Create: `daemon/tests/test_debug_routes.py`
- Modify: `daemon/src/brn_daemon/main.py` (lines 27–31, 213–214, 225–231)

- [ ] **Step 1: Write the failing tests**

Create `/Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/daemon/tests/test_debug_routes.py`:

```python
import logging
import pytest
from httpx import AsyncClient, ASGITransport
from brn_daemon.log_buffer import log_buffer
from brn_daemon.main import app


@pytest.fixture(autouse=True)
def clear_log_buffer():
    """Clear the module-level log_buffer before each test."""
    log_buffer._buf.clear()
    yield
    log_buffer._buf.clear()


@pytest.mark.asyncio
async def test_get_logs_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/logs")
    assert resp.status_code == 200
    data = resp.json()
    assert "lines" in data
    assert isinstance(data["lines"], list)


@pytest.mark.asyncio
async def test_get_logs_returns_recent_lines():
    # Seed the buffer directly
    for msg in ["alpha", "beta", "gamma"]:
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None
        )
        log_buffer.append(record)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/logs?limit=10")
    assert resp.status_code == 200
    msgs = [l["msg"] for l in resp.json()["lines"]]
    assert "alpha" in msgs
    assert "gamma" in msgs


@pytest.mark.asyncio
async def test_get_logs_level_filter():
    for level, msg in [
        (logging.INFO, "info line"),
        (logging.WARNING, "warn line"),
        (logging.ERROR, "error line"),
    ]:
        record = logging.LogRecord(
            name="test", level=level, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None
        )
        log_buffer.append(record)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/logs?level=WARNING")
    lines = resp.json()["lines"]
    assert all(l["level"] in ("WARNING", "ERROR") for l in lines)
    assert not any(l["msg"] == "info line" for l in lines)


@pytest.mark.asyncio
async def test_get_debug_status_shape():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/debug/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "daemon" in data
    assert "gateway" in data
    assert "chroma" in data
    assert "last_error" in data
    assert "status" in data["daemon"]
    assert "reachable" in data["gateway"]
    assert "activity_memories" in data["chroma"]
    assert "note_memories" in data["chroma"]
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/daemon
uv run --extra dev pytest tests/test_debug_routes.py -v
```

Expected: `404` errors or import errors since the routes don't exist yet.

- [ ] **Step 3: Create `debug_routes.py`**

Create `/Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/daemon/src/brn_daemon/routes/debug_routes.py`:

```python
from fastapi import APIRouter, Query
from pydantic import BaseModel
import httpx

router = APIRouter()


class LogsResponse(BaseModel):
    lines: list[dict]


class DebugStatusResponse(BaseModel):
    daemon: dict
    gateway: dict
    chroma: dict
    last_error: dict | None


@router.get("/logs", response_model=LogsResponse)
async def get_logs(
    level: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    from brn_daemon.log_buffer import log_buffer
    return LogsResponse(lines=log_buffer.get(level=level, limit=limit))


@router.get("/debug/status", response_model=DebugStatusResponse)
async def get_debug_status():
    from brn_daemon.main import app_state
    from brn_daemon.config import load_config

    cfg = load_config()

    # Daemon section — reuse existing app_state
    daemon_section = {
        "status": "paused" if app_state.get("paused") else "capturing",
        "capture_count_today": app_state.get("capture_count_today", 0),
        "last_captured_at": app_state.get("last_captured_at"),
        "paused": bool(app_state.get("paused")),
    }

    # Gateway reachability — try /actuator/health with 3s timeout
    gateway_reachable = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{cfg.gateway_url}/actuator/health")
            gateway_reachable = r.status_code == 200
    except Exception:
        gateway_reachable = False

    gateway_section = {
        "url": cfg.gateway_url,
        "reachable": gateway_reachable,
        "model": cfg.llm_model,
    }

    # Chroma counts
    chroma = app_state.get("chroma_store")
    activity_count = 0
    note_count = 0
    if chroma is not None:
        try:
            activity_count = chroma.collection.count()
            note_count = chroma.note_collection.count()
        except Exception:
            pass

    chroma_section = {
        "activity_memories": activity_count,
        "note_memories": note_count,
    }

    # Last error from log buffer
    from brn_daemon.log_buffer import log_buffer
    errors = log_buffer.get(level="ERROR", limit=500)
    last_error = errors[-1] if errors else None

    return DebugStatusResponse(
        daemon=daemon_section,
        gateway=gateway_section,
        chroma=chroma_section,
        last_error=last_error,
    )
```

- [ ] **Step 4: Wire log buffer handler and register debug router in `main.py`**

In `/Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/daemon/src/brn_daemon/main.py`, make two changes:

**Change 1** — after `logging.basicConfig(...)` (line 30), add the buffer handler:

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Wire log buffer into root logger so all modules' logs are captured
from brn_daemon.log_buffer import log_buffer, LogBufferHandler
logging.getLogger().addHandler(LogBufferHandler(log_buffer))
```

**Change 2** — in `create_app()` (lines 213–231), add the debug router import and registration:

```python
def create_app() -> FastAPI:
    from brn_daemon.routes import status, captures, activities
    from brn_daemon.routes import journal_routes, chat_routes, settings_routes, insights_routes
    from brn_daemon.routes import debug_routes

    app = FastAPI(title="2brn Daemon", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_origin_regex=r"(file://.*|.*localhost.*)",
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(status.router)
    app.include_router(captures.router)
    app.include_router(activities.router)
    app.include_router(journal_routes.router)
    app.include_router(chat_routes.router)
    app.include_router(settings_routes.router)
    app.include_router(insights_routes.router)
    app.include_router(debug_routes.router)
    return app
```

- [ ] **Step 5: Run all tests**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/daemon
uv run --extra dev pytest tests/test_log_buffer.py tests/test_debug_routes.py -v
```

Expected: `11 passed`

- [ ] **Step 6: Run full suite to check for regressions**

```bash
uv run --extra dev pytest tests/ -v
```

Expected: all 50 existing tests + 11 new = `61 passed`

- [ ] **Step 7: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add daemon/src/brn_daemon/routes/debug_routes.py \
        daemon/tests/test_debug_routes.py \
        daemon/src/brn_daemon/main.py
git commit -m "$(cat <<'EOF'
feat(daemon): add /logs and /debug/status debug endpoints

GET /logs returns recent lines from in-memory log buffer with
optional level filter and limit. GET /debug/status returns daemon
state, gateway reachability, chroma counts, and last error.

Co-Authored-By: Claude Opus 4.6 <noreply@openclaude.dev>
EOF
)"
```

---

### Task 3: UI types and API client

**Files:**
- Modify: `ui/src/api/types.ts`
- Modify: `ui/src/api/client.ts`

- [ ] **Step 1: Add `LogLine` and `DebugStatus` to `types.ts`**

Open `/Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui/src/api/types.ts` and append at the end:

```typescript
export interface LogLine {
  ts: string  // "HH:MM:SS"
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

- [ ] **Step 2: Add `getLogs` and `getDebugStatus` to `client.ts`**

Open `/Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui/src/api/client.ts`.

First, add `LogLine` and `DebugStatus` to the import at the top:

```typescript
import type {
  DaemonStatus, CaptureRecord, ActivityRecord, JournalEntry,
  DailyInsights, AppSettings, AppExclusion, LogLine, DebugStatus
} from './types'
```

Then add the two new methods to the `api` object (after `getDailyInsights`):

```typescript
  getLogs: (level?: string, limit?: number) => {
    const q = new URLSearchParams()
    if (level) q.set('level', level)
    if (limit) q.set('limit', String(limit))
    return get<{ lines: LogLine[] }>(`/logs?${q}`)
  },
  getDebugStatus: () => get<DebugStatus>('/debug/status'),
```

- [ ] **Step 3: TypeScript check**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
nvm --version
pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/src/api/types.ts ui/src/api/client.ts
git commit -m "$(cat <<'EOF'
feat(ui): add LogLine, DebugStatus types and getLogs/getDebugStatus API methods

Co-Authored-By: Claude Opus 4.6 <noreply@openclaude.dev>
EOF
)"
```

---

### Task 4: DebugPanel component

**Files:**
- Create: `ui/src/components/shared/DebugPanel.tsx`

- [ ] **Step 1: Create `DebugPanel.tsx`**

Create `/Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui/src/components/shared/DebugPanel.tsx`:

```tsx
import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { LogLine } from '../../api/types'

interface Props {
  onClose: () => void
}

type Tab = 'logs' | 'status'
type LevelFilter = 'INFO' | 'WARNING' | 'ERROR'

export default function DebugPanel({ onClose }: Props) {
  const [tab, setTab] = useState<Tab>('logs')
  const [filters, setFilters] = useState<Set<LevelFilter>>(
    new Set(['INFO', 'WARNING', 'ERROR'])
  )
  const [cleared, setCleared] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const userScrolledUp = useRef(false)

  // ── Logs query ──────────────────────────────────────────────
  const { data: logsData } = useQuery({
    queryKey: ['debug-logs'],
    queryFn: () => api.getLogs(undefined, 100),
    refetchInterval: 2000,
    enabled: tab === 'logs',
  })

  // ── Status query ─────────────────────────────────────────────
  const { data: statusData } = useQuery({
    queryKey: ['debug-status'],
    queryFn: api.getDebugStatus,
    refetchInterval: 5000,
    enabled: tab === 'status',
  })

  // ── Auto-scroll to bottom unless user scrolled up ────────────
  useEffect(() => {
    if (cleared) return
    if (userScrolledUp.current) return
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logsData, cleared])

  function handleScroll() {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 8
    userScrolledUp.current = !atBottom
  }

  function toggleFilter(f: LevelFilter) {
    setFilters(prev => {
      const next = new Set(prev)
      if (next.has(f)) next.delete(f)
      else next.add(f)
      return next
    })
  }

  // ── Derive displayed lines ────────────────────────────────────
  const allLines: LogLine[] = cleared ? [] : (logsData?.lines ?? [])
  const visibleLines = allLines.filter(l => filters.has(l.level as LevelFilter))

  // ── Level colour ─────────────────────────────────────────────
  function levelColour(level: string): string {
    if (level === 'ERROR') return 'var(--red)'
    if (level === 'WARNING') return 'var(--amber)'
    if (level === 'INFO') return 'var(--text-dim)'
    return 'var(--text-dim)'
  }

  // ── Header dot colour based on daemon status ──────────────────
  const daemonStatus = statusData?.daemon?.status
  const dotColour = daemonStatus === 'capturing'
    ? 'var(--green)'
    : daemonStatus === 'paused'
    ? 'var(--amber)'
    : 'var(--red)'

  return (
    <div
      className="flex flex-col shrink-0 border-l overflow-hidden"
      style={{ width: 270, background: '#0b0b0f', borderColor: 'var(--border)' }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 shrink-0 border-b"
        style={{ height: 34, borderColor: 'var(--border)' }}
      >
        <div className="flex items-center gap-1.5">
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: dotColour }}
          />
          <span
            className="text-[10px] font-mono font-medium"
            style={{ color: 'var(--accent)' }}
          >
            ⬡ debug
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-[9px] font-mono hover:opacity-80 transition-opacity"
          style={{ color: 'var(--text-dim)' }}
        >
          ✕ close
        </button>
      </div>

      {/* Tabs */}
      <div className="flex shrink-0 border-b" style={{ borderColor: 'var(--border)' }}>
        {(['logs', 'status'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="px-3 py-1.5 text-[10px] font-mono transition-colors"
            style={{
              color: tab === t ? 'var(--accent)' : 'var(--text-dim)',
              borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent',
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-hidden">
        {tab === 'logs' && (
          <div
            ref={scrollRef}
            onScroll={handleScroll}
            className="h-full overflow-y-auto p-2"
          >
            {visibleLines.length === 0 ? (
              <p className="text-[9px] font-mono" style={{ color: 'var(--text-dim)' }}>
                no log lines
              </p>
            ) : (
              visibleLines.map((line, i) => (
                <div key={i} className="flex gap-1.5 mb-0.5 font-mono text-[9px] leading-[1.5]">
                  <span style={{ color: 'var(--text-dim)', flexShrink: 0 }}>{line.ts}</span>
                  <span style={{ color: levelColour(line.level), flexShrink: 0, width: 26, fontWeight: 700 }}>
                    {line.level.slice(0, 3)}
                  </span>
                  <span
                    className="overflow-hidden text-ellipsis whitespace-nowrap"
                    style={{ color: 'rgba(240,240,245,0.6)' }}
                    title={line.msg}
                  >
                    {line.msg}
                  </span>
                </div>
              ))
            )}
          </div>
        )}

        {tab === 'status' && (
          <div className="h-full overflow-y-auto p-2.5">
            {!statusData ? (
              <p className="text-[9px] font-mono" style={{ color: 'var(--text-dim)' }}>loading…</p>
            ) : (
              <>
                <StatusSection label="daemon">
                  <StatusRow k="status" v={statusData.daemon.status}
                    colour={statusData.daemon.status === 'capturing' ? 'var(--green)' : 'var(--amber)'} />
                  <StatusRow k="captures today" v={String(statusData.daemon.capture_count_today)}
                    colour="var(--accent)" />
                  <StatusRow k="last capture"
                    v={statusData.daemon.last_captured_at
                      ? statusData.daemon.last_captured_at.slice(11, 19)
                      : '—'} />
                  <StatusRow k="paused" v={String(statusData.daemon.paused)} />
                </StatusSection>

                <StatusSection label="gateway">
                  <StatusRow k="url" v={statusData.gateway.url} />
                  <StatusRow k="reachable"
                    v={statusData.gateway.reachable ? '● yes' : '● no'}
                    colour={statusData.gateway.reachable ? 'var(--green)' : 'var(--red)'} />
                  <StatusRow k="model" v={statusData.gateway.model} />
                </StatusSection>

                <StatusSection label="chroma">
                  <StatusRow k="activity_memories"
                    v={statusData.chroma.activity_memories.toLocaleString()}
                    colour="var(--accent)" />
                  <StatusRow k="note_memories"
                    v={statusData.chroma.note_memories.toLocaleString()}
                    colour="var(--accent)" />
                </StatusSection>

                <StatusSection label="last error">
                  {statusData.last_error ? (
                    <>
                      <StatusRow k="msg" v={statusData.last_error.msg} colour="var(--red)" />
                      <StatusRow k="at" v={statusData.last_error.ts} />
                    </>
                  ) : (
                    <StatusRow k="none" v="—" />
                  )}
                </StatusSection>
              </>
            )}
          </div>
        )}
      </div>

      {/* Footer — only on logs tab */}
      {tab === 'logs' && (
        <div
          className="flex items-center gap-1.5 px-2 shrink-0 border-t"
          style={{ height: 28, borderColor: 'var(--border)' }}
        >
          {(['INFO', 'WARNING', 'ERROR'] as LevelFilter[]).map(f => (
            <button
              key={f}
              onClick={() => toggleFilter(f)}
              className="text-[8px] font-mono px-1.5 py-0.5 rounded transition-colors"
              style={filters.has(f)
                ? { background: 'rgba(129,140,248,0.15)', color: 'var(--accent)', border: '1px solid rgba(129,140,248,0.3)' }
                : { background: 'transparent', color: 'var(--text-dim)', border: '1px solid rgba(255,255,255,0.08)' }
              }
            >
              {f === 'INFO' ? 'inf' : f === 'WARNING' ? 'wrn' : 'err'}
            </button>
          ))}
          <button
            onClick={() => { setCleared(true); setTimeout(() => setCleared(false), 2100) }}
            className="text-[8px] font-mono ml-auto hover:opacity-80"
            style={{ color: 'var(--text-dim)' }}
          >
            clear
          </button>
        </div>
      )}
    </div>
  )
}

// ── Small helpers ────────────────────────────────────────────────────────────

function StatusSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <div
        className="text-[8px] font-mono uppercase tracking-widest mb-1"
        style={{ color: 'var(--text-dim)' }}
      >
        {label}
      </div>
      {children}
    </div>
  )
}

function StatusRow({ k, v, colour }: { k: string; v: string; colour?: string }) {
  return (
    <div
      className="flex justify-between items-center py-0.5 font-mono text-[9px]"
      style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
    >
      <span style={{ color: 'var(--text-muted)' }}>{k}</span>
      <span style={{ color: colour ?? 'var(--text-dim)' }}>{v}</span>
    </div>
  )
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
nvm --version
pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/src/components/shared/DebugPanel.tsx
git commit -m "$(cat <<'EOF'
feat(ui): add DebugPanel component — tabbed logs + status panel

270px right-side panel. Logs tab: live stream, level filters,
auto-scroll, clear. Status tab: daemon/gateway/chroma/last-error.

Co-Authored-By: Claude Opus 4.6 <noreply@openclaude.dev>
EOF
)"
```

---

### Task 5: Wire DebugPanel into App.tsx

**Files:**
- Modify: `ui/src/App.tsx`

- [ ] **Step 1: Update `App.tsx`**

Replace the entire content of `/Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui/src/App.tsx` with:

```tsx
import { useState } from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard   from './components/Dashboard'
import Chat        from './components/Chat'
import Journal     from './components/Journal'
import Timeline    from './components/Timeline'
import Insights    from './components/Insights'
import Settings    from './components/Settings'
import DaemonStatus from './components/shared/DaemonStatus'
import StatsBar     from './components/shared/StatsBar'
import DebugPanel   from './components/shared/DebugPanel'

const NAV = [
  { to: '/',         label: 'Home',     icon: '⌂',  end: true },
  { to: '/chat',     label: 'Chat',     icon: '💬' },
  { to: '/journal',  label: 'Journal',  icon: '📔' },
  { to: '/timeline', label: 'Timeline', icon: '⏱' },
  { to: '/insights', label: 'Insights', icon: '◎' },
  { to: '/settings', label: 'Settings', icon: '⚙' },
]

export default function App() {
  const [debugOpen, setDebugOpen] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-base)' }}>

      {/* ── Sidebar ── */}
      <aside
        className="flex flex-col w-[200px] shrink-0 border-r"
        style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
      >
        {/* Logo */}
        <div
          className="flex items-center px-4 h-[52px] border-b shrink-0"
          style={{ borderColor: 'var(--border)' }}
        >
          <span className="font-mono text-[15px] font-semibold tracking-tight" style={{ color: 'var(--text)' }}>
            2<span style={{ color: 'var(--accent)' }}>brn</span>
          </span>
        </div>

        {/* Nav */}
        <nav className="flex-1 flex flex-col gap-0.5 p-2 pt-3 overflow-y-auto">
          {NAV.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className="flex items-center gap-2.5 px-3 py-2 rounded-[9px] text-[13px] transition-all duration-150 select-none"
              style={({ isActive }) => isActive
                ? { background: 'var(--accent-glow)', color: 'var(--text)', fontWeight: 500 }
                : { color: 'var(--text-muted)' }
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className="text-[13px] w-[18px] text-center shrink-0"
                    style={{ color: isActive ? 'var(--accent)' : undefined, opacity: isActive ? 1 : 0.55 }}
                  >
                    {item.icon}
                  </span>
                  {item.label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Debug button */}
        <div className="px-3 pb-1">
          <button
            onClick={() => setDebugOpen(o => !o)}
            className="w-full text-[11px] font-mono py-1.5 rounded-[7px] transition-all duration-150 border"
            style={debugOpen
              ? { background: 'var(--accent-glow)', color: 'var(--accent)', borderColor: 'rgba(129,140,248,0.35)' }
              : { background: 'var(--bg-surface-2)', color: 'var(--text-dim)', borderColor: 'var(--border)' }
            }
          >
            ⬡ debug
          </button>
        </div>

        {/* Daemon status */}
        <div className="px-4 py-3 border-t" style={{ borderColor: 'var(--border)' }}>
          <DaemonStatus />
        </div>
      </aside>

      {/* ── Content ── */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <StatsBar />
        <div className="flex flex-1 min-h-0 overflow-hidden">
          <main className="flex-1 overflow-auto">
            <Routes>
              <Route path="/"         element={<Dashboard />} />
              <Route path="/chat"     element={<Chat />} />
              <Route path="/journal"  element={<Journal />} />
              <Route path="/timeline" element={<Timeline />} />
              <Route path="/insights" element={<Insights />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </main>
          {debugOpen && <DebugPanel onClose={() => setDebugOpen(false)} />}
        </div>
      </div>

    </div>
  )
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
nvm --version
pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Smoke test in dev mode**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
pnpm electron:dev
```

Verify:
- ⬡ debug button appears in sidebar above daemon status
- Clicking it opens the right-side panel
- Logs tab shows live log lines (if daemon is running) or "no log lines" if not
- Status tab shows daemon/gateway/chroma sections
- Clicking ⬡ debug again or ✕ closes the panel
- Navigating between pages keeps the panel open

- [ ] **Step 4: Run full daemon test suite one more time**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/daemon
uv run --extra dev pytest tests/ -v
```

Expected: `61 passed`

- [ ] **Step 5: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/src/App.tsx
git commit -m "$(cat <<'EOF'
feat(ui): wire DebugPanel into App — sidebar toggle button and panel render

Panel sits alongside <main>, persists across route changes.
Button highlights when open, muted when closed.

Co-Authored-By: Claude Opus 4.6 <noreply@openclaude.dev>
EOF
)"
```
