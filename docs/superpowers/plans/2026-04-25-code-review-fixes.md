# 2brn Code Review — Issue Tracker & Fix Log

> Generated: 2026-04-25 after TanStack Query migration  
> Scope: Full stack — Python daemon + React UI  
> Status key: ⬜ pending | 🔄 in progress | ✅ fixed | ⏭ deferred  
> **All issues resolved 2026-04-25**

---

## Commit Summary

| Commit | Description |
|--------|-------------|
| `35762cc` | fix(tier1): journal conflict target, bounded inference queue, remove chat_complete stream param, propagate keyring errors |
| `819f920` | fix(tier2): reuse httpx client, embed_batch, range-bound queries, poll cursor, journal guard, empty chroma guard, single DB conn per tick, dedup get_brn_home, CATEGORY_COLORS extracted |
| `680113e` | fix(tier3): Config field default, IntegrityError-only 409, OCR timeout warning, dead code removed, MAX_OCR_CHARS constant, shared ChromaStore in app_state |

---

## 🔴 Tier 1 — Critical (data corruption / OOM / silent data loss)

| ID | Status | File | Issue |
|----|--------|------|-------|
| L1 | ✅ | `routes/journal_routes.py:46` | `ON CONFLICT(date)` missing label — breaks journal PUT for morning/evening entries |
| L2 | ✅ | `main.py` inference queue | Unbounded queue — OOM risk when gateway is down for hours |
| L3 | ✅ | `gateway.py:37` | `chat_complete(stream=True)` silently returns None / crashes |
| E1 | ✅ | `config.py:88` | `set_gateway_token` swallows keyring errors — token silently not saved |

---

## 🟠 Tier 2 — High (performance bottlenecks, real logic bugs)

| ID | Status | File | Issue |
|----|--------|------|-------|
| P1 | ✅ | `joplin_watcher.py:146` | Bulk embed: 148 sequential HTTP calls on startup (~45s) |
| P2 | ✅ | `gateway.py:75` | New `httpx.AsyncClient` per embed call — connection per request |
| P3 | ✅ | `insights_routes.py:10` | `date(started_at)` in WHERE prevents index use |
| L4 | ✅ | `joplin_watcher.py:198` | Poll cursor advances past failed embeds — notes never retried |
| L5 | ✅ | `journal_routes.py:30` | No concurrency guard on generate — double LLM call on double-click |
| E3 | ✅ | `embeddings.py:51` | `ChromaStore.query()` throws on empty collection (unlike `query_notes`) |
| P4 | ✅ | `main.py:_capture_loop` | New DB connection per monitor per tick |
| Q1 | ✅ | `config.py:28` + `db.py:5` | `get_brn_home()` duplicated in both files |
| Q2 | ✅ | `main.py:17` | `capture_all_monitors` import now unused |
| Q3 | ✅ | `Timeline.tsx` + `Insights.tsx` | `CATEGORY_COLORS` copy-pasted in both components |

---

## 🟡 Tier 3 — Medium / polish

| ID | Status | File | Issue |
|----|--------|------|-------|
| P5 | ✅ | `joplin_watcher.py:218` | Per-chunk serial embeds within a note (follow-on to P1/P2) |
| P6 | ✅ | `settings_routes.py:148` | `ChromaStore()` re-instantiated on every `/chroma-status` request |
| L7 | ✅ | `config.py:18` | Mutable default in Config dataclass |
| L8 | ✅ | `settings_routes.py:83` | `except Exception` masks real DB errors as "already excluded" |
| E2 | ✅ | `ocr.py` | Silent OCR timeout produces empty inference with no warning |
| E4 | ✅ | `journal.py:173` | Dead code in `JournalMirror._find_daily_note` |
| Q4 | ✅ | `inference.py:34` | Magic number `2000` for OCR truncation |

---

## Fix Details

### ✅ L1 — `ON CONFLICT(date)` wrong in journal PUT route

**File:** `daemon/src/brn_daemon/routes/journal_routes.py`  
**Problem:** `ON CONFLICT(date)` does not match the actual unique index `(date, COALESCE(label, ''))`. Morning/evening journal PUTs would throw unhandled `IntegrityError`.  
**Fix:** Changed to `ON CONFLICT(date, COALESCE(label, ''))`.  
**Commit:** `35762cc`

---

### ✅ L2 — Unbounded inference queue

**File:** `daemon/src/brn_daemon/inference.py`  
**Problem:** `asyncio.Queue()` with no maxsize. Gateway downtime → queue grows until OOM.  
**Fix:** `asyncio.Queue(maxsize=500)`. `enqueue` uses `put_nowait` + catches `QueueFull` with a warning log and drop.  
**Commit:** `35762cc`

---

### ✅ L3 — `chat_complete(stream=True)` silent crash

**File:** `daemon/src/brn_daemon/gateway.py`  
**Problem:** Streaming response doesn't have `.choices[0].message.content`.  
**Fix:** Removed `stream` parameter entirely. Callers must use `chat_stream()` for streaming.  
**Commit:** `35762cc`

---

### ✅ E1 — `set_gateway_token` silently swallows errors

**File:** `daemon/src/brn_daemon/config.py`  
**Problem:** `except Exception: pass` — token silently not saved if keychain fails.  
**Fix:** Log warning + raise `RuntimeError`. Settings route catches it and returns HTTP 500.  
**Commit:** `35762cc`

---

### ✅ P2 — New `httpx.AsyncClient` per embed call

**File:** `daemon/src/brn_daemon/gateway.py`  
**Problem:** New TCP connection per embed request.  
**Fix:** Persistent `self._http = httpx.AsyncClient(...)` instance. Closed via `await gateway.aclose()` on shutdown.  
**Commit:** `819f920`

---

### ✅ P1 + P5 — Sequential embed calls → `embed_batch`

**Files:** `gateway.py`, `joplin_watcher.py`  
**Problem:** 148 notes × N chunks, each awaited serially = hundreds of HTTP round-trips on startup.  
**Fix:** Added `GatewayClient.embed_batch(texts: list[str])` — sends all texts in one `inputs:[...]` call. `JoplinWatcher._embed_note` now batches all chunks of a note in one call. `embed(text)` delegates to `embed_batch([text])`.  
**Commit:** `819f920`

---

### ✅ P3 — `date()` function prevents index use

**Files:** `insights_routes.py`, `activities.py`, `journal.py`  
**Problem:** `WHERE date(started_at) = ?` applies function to every row, defeating the `idx_activities_started_at` index.  
**Fix:** Changed to range bounds: `WHERE started_at >= 'DATE T00:00:00' AND started_at <= 'DATE T23:59:59.999999'`. Index is now used for all date-filtered queries.  
**Commit:** `819f920`

---

### ✅ L4 — Poll cursor advances past failed embeds

**File:** `joplin_watcher.py`  
**Problem:** `_last_poll_ms` advanced to max of all polled notes, including failed ones. Failed notes never retried.  
**Fix:** Track `max_embedded_ms` separately, only advance cursor for successfully embedded notes.  
**Commit:** `819f920`

---

### ✅ L5 — No concurrency guard on journal generation

**File:** `routes/journal_routes.py`  
**Problem:** Double-click fires two concurrent LLM calls for same date.  
**Fix:** `app_state["journal_generating"]` set tracks in-progress dates. Returns HTTP 409 if date already generating. Cleared in `finally`.  
**Commit:** `819f920`

---

### ✅ E3 — `ChromaStore.query()` throws on empty collection

**File:** `embeddings.py`  
**Problem:** `query_notes()` had empty-collection guard; `query()` did not. First chat on fresh install crashed.  
**Fix:** Added same `count == 0` early-return guard to `query()`, wrapped in try/except.  
**Commit:** `819f920`

---

### ✅ P4 — New DB connection per monitor per tick

**File:** `main.py`  
**Problem:** 2 connections/second on dual-monitor setup.  
**Fix:** Single `async with aiosqlite.connect(...)` per capture-loop tick, used for both exclusion lookup and all INSERTs.  
**Commit:** `819f920`

---

### ✅ Q1 — Duplicate `get_brn_home()` in config.py

**File:** `config.py`  
**Fix:** Removed private `_get_brn_home()`, imported `get_brn_home` from `db`.  
**Commit:** `819f920`

---

### ✅ Q2 — Unused import `capture_all_monitors`

**File:** `main.py`  
**Fix:** Removed from import line.  
**Commit:** `819f920`

---

### ✅ Q3 — `CATEGORY_COLORS` duplicated

**Files:** `Timeline.tsx`, `Insights.tsx`  
**Fix:** Extracted to `ui/src/utils/colors.ts`. Also extracted `STATE_COLORS`. Both components now import from there.  
**Commit:** `819f920`

---

### ✅ L7 — Mutable default in Config dataclass

**File:** `config.py`  
**Fix:** `excluded_apps: list[str] = field(default_factory=list)`. Removed `__post_init__`.  
**Commit:** `680113e`

---

### ✅ L8 — Exclusion error masks real DB errors

**File:** `settings_routes.py`  
**Fix:** Changed `except Exception` to `except aiosqlite.IntegrityError` for the 409.  
**Commit:** `680113e`

---

### ✅ E2 — OCR timeout silent

**File:** `ocr.py`  
**Fix:** Added explicit `except RuntimeError` branch (pytesseract raises this on timeout) with `logger.warning`.  
**Commit:** `680113e`

---

### ✅ E4 — Dead code in `JournalMirror._find_daily_note`

**File:** `journal.py`  
**Fix:** Removed the dead `self._api("GET", "/search", ...)` call and unused result variable.  
**Commit:** `680113e`

---

### ✅ Q4 — Magic number 2000 for OCR truncation

**File:** `inference.py`  
**Fix:** Added `MAX_OCR_CHARS = 2000` constant with explanatory comment. Used in `build_inference_prompt`.  
**Commit:** `680113e`

---

### ✅ P6 — `ChromaStore()` re-instantiated on chroma-status

**File:** `settings_routes.py`, `main.py`  
**Fix:** `app_state["chroma_store"]` stores the shared instance from lifespan. `/settings/chroma-status` reuses it.  
**Commit:** `680113e`

---

## Test results

```
50 passed, 1 warning in 2.03s  (all 50 tests green after all fixes)
```

Started at 49 tests, added 1 new test (`test_embed_batch_returns_list_of_lists`).

## Deferred / out of scope

| ID | Reason |
|----|--------|
| L6 | `get_active_app` multi-window title — now only used as fallback; low impact since per-monitor detection is the primary path |
| Q5 | `hasAutoSent` ref in Chat.tsx — works correctly, refactor adds no correctness value |
| Q6 | Purge scheduler UTC awareness — purge runs at 2am and has 6-month window; off-by-hours not meaningful |
