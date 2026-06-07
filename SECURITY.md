# Security Policy

2brn is a local-first application that captures your screen, runs OCR, and stores
activity data on your own machine. Because of the sensitive nature of that data,
we take security reports seriously.

## Supported versions

This project is pre-1.0 and under active development. Security fixes are applied
to the latest `main` branch. There are no maintained older release lines yet.

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues,
discussions, or pull requests.**

Instead, report privately through GitHub's built-in private vulnerability
reporting:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**
   (<https://github.com/SasidharanGS/2brn/security/advisories/new>).
3. Describe the issue, including steps to reproduce and the potential impact.

You should receive an acknowledgement within a few days. We'll work with you to
understand and fix the issue, and we'll credit you in the advisory unless you'd
prefer to remain anonymous.

## Scope and good-faith guidelines

The following are especially relevant to 2brn's threat model:

- **Local data at rest** — the SQLite database, ChromaDB store, and screenshots
  under `~/.2brn/`. Screenshots can be AES-256-GCM encrypted.
- **Secret handling** — API keys and plugin secrets are stored in the OS keychain
  and must never be written to disk or logs.
- **The local API** — the daemon listens on `127.0.0.1:7842` (loopback only).
- **The plugin system** — plugins are local MCP servers launched as subprocesses
  over stdio. Reports about sandboxing, argument injection, or secret leakage are
  welcome.

When researching, please act in good faith: only test against your own local
installation, don't access or exfiltrate other people's data, and don't run
denial-of-service or destructive tests.

## What is *not* a vulnerability

- The app captures your own screen by design; that is the core feature, not a
  data leak.
- Sending your data to an AI provider *you explicitly configured* is expected
  behaviour. Choose a local provider (e.g. Ollama) if you want zero outbound data.
