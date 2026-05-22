# 2brn — Second Brain

A local-first personal productivity companion. Captures your screen every 60 seconds, runs OCR, uses an AI provider of your choice to infer what you were doing, and gives you a chat interface to ask questions about your day.

## Features

- 📸 **Screen capture** — periodic screenshots with active app detection
- 🔍 **OCR + AI inference** — Tesseract extracts text; your AI provider infers activity summary, task category (`work` / `research` / `play` / `learning` / `communication` / `creative` / `admin` / `other`) and productivity state (`productive` / `focused` / `chilling` / `procrastinating` / `distracted` / `in-meeting` / `idle`)
- 🧠 **Semantic search** — ChromaDB embeddings over all activities
- 📓 **Joplin integration** — notes are embedded alongside screen activities; daily journal mirrored to Joplin
- 💬 **Chat** — ask questions about your day, get answers grounded in what you actually did
- 📊 **Insights** — daily and weekly productivity breakdowns
- 🔐 **Screenshot encryption** — AES-256-GCM at-rest encryption for screenshots
- 🖥️ **Cross-platform** — macOS, Windows, Linux via Electron + Python

## Prerequisites

- **Python 3.12+** with [uv](https://docs.astral.sh/uv/) installed
- **Node.js 20+** with [pnpm](https://pnpm.io/) installed
- **Tesseract OCR** — `brew install tesseract` / `apt install tesseract-ocr`
- **An AI provider** for chat and embeddings — any OpenAI-compatible endpoint works:
  - [OpenAI](https://platform.openai.com/) — `base_url: https://api.openai.com/v1`
  - [Ollama](https://ollama.com/) (local, no API key needed) — `base_url: http://localhost:11434/v1`
  - [LM Studio](https://lmstudio.ai/) (local) — `base_url: http://localhost:1234/v1`
  - [Groq](https://groq.com/), [Together AI](https://www.together.ai/), [Anthropic](https://anthropic.com/), or any other litellm-supported provider
  - Any OpenAI-compatible proxy or corporate gateway

## Quick Start

### 1. Start the daemon

```bash
cd daemon
uv sync
uv run python -m brn_daemon.main
```

### 2. Start the UI

```bash
cd ui
pnpm install
pnpm electron:dev
```

### 3. Configure your AI provider

Open the app → **Settings** → fill in your **Chat Provider** and **Embed Provider** details. Your API key is stored securely in the OS keychain (never written to disk).

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Electron UI (React + TypeScript)                       │
│  Dashboard │ Chat │ Journal │ Timeline │ Insights        │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (port 7842)
┌──────────────────────▼──────────────────────────────────┐
│  Python Daemon (FastAPI)                                │
│  capture → OCR → inference → embed → journal → chat     │
│                                                         │
│  LOCAL STORAGE          AI Provider (your choice)       │
│  SQLite + ChromaDB  ←→  /v1/chat/completions            │
│  ~/.2brn/               /v1/embeddings                  │
└─────────────────────────────────────────────────────────┘
```

## Configuration

All config lives in `~/.2brn/config.json`. The easiest way to edit it is through the Settings UI.

| Setting | Description |
|---|---|
| Chat Provider | LLM for activity inference, journal generation, and chat |
| Embed Provider | Embeddings for semantic search — must be OpenAI-compatible or Custom format |
| Capture interval | Seconds between screenshots (default: 60) |
| Purge months | Auto-delete screenshots older than N months (default: 12) |

### Embed provider types

- **`openai_compatible`** — standard OpenAI `/v1/embeddings` format (`{"input": [...]}` → `{"data": [{"embedding": [...]}]}`)
- **`custom`** — non-standard format used by some gateways (`{"inputs": [...]}` → `{"data": {"embeddings": [[...]]}}`)

## Joplin Integration

If you use [Joplin](https://joplinapp.org/) as your notes app, 2brn will embed your notes into the same semantic index as your screen activities. See [docs/integrations.md](docs/integrations.md) for setup details.

## Auto-start (macOS)

```bash
cp daemon/com.2brn.daemon.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.2brn.daemon.plist
```

## Tech Stack

| Component | Technology |
|---|---|
| UI | Electron 31, React 19, TypeScript, Tailwind CSS |
| Daemon | Python 3.12, FastAPI, APScheduler |
| OCR | Tesseract via pytesseract |
| LLM chat | litellm (100+ providers) |
| Embeddings | Custom EmbedClient protocol (OpenAI-compatible + custom format) |
| Vector store | ChromaDB |
| Database | SQLite via aiosqlite |
| Encryption | AES-256-GCM via cryptography |

## Development

```bash
# Run daemon tests
cd daemon && uv run --extra dev pytest tests/ -v

# TypeScript check
cd ui && pnpm exec tsc --noEmit
```

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, the
development workflow, and the project's design principles, and please review our
[Code of Conduct](CODE_OF_CONDUCT.md). To report a security issue, follow
[SECURITY.md](SECURITY.md) — don't open a public issue.

## License

[MIT](LICENSE) © 2026 SasidharanGS
