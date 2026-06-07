# 2brn — Improvements (June 2026)

A round of hardening across the daemon and UI, plus open-source scaffolding. This
work has since been merged into `main` (together with the `feat/mobile-bridge`
daemon branch) and pushed to `origin/main`. Everything below is verified:
the daemon passes `ruff`, `pyright` (0 errors), and the full `pytest` suite
(**319 passing, 1 skipped**), and the UI passes `tsc --noEmit`.

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
- **Plugins (more):** out-of-range schedule times and `args_template` keys not in the
  tool's schema are rejected at save time; JSON-RPC ids are normalized; live plugin
  subprocesses are capped (LRU eviction).
- **Data & resilience:** the manual ChromaDB resync embeds in batches; the heal pass
  keeps real tags and drains fully; purge subtracts whole calendar months and deletes
  files only after the DB commit; activity override takes a request body and 404s on a
  missing id; edits refresh `generated_at`; config reads run off the loop.
- **Quality & a11y:** input validation, env-var fallbacks, per-monitor screenshot
  filenames, the blog honoring user instructions, dropped-inference + queue-depth
  health metrics, Joplin note chunking that preserves markdown structure, accessible
  Toggle/Btn, centralized query keys, an ErrorBoundary "Try again", and AI-client
  setters in place of private-attribute pokes.

## 5. Code-review coverage

This round worked through the **entire** 2026-06-08 deep code review
(`2brn-code-review.html`): 62 tracked findings across 9 areas plus 5 cross-cutting
themes. Every finding is either implemented here or listed under "Known follow-ups"
below with a reason — nothing was silently dropped.

| Review area | # | Status |
|---|---|---|
| Cross-cutting themes | 5 | Timezone · RAG-count · auth/CORS · DB-access · off-loop — all addressed (two carry a documented tail) |
| Capture & data pipeline (`F-CORE`) | 7 | All addressed |
| RAG / AI layer (`F-RAG`) | 5 | All addressed |
| API routes (`F-ROUTE`) | 10 | All addressed |
| Plugin security (`F-SEC`) | 11 | All addressed |
| UI — Electron / React (`F-UI`) | 10 | 8 implemented; CSP + history-polling deferred |
| Architecture (`A`) | 7 | 5 implemented; A-1 deferred, A-2 done for write paths |
| Performance (`P`) | 6 | 4 implemented; mss-thread + cheaper-hash are deliberate skips |
| Product (`F-PROD`) | 6 | 4 implemented; durations + cross-platform deferred |

About **49 of the 62 findings are fully implemented, committed, and covered by the
test suite**; the rest are the deliberate calls listed below.

---

## Project layout

- `daemon/` — Python 3.12 backend (FastAPI), managed by **uv**. Tests:
  `cd daemon && uv run --extra dev pytest tests/`.
- `ui/` — Electron + React + TypeScript, managed by **pnpm**. Typecheck:
  `cd ui && pnpm exec tsc --noEmit`.

See `README.md` for setup and `CONTRIBUTING.md` for the dev workflow.

## Known follow-ups (intentionally not done here)

Two kinds: **deliberate skips** (the review suggested a change, but the current code
is the better choice once you check it) and **deferrals** (need hardware, a product
decision, or runtime testing — or are cosmetic with no functional gain).

**Deliberate skips**

- **Cheaper dedup hash** (`F-CORE-5` / `P-2`) — the review suggested swapping the
  wavelet hash for `pHash`/`dHash`. Tested: those collapse near-identical flat
  capture frames and hurt dedup quality, so the wavelet hash is kept on purpose
  (only the misleading function name/docstring was corrected).

**Deferrals**

- **Cross-platform verification** (`F-PROD-5`) — Windows/Linux active-app detection
  and tesseract resolution need those platforms to actually test.
- **Activity durations** (`F-PROD-3`) — the `ended_at` column is unused; populating
  it needs a decision on what a "duration" means and UI to display it.
- **A renderer Content-Security-Policy** (`F-UI-10`) — worth adding, but must be
  tested against both the Vite dev server and the packaged app (a strict CSP breaks
  Vite's dev-mode inline scripts), which requires running the app.
- **Remaining read-path DB calls → `get_conn()`** (`A-2` tail) — purely stylistic:
  in WAL mode reads don't take the write lock, so they gain nothing from the
  foreign-keys / busy-timeout that the write paths now use.
- **A dedicated capture thread + a reused connection in the capture loop**
  (`P-1` / `P-4`) — at ~1 capture/sec the per-tick executor and per-op connection are
  not a bottleneck.
- **Folding journal/blog into one generator** (`A-1`) — structural only; the drift it
  was meant to prevent (the blog ignoring user instructions) is already fixed.
- **The optional Joplin watcher's ChromaDB upsert off the loop** — that integration is
  off by default.
- **ExecutionHistory polling → `invalidateQueries`** (`F-UI-9` sub-item) — minor; the
  5 s poll is harmless while the panel is mounted.
- Already-embedded activities keep a UTC date tag until a one-off **Settings → Resync
  ChromaDB**; new activities use the local date.
