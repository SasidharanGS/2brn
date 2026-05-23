# 2brn — Your Second Brain

A cross-platform desktop app that silently captures what you do on your computer, infers context using AI, and lets you recall anything through natural language chat.

## Features

- 📸 **Passive capture** — hybrid heartbeat (60s) + change detection via perceptual hash dedup; no redundant frames
- 🔍 **OCR + AI inference** — Tesseract extracts text; JLL GPT Gateway infers activity summary, task category (`work` / `research` / `play` / `learning` / `communication` / `creative` / `admin` / `other`) and productivity state (`productive` / `focused` / `chilling` / `procrastinating` / `distracted` / `in-meeting` / `idle`)
- 💬 **Chat interface** — RAG pipeline: ask "what was I doing last Tuesday?" and get accurate, context-grounded answers with streaming
- 📔 **Daily journal** — auto-generated first-person narrative of your day, editable, regeneratable
- 📊 **Insights** — time breakdown by category, productivity distribution, top apps by time spent
- 🔒 **Privacy-first** — raw screenshots never leave your machine; only extracted text summaries sent to the LLM gateway
- ⚙️ **App exclusions** — block sensitive apps (banking, password managers) from ever being captured

## Requirements

- **Python 3.12+** with [uv](https://docs.astral.sh/uv/)
- **Node.js 20+** with [pnpm](https://pnpm.io/)
- **Tesseract OCR**
  - macOS: `brew install tesseract`
  - Linux: `apt install tesseract-ocr`
  - Windows: [installer](https://github.com/UB-Mannheim/tesseract/wiki)
- **JLL GPT Gateway** running and accessible (default: `http://localhost:8888`)

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd 2brn
```

### 2. Start the daemon

```bash
cd daemon
uv sync
uv run python -m brn_daemon.main
```

The daemon starts on `http://127.0.0.1:7842`.

### 3. Start the UI

In a new terminal:

```bash
cd ui
pnpm install
pnpm electron:dev
```

### 4. Configure gateway token

Open the app → **Settings** → enter your JLL GPT Gateway Bearer token. It is stored securely in the OS keychain (not written to disk).

## Data Storage

All data lives in `~/.2brn/`:

| Path | Contents |
|------|----------|
| `2brn.db` | SQLite: captures, activities, journals, exclusions |
| `screenshots/YYYY/MM/DD/` | JPEG captures (~40–80KB each) |
| `chroma/` | ChromaDB vector embeddings for semantic search |
| `config.json` | App config (token stored in keychain, not here) |
| `daemon.log` | Rotating log file |

**Auto-purge:** screenshots older than 6 months are deleted automatically. Configurable in Settings.

## Architecture

```
┌────────────────────────────────────────┐
│  Electron + React UI (port 5173/app)   │
│  Dashboard · Chat · Journal · Timeline │
│  Insights · Settings                   │
└─────────────────┬──────────────────────┘
                  │ HTTP + SSE (localhost:7842)
┌─────────────────▼──────────────────────┐
│  Python 3.12 Daemon (FastAPI)          │
│  Capture → OCR → Inference Queue      │
│  ChromaDB · SQLite · APScheduler      │
└──────────┬─────────────────────────────┘
           │ OpenAI-compatible API
┌──────────▼─────────────────────────────┐
│  JLL GPT Gateway (localhost:8888)      │
│  Summarization · Embeddings · Chat    │
└────────────────────────────────────────┘
```

## Running Tests

```bash
cd daemon
uv run --extra dev pytest tests/ -v
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| App shell | Electron 31 |
| UI | React 19 + TypeScript + Tailwind CSS v4 |
| Charts | Recharts |
| Daemon | Python 3.12 + FastAPI + uvicorn |
| Screenshot | mss (cross-platform) |
| OCR | Tesseract + pytesseract |
| Dedup | imagehash (wavelet hash) |
| LLM client | openai SDK → JLL GPT Gateway |
| Structured storage | SQLite via aiosqlite |
| Vector search | ChromaDB (embedded) |
| Scheduling | APScheduler |
| Package management | uv (Python) + pnpm (Node) |
