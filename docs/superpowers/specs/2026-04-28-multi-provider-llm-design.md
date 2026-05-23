# Multi-Provider LLM Abstraction — Design Spec

**Date:** 2026-04-28  
**Branch:** `feat/multi-provider-llm`  
**Status:** Approved — ready for implementation

---

## Problem

2brn is hardwired to the JLL GPT Gateway. Every LLM call goes through `gateway.py`, which has JLL-specific logic baked in:
- Custom embed format: `{"inputs": [...]}` request, `{"data":{"embeddings":[...]}}` response
- `AsyncOpenAI` for chat, raw `httpx` for embeddings
- Single keychain key: `jll_gateway_token`
- Default model names: `GPT_4_1`, `text-embedding-ada-002`
- Settings UI hardcoded as "JLL GPT Gateway"

The goal is to make the provider layer pluggable — JLL GPT, OpenAI, Anthropic, Ollama, and any OpenAI-compatible URL — without changing a single line in the consumers (`inference.py`, `journal.py`, `blog.py`, `chat.py`, `embeddings.py`, `joplin_watcher.py`).

---

## Design Decisions

| Question | Decision |
|---|---|
| Architecture | Protocol + named adapters (Approach A) |
| Providers at launch | JLL GPT, OpenAI, Anthropic, Ollama, Custom URL |
| Chat vs embed providers | Separate — can use different providers for each |
| API key storage | OS keychain, one entry per provider (`2brn` service, `provider.<name>` username) |
| Config migration | Auto-upgrade v1 (`gateway_url/llm_model/embed_model`) → v2 (`chat_provider/embed_provider`) on load |
| Open-source friendliness | Protocol is the public contribution interface — add a new provider by writing one file |

---

## Section 1: The `LLMProvider` Protocol

**File:** `daemon/src/brn_daemon/providers/base.py`

```python
from typing import Protocol, AsyncIterator, runtime_checkable

@runtime_checkable
class LLMProvider(Protocol):
    async def chat_complete(self, messages: list[dict], model: str | None = None) -> str: ...
    async def chat_stream(self, messages: list[dict], model: str | None = None) -> AsyncIterator[str]: ...
    async def embed_batch(self, texts: list[str], model: str | None = None) -> list[list[float]]: ...
    async def embed(self, text: str, model: str | None = None) -> list[float]: ...
    async def aclose(self) -> None: ...
```

All existing callers use exactly these five methods on the `gateway` object today. No callers change.

`embed()` has a default implementation: `return (await self.embed_batch([text]))[0]`.

---

## Section 2: Provider Adapters

**Directory:** `daemon/src/brn_daemon/providers/`

### `jll.py` — JLL GPT Gateway
- Chat: `AsyncOpenAI(base_url=f"{base_url}/v1", api_key=token)` — OpenAI-compatible endpoint
- Embed: raw `httpx.AsyncClient` — JLL's non-standard format
  - Request: `POST /v1/embeddings` with `{"model": "...", "inputs": ["text1", ...]}`
  - Response: `{"success": true, "data": {"embeddings": [[...]]}}`
- Required config: `base_url`, `model`, `embed_model`, API key in keychain at `provider.jll`
- Retry: exponential backoff, 3 attempts (same as today)

### `openai.py` — OpenAI Direct
- Chat: `AsyncOpenAI(api_key=token)` (no base_url — uses api.openai.com)
- Embed: OpenAI SDK `client.embeddings.create(input=texts, model=model)` → standard `data[i].embedding`
- Required config: `model` (e.g. `gpt-4o`), `embed_model` (e.g. `text-embedding-3-small`), API key at `provider.openai`

### `anthropic.py` — Anthropic Direct
- Chat: `anthropic.AsyncAnthropic(api_key=token)` — Anthropic SDK
  - Maps OpenAI-style `messages` list (including system) to Anthropic's `system` + `messages` format
  - `chat_stream` uses Anthropic's streaming response
- Embed: raises `NotImplementedError("Anthropic does not support embeddings. Configure a separate embed provider.")`
- Required config: `model` (e.g. `claude-3-5-sonnet-20241022`), API key at `provider.anthropic`
- New Python dep: `anthropic>=0.30` (lazy import — only imported if this provider is instantiated)

### `ollama.py` — Ollama Local
- Chat: `AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")`
- Embed: `httpx.AsyncClient` → `POST http://localhost:11434/api/embed` with `{"model": "...", "input": ["text"]}`
  - Response: `{"embeddings": [[...]]}`
- Required config: `model` (e.g. `llama3`, `mistral`), `embed_model` (e.g. `nomic-embed-text`)
- No API key required (local)

### `custom.py` — Any OpenAI-compatible URL
- Chat: `AsyncOpenAI(base_url=base_url, api_key=token)`
- Embed: OpenAI SDK embeddings (standard format)
- Required config: `base_url`, `model`, `embed_model`, API key at `provider.custom`
- Use case: Azure OpenAI, Groq, Together, LM Studio, vLLM, etc.

### `__init__.py` exports
```python
from .base import LLMProvider
from .jll import JLLProvider
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .ollama import OllamaProvider
from .custom import CustomProvider

def make_chat_provider(cfg: "ProviderConfig") -> LLMProvider: ...
def make_embed_provider(cfg: "ProviderConfig") -> LLMProvider: ...
```

---

## Section 3: Config + Keychain

### `ProviderConfig` dataclass
```python
@dataclass
class ProviderConfig:
    name: str      # "jll" | "openai" | "anthropic" | "ollama" | "custom"
    base_url: str  # used by jll, custom; empty for openai, anthropic
    model: str     # chat model name
    embed_model: str  # embedding model name (ignored for anthropic)
```

### Updated `Config` dataclass
```python
@dataclass
class Config:
    chat_provider: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        name="jll", base_url="http://localhost:8888",
        model="GPT_4_1", embed_model="text-embedding-ada-002"
    ))
    embed_provider: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        name="jll", base_url="http://localhost:8888",
        model="GPT_4_1", embed_model="text-embedding-ada-002"
    ))
    capture_interval_seconds: int = 60
    purge_months: int = 6
    paused: bool = False
    blog_generation_time: str = "21:30"
    blog_mirror_enabled: bool = True
```

### Keychain functions
```python
def get_provider_token(provider_name: str) -> str | None:
    """Read API key for a provider. Falls back to env BRN_<NAME>_TOKEN."""
    keyring.get_password("2brn", f"provider.{provider_name}")

def set_provider_token(provider_name: str, token: str) -> None:
    keyring.set_password("2brn", f"provider.{provider_name}", token)
```

### V1 → V2 migration (in `load_config`)
When loading a config file that contains `gateway_url` (v1 format):
1. Build `ProviderConfig(name="jll", base_url=data["gateway_url"], model=data["llm_model"], embed_model=data["embed_model"])`
2. Also migrate the keychain: if `jll_gateway_token` exists and `provider.jll` does not, copy it
3. Return v2 `Config` — no file rewrite (lazy migration — file is rewritten on next settings save)

---

## Section 4: Settings API + UI

### API changes — `settings_routes.py`

**GET `/settings` response:**
```json
{
  "chat_provider": {"name": "jll", "base_url": "...", "model": "GPT_4_1", "embed_model": "..."},
  "embed_provider": {"name": "openai", "base_url": "", "model": "gpt-4o", "embed_model": "text-embedding-3-small"},
  "chat_provider_has_token": true,
  "embed_provider_has_token": true,
  "capture_interval_seconds": 60,
  "purge_months": 6,
  "paused": false,
  "blog_generation_time": "21:30",
  "blog_mirror_enabled": true
}
```

**PUT `/settings` request body:**
```json
{
  "chat_provider": {"name": "openai", "base_url": "", "model": "gpt-4o", "embed_model": ""},
  "embed_provider": {"name": "openai", "base_url": "", "model": "gpt-4o", "embed_model": "text-embedding-3-small"}
}
```

**New endpoint — POST `/settings/providers/{name}/token`:**
```json
{"token": "sk-..."}
```
Stores the token in keychain under `provider.{name}`.

**New endpoint — GET `/settings/providers/validate`:**
Fires a minimal test call to each configured provider (1-token completion for chat, single-string embed for embed).
Returns:
```json
{
  "chat": {"ok": true, "latency_ms": 312},
  "embed": {"ok": false, "error": "Invalid API key"}
}
```

### UI changes — `Settings.tsx`

Replace the "JLL GPT Gateway" section with two cards side by side (or stacked on narrow):

**Card: Chat Provider**
- Dropdown: `JLL GPT Gateway | OpenAI | Anthropic | Ollama | Custom URL`
- Model field (text, pre-filled with provider default on dropdown change)
- Base URL field (visible only when name = "jll" or "custom")
- API Key field (password; shows `(keychain ✓)` if present; not shown for ollama)
- "Test" button → calls `/settings/providers/validate`, shows latency or error inline

**Card: Embedding Provider**
- Same structure
- When `name = "anthropic"` is selected: show a warning banner "Anthropic does not support embeddings"

Provider defaults table (pre-fills model on dropdown change):

| Provider | Default chat model | Default embed model |
|---|---|---|
| jll | GPT_4_1 | text-embedding-ada-002 |
| openai | gpt-4o | text-embedding-3-small |
| anthropic | claude-3-5-sonnet-20241022 | — |
| ollama | llama3 | nomic-embed-text |
| custom | (empty) | (empty) |

---

## Section 5: Wiring + Tests

### `main.py` changes
```python
from brn_daemon.providers import make_chat_provider, make_embed_provider

# In lifespan:
chat_provider = make_chat_provider(cfg.chat_provider)
embed_provider = make_embed_provider(cfg.embed_provider)

inference_queue = InferenceQueue(gateway=chat_provider, ...)  # unchanged signature
journal_gen = JournalGenerator(gateway=chat_provider)         # unchanged
blog_gen = BlogGenerator(gateway=chat_provider)               # unchanged
chat_service = ChatService(gateway=chat_provider, chroma_store=chroma)  # unchanged
embedding_service = EmbeddingService(gateway=embed_provider, ...)       # unchanged
vault_watcher = JoplinWatcher(gateway=embed_provider, ...)              # unchanged

# Shutdown:
await chat_provider.aclose()
await embed_provider.aclose()  # safe to call even if same underlying client
```

No changes to any consumer module (inference, journal, blog, chat, embeddings, joplin_watcher).

### New Python dependency
`anthropic>=0.30` added to `pyproject.toml`. Lazy import inside `providers/anthropic.py` — only runs `import anthropic` when that adapter is instantiated.

### Files changed

| Action | File |
|---|---|
| NEW | `daemon/src/brn_daemon/providers/__init__.py` |
| NEW | `daemon/src/brn_daemon/providers/base.py` |
| NEW | `daemon/src/brn_daemon/providers/jll.py` |
| NEW | `daemon/src/brn_daemon/providers/openai.py` |
| NEW | `daemon/src/brn_daemon/providers/anthropic.py` |
| NEW | `daemon/src/brn_daemon/providers/ollama.py` |
| NEW | `daemon/src/brn_daemon/providers/custom.py` |
| NEW | `daemon/tests/test_providers.py` |
| MODIFY | `daemon/src/brn_daemon/config.py` |
| MODIFY | `daemon/src/brn_daemon/main.py` |
| MODIFY | `daemon/src/brn_daemon/routes/settings_routes.py` |
| MODIFY | `ui/src/components/Settings.tsx` |
| MODIFY | `ui/src/api/types.ts` |
| DELETE | `daemon/src/brn_daemon/gateway.py` (logic moved to `providers/jll.py`) |

### Tests
- `test_providers.py` — one test class per adapter, same mock pattern as `test_gateway.py`
- `test_config.py` — add migration test: feed v1 JSON, assert v2 `Config` comes back
- All existing 91 daemon tests pass unchanged (callers are duck-typed, existing `GatewayClient` mocks satisfy the `LLMProvider` protocol)

---

## Out of Scope
- Streaming progress in the Settings UI "Test" button (returns result after completion)
- Provider-level rate limiting / quota tracking
- Model capability validation (e.g. checking if a model supports function calling)
- Multi-key rotation / failover between providers
