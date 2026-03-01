# litellm Multi-Provider Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic `GatewayClient` with `litellm` for chat and a thin `EmbedClient` protocol for embeddings, so any provider (OpenAI, Anthropic, Azure, Ollama, JLL, etc.) can be configured independently for chat and embeddings.

**Architecture:** `litellm.acompletion()` handles all chat providers via a single interface. Embeddings use a protocol (`EmbedClient`) with two concrete drivers: `OpenAIEmbedClient` (standard format) and `JLLEmbedClient` (custom `inputs`/`data.embeddings` format). Config gains two top-level blocks — `chat_provider` and `embed_provider` — replacing the old flat fields. Hard cutover: old config fields are dropped.

**Tech Stack:** Python 3.12, `litellm>=1.40`, `httpx`, FastAPI, existing `keyring` for secrets.

**Working directory:** All daemon work is in `.worktrees/litellm-providers/daemon/`. Run all commands from there.

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `daemon/pyproject.toml` | Modify | Add `litellm>=1.40`, remove `openai` |
| `daemon/src/brn_daemon/providers.py` | **Create** | `EmbedClient` protocol + `OpenAIEmbedClient` + `JLLEmbedClient` + `make_embed_client()` |
| `daemon/src/brn_daemon/llm.py` | **Create** | `chat_complete()`, `chat_stream()` wrappers over litellm + `make_chat_kwargs()` |
| `daemon/src/brn_daemon/config.py` | Modify | New `ProviderConfig` dataclass, new `Config` shape, new keychain keys, drop old fields |
| `daemon/src/brn_daemon/gateway.py` | **Delete** | Replaced by `providers.py` + `llm.py` |
| `daemon/src/brn_daemon/main.py` | Modify | Wire `make_embed_client()` + litellm instead of `GatewayClient` |
| `daemon/src/brn_daemon/inference.py` | Modify | Accept `chat_complete` callable instead of `gateway` |
| `daemon/src/brn_daemon/embeddings.py` | Modify | Accept `EmbedClient` instead of `gateway` |
| `daemon/src/brn_daemon/chat.py` | Modify | Accept `chat_stream` callable + `EmbedClient` instead of `gateway` |
| `daemon/src/brn_daemon/journal.py` | Modify | Accept `chat_complete` callable instead of `gateway` |
| `daemon/src/brn_daemon/joplin_watcher.py` | Modify | Accept `EmbedClient` instead of `gateway` |
| `daemon/src/brn_daemon/routes/settings_routes.py` | Modify | New response/request shapes for `chat_provider`/`embed_provider` |
| `daemon/src/brn_daemon/routes/debug_routes.py` | Modify | Update gateway health check URL to use `chat_provider.base_url` |
| `daemon/tests/test_providers.py` | **Create** | Tests for both embed drivers |
| `daemon/tests/test_llm.py` | **Create** | Tests for litellm chat wrappers |
| `daemon/tests/test_config.py` | Modify | Update for new config shape |
| `daemon/tests/test_gateway.py` | **Delete** | Superseded by test_providers.py + test_llm.py |
| `ui/src/components/Settings.tsx` | Modify | Two provider sections instead of one gateway section |
| `ui/src/api/types.ts` | Modify | New `SettingsResponse` / `SettingsUpdateRequest` types |

---

## Task 1: Add litellm dependency, remove openai

**Files:**
- Modify: `daemon/pyproject.toml`

- [ ] **Step 1: Update pyproject.toml**

Replace `"openai>=1.30"` with `"litellm>=1.40"`:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "aiosqlite>=0.20",
    "chromadb>=0.5",
    "pytesseract>=0.3.13",
    "mss>=9.0",
    "imagehash>=4.3",
    "Pillow>=10.0",
    "litellm>=1.40",
    "keyring>=25.0",
    "APScheduler>=3.10",
    "sse-starlette>=2.1",
    "numpy>=1.26",
    "python-dotenv>=1.0",
    "pyobjc-framework-Cocoa>=10.0; sys_platform == 'darwin'",
    "pyobjc-framework-Quartz>=10.0; sys_platform == 'darwin'",
]
```

- [ ] **Step 2: Sync dependencies**

```bash
uv sync
```

Expected: litellm installs, openai removed (litellm bundles its own openai dep as needed).

- [ ] **Step 3: Verify litellm importable**

```bash
uv run python -c "import litellm; print(litellm.__version__)"
```

Expected: prints a version string.

- [ ] **Step 4: Commit**

```bash
git add daemon/pyproject.toml daemon/uv.lock
git commit -m "chore: swap openai for litellm"
```

---

## Task 2: New config schema (`config.py`)

**Files:**
- Modify: `daemon/src/brn_daemon/config.py`
- Modify: `daemon/tests/test_config.py`

- [ ] **Step 1: Write failing tests**

Replace the content of `daemon/tests/test_config.py` with:

```python
import json
import pytest
from brn_daemon.config import load_config, save_config, Config, ProviderConfig


def test_load_config_returns_defaults_when_no_file(tmp_home):
    cfg = load_config()
    assert cfg.chat_provider.base_url == "http://localhost:8889/v1"
    assert cfg.chat_provider.model == "GPT_5_2"
    assert cfg.chat_provider.type == "openai_compatible"
    assert cfg.embed_provider.base_url == "http://localhost:8889"
    assert cfg.embed_provider.model == "TEXT_EMBEDDING_3_LARGE"
    assert cfg.embed_provider.type == "jll"
    assert cfg.capture_interval_seconds == 60
    assert cfg.purge_months == 6
    assert cfg.paused is False


def test_save_and_reload_config(tmp_home):
    cfg = load_config()
    cfg.paused = True
    cfg.chat_provider.model = "gpt-4o"
    save_config(cfg)
    reloaded = load_config()
    assert reloaded.paused is True
    assert reloaded.chat_provider.model == "gpt-4o"


def test_config_file_written_as_json(tmp_home):
    cfg = load_config()
    save_config(cfg)
    config_path = tmp_home / "config.json"
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert "chat_provider" in data
    assert "embed_provider" in data
    assert "gateway_url" not in data
    assert "llm_model" not in data
    assert "embed_model" not in data


def test_config_blog_defaults(tmp_home):
    cfg = load_config()
    assert cfg.blog_mirror_enabled is True


def test_config_blog_fields_persist(tmp_home):
    cfg = load_config()
    cfg.blog_mirror_enabled = False
    save_config(cfg)
    loaded = load_config()
    assert loaded.blog_mirror_enabled is False


def test_provider_config_extra_headers(tmp_home):
    cfg = load_config()
    cfg.chat_provider.extra_headers = {"api-key": "abc123"}
    save_config(cfg)
    reloaded = load_config()
    assert reloaded.chat_provider.extra_headers == {"api-key": "abc123"}
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --extra dev pytest tests/test_config.py -v
```

Expected: ImportError or AttributeError on `ProviderConfig`.

- [ ] **Step 3: Rewrite `config.py`**

Replace the entire file with:

```python
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from brn_daemon.db import get_brn_home

logger = logging.getLogger(__name__)

KEYCHAIN_SERVICE = "2brn"
KEYCHAIN_CHAT_KEY = "chat_api_key"
KEYCHAIN_EMBED_KEY = "embed_api_key"


@dataclass
class ProviderConfig:
    type: str = "openai_compatible"
    base_url: str = ""
    model: str = ""
    extra_headers: dict = field(default_factory=dict)


@dataclass
class Config:
    chat_provider: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        type="openai_compatible",
        base_url="http://localhost:8889/v1",
        model="GPT_5_2",
    ))
    embed_provider: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        type="jll",
        base_url="http://localhost:8889",
        model="TEXT_EMBEDDING_3_LARGE",
    ))
    capture_interval_seconds: int = 60
    purge_months: int = 6
    paused: bool = False
    excluded_apps: list[str] = field(default_factory=list)
    blog_mirror_enabled: bool = True
    joplin_token: str = ""


def _config_path() -> Path:
    return get_brn_home() / "config.json"


def _parse_provider(data: dict) -> ProviderConfig:
    return ProviderConfig(
        type=data.get("type", "openai_compatible"),
        base_url=data.get("base_url", ""),
        model=data.get("model", ""),
        extra_headers=data.get("extra_headers", {}),
    )


def load_config() -> Config:
    path = _config_path()
    if not path.exists():
        return Config()
    try:
        data = json.loads(path.read_text())
        return Config(
            chat_provider=_parse_provider(data.get("chat_provider", {})),
            embed_provider=_parse_provider(data.get("embed_provider", {})),
            capture_interval_seconds=data.get("capture_interval_seconds", 60),
            purge_months=data.get("purge_months", 6),
            paused=data.get("paused", False),
            excluded_apps=data.get("excluded_apps", []),
            blog_mirror_enabled=data.get("blog_mirror_enabled", True),
            joplin_token=data.get("joplin_token", ""),
        )
    except (json.JSONDecodeError, KeyError):
        logger.warning("Corrupt config.json — using defaults")
        return Config()


def save_config(cfg: Config) -> None:
    get_brn_home().mkdir(parents=True, exist_ok=True)

    def _provider_dict(p: ProviderConfig) -> dict:
        d = {"type": p.type, "base_url": p.base_url, "model": p.model}
        if p.extra_headers:
            d["extra_headers"] = p.extra_headers
        return d

    data = {
        "chat_provider": _provider_dict(cfg.chat_provider),
        "embed_provider": _provider_dict(cfg.embed_provider),
        "capture_interval_seconds": cfg.capture_interval_seconds,
        "purge_months": cfg.purge_months,
        "paused": cfg.paused,
        "blog_mirror_enabled": cfg.blog_mirror_enabled,
        "joplin_token": cfg.joplin_token,
    }
    _config_path().write_text(json.dumps(data, indent=2))


def get_api_key(keychain_key: str, env_fallback: str) -> str | None:
    try:
        import keyring
        val = keyring.get_password(KEYCHAIN_SERVICE, keychain_key)
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(env_fallback)


def get_chat_api_key() -> str | None:
    return get_api_key(KEYCHAIN_CHAT_KEY, "BRN_CHAT_API_KEY")


def get_embed_api_key() -> str | None:
    return get_api_key(KEYCHAIN_EMBED_KEY, "BRN_EMBED_API_KEY")


def set_chat_api_key(token: str) -> None:
    try:
        import keyring
        keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_CHAT_KEY, token)
    except Exception as exc:
        raise RuntimeError(f"Could not save chat API key to keychain: {exc}") from exc


def set_embed_api_key(token: str) -> None:
    try:
        import keyring
        keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_EMBED_KEY, token)
    except Exception as exc:
        raise RuntimeError(f"Could not save embed API key to keychain: {exc}") from exc
```

- [ ] **Step 4: Run tests — expect pass**

```bash
uv run --extra dev pytest tests/test_config.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 5: Migrate existing config.json on disk**

```bash
uv run python -c "
import json
from pathlib import Path
p = Path.home() / '.2brn/config.json'
if p.exists():
    d = json.loads(p.read_text())
    if 'gateway_url' in d:
        new = {
            'chat_provider': {'type': 'openai_compatible', 'base_url': d.get('gateway_url','http://localhost:8889') + '/v1', 'model': d.get('llm_model','GPT_5_2')},
            'embed_provider': {'type': 'jll', 'base_url': d.get('gateway_url','http://localhost:8889'), 'model': d.get('embed_model','TEXT_EMBEDDING_3_LARGE')},
            'capture_interval_seconds': d.get('capture_interval_seconds', 60),
            'purge_months': d.get('purge_months', 6),
            'paused': d.get('paused', False),
            'blog_mirror_enabled': d.get('blog_mirror_enabled', True),
            'joplin_token': d.get('joplin_token', ''),
        }
        p.write_text(json.dumps(new, indent=2))
        print('Migrated config.json')
    else:
        print('Already new format')
"
```

- [ ] **Step 6: Commit**

```bash
git add daemon/src/brn_daemon/config.py daemon/tests/test_config.py
git commit -m "feat: new chat_provider/embed_provider config schema"
```

---

## Task 3: EmbedClient protocol + drivers (`providers.py`)

**Files:**
- Create: `daemon/src/brn_daemon/providers.py`
- Create: `daemon/tests/test_providers.py`

- [ ] **Step 1: Write failing tests**

Create `daemon/tests/test_providers.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from brn_daemon.providers import JLLEmbedClient, OpenAIEmbedClient


@pytest.fixture
def jll_client():
    return JLLEmbedClient(base_url="http://localhost:8889", api_key="test-token", model="TEXT_EMBEDDING_3_LARGE")


@pytest.fixture
def openai_client():
    return OpenAIEmbedClient(base_url="http://localhost:8889/v1", api_key="test-token", model="text-embedding-3-large")


async def test_jll_embed_batch_returns_list_of_lists(jll_client):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={
        "success": True,
        "data": {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
    })
    with patch.object(jll_client._http, "post", AsyncMock(return_value=mock_resp)) as mock_post:
        result = await jll_client.embed_batch(["hello", "world"])
    assert result == [[0.1, 0.2], [0.3, 0.4]]
    call_json = mock_post.call_args.kwargs["json"]
    assert call_json["inputs"] == ["hello", "world"]


async def test_jll_embed_single_returns_list(jll_client):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={
        "success": True,
        "data": {"embeddings": [[0.5, 0.6]]}
    })
    with patch.object(jll_client._http, "post", AsyncMock(return_value=mock_resp)):
        result = await jll_client.embed("hello")
    assert result == [0.5, 0.6]


async def test_jll_embed_batch_retries_on_failure(jll_client):
    call_count = 0
    async def flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise Exception("connection error")
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"success": True, "data": {"embeddings": [[0.1]]}})
        return mock_resp
    with patch.object(jll_client._http, "post", flaky):
        with patch("brn_daemon.providers.asyncio.sleep", AsyncMock()):
            result = await jll_client.embed_batch(["hello"])
    assert result == [[0.1]]
    assert call_count == 2


async def test_openai_embed_batch_returns_list_of_lists(openai_client):
    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=[0.1, 0.2]), MagicMock(embedding=[0.3, 0.4])]
    with patch.object(openai_client._client.embeddings, "create", AsyncMock(return_value=mock_resp)):
        result = await openai_client.embed_batch(["hello", "world"])
    assert result == [[0.1, 0.2], [0.3, 0.4]]


async def test_openai_embed_single_returns_list(openai_client):
    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=[0.7, 0.8])]
    with patch.object(openai_client._client.embeddings, "create", AsyncMock(return_value=mock_resp)):
        result = await openai_client.embed("hello")
    assert result == [0.7, 0.8]
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --extra dev pytest tests/test_providers.py -v
```

Expected: ImportError — `providers` module doesn't exist.

- [ ] **Step 3: Create `providers.py`**

Create `daemon/src/brn_daemon/providers.py`:

```python
import asyncio
import logging
from typing import Protocol, runtime_checkable

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3


@runtime_checkable
class EmbedClient(Protocol):
    async def embed(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class JLLEmbedClient:
    """Embed client for JLL Gateway's custom format.

    Request:  POST /v1/embeddings  {"model": "...", "inputs": ["text1", ...]}
    Response: {"success": true, "data": {"embeddings": [[...], ...]}}
    """

    def __init__(self, base_url: str, api_key: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._http = httpx.AsyncClient(
            timeout=30,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def embed(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._http.post(
                    f"{self._base_url}/v1/embeddings",
                    json={"model": self._model, "inputs": texts},
                )
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success"):
                    raise ValueError(f"Embedding failed: {data.get('errorMessage', data)}")
                return data["data"]["embeddings"]
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning("JLL embed attempt %d failed (%d texts): %s — retrying in %ds",
                               attempt + 1, len(texts), exc, wait)
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
                else:
                    raise


class OpenAIEmbedClient:
    """Embed client for any OpenAI-compatible embeddings endpoint.

    Works with: OpenAI, Azure OpenAI, Ollama, any standard /v1/embeddings endpoint.
    """

    def __init__(self, base_url: str, api_key: str, model: str):
        self._model = model
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key or "no-key",
        )

    async def aclose(self) -> None:
        await self._client.close()

    async def embed(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._client.embeddings.create(
                    model=self._model,
                    input=texts,
                )
                return [item.embedding for item in resp.data]
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning("OpenAI embed attempt %d failed (%d texts): %s — retrying in %ds",
                               attempt + 1, len(texts), exc, wait)
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
                else:
                    raise


def make_embed_client() -> JLLEmbedClient | OpenAIEmbedClient:
    """Factory: reads config and returns the right embed driver."""
    from brn_daemon.config import load_config, get_embed_api_key
    cfg = load_config()
    ep = cfg.embed_provider
    api_key = get_embed_api_key() or ""
    if ep.type == "jll":
        return JLLEmbedClient(base_url=ep.base_url, api_key=api_key, model=ep.model)
    return OpenAIEmbedClient(base_url=ep.base_url, api_key=api_key, model=ep.model)
```

- [ ] **Step 4: Run tests — expect pass**

```bash
uv run --extra dev pytest tests/test_providers.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/providers.py daemon/tests/test_providers.py
git commit -m "feat: EmbedClient protocol with JLL and OpenAI drivers"
```

---

## Task 4: litellm chat wrappers (`llm.py`)

**Files:**
- Create: `daemon/src/brn_daemon/llm.py`
- Create: `daemon/tests/test_llm.py`

- [ ] **Step 1: Write failing tests**

Create `daemon/tests/test_llm.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from brn_daemon.llm import chat_complete, chat_stream, make_chat_kwargs


def test_make_chat_kwargs_openai_compatible():
    kwargs = make_chat_kwargs(
        provider_type="openai_compatible",
        base_url="http://localhost:8889/v1",
        api_key="mykey",
        model="GPT_5_2",
        extra_headers={},
    )
    assert kwargs["model"] == "openai/GPT_5_2"
    assert kwargs["api_key"] == "mykey"
    assert kwargs["base_url"] == "http://localhost:8889/v1"


def test_make_chat_kwargs_anthropic():
    kwargs = make_chat_kwargs(
        provider_type="anthropic",
        base_url="https://example.com/anthropic/v1",
        api_key="sk-ant-xyz",
        model="claude-sonnet-4-6",
        extra_headers={"api-key": "sk-ant-xyz"},
    )
    assert kwargs["model"] == "anthropic/claude-sonnet-4-6"
    assert kwargs["extra_headers"] == {"api-key": "sk-ant-xyz"}


def test_make_chat_kwargs_ollama():
    kwargs = make_chat_kwargs(
        provider_type="ollama",
        base_url="http://localhost:11434",
        api_key="",
        model="llama3",
        extra_headers={},
    )
    assert kwargs["model"] == "ollama/llama3"


async def test_chat_complete_returns_string():
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "hello"
    with patch("brn_daemon.llm.litellm.acompletion", AsyncMock(return_value=mock_resp)):
        result = await chat_complete(
            messages=[{"role": "user", "content": "hi"}],
            provider_type="openai_compatible",
            base_url="http://localhost:8889/v1",
            api_key="1",
            model="GPT_5_2",
            extra_headers={},
        )
    assert result == "hello"


async def test_chat_complete_retries_on_failure():
    call_count = 0
    async def flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("rate limit")
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "ok"
        return mock_resp
    with patch("brn_daemon.llm.litellm.acompletion", flaky):
        with patch("brn_daemon.llm.asyncio.sleep", AsyncMock()):
            result = await chat_complete(
                messages=[{"role": "user", "content": "hi"}],
                provider_type="openai_compatible",
                base_url="http://localhost:8889/v1",
                api_key="1",
                model="GPT_5_2",
                extra_headers={},
            )
    assert result == "ok"
    assert call_count == 3
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --extra dev pytest tests/test_llm.py -v
```

Expected: ImportError — `llm` module doesn't exist.

- [ ] **Step 3: Create `llm.py`**

Create `daemon/src/brn_daemon/llm.py`:

```python
import asyncio
import logging
from typing import AsyncIterator

import litellm

litellm.drop_params = True  # silently drop unsupported params per provider

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3

_PROVIDER_PREFIX = {
    "openai_compatible": "openai",
    "openai": "openai",
    "anthropic": "anthropic",
    "azure": "azure",
    "ollama": "ollama",
    "groq": "groq",
    "together": "together_ai",
    "cohere": "cohere",
}


def make_chat_kwargs(
    provider_type: str,
    base_url: str,
    api_key: str,
    model: str,
    extra_headers: dict,
) -> dict:
    """Build kwargs dict for litellm.acompletion()."""
    prefix = _PROVIDER_PREFIX.get(provider_type, "openai")
    kwargs: dict = {
        "model": f"{prefix}/{model}",
        "api_key": api_key or "no-key",
    }
    if base_url:
        kwargs["base_url"] = base_url
    if extra_headers:
        kwargs["extra_headers"] = extra_headers
    return kwargs


async def chat_complete(
    messages: list[dict],
    provider_type: str,
    base_url: str,
    api_key: str,
    model: str,
    extra_headers: dict,
) -> str:
    kwargs = make_chat_kwargs(provider_type, base_url, api_key, model, extra_headers)
    kwargs["messages"] = messages
    kwargs["stream"] = False

    for attempt in range(_MAX_RETRIES):
        try:
            resp = await litellm.acompletion(**kwargs)
            return resp.choices[0].message.content
        except Exception as exc:
            wait = 2 ** attempt
            logger.warning("Chat attempt %d failed: %s — retrying in %ds", attempt + 1, exc, wait)
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(wait)
            else:
                raise


async def chat_stream(
    messages: list[dict],
    provider_type: str,
    base_url: str,
    api_key: str,
    model: str,
    extra_headers: dict,
) -> AsyncIterator[str]:
    kwargs = make_chat_kwargs(provider_type, base_url, api_key, model, extra_headers)
    kwargs["messages"] = messages
    kwargs["stream"] = True

    resp = await litellm.acompletion(**kwargs)
    async for chunk in resp:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def make_chat_fn():
    """Return (chat_complete_fn, chat_stream_fn) bound to current config."""
    from brn_daemon.config import load_config, get_chat_api_key
    cfg = load_config()
    cp = cfg.chat_provider
    api_key = get_chat_api_key() or ""

    async def _complete(messages: list[dict]) -> str:
        return await chat_complete(
            messages=messages,
            provider_type=cp.type,
            base_url=cp.base_url,
            api_key=api_key,
            model=cp.model,
            extra_headers=cp.extra_headers,
        )

    async def _stream(messages: list[dict]) -> AsyncIterator[str]:
        async for chunk in chat_stream(
            messages=messages,
            provider_type=cp.type,
            base_url=cp.base_url,
            api_key=api_key,
            model=cp.model,
            extra_headers=cp.extra_headers,
        ):
            yield chunk

    return _complete, _stream
```

- [ ] **Step 4: Run tests — expect pass**

```bash
uv run --extra dev pytest tests/test_llm.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/llm.py daemon/tests/test_llm.py
git commit -m "feat: litellm chat wrappers in llm.py"
```

---

## Task 5: Wire new providers into `main.py`, update callers

**Files:**
- Modify: `daemon/src/brn_daemon/main.py`
- Modify: `daemon/src/brn_daemon/inference.py`
- Modify: `daemon/src/brn_daemon/embeddings.py`
- Modify: `daemon/src/brn_daemon/chat.py`
- Modify: `daemon/src/brn_daemon/journal.py`
- Modify: `daemon/src/brn_daemon/joplin_watcher.py`

- [ ] **Step 1: Update `inference.py` — accept callable instead of gateway**

In `inference.py`, change `InferenceQueue.__init__` to accept a `chat_fn` callable instead of `gateway`:

```python
class InferenceQueue:
    def __init__(self, chat_fn, db_path_fn, embedding_service=None):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=INFERENCE_QUEUE_MAX)
        self._chat_fn = chat_fn
        self._db_path_fn = db_path_fn
        self._embedding_service = embedding_service
```

In `_process_one`, replace:
```python
raw = await self._gateway.chat_complete([
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt},
])
```
with:
```python
raw = await self._chat_fn([
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt},
])
```

- [ ] **Step 2: Update `embeddings.py` — accept `EmbedClient` instead of gateway**

In `EmbeddingService.__init__`, rename `gateway` param to `embed_client`:

```python
class EmbeddingService:
    def __init__(self, embed_client, chroma_store: ChromaStore):
        self._embed_client = embed_client
        self._store = chroma_store

    async def embed_activity(self, activity_id: int, summary: str, metadata: dict) -> None:
        try:
            embedding = await self._embed_client.embed(summary)
            # ... rest unchanged
```

- [ ] **Step 3: Update `chat.py` — accept callables instead of gateway**

```python
class ChatService:
    def __init__(self, chat_fn, stream_fn, embed_client, chroma_store):
        self._chat_fn = chat_fn
        self._stream_fn = stream_fn
        self._embed_client = embed_client
        self._store = chroma_store

    async def chat(self, question, date_filter=None, category_filter=None, n_results=10):
        try:
            query_embedding = await self._embed_client.embed(question)
        except Exception as exc:
            logger.error("Failed to embed query: %s", exc)
            yield "Sorry, I couldn't process your question right now."
            return
        # ... ChromaDB query unchanged ...
        async for chunk in self._stream_fn(messages):
            yield chunk
```

- [ ] **Step 4: Update `journal.py` — accept `chat_fn` callable**

Find all `JournalGenerator`, `BlogGenerator`, `ResumeUpdater` constructors that take `gateway`. Change to accept `chat_fn`:

```python
class JournalGenerator:
    def __init__(self, chat_fn):
        self._chat_fn = chat_fn

    async def generate(self, ...):
        # replace self._gateway.chat_complete(...) with self._chat_fn(...)
```

Apply the same pattern to `BlogGenerator` and `ResumeUpdater`.

- [ ] **Step 5: Update `joplin_watcher.py` — accept `embed_client`**

Find `JoplinWatcher.__init__` — change `gateway` param to `embed_client`. Replace all `self._gateway.embed(...)` / `self._gateway.embed_batch(...)` calls with `self._embed_client.embed(...)` / `self._embed_client.embed_batch(...)`.

- [ ] **Step 6: Update `main.py` — wire everything together**

Replace the GatewayClient construction block in `lifespan`:

```python
# OLD (remove these lines):
from brn_daemon.gateway import GatewayClient
...
gateway = GatewayClient(base_url=cfg.gateway_url, token=get_gateway_token() or "",
                        llm_model=cfg.llm_model, embed_model=cfg.embed_model)

# NEW (replace with):
from brn_daemon.llm import make_chat_fn
from brn_daemon.providers import make_embed_client
from brn_daemon.config import load_config

cfg = load_config()
chat_fn, stream_fn = make_chat_fn()
embed_client = make_embed_client()

chroma = ChromaStore()
embedding_service = EmbeddingService(embed_client=embed_client, chroma_store=chroma)
app_state["chroma_store"] = chroma
inference_queue = InferenceQueue(chat_fn=chat_fn, db_path_fn=get_db_path,
                                 embedding_service=embedding_service)
journal_gen = JournalGenerator(chat_fn=chat_fn)
journal_mirror = JournalMirror(token=cfg.joplin_token)
blog_gen = BlogGenerator(chat_fn=chat_fn)
blog_mirror = BlogMirror(token=cfg.joplin_token)
resume_updater = ResumeUpdater(chat_fn=chat_fn, token=cfg.joplin_token)
chat_service = ChatService(chat_fn=chat_fn, stream_fn=stream_fn,
                           embed_client=embed_client, chroma_store=chroma)
vault_watcher = JoplinWatcher(embed_client=embed_client, chroma_client=chroma.chroma_client)
```

Also update the `aclose` call on shutdown — replace `await gateway.aclose()` with `await embed_client.aclose()`.

- [ ] **Step 7: Delete `gateway.py` and its tests**

```bash
rm daemon/src/brn_daemon/gateway.py
rm daemon/tests/test_gateway.py
```

- [ ] **Step 8: Run full test suite**

```bash
uv run --extra dev pytest tests/ -v
```

Expected: all tests pass (test_gateway.py is gone, no other test imports gateway).

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: wire litellm chat + EmbedClient into all callers, remove GatewayClient"
```

---

## Task 6: Update settings API route

**Files:**
- Modify: `daemon/src/brn_daemon/routes/settings_routes.py`
- Modify: `daemon/src/brn_daemon/routes/debug_routes.py`

- [ ] **Step 1: Rewrite `settings_routes.py` models and handlers**

Update the Pydantic models and GET/PUT handlers:

```python
from pydantic import BaseModel
from fastapi import APIRouter
from brn_daemon.config import (
    load_config, save_config, ProviderConfig,
    get_chat_api_key, get_embed_api_key,
    set_chat_api_key, set_embed_api_key,
)

router = APIRouter()


class ProviderConfigOut(BaseModel):
    type: str
    base_url: str
    model: str
    extra_headers: dict = {}


class SettingsResponse(BaseModel):
    chat_provider: ProviderConfigOut
    embed_provider: ProviderConfigOut
    has_chat_key: bool
    has_embed_key: bool
    capture_interval_seconds: int
    purge_months: int
    paused: bool
    blog_mirror_enabled: bool


class ProviderConfigIn(BaseModel):
    type: str | None = None
    base_url: str | None = None
    model: str | None = None
    extra_headers: dict | None = None
    api_key: str | None = None  # written to keychain if provided


class SettingsUpdateRequest(BaseModel):
    chat_provider: ProviderConfigIn | None = None
    embed_provider: ProviderConfigIn | None = None
    capture_interval_seconds: int | None = None
    purge_months: int | None = None
    blog_mirror_enabled: bool | None = None


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    cfg = load_config()
    return SettingsResponse(
        chat_provider=ProviderConfigOut(**vars(cfg.chat_provider)),
        embed_provider=ProviderConfigOut(**vars(cfg.embed_provider)),
        has_chat_key=bool(get_chat_api_key()),
        has_embed_key=bool(get_embed_api_key()),
        capture_interval_seconds=cfg.capture_interval_seconds,
        purge_months=cfg.purge_months,
        paused=cfg.paused,
        blog_mirror_enabled=cfg.blog_mirror_enabled,
    )


@router.put("/settings")
async def update_settings(body: SettingsUpdateRequest):
    cfg = load_config()
    if body.chat_provider:
        p = body.chat_provider
        if p.type is not None:
            cfg.chat_provider.type = p.type
        if p.base_url is not None:
            cfg.chat_provider.base_url = p.base_url
        if p.model is not None:
            cfg.chat_provider.model = p.model
        if p.extra_headers is not None:
            cfg.chat_provider.extra_headers = p.extra_headers
        if p.api_key:
            set_chat_api_key(p.api_key)
    if body.embed_provider:
        p = body.embed_provider
        if p.type is not None:
            cfg.embed_provider.type = p.type
        if p.base_url is not None:
            cfg.embed_provider.base_url = p.base_url
        if p.model is not None:
            cfg.embed_provider.model = p.model
        if p.extra_headers is not None:
            cfg.embed_provider.extra_headers = p.extra_headers
        if p.api_key:
            set_embed_api_key(p.api_key)
    if body.capture_interval_seconds is not None:
        cfg.capture_interval_seconds = body.capture_interval_seconds
    if body.purge_months is not None:
        cfg.purge_months = body.purge_months
    if body.blog_mirror_enabled is not None:
        cfg.blog_mirror_enabled = body.blog_mirror_enabled
    save_config(cfg)
    return {"ok": True}
```

Keep the existing `/settings/paused`, `/settings/exclusions`, `/settings/resync-chroma`, `/settings/chroma-status` endpoints unchanged.

- [ ] **Step 2: Update `debug_routes.py`**

Replace `cfg.gateway_url` reference with `cfg.chat_provider.base_url` (strip `/v1` suffix for the health check URL):

```python
base = cfg.chat_provider.base_url.rstrip("/")
if base.endswith("/v1"):
    base = base[:-3]
r = await client.get(f"{base}/actuator/health")
```

- [ ] **Step 3: Verify imports are clean**

```bash
uv run python -c "from brn_daemon.routes.settings_routes import router; print('ok')"
uv run python -c "from brn_daemon.main import app; print('ok')"
```

Expected: both print `ok`.

- [ ] **Step 4: Run full test suite**

```bash
uv run --extra dev pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/routes/settings_routes.py daemon/src/brn_daemon/routes/debug_routes.py
git commit -m "feat: update settings API for chat_provider/embed_provider"
```

---

## Task 7: Update Settings UI

**Files:**
- Modify: `ui/src/api/types.ts`
- Modify: `ui/src/components/Settings.tsx`

- [ ] **Step 1: Update `api/types.ts`**

Find and replace the settings-related types. The new types:

```typescript
export interface ProviderConfig {
  type: string
  base_url: string
  model: string
  extra_headers?: Record<string, string>
}

export interface SettingsResponse {
  chat_provider: ProviderConfig
  embed_provider: ProviderConfig
  has_chat_key: boolean
  has_embed_key: boolean
  capture_interval_seconds: number
  purge_months: number
  paused: boolean
  blog_mirror_enabled: boolean
}

export interface ProviderConfigUpdate {
  type?: string
  base_url?: string
  model?: string
  extra_headers?: Record<string, string>
  api_key?: string
}

export interface SettingsUpdateRequest {
  chat_provider?: ProviderConfigUpdate
  embed_provider?: ProviderConfigUpdate
  capture_interval_seconds?: number
  purge_months?: number
  blog_mirror_enabled?: boolean
}
```

- [ ] **Step 2: Rewrite the provider sections in `Settings.tsx`**

Replace the state variables:

```typescript
const [chatType, setChatType]         = useState('')
const [chatUrl, setChatUrl]           = useState('')
const [chatModel, setChatModel]       = useState('')
const [chatKey, setChatKey]           = useState('')
const [embedType, setEmbedType]       = useState('')
const [embedUrl, setEmbedUrl]         = useState('')
const [embedModel, setEmbedModel]     = useState('')
const [embedKey, setEmbedKey]         = useState('')
```

Update the `useEffect` to populate from new shape:

```typescript
useEffect(() => {
  if (settings && !chatUrl) {
    setChatType(settings.chat_provider.type)
    setChatUrl(settings.chat_provider.base_url)
    setChatModel(settings.chat_provider.model)
    setEmbedType(settings.embed_provider.type)
    setEmbedUrl(settings.embed_provider.base_url)
    setEmbedModel(settings.embed_provider.model)
    setBlogMirror(settings.blog_mirror_enabled ?? true)
  }
}, [settings?.chat_provider?.base_url])
```

Update `saveGateway` mutation:

```typescript
const saveProviders = useMutation({
  mutationFn: () => api.updateSettings({
    chat_provider: {
      type: chatType, base_url: chatUrl, model: chatModel,
      ...(chatKey ? { api_key: chatKey } : {}),
    },
    embed_provider: {
      type: embedType, base_url: embedUrl, model: embedModel,
      ...(embedKey ? { api_key: embedKey } : {}),
    },
    blog_mirror_enabled: blogMirror,
  }),
  onSuccess: () => {
    setChatKey(''); setEmbedKey('')
    flash('Settings saved')
    qc.invalidateQueries({ queryKey: queryKeys.settings() })
  },
  onError: () => flash('Failed to save'),
})
```

Replace the `<Section title="JLL GPT Gateway">` block with two new sections:

```tsx
{/* Chat Provider */}
<Section title="Chat Provider">
  <Field label="Provider Type">
    <Input value={chatType} onChange={e => setChatType(e.target.value)}
           placeholder="openai_compatible / anthropic / ollama / groq" />
  </Field>
  <Field label="Base URL">
    <Input value={chatUrl} onChange={e => setChatUrl(e.target.value)}
           placeholder="e.g. http://localhost:8889/v1" />
  </Field>
  <Field label="Model">
    <Input value={chatModel} onChange={e => setChatModel(e.target.value)}
           placeholder="e.g. GPT_5_2 / gpt-4o / claude-sonnet-4-6" />
  </Field>
  <Field label="API Key" sublabel={settings.has_chat_key ? '(keychain ✓)' : '(not set)'}>
    <Input type="password" value={chatKey} onChange={e => setChatKey(e.target.value)}
           placeholder="Enter new key to update…" />
  </Field>
</Section>

{/* Embed Provider */}
<Section title="Embed Provider">
  <Field label="Provider Type">
    <Input value={embedType} onChange={e => setEmbedType(e.target.value)}
           placeholder="jll / openai" />
  </Field>
  <Field label="Base URL">
    <Input value={embedUrl} onChange={e => setEmbedUrl(e.target.value)}
           placeholder="e.g. http://localhost:8889" />
  </Field>
  <Field label="Model">
    <Input value={embedModel} onChange={e => setEmbedModel(e.target.value)}
           placeholder="e.g. TEXT_EMBEDDING_3_LARGE / text-embedding-3-large" />
  </Field>
  <Field label="API Key" sublabel={settings.has_embed_key ? '(keychain ✓)' : '(not set)'}>
    <Input type="password" value={embedKey} onChange={e => setEmbedKey(e.target.value)}
           placeholder="Enter new key to update…" />
  </Field>
  <button
    onClick={() => saveProviders.mutate()}
    disabled={saveProviders.isPending}
    className="px-5 py-2 rounded-[9px] text-[13px] font-semibold transition-all disabled:opacity-40"
    style={{ background: 'var(--accent)', color: '#fff' }}
  >
    {saveProviders.isPending ? 'Saving…' : 'Save Provider Settings'}
  </button>
</Section>
```

- [ ] **Step 3: TypeScript check**

```bash
cd ui && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add ui/src/api/types.ts ui/src/components/Settings.tsx
git commit -m "feat: Settings UI — Chat Provider + Embed Provider sections"
```

---

## Task 8: Smoke test end-to-end

- [ ] **Step 1: Migrate config on disk and set API keys**

```bash
cd daemon && uv run python -c "
from brn_daemon.config import set_chat_api_key, set_embed_api_key
set_chat_api_key('1')
set_embed_api_key('1')
print('keys set')
"
```

- [ ] **Step 2: Start daemon and verify /status**

```bash
lsof -ti :7842 | xargs kill -9 2>/dev/null; true
cd daemon && uv run python -m brn_daemon.main &
sleep 3 && curl -s http://localhost:7842/status
```

Expected: `{"status":"capturing",...}`

- [ ] **Step 3: Verify /settings returns new shape**

```bash
curl -s http://localhost:7842/settings | python3 -m json.tool
```

Expected: JSON with `chat_provider`, `embed_provider`, `has_chat_key: true`, `has_embed_key: true`.

- [ ] **Step 4: Verify chat works**

```bash
curl -s -X POST http://localhost:7842/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"what did I do today?"}' \
  --no-buffer
```

Expected: SSE stream with text chunks.

- [ ] **Step 5: Run full test suite one last time**

```bash
cd daemon && uv run --extra dev pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: smoke test verified — litellm multi-provider complete"
```
