# 2brn — Improvements (June 2026)

A round of hardening across the daemon and UI, plus open-source scaffolding. All
changes are on this branch; `main` is unchanged. Everything below is verified:
the daemon passes `ruff` + `pyright` + the full `pytest` suite (316 passing),
and the UI passes `tsc --noEmit`.

> One thing still needs a manual check: the **end-to-end Electron auth flow**
> (the daemon now requires a token the UI reads from `~/.2brn/api_token`). The
> daemon middleware and UI types are tested, but the packaged app wasn't launched
> here — please run it once to confirm.

---

## 1. Open-source setup

- `LICENSE` (MIT), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`.
- `.github/`: bug/feature issue forms, PR template, Dependabot (uv + pnpm + Actions).
- CI: added a UI typecheck/build job (was daemon-only).
- Tooling: `.editorconfig`, `.pre-commit-config.yaml` (ruff + tsc), `pre-commit` dev dep.

## 2. Correctness & security fixes (highest impact)

- **RAG chat survives restart.** `ChromaStore` counted documents in an in-process
  counter that reset to 0 on every start, so "ask about your day" returned empty
  results after each restart. It now reads the live collection count.
- **Local-day timezone handling.** Timestamps are stored in UTC, but journals,
  blogs, insights, and date-filtered chat now bucket by the user's **local** day
  (previously UTC, giving wrong-day results for non-UTC users). Activities are
  also stamped at **capture** time, not inference time, so a processing backlog
  no longer re-dates them. New `timeutil.py` + timezone-pinned tests.
- **Local API authentication.** The daemon (loopback `127.0.0.1`) had no auth and
  permissive CORS. It now requires a per-machine bearer token (`~/.2brn/api_token`,
  `0600`) on every endpoint except the `/status` health probe; CORS is narrowed;
  the UI attaches the token automatically. Plugin commands can no longer be a bare
  shell (blocks the `sh -c '<arbitrary>'` path).

## 3. Reliability & polish

- **Plugins (MCP):** writes to the server are serialized (concurrent tool calls
  no longer corrupt the JSON-RPC stream); a large tool result no longer overflows
  the 64 KiB read buffer and hangs every pending call (now 16 MiB).
- **Database:** new `get_conn()` helper enables `foreign_keys` (so `ON DELETE
  CASCADE` is reliable) and a `busy_timeout` (fewer "database is locked" errors
  under concurrent writers), adopted in the write and cascade-delete paths.
- **Purge:** screenshot files are deleted only **after** the DB rows are committed
  (a crash mid-purge no longer leaves rows pointing at missing files).
- **Background jobs:** long-running resync/encrypt tasks are kept referenced so the
  GC can't cancel them mid-run.
- **UI:** chat no longer leaves a blinking cursor after you navigate away; Journal /
  Blog / Insights show a real error state instead of "no data" when a request fails;
  deleting a user instruction now asks for confirmation.

## 4. Performance & further robustness

- **Plugins:** concurrent tool executions are capped (an event burst can't pile up);
  a timed-out tool call is recorded as `timeout` (not a generic error); plugin secret
  values are scrubbed from stored/returned error messages; one plugin's slow startup
  no longer blocks the others.
- **API:** the journal/blog generate endpoints return `400` on a malformed date (was a
  `500`); `GET /captures` uses an index-friendly, local-day range query.
- **Event loop:** capture-image read/decrypt and ChromaDB `count()` calls now run off
  the event loop, so they no longer stall capture / inference / HTTP.

---

## Project layout

- `daemon/` — Python 3.12 backend (FastAPI), managed by **uv**. Tests:
  `cd daemon && uv run --extra dev pytest tests/`.
- `ui/` — Electron + React + TypeScript, managed by **pnpm**. Typecheck:
  `cd ui && pnpm exec tsc --noEmit`.

See `README.md` for setup and `CONTRIBUTING.md` for the dev workflow.

## Known follow-ups (not done here)

- Migrate the remaining read-path DB call sites to `get_conn()` (mechanical).
- Batch embeddings in the manual "Resync ChromaDB" job; validate plugin-rule args
  against the tool schema; move the optional Joplin watcher's writes off the loop.
- Product ideas from the review: an in-app health surface (embed backlog, queue
  depth) and activity durations.
- Already-embedded activities keep a UTC date tag until a one-off **Settings →
  Resync ChromaDB**; new activities use the local date.
- Remaining low/polish items from the review report.
