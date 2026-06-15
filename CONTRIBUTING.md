# Contributing to 2brn

Thanks for your interest in improving 2brn! This is a local-first "second brain"
desktop app — a Python daemon plus an Electron UI. The notes below get you from a
fresh clone to a green pull request.

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Project layout

```
daemon/   Python 3.12 backend (FastAPI + APScheduler), managed by uv
ui/       Electron + React + TypeScript front-end, managed by pnpm
docs/     Architecture and design docs
```

The two sub-projects are independent and have their own toolchains — work in the
one your change touches.

## Prerequisites

- **Python 3.12+** with [uv](https://docs.astral.sh/uv/)
- **Node.js 20+** with [pnpm](https://pnpm.io/)
- **Tesseract OCR** — `brew install tesseract` / `apt install tesseract-ocr`

## Getting started

```bash
# Daemon
cd daemon
uv sync --extra dev
uv run python -m brn_daemon.main      # starts the API on http://127.0.0.1:7842

# UI (in a second terminal)
cd ui
pnpm install
pnpm electron:dev
```

## Development workflow

### Daemon (Python)

```bash
cd daemon
uv run ruff check src/                 # lint
uv run ruff format src/                # format
uv run pyright src/brn_daemon          # type-check
uv run --extra dev pytest tests/ -v    # tests
```

CI enforces lint, type-check, and tests with a **coverage floor of 60%**
(`--cov-fail-under=60`). Please add or update tests alongside behaviour changes.

### UI (TypeScript)

```bash
cd ui
pnpm exec tsc --noEmit                 # type-check
pnpm lint                              # eslint src
pnpm test                              # vitest run (unit tests for hooks/helpers)
pnpm build                             # tsc + vite build
```

### Pre-commit hooks

We use [pre-commit](https://pre-commit.com/) to run the same checks locally that
CI runs. Install the git hook once after cloning:

```bash
cd daemon
uv run pre-commit install              # installs into the repo's .git/hooks
uv run pre-commit run --all-files      # optional: run against the whole tree
```

The hooks run `ruff` (lint + format) on changed Python files and
`tsc --noEmit` when UI sources change.

## Branches and commits

- Branch off `main`. Use a descriptive prefix, e.g. `feat/…`, `fix/…`,
  `chore/…`, `docs/…`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat:`, `fix:`, `refactor:`, `chore:`, `docs:`, `ci:`, `perf:`, `test:`.
  Scopes are encouraged, e.g. `feat(daemon): …`, `fix(ui): …`.

## Pull requests

1. Make sure lint, type-check, and tests pass locally for the sub-project(s) you
   touched.
2. Open a PR against `main` and fill in the template.
3. CI must be green before merge.

## Design principles

2brn has a few constraints that every change should respect — they're what make
the project trustworthy:

- **Local-first.** All user data stays on the user's machine / local
  infrastructure. Nothing is sent to third-party clouds by default. The user's
  chosen AI provider is the only outbound dependency, and it is configurable
  (including fully local options like Ollama / LM Studio).
- **Graceful degradation.** If the daemon, the AI provider, or an integration is
  unavailable, the app must not crash or lose data — capture and core features
  keep working.
- **Additive changes.** Prefer extending behaviour over changing it. Don't break
  existing journals, captures, or plugin rules.
- **No secrets on disk.** API keys and plugin secrets live in the OS keychain,
  never in config files or the database.

## Reporting bugs and requesting features

Use the [issue templates](https://github.com/SasidharanGS/2brn/issues/new/choose).
For anything security-sensitive, follow [SECURITY.md](SECURITY.md) instead of
opening a public issue.

When sharing logs or reproductions, **scrub anything private** — 2brn captures
your screen, so OCR text, journal content, and screenshots may contain sensitive
data you don't want in a public issue.
