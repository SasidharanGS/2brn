# 2brn Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete 2brn second brain app — Python daemon (capture, OCR, inference, journal, RAG chat) + Electron/React UI (dashboard, chat, journal, timeline, insights, settings).

**Architecture:** Python 3.12 FastAPI daemon handles all background capture, OCR, LLM inference via JLL GPT Gateway, and exposes REST+SSE endpoints on localhost. Electron app hosts React 19 UI that connects to the daemon over localhost HTTP. All raw data stored locally in SQLite + ChromaDB + JPEG files under `~/.2brn/`.

**Tech Stack:** Python 3.12 · uv · FastAPI · aiosqlite · ChromaDB · pytesseract · mss · imagehash · APScheduler · openai SDK · keyring · Electron · React 19 · TypeScript · Tailwind CSS v4 · Recharts · pnpm

---

## File Map

```
2brn/
  daemon/
    pyproject.toml
    src/
      brn_daemon/
        __init__.py
        main.py              # FastAPI app + scheduler + capture loop startup
        config.py            # Load/save ~/.2brn/config.json
        db.py                # SQLite schema init + aiosqlite pool
        capture.py           # mss screenshot + active app/window detection
        dedup.py             # Perceptual hash dedup
        ocr.py               # pytesseract wrapper
        inference.py         # Async queue: OCR text → JLL GPT → structured JSON → SQLite
        embeddings.py        # Summary → JLL GPT embeddings → ChromaDB
        journal.py           # Daily journal generation via JLL GPT
        chat.py              # RAG: embed query → ChromaDB → SQLite → JLL GPT stream
        purge.py             # Delete screenshots + rows older than N months
        gateway.py           # JLL GPT Gateway HTTP client (shared by inference/embeddings/journal/chat)
        routes/
          __init__.py
          status.py          # GET /status
          captures.py        # GET /captures
          activities.py      # GET /activities
          journal_routes.py  # GET|POST|PUT /journal/:date
          chat_routes.py     # POST /chat (SSE)
          settings_routes.py # GET|PUT /settings, exclusions CRUD
          insights_routes.py # GET /insights/daily|weekly|monthly
    tests/
      conftest.py
      test_db.py
      test_dedup.py
      test_ocr.py
      test_inference.py
      test_embeddings.py
      test_journal.py
      test_chat.py
      test_purge.py
  ui/
    package.json
    tsconfig.json
    electron/
      main.ts                # Electron main: window + daemon subprocess management
      preload.ts             # Context bridge
    src/
      main.tsx
      App.tsx
      index.css
      api/
        client.ts            # Typed fetch client to daemon
        types.ts             # Shared TS types
      components/
        Dashboard.tsx
        Chat.tsx
        Journal.tsx
        Timeline.tsx
        Insights.tsx
        Settings.tsx
        shared/
          StatsBar.tsx
          DaemonStatus.tsx
          MarkdownRenderer.tsx
  .gitignore
  README.md
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `daemon/pyproject.toml`
- Create: `daemon/src/brn_daemon/__init__.py`
- Create: `ui/package.json`
- Create: `ui/tsconfig.json`

- [ ] **Step 1: Create .gitignore**

```
# Python
__pycache__/
*.pyc
.venv/
dist/
*.egg-info/
.pytest_cache/
# Node
node_modules/
ui/dist/
ui/out/
# App data
.superpowers/
# Env
.env
# OS
.DS_Store
```

- [ ] **Step 2: Create daemon/pyproject.toml**

```toml
[project]
name = "brn-daemon"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "aiosqlite>=0.20",
    "chromadb>=0.5",
    "pytesseract>=0.3.13",
    "mss>=9.0",
    "imagehash>=4.3",
    "Pillow>=10.0",
    "openai>=1.30",
    "keyring>=25.0",
    "APScheduler>=3.10",
    "sse-starlette>=2.1",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23", "httpx>=0.27"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: Initialise daemon with uv**

```bash
cd daemon && uv sync
```

Expected: `Resolved N packages` and `.venv/` created.

- [ ] **Step 4: Create ui/package.json**

```json
{
  "name": "2brn-ui",
  "version": "0.1.0",
  "private": true,
  "main": "dist/electron/main.js",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "electron:dev": "concurrently \"vite\" \"wait-on http://localhost:5173 && electron .\"",
    "electron:build": "pnpm build && electron-builder"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^6.23",
    "recharts": "^2.12",
    "react-markdown": "^9.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3",
    "autoprefixer": "^10.4",
    "concurrently": "^8.2",
    "electron": "^31.0",
    "electron-builder": "^24.0",
    "postcss": "^8.4",
    "tailwindcss": "^4.0",
    "typescript": "^5.5",
    "vite": "^5.3",
    "vite-plugin-electron": "^0.28",
    "wait-on": "^7.2"
  }
}
```

- [ ] **Step 5: Install UI dependencies**

```bash
cd ui && pnpm install
```

Expected: `node_modules/` created, no errors.

- [ ] **Step 6: Create ui/tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "outDir": "dist"
  },
  "include": ["src", "electron"]
}
```

- [ ] **Step 7: Commit**

```bash
git add .gitignore README.md daemon/pyproject.toml daemon/src/ ui/package.json ui/tsconfig.json
git commit -m "chore: scaffold project structure — daemon pyproject + ui package.json"
```

---

## Task 2: Database Layer

**Files:**
- Create: `daemon/src/brn_daemon/db.py`
- Create: `daemon/tests/conftest.py`
- Create: `daemon/tests/test_db.py`

- [ ] **Step 1: Write the failing test**

Create `daemon/tests/conftest.py`:
```python
import asyncio
import tempfile
import pytest
import aiosqlite
from pathlib import Path
from brn_daemon.db import init_db, get_db_path

@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("BRN_HOME", str(tmp_path))
    return tmp_path

@pytest.fixture
async def db(tmp_home):
    await init_db()
    path = get_db_path()
    async with aiosqlite.connect(path) as conn:
        yield conn
```

Create `daemon/tests/test_db.py`:
```python
import pytest
from brn_daemon.db import init_db, get_db_path

async def test_init_db_creates_all_tables(tmp_home):
    await init_db()
    import aiosqlite
    async with aiosqlite.connect(get_db_path()) as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in await cursor.fetchall()}
    assert tables == {"activities", "app_exclusions", "captures", "journals"}

async def test_init_db_idempotent(tmp_home):
    await init_db()
    await init_db()  # second call must not raise
    import aiosqlite
    async with aiosqlite.connect(get_db_path()) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM captures")
        count = (await cursor.fetchone())[0]
    assert count == 0

async def test_captures_table_schema(db):
    await db.execute(
        "INSERT INTO captures (captured_at, app_name, window_title, file_path, ocr_text, phash, trigger) "
        "VALUES (datetime('now'), 'TestApp', 'Test Window', '/tmp/a.jpg', 'hello', 'abc123', 'heartbeat')"
    )
    await db.commit()
    cursor = await db.execute("SELECT app_name, trigger FROM captures")
    row = await cursor.fetchone()
    assert row == ("TestApp", "heartbeat")

async def test_activities_table_schema(db):
    await db.execute(
        "INSERT INTO captures (captured_at, trigger) VALUES (datetime('now'), 'heartbeat')"
    )
    await db.commit()
    cursor = await db.execute("SELECT last_insert_rowid()")
    capture_id = (await cursor.fetchone())[0]
    await db.execute(
        "INSERT INTO activities (capture_id, started_at, summary, tags, task_category, "
        "task_category_confidence, productivity_state, productivity_confidence) "
        "VALUES (?, datetime('now'), 'coding', '[\"python\"]', 'work', 0.9, 'focused', 0.85)",
        (capture_id,)
    )
    await db.commit()
    cursor = await db.execute("SELECT task_category, productivity_state FROM activities")
    row = await cursor.fetchone()
    assert row == ("work", "focused")

async def test_journals_date_unique(db):
    await db.execute("INSERT INTO journals (date, content) VALUES ('2026-04-12', 'Day one')")
    await db.commit()
    with pytest.raises(Exception):
        await db.execute("INSERT INTO journals (date, content) VALUES ('2026-04-12', 'Duplicate')")
        await db.commit()

async def test_app_exclusions_name_unique(db):
    await db.execute("INSERT INTO app_exclusions (app_name) VALUES ('1Password')")
    await db.commit()
    with pytest.raises(Exception):
        await db.execute("INSERT INTO app_exclusions (app_name) VALUES ('1Password')")
        await db.commit()
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd daemon && uv run pytest tests/test_db.py -v
```

Expected: `ModuleNotFoundError: No module named 'brn_daemon.db'`

- [ ] **Step 3: Implement db.py**

Create `daemon/src/brn_daemon/db.py`:
```python
import os
import aiosqlite
from pathlib import Path

def get_brn_home() -> Path:
    override = os.environ.get("BRN_HOME")
    if override:
        return Path(override)
    return Path.home() / ".2brn"

def get_db_path() -> Path:
    return get_brn_home() / "2brn.db"

async def init_db() -> None:
    home = get_brn_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "screenshots").mkdir(exist_ok=True)

    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS captures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at DATETIME NOT NULL,
                app_name TEXT,
                window_title TEXT,
                file_path TEXT,
                ocr_text TEXT,
                phash TEXT,
                trigger TEXT CHECK(trigger IN ('heartbeat', 'change'))
            );

            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                capture_id INTEGER REFERENCES captures(id),
                started_at DATETIME NOT NULL,
                ended_at DATETIME,
                summary TEXT,
                tags TEXT,
                chroma_id TEXT,
                task_category TEXT CHECK(task_category IN (
                    'work','research','play','learning',
                    'communication','creative','admin','other'
                )),
                task_category_confidence REAL,
                productivity_state TEXT CHECK(productivity_state IN (
                    'productive','focused','chilling','procrastinating',
                    'distracted','in-meeting','idle'
                )),
                productivity_confidence REAL,
                category_overridden_by_user INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS journals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                content TEXT,
                generated_at DATETIME,
                edited_by_user INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS app_exclusions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_name TEXT UNIQUE NOT NULL,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_captures_captured_at ON captures(captured_at);
            CREATE INDEX IF NOT EXISTS idx_activities_capture_id ON activities(capture_id);
            CREATE INDEX IF NOT EXISTS idx_activities_started_at ON activities(started_at);
            CREATE INDEX IF NOT EXISTS idx_journals_date ON journals(date);
        """)
        await conn.commit()
```

Also create `daemon/src/brn_daemon/__init__.py` (empty):
```python
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd daemon && uv run pytest tests/test_db.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/__init__.py daemon/src/brn_daemon/db.py daemon/tests/
git commit -m "feat: SQLite schema — captures, activities, journals, app_exclusions tables"
```

---

## Task 3: Config & Keychain

**Files:**
- Create: `daemon/src/brn_daemon/config.py`

- [ ] **Step 1: Write the failing test**

Create `daemon/tests/test_config.py`:
```python
import json
import pytest
from brn_daemon.config import load_config, save_config, Config, DEFAULT_CONFIG

def test_load_config_returns_defaults_when_no_file(tmp_home):
    cfg = load_config()
    assert cfg.gateway_url == "http://localhost:8888"
    assert cfg.capture_interval_seconds == 60
    assert cfg.purge_months == 6
    assert cfg.paused is False

def test_save_and_reload_config(tmp_home):
    cfg = load_config()
    cfg.paused = True
    cfg.capture_interval_seconds == 30
    save_config(cfg)
    reloaded = load_config()
    assert reloaded.paused is True

def test_config_file_written_as_json(tmp_home):
    cfg = load_config()
    save_config(cfg)
    config_path = tmp_home / "config.json"
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert "gateway_url" in data
    assert "gateway_token" not in data  # token stored in keychain, not file
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd daemon && uv run pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'brn_daemon.config'`

- [ ] **Step 3: Implement config.py**

Create `daemon/src/brn_daemon/config.py`:
```python
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from brn_daemon.db import get_brn_home

KEYCHAIN_SERVICE = "2brn"
KEYCHAIN_USERNAME = "jll_gateway_token"

@dataclass
class Config:
    gateway_url: str = "http://localhost:8888"
    capture_interval_seconds: int = 60
    purge_months: int = 6
    paused: bool = False
    excluded_apps: list = None

    def __post_init__(self):
        if self.excluded_apps is None:
            self.excluded_apps = []

DEFAULT_CONFIG = Config()

def _config_path() -> Path:
    return get_brn_home() / "config.json"

def load_config() -> Config:
    path = _config_path()
    if not path.exists():
        return Config()
    try:
        data = json.loads(path.read_text())
        return Config(
            gateway_url=data.get("gateway_url", DEFAULT_CONFIG.gateway_url),
            capture_interval_seconds=data.get("capture_interval_seconds", DEFAULT_CONFIG.capture_interval_seconds),
            purge_months=data.get("purge_months", DEFAULT_CONFIG.purge_months),
            paused=data.get("paused", DEFAULT_CONFIG.paused),
            excluded_apps=data.get("excluded_apps", []),
        )
    except (json.JSONDecodeError, KeyError):
        return Config()

def save_config(cfg: Config) -> None:
    get_brn_home().mkdir(parents=True, exist_ok=True)
    data = asdict(cfg)
    data.pop("excluded_apps", None)  # stored in DB, not config file
    _config_path().write_text(json.dumps(data, indent=2))

def get_gateway_token() -> str | None:
    try:
        import keyring
        return keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_USERNAME)
    except Exception:
        return os.environ.get("BRN_GATEWAY_TOKEN")

def set_gateway_token(token: str) -> None:
    try:
        import keyring
        keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_USERNAME, token)
    except Exception:
        pass  # fall back to env var at runtime
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd daemon && uv run pytest tests/test_config.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/config.py daemon/tests/test_config.py
git commit -m "feat: config load/save + keychain-backed gateway token"
```

---

## Task 4: Dedup Engine

**Files:**
- Create: `daemon/src/brn_daemon/dedup.py`
- Create: `daemon/tests/test_dedup.py`

- [ ] **Step 1: Write the failing test**

Create `daemon/tests/test_dedup.py`:
```python
import pytest
from PIL import Image
import numpy as np
from brn_daemon.dedup import compute_phash, is_duplicate

def _solid_image(color: tuple, size=(100, 100)) -> Image.Image:
    arr = np.full((size[1], size[0], 3), color, dtype=np.uint8)
    return Image.fromarray(arr)

def test_identical_images_are_duplicate():
    img = _solid_image((100, 149, 200))
    h = compute_phash(img)
    assert is_duplicate(h, h, threshold=0.95) is True

def test_very_different_images_are_not_duplicate():
    img_a = _solid_image((0, 0, 0))
    img_b = _solid_image((255, 255, 255))
    h_a = compute_phash(img_a)
    h_b = compute_phash(img_b)
    assert is_duplicate(h_a, h_b, threshold=0.95) is False

def test_slightly_different_images_are_not_duplicate():
    img_a = _solid_image((100, 100, 100))
    # change a small portion
    arr = np.full((100, 100, 3), (100, 100, 100), dtype=np.uint8)
    arr[0:30, 0:30] = (200, 50, 10)
    img_b = Image.fromarray(arr)
    h_a = compute_phash(img_a)
    h_b = compute_phash(img_b)
    # significant change → not duplicate
    assert is_duplicate(h_a, h_b, threshold=0.95) is False

def test_compute_phash_returns_string():
    img = _solid_image((123, 45, 67))
    h = compute_phash(img)
    assert isinstance(h, str)
    assert len(h) > 0

def test_none_prev_hash_is_not_duplicate():
    img = _solid_image((10, 20, 30))
    h = compute_phash(img)
    assert is_duplicate(h, None, threshold=0.95) is False
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd daemon && uv run pytest tests/test_dedup.py -v
```

Expected: `ModuleNotFoundError: No module named 'brn_daemon.dedup'`

- [ ] **Step 3: Implement dedup.py**

Create `daemon/src/brn_daemon/dedup.py`:
```python
from PIL import Image
import imagehash

_HASH_BITS = 64  # phash produces 64-bit hash → max distance = 64

def compute_phash(image: Image.Image) -> str:
    return str(imagehash.phash(image))

def is_duplicate(current_hash: str, prev_hash: str | None, threshold: float = 0.95) -> bool:
    if prev_hash is None:
        return False
    h1 = imagehash.hex_to_hash(current_hash)
    h2 = imagehash.hex_to_hash(prev_hash)
    distance = h1 - h2  # Hamming distance
    similarity = 1.0 - (distance / _HASH_BITS)
    return similarity >= threshold
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd daemon && uv run pytest tests/test_dedup.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/dedup.py daemon/tests/test_dedup.py
git commit -m "feat: perceptual hash dedup — discard near-identical frames before OCR"
```

---

## Task 5: OCR Pipeline

**Files:**
- Create: `daemon/src/brn_daemon/ocr.py`
- Create: `daemon/tests/test_ocr.py`

- [ ] **Step 1: Write the failing test**

Create `daemon/tests/test_ocr.py`:
```python
import pytest
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from brn_daemon.ocr import extract_text, is_text_sparse

def _blank_image() -> Image.Image:
    return Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))

def _text_image(text: str) -> Image.Image:
    img = Image.new("RGB", (400, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), text, fill=(0, 0, 0))
    return img

def test_extract_text_from_blank_returns_empty_string():
    img = _blank_image()
    result = extract_text(img)
    assert isinstance(result, str)
    # blank image may produce whitespace or empty
    assert result.strip() == "" or len(result.strip()) < 5

def test_extract_text_from_text_image():
    img = _text_image("Hello World")
    result = extract_text(img)
    assert "Hello" in result or "World" in result

def test_is_text_sparse_true_for_empty():
    assert is_text_sparse("") is True
    assert is_text_sparse("   ") is True
    assert is_text_sparse("ab") is True

def test_is_text_sparse_false_for_content():
    assert is_text_sparse("This is a normal sentence with enough text.") is False

def test_extract_text_returns_string_type():
    img = _blank_image()
    result = extract_text(img)
    assert isinstance(result, str)
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd daemon && uv run pytest tests/test_ocr.py -v
```

Expected: `ModuleNotFoundError: No module named 'brn_daemon.ocr'`

- [ ] **Step 3: Implement ocr.py**

Create `daemon/src/brn_daemon/ocr.py`:
```python
from PIL import Image
import pytesseract
import logging

logger = logging.getLogger(__name__)

def extract_text(image: Image.Image) -> str:
    try:
        text = pytesseract.image_to_string(image, timeout=10)
        return text.strip()
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return ""

def is_text_sparse(text: str, min_chars: int = 20) -> bool:
    return len(text.strip()) < min_chars
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd daemon && uv run pytest tests/test_ocr.py -v
```

Expected: `5 passed` (requires Tesseract installed: `brew install tesseract` / `apt install tesseract-ocr`)

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/ocr.py daemon/tests/test_ocr.py
git commit -m "feat: OCR pipeline — pytesseract wrapper with sparse-text detection"
```

---

## Task 6: Gateway Client

**Files:**
- Create: `daemon/src/brn_daemon/gateway.py`

- [ ] **Step 1: Write the failing test**

Create `daemon/tests/test_gateway.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from brn_daemon.gateway import GatewayClient

@pytest.fixture
def client():
    return GatewayClient(base_url="http://localhost:8888", token="test-token")

async def test_chat_complete_returns_content(client):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"summary":"coding","tags":["python"],"task_category":"work","task_category_confidence":0.9,"productivity_state":"focused","productivity_confidence":0.85}'
    with patch.object(client._client.chat.completions, "create", new=AsyncMock(return_value=mock_response)):
        result = await client.chat_complete([{"role": "user", "content": "test"}])
    assert result == mock_response.choices[0].message.content

async def test_embed_returns_list(client):
    mock_response = MagicMock()
    mock_response.data = [MagicMock()]
    mock_response.data[0].embedding = [0.1, 0.2, 0.3]
    with patch.object(client._client.embeddings, "create", new=AsyncMock(return_value=mock_response)):
        result = await client.embed("hello world")
    assert result == [0.1, 0.2, 0.3]

async def test_chat_complete_retries_on_failure(client):
    call_count = 0
    async def flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("connection error")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"
        return mock_response
    with patch.object(client._client.chat.completions, "create", new=flaky):
        result = await client.chat_complete([{"role": "user", "content": "test"}])
    assert result == "ok"
    assert call_count == 3
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd daemon && uv run pytest tests/test_gateway.py -v
```

Expected: `ModuleNotFoundError: No module named 'brn_daemon.gateway'`

- [ ] **Step 3: Implement gateway.py**

Create `daemon/src/brn_daemon/gateway.py`:
```python
import asyncio
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "GPT_4_1"
_DEFAULT_EMBED_MODEL = "text-embedding-ada-002"
_MAX_RETRIES = 3


class GatewayClient:
    def __init__(self, base_url: str, token: str):
        self._client = AsyncOpenAI(
            base_url=f"{base_url}/v1",
            api_key=token or "no-token",
        )

    async def chat_complete(
        self,
        messages: list[dict],
        model: str = _DEFAULT_MODEL,
        stream: bool = False,
    ) -> str:
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=stream,
                )
                return resp.choices[0].message.content
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning("Gateway attempt %d failed: %s — retrying in %ds", attempt + 1, exc, wait)
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
                else:
                    raise

    async def chat_stream(self, messages: list[dict], model: str = _DEFAULT_MODEL):
        stream = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def embed(self, text: str, model: str = _DEFAULT_EMBED_MODEL) -> list[float]:
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._client.embeddings.create(model=model, input=text)
                return resp.data[0].embedding
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning("Embed attempt %d failed: %s — retrying in %ds", attempt + 1, exc, wait)
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
                else:
                    raise


def make_gateway_client() -> GatewayClient:
    from brn_daemon.config import load_config, get_gateway_token
    cfg = load_config()
    token = get_gateway_token() or ""
    return GatewayClient(base_url=cfg.gateway_url, token=token)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd daemon && uv run pytest tests/test_gateway.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/gateway.py daemon/tests/test_gateway.py
git commit -m "feat: JLL GPT Gateway client — chat completions + embeddings + retry logic"
```

---

## Task 7: Inference Worker

**Files:**
- Create: `daemon/src/brn_daemon/inference.py`
- Create: `daemon/tests/test_inference.py`

- [ ] **Step 1: Write the failing test**

Create `daemon/tests/test_inference.py`:
```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from brn_daemon.inference import build_inference_prompt, parse_inference_response, InferenceResult

def test_build_prompt_includes_app_and_ocr():
    prompt = build_inference_prompt(
        app_name="Visual Studio Code",
        window_title="main.py — 2brn",
        ocr_text="def capture_screen():\n    pass"
    )
    assert "Visual Studio Code" in prompt
    assert "main.py" in prompt
    assert "def capture_screen" in prompt

def test_parse_valid_inference_response():
    raw = json.dumps({
        "summary": "User was writing Python code in VS Code.",
        "tags": ["coding", "python"],
        "task_category": "work",
        "task_category_confidence": 0.92,
        "productivity_state": "focused",
        "productivity_confidence": 0.88
    })
    result = parse_inference_response(raw)
    assert isinstance(result, InferenceResult)
    assert result.task_category == "work"
    assert result.productivity_state == "focused"
    assert result.task_category_confidence == 0.92
    assert "coding" in result.tags

def test_parse_handles_json_wrapped_in_markdown():
    raw = '```json\n{"summary":"test","tags":[],"task_category":"work","task_category_confidence":0.8,"productivity_state":"focused","productivity_confidence":0.7}\n```'
    result = parse_inference_response(raw)
    assert result.task_category == "work"

def test_parse_invalid_response_returns_defaults():
    result = parse_inference_response("not json at all")
    assert result.task_category == "other"
    assert result.productivity_state == "idle"
    assert result.task_category_confidence == 0.0

def test_parse_unknown_category_falls_back_to_other():
    raw = json.dumps({
        "summary": "unknown",
        "tags": [],
        "task_category": "INVALID_CATEGORY",
        "task_category_confidence": 0.5,
        "productivity_state": "focused",
        "productivity_confidence": 0.5
    })
    result = parse_inference_response(raw)
    assert result.task_category == "other"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd daemon && uv run pytest tests/test_inference.py -v
```

Expected: `ModuleNotFoundError: No module named 'brn_daemon.inference'`

- [ ] **Step 3: Implement inference.py**

Create `daemon/src/brn_daemon/inference.py`:
```python
import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"work", "research", "play", "learning", "communication", "creative", "admin", "other"}
VALID_STATES = {"productive", "focused", "chilling", "procrastinating", "distracted", "in-meeting", "idle"}

INFERENCE_SYSTEM_PROMPT = """You are analyzing screen activity. Given screen content, return ONLY a valid JSON object with these exact keys:
- summary: string, 1-2 sentences describing what the user was doing
- tags: array of strings, specific activity keywords (max 5)
- task_category: one of exactly: work, research, play, learning, communication, creative, admin, other
- task_category_confidence: float between 0 and 1
- productivity_state: one of exactly: productive, focused, chilling, procrastinating, distracted, in-meeting, idle
- productivity_confidence: float between 0 and 1
Return ONLY the JSON. No explanation. No markdown."""


@dataclass
class InferenceResult:
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    task_category: str = "other"
    task_category_confidence: float = 0.0
    productivity_state: str = "idle"
    productivity_confidence: float = 0.0


def build_inference_prompt(app_name: str, window_title: str, ocr_text: str) -> str:
    return f"App: {app_name} | Window: {window_title}\nOCR text:\n{ocr_text[:2000]}"


def parse_inference_response(raw: str) -> InferenceResult:
    # Strip markdown code fences if present
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
        category = data.get("task_category", "other")
        if category not in VALID_CATEGORIES:
            category = "other"
        state = data.get("productivity_state", "idle")
        if state not in VALID_STATES:
            state = "idle"
        return InferenceResult(
            summary=str(data.get("summary", "")),
            tags=list(data.get("tags", [])),
            task_category=category,
            task_category_confidence=float(data.get("task_category_confidence", 0.0)),
            productivity_state=state,
            productivity_confidence=float(data.get("productivity_confidence", 0.0)),
        )
    except Exception as exc:
        logger.warning("Failed to parse inference response: %s | raw: %s", exc, raw[:200])
        return InferenceResult()


class InferenceQueue:
    def __init__(self, gateway, db_path_fn):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._gateway = gateway
        self._db_path_fn = db_path_fn

    async def enqueue(self, capture_id: int, app_name: str, window_title: str, ocr_text: str) -> None:
        await self._queue.put((capture_id, app_name, window_title, ocr_text))

    async def run(self) -> None:
        import aiosqlite
        while True:
            capture_id, app_name, window_title, ocr_text = await self._queue.get()
            try:
                user_prompt = build_inference_prompt(app_name, window_title, ocr_text)
                raw = await self._gateway.chat_complete([
                    {"role": "system", "content": INFERENCE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ])
                result = parse_inference_response(raw)
                now = datetime.now(timezone.utc).isoformat()
                async with aiosqlite.connect(self._db_path_fn()) as conn:
                    await conn.execute(
                        """INSERT INTO activities
                           (capture_id, started_at, summary, tags, task_category,
                            task_category_confidence, productivity_state, productivity_confidence)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (capture_id, now, result.summary, json.dumps(result.tags),
                         result.task_category, result.task_category_confidence,
                         result.productivity_state, result.productivity_confidence),
                    )
                    await conn.commit()
            except Exception as exc:
                logger.error("Inference failed for capture %d: %s", capture_id, exc)
            finally:
                self._queue.task_done()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd daemon && uv run pytest tests/test_inference.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/inference.py daemon/tests/test_inference.py
git commit -m "feat: inference worker — async queue, JLL GPT prompt, structured JSON parse"
```

---

## Task 8: Capture Engine

**Files:**
- Create: `daemon/src/brn_daemon/capture.py`

- [ ] **Step 1: Write the failing test**

Create `daemon/tests/test_capture.py`:
```python
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from PIL import Image
import numpy as np

def _make_mock_screenshot(color=(100, 100, 100)):
    arr = np.full((1080, 1920, 3), color, dtype=np.uint8)
    return Image.fromarray(arr)

def test_get_active_app_returns_string():
    from brn_daemon.capture import get_active_app
    app_name, window_title = get_active_app()
    assert isinstance(app_name, str)
    assert isinstance(window_title, str)

def test_save_screenshot_creates_file(tmp_home):
    from brn_daemon.capture import save_screenshot
    from brn_daemon.db import get_brn_home
    img = _make_mock_screenshot()
    path = save_screenshot(img)
    assert path.exists()
    assert path.suffix == ".jpg"
    # should be under ~/.2brn/screenshots/
    assert str(get_brn_home()) in str(path)

def test_save_screenshot_nested_by_date(tmp_home):
    from brn_daemon.capture import save_screenshot
    img = _make_mock_screenshot()
    path = save_screenshot(img)
    # path should be YYYY/MM/DD/<timestamp>.jpg
    parts = path.parts
    assert len(parts) >= 4
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd daemon && uv run pytest tests/test_capture.py -v
```

Expected: `ModuleNotFoundError: No module named 'brn_daemon.capture'`

- [ ] **Step 3: Implement capture.py**

Create `daemon/src/brn_daemon/capture.py`:
```python
import logging
import platform
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
import mss
import mss.tools

from brn_daemon.db import get_brn_home

logger = logging.getLogger(__name__)


def get_active_app() -> tuple[str, str]:
    """Return (app_name, window_title) for the currently focused window."""
    system = platform.system()
    try:
        if system == "Darwin":
            from AppKit import NSWorkspace  # type: ignore
            ws = NSWorkspace.sharedWorkspace()
            app = ws.frontmostApplication()
            app_name = app.localizedName() or ""
            # Get window title via Quartz
            try:
                import Quartz  # type: ignore
                wins = Quartz.CGWindowListCopyWindowInfo(
                    Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
                    Quartz.kCGNullWindowID,
                )
                for w in wins:
                    if w.get("kCGWindowOwnerName") == app_name and w.get("kCGWindowName"):
                        return app_name, w["kCGWindowName"]
            except Exception:
                pass
            return app_name, ""
        elif system == "Windows":
            import pygetwindow as gw  # type: ignore
            win = gw.getActiveWindow()
            if win:
                return win.title.split(" - ")[-1] if " - " in win.title else win.title, win.title
            return "", ""
        else:
            # Linux: use xdotool
            import subprocess
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=2
            )
            title = result.stdout.strip()
            return title, title
    except Exception as exc:
        logger.debug("Could not get active app: %s", exc)
        return "", ""


def capture_screenshot() -> Image.Image:
    """Capture the primary monitor and return a PIL Image."""
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # primary monitor
        raw = sct.grab(monitor)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def save_screenshot(image: Image.Image) -> Path:
    """Save screenshot as JPEG under ~/.2brn/screenshots/YYYY/MM/DD/<ts>.jpg"""
    now = datetime.now(timezone.utc)
    dir_path = get_brn_home() / "screenshots" / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d")
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{now.strftime('%H%M%S_%f')}.jpg"
    image.save(file_path, "JPEG", quality=80)
    return file_path
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd daemon && uv run pytest tests/test_capture.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/capture.py daemon/tests/test_capture.py
git commit -m "feat: capture engine — mss screenshot, active app detection, JPEG save"
```

---

## Task 9: Embedding Service + ChromaDB

**Files:**
- Create: `daemon/src/brn_daemon/embeddings.py`
- Create: `daemon/tests/test_embeddings.py`

- [ ] **Step 1: Write the failing test**

Create `daemon/tests/test_embeddings.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from brn_daemon.embeddings import EmbeddingService, ChromaStore

@pytest.fixture
def chroma_store(tmp_home):
    return ChromaStore(persist_dir=str(tmp_home / "chroma"))

@pytest.fixture
def mock_gateway():
    gw = MagicMock()
    gw.embed = AsyncMock(return_value=[0.1] * 384)
    return gw

def test_chroma_store_initialises(chroma_store):
    col = chroma_store.collection
    assert col is not None
    assert col.name == "activity_memories"

def test_chroma_store_add_and_query(chroma_store):
    chroma_store.add(
        doc_id="test-1",
        text="writing Python code in VS Code",
        metadata={"timestamp": "2026-04-12T10:00:00", "app_name": "Code",
                  "tags": "coding,python", "date": "2026-04-12",
                  "task_category": "work", "productivity_state": "focused"},
        embedding=[0.1] * 384,
    )
    results = chroma_store.query(embedding=[0.1] * 384, n_results=1)
    assert len(results["ids"][0]) == 1
    assert results["ids"][0][0] == "test-1"

def test_chroma_store_update_chroma_id_in_db(tmp_home, chroma_store):
    import asyncio
    import aiosqlite
    from brn_daemon.db import init_db, get_db_path

    async def run():
        await init_db()
        async with aiosqlite.connect(get_db_path()) as conn:
            await conn.execute(
                "INSERT INTO captures (captured_at, trigger) VALUES (datetime('now'), 'heartbeat')"
            )
            await conn.commit()
            cur = await conn.execute("SELECT last_insert_rowid()")
            cap_id = (await cur.fetchone())[0]
            await conn.execute(
                "INSERT INTO activities (capture_id, started_at, summary, tags, task_category, "
                "task_category_confidence, productivity_state, productivity_confidence) "
                "VALUES (?, datetime('now'), 'coding', '[]', 'work', 0.9, 'focused', 0.8)",
                (cap_id,)
            )
            await conn.commit()
            cur = await conn.execute("SELECT last_insert_rowid()")
            act_id = (await cur.fetchone())[0]
            return act_id

    act_id = asyncio.run(run())
    chroma_store.add(
        doc_id=f"activity-{act_id}",
        text="coding in VS Code",
        metadata={"timestamp": "2026-04-12T10:00:00", "app_name": "Code",
                  "tags": "coding", "date": "2026-04-12",
                  "task_category": "work", "productivity_state": "focused"},
        embedding=[0.1] * 384,
    )
    assert chroma_store.collection.count() == 1
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd daemon && uv run pytest tests/test_embeddings.py -v
```

Expected: `ModuleNotFoundError: No module named 'brn_daemon.embeddings'`

- [ ] **Step 3: Implement embeddings.py**

Create `daemon/src/brn_daemon/embeddings.py`:
```python
import logging
import aiosqlite
import chromadb
from chromadb.config import Settings
from pathlib import Path

from brn_daemon.db import get_brn_home, get_db_path

logger = logging.getLogger(__name__)

COLLECTION_NAME = "activity_memories"


class ChromaStore:
    def __init__(self, persist_dir: str | None = None):
        dir_path = persist_dir or str(get_brn_home() / "chroma")
        self._client = chromadb.PersistentClient(
            path=dir_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def collection(self):
        return self._collection

    def add(self, doc_id: str, text: str, metadata: dict, embedding: list[float]) -> None:
        self._collection.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata],
            embeddings=[embedding],
        )

    def query(self, embedding: list[float], n_results: int = 10,
              where: dict | None = None) -> dict:
        kwargs = {"query_embeddings": [embedding], "n_results": n_results,
                  "include": ["documents", "metadatas", "distances"]}
        if where:
            kwargs["where"] = where
        return self._collection.query(**kwargs)


class EmbeddingService:
    def __init__(self, gateway, chroma_store: ChromaStore):
        self._gateway = gateway
        self._store = chroma_store

    async def embed_activity(self, activity_id: int, summary: str, metadata: dict) -> None:
        try:
            embedding = await self._gateway.embed(summary)
            doc_id = f"activity-{activity_id}"
            self._store.add(doc_id=doc_id, text=summary, metadata=metadata, embedding=embedding)
            # Write chroma_id back to SQLite
            async with aiosqlite.connect(get_db_path()) as conn:
                await conn.execute(
                    "UPDATE activities SET chroma_id = ? WHERE id = ?",
                    (doc_id, activity_id),
                )
                await conn.commit()
        except Exception as exc:
            logger.error("Failed to embed activity %d: %s", activity_id, exc)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd daemon && uv run pytest tests/test_embeddings.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/embeddings.py daemon/tests/test_embeddings.py
git commit -m "feat: ChromaDB embedding service — activity summaries indexed for semantic search"
```

---

## Task 10: Journal Generator

**Files:**
- Create: `daemon/src/brn_daemon/journal.py`
- Create: `daemon/tests/test_journal.py`

- [ ] **Step 1: Write the failing test**

Create `daemon/tests/test_journal.py`:
```python
import pytest
import asyncio
import aiosqlite
from unittest.mock import AsyncMock, MagicMock
from datetime import date
from brn_daemon.db import init_db, get_db_path
from brn_daemon.journal import build_journal_prompt, JournalGenerator

def test_build_journal_prompt_includes_summaries():
    summaries = ["Worked on Python code", "Reviewed emails", "Team standup meeting"]
    prompt = build_journal_prompt("2026-04-12", summaries)
    assert "2026-04-12" in prompt
    assert "Python code" in prompt
    assert "emails" in prompt
    assert "standup" in prompt

def test_build_journal_prompt_empty_day():
    prompt = build_journal_prompt("2026-04-12", [])
    assert "2026-04-12" in prompt
    assert "no recorded" in prompt.lower() or "no activities" in prompt.lower()

async def test_generate_saves_to_db(tmp_home):
    await init_db()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO captures (captured_at, trigger) VALUES ('2026-04-12T10:00:00', 'heartbeat')"
        )
        await conn.commit()
        cur = await conn.execute("SELECT last_insert_rowid()")
        cap_id = (await cur.fetchone())[0]
        await conn.execute(
            "INSERT INTO activities (capture_id, started_at, summary, tags, task_category, "
            "task_category_confidence, productivity_state, productivity_confidence) "
            "VALUES (?, '2026-04-12T10:00:00', 'Worked on Python', '[]', 'work', 0.9, 'focused', 0.85)",
            (cap_id,)
        )
        await conn.commit()

    mock_gateway = MagicMock()
    mock_gateway.chat_complete = AsyncMock(return_value="Today I wrote Python code and focused deeply.")

    gen = JournalGenerator(gateway=mock_gateway)
    await gen.generate(target_date=date(2026, 4, 12))

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT content, edited_by_user FROM journals WHERE date = '2026-04-12'")
        row = await cur.fetchone()
    assert row is not None
    assert "Python" in row[0]
    assert row[1] == 0

async def test_generate_skips_if_user_edited(tmp_home):
    await init_db()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO journals (date, content, edited_by_user) VALUES ('2026-04-12', 'My edit', 1)"
        )
        await conn.commit()

    mock_gateway = MagicMock()
    mock_gateway.chat_complete = AsyncMock(return_value="New content")
    gen = JournalGenerator(gateway=mock_gateway)
    await gen.generate(target_date=date(2026, 4, 12))

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT content FROM journals WHERE date = '2026-04-12'")
        row = await cur.fetchone()
    assert row[0] == "My edit"  # not overwritten
    mock_gateway.chat_complete.assert_not_called()
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd daemon && uv run pytest tests/test_journal.py -v
```

Expected: `ModuleNotFoundError: No module named 'brn_daemon.journal'`

- [ ] **Step 3: Implement journal.py**

Create `daemon/src/brn_daemon/journal.py`:
```python
import logging
import aiosqlite
from datetime import date, datetime, timezone

from brn_daemon.db import get_db_path

logger = logging.getLogger(__name__)

JOURNAL_SYSTEM_PROMPT = """You write personal daily journal entries.
Tone: reflective, honest, human, first-person.
Include: what was worked on, key moments, productivity patterns.
Do not be preachy or give unsolicited advice.
Write 2-4 paragraphs in flowing prose. Use markdown."""


def build_journal_prompt(target_date: str, summaries: list[str]) -> str:
    if not summaries:
        return (
            f"Date: {target_date}\n"
            f"There were no recorded activities for this day. "
            f"Write a brief journal entry noting that this was an unrecorded day."
        )
    joined = "\n".join(f"- {s}" for s in summaries)
    return f"Date: {target_date}\n\nActivities:\n{joined}\n\nWrite the journal entry."


class JournalGenerator:
    def __init__(self, gateway):
        self._gateway = gateway

    async def generate(self, target_date: date) -> str | None:
        date_str = target_date.isoformat()

        async with aiosqlite.connect(get_db_path()) as conn:
            # Check if user has edited this entry
            cur = await conn.execute(
                "SELECT id, edited_by_user FROM journals WHERE date = ?", (date_str,)
            )
            existing = await cur.fetchone()
            if existing and existing[1] == 1:
                logger.info("Journal for %s was edited by user — skipping regeneration", date_str)
                return None

            # Fetch summaries for the day
            cur = await conn.execute(
                "SELECT summary FROM activities "
                "WHERE date(started_at) = ? AND summary IS NOT NULL AND summary != '' "
                "ORDER BY started_at",
                (date_str,),
            )
            rows = await cur.fetchall()
            summaries = [r[0] for r in rows]

        prompt = build_journal_prompt(date_str, summaries)
        content = await self._gateway.chat_complete([
            {"role": "system", "content": JOURNAL_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])

        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(get_db_path()) as conn:
            await conn.execute(
                """INSERT INTO journals (date, content, generated_at, edited_by_user)
                   VALUES (?, ?, ?, 0)
                   ON CONFLICT(date) DO UPDATE SET
                     content = excluded.content,
                     generated_at = excluded.generated_at
                   WHERE edited_by_user = 0""",
                (date_str, content, now),
            )
            await conn.commit()

        return content
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd daemon && uv run pytest tests/test_journal.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/journal.py daemon/tests/test_journal.py
git commit -m "feat: journal generator — daily narrative via JLL GPT, respects user edits"
```

---

## Task 11: Chat RAG Pipeline

**Files:**
- Create: `daemon/src/brn_daemon/chat.py`
- Create: `daemon/tests/test_chat.py`

- [ ] **Step 1: Write the failing test**

Create `daemon/tests/test_chat.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from brn_daemon.chat import build_rag_prompt, ChatService

def test_build_rag_prompt_includes_question_and_context():
    context_chunks = [
        {"text": "User was coding in VS Code", "metadata": {"date": "2026-04-12", "app_name": "Code"}},
        {"text": "User reviewed pull requests on GitHub", "metadata": {"date": "2026-04-12", "app_name": "Chrome"}},
    ]
    prompt = build_rag_prompt(
        question="What was I working on last Tuesday?",
        context_chunks=context_chunks,
    )
    assert "VS Code" in prompt
    assert "pull requests" in prompt
    assert "What was I working on" in prompt

def test_build_rag_prompt_no_context():
    prompt = build_rag_prompt(question="What did I do today?", context_chunks=[])
    assert "What did I do today?" in prompt
    assert "no recorded" in prompt.lower() or "no context" in prompt.lower()

async def test_chat_service_calls_gateway(tmp_home):
    from brn_daemon.db import init_db
    await init_db()

    mock_gateway = MagicMock()
    mock_gateway.embed = AsyncMock(return_value=[0.1] * 384)

    mock_chroma = MagicMock()
    mock_chroma.query = MagicMock(return_value={
        "ids": [["activity-1"]],
        "documents": [["coding in Python"]],
        "metadatas": [[{"date": "2026-04-12", "app_name": "Code", "task_category": "work",
                        "productivity_state": "focused", "tags": "coding", "timestamp": "2026-04-12T10:00:00"}]],
        "distances": [[0.1]],
    })

    chunks_seen = []
    async def fake_stream(messages, model=None):
        for chunk in ["Here ", "is ", "your ", "answer."]:
            chunks_seen.append(chunk)
            yield chunk

    mock_gateway.chat_stream = fake_stream

    service = ChatService(gateway=mock_gateway, chroma_store=mock_chroma)
    collected = []
    async for chunk in service.chat(question="What was I doing?"):
        collected.append(chunk)

    assert "".join(collected) == "Here is your answer."
    mock_chroma.query.assert_called_once()
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd daemon && uv run pytest tests/test_chat.py -v
```

Expected: `ModuleNotFoundError: No module named 'brn_daemon.chat'`

- [ ] **Step 3: Implement chat.py**

Create `daemon/src/brn_daemon/chat.py`:
```python
import logging
from typing import AsyncIterator

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = """You are a personal second brain assistant.
You help the user recall what they did on their computer.
Answer questions based ONLY on the provided context.
If context is insufficient, say so honestly.
Be concise, specific, and cite dates/apps when relevant."""


def build_rag_prompt(question: str, context_chunks: list[dict]) -> str:
    if not context_chunks:
        return (
            f"Context: No recorded activities found for this query.\n\n"
            f"User question: {question}\n\n"
            f"Answer honestly that there is no recorded context for this query."
        )
    context_text = "\n\n".join(
        f"[{i+1}] Date: {c['metadata'].get('date','?')} | App: {c['metadata'].get('app_name','?')}\n{c['text']}"
        for i, c in enumerate(context_chunks)
    )
    return f"Context from your activity history:\n\n{context_text}\n\nUser question: {question}"


class ChatService:
    def __init__(self, gateway, chroma_store):
        self._gateway = gateway
        self._store = chroma_store

    async def chat(
        self,
        question: str,
        date_filter: str | None = None,
        category_filter: str | None = None,
        n_results: int = 10,
    ) -> AsyncIterator[str]:
        # 1. Embed the query
        try:
            query_embedding = await self._gateway.embed(question)
        except Exception as exc:
            logger.error("Failed to embed query: %s", exc)
            yield "Sorry, I couldn't process your question right now."
            return

        # 2. Build ChromaDB where filter
        where = {}
        if date_filter:
            where["date"] = {"$eq": date_filter}
        if category_filter:
            where["task_category"] = {"$eq": category_filter}

        # 3. Semantic search
        try:
            results = self._store.query(
                embedding=query_embedding,
                n_results=n_results,
                where=where if where else None,
            )
        except Exception as exc:
            logger.error("ChromaDB query failed: %s", exc)
            yield "Sorry, I couldn't search your activity history right now."
            return

        # 4. Build context chunks
        context_chunks = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        for doc, meta in zip(docs, metas):
            context_chunks.append({"text": doc, "metadata": meta})

        # 5. Build and stream RAG response
        user_prompt = build_rag_prompt(question, context_chunks)
        messages = [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        async for chunk in self._gateway.chat_stream(messages):
            yield chunk
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd daemon && uv run pytest tests/test_chat.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/chat.py daemon/tests/test_chat.py
git commit -m "feat: RAG chat pipeline — embed query, ChromaDB search, stream JLL GPT answer"
```

---

## Task 12: Auto-Purge

**Files:**
- Create: `daemon/src/brn_daemon/purge.py`
- Create: `daemon/tests/test_purge.py`

- [ ] **Step 1: Write the failing test**

Create `daemon/tests/test_purge.py`:
```python
import pytest
import asyncio
import aiosqlite
from datetime import datetime, timezone, timedelta
from pathlib import Path
from brn_daemon.db import init_db, get_db_path, get_brn_home
from brn_daemon.purge import purge_old_captures

async def _insert_capture(conn, captured_at: str, file_path: str):
    await conn.execute(
        "INSERT INTO captures (captured_at, trigger, file_path) VALUES (?, 'heartbeat', ?)",
        (captured_at, file_path)
    )

async def test_purge_removes_old_screenshots(tmp_home):
    await init_db()
    screenshots_dir = get_brn_home() / "screenshots"

    # Create fake screenshot files
    old_file = screenshots_dir / "old.jpg"
    old_file.parent.mkdir(parents=True, exist_ok=True)
    old_file.write_bytes(b"fake")

    new_file = screenshots_dir / "new.jpg"
    new_file.write_bytes(b"fake")

    old_date = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    new_date = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(get_db_path()) as conn:
        await _insert_capture(conn, old_date, str(old_file))
        await _insert_capture(conn, new_date, str(new_file))
        await conn.commit()

    await purge_old_captures(months=6)

    assert not old_file.exists(), "Old file should be deleted"
    assert new_file.exists(), "New file should be kept"

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT COUNT(*) FROM captures")
        count = (await cur.fetchone())[0]
    assert count == 1  # only new capture remains

async def test_purge_handles_missing_file_gracefully(tmp_home):
    await init_db()
    old_date = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO captures (captured_at, trigger, file_path) VALUES (?, 'heartbeat', ?)",
            (old_date, "/nonexistent/path.jpg")
        )
        await conn.commit()
    # Should not raise even though file doesn't exist
    await purge_old_captures(months=6)
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd daemon && uv run pytest tests/test_purge.py -v
```

Expected: `ModuleNotFoundError: No module named 'brn_daemon.purge'`

- [ ] **Step 3: Implement purge.py**

Create `daemon/src/brn_daemon/purge.py`:
```python
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import aiosqlite
from brn_daemon.db import get_db_path

logger = logging.getLogger(__name__)


async def purge_old_captures(months: int = 6) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
    cutoff_str = cutoff.isoformat()
    deleted_count = 0

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "SELECT id, file_path FROM captures WHERE captured_at < ?",
            (cutoff_str,)
        )
        old_captures = await cur.fetchall()

        for capture_id, file_path in old_captures:
            if file_path:
                try:
                    p = Path(file_path)
                    if p.exists():
                        p.unlink()
                        deleted_count += 1
                except Exception as exc:
                    logger.warning("Could not delete file %s: %s", file_path, exc)

        ids = [row[0] for row in old_captures]
        if ids:
            placeholders = ",".join("?" * len(ids))
            await conn.execute(f"DELETE FROM activities WHERE capture_id IN ({placeholders})", ids)
            await conn.execute(f"DELETE FROM captures WHERE id IN ({placeholders})", ids)
            await conn.commit()

    logger.info("Purged %d old captures (cutoff: %s)", len(old_captures), cutoff_str)
    return deleted_count
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd daemon && uv run pytest tests/test_purge.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add daemon/src/brn_daemon/purge.py daemon/tests/test_purge.py
git commit -m "feat: auto-purge — delete screenshots + DB rows older than N months"
```

---

## Task 13: Daemon API Routes + Main

**Files:**
- Create: `daemon/src/brn_daemon/routes/__init__.py`
- Create: `daemon/src/brn_daemon/routes/status.py`
- Create: `daemon/src/brn_daemon/routes/captures.py`
- Create: `daemon/src/brn_daemon/routes/activities.py`
- Create: `daemon/src/brn_daemon/routes/journal_routes.py`
- Create: `daemon/src/brn_daemon/routes/chat_routes.py`
- Create: `daemon/src/brn_daemon/routes/settings_routes.py`
- Create: `daemon/src/brn_daemon/routes/insights_routes.py`
- Create: `daemon/src/brn_daemon/main.py`

- [ ] **Step 1: Create routes/__init__.py** (empty)

```python
```

- [ ] **Step 2: Create routes/status.py**

```python
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class StatusResponse(BaseModel):
    status: str  # "capturing" | "paused" | "error"
    capture_count_today: int
    last_captured_at: str | None
    daemon_version: str

@router.get("/status", response_model=StatusResponse)
async def get_status():
    from brn_daemon.main import app_state
    return StatusResponse(
        status="paused" if app_state["paused"] else "capturing",
        capture_count_today=app_state.get("capture_count_today", 0),
        last_captured_at=app_state.get("last_captured_at"),
        daemon_version="0.1.0",
    )
```

- [ ] **Step 3: Create routes/captures.py**

```python
from fastapi import APIRouter, Query
from pydantic import BaseModel
import aiosqlite
from brn_daemon.db import get_db_path

router = APIRouter()

class CaptureRecord(BaseModel):
    id: int
    captured_at: str
    app_name: str | None
    window_title: str | None
    file_path: str | None
    trigger: str | None

@router.get("/captures", response_model=list[CaptureRecord])
async def get_captures(date: str = Query(..., description="YYYY-MM-DD")):
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT id, captured_at, app_name, window_title, file_path, trigger "
            "FROM captures WHERE date(captured_at) = ? ORDER BY captured_at",
            (date,)
        )
        rows = await cur.fetchall()
    return [CaptureRecord(**dict(r)) for r in rows]
```

- [ ] **Step 4: Create routes/activities.py**

```python
from fastapi import APIRouter, Query
from pydantic import BaseModel
import aiosqlite
from brn_daemon.db import get_db_path

router = APIRouter()

class ActivityRecord(BaseModel):
    id: int
    capture_id: int | None
    started_at: str
    ended_at: str | None
    summary: str | None
    tags: str | None
    task_category: str | None
    task_category_confidence: float | None
    productivity_state: str | None
    productivity_confidence: float | None
    category_overridden_by_user: bool

@router.get("/activities", response_model=list[ActivityRecord])
async def get_activities(
    date: str = Query(None),
    task_category: str = Query(None),
    productivity_state: str = Query(None),
):
    conditions = []
    params = []
    if date:
        conditions.append("date(started_at) = ?")
        params.append(date)
    if task_category:
        conditions.append("task_category = ?")
        params.append(task_category)
    if productivity_state:
        conditions.append("productivity_state = ?")
        params.append(productivity_state)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            f"SELECT id, capture_id, started_at, ended_at, summary, tags, "
            f"task_category, task_category_confidence, productivity_state, "
            f"productivity_confidence, category_overridden_by_user "
            f"FROM activities {where} ORDER BY started_at",
            params
        )
        rows = await cur.fetchall()
    return [ActivityRecord(**dict(r)) for r in rows]

@router.patch("/activities/{activity_id}/override")
async def override_activity(activity_id: int, task_category: str, productivity_state: str):
    from brn_daemon.inference import VALID_CATEGORIES, VALID_STATES
    if task_category not in VALID_CATEGORIES or productivity_state not in VALID_STATES:
        from fastapi import HTTPException
        raise HTTPException(400, "Invalid category or state")
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "UPDATE activities SET task_category = ?, productivity_state = ?, "
            "category_overridden_by_user = 1 WHERE id = ?",
            (task_category, productivity_state, activity_id)
        )
        await conn.commit()
    return {"ok": True}
```

- [ ] **Step 5: Create routes/journal_routes.py**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import aiosqlite
from brn_daemon.db import get_db_path

router = APIRouter()

class JournalResponse(BaseModel):
    date: str
    content: str | None
    generated_at: str | None
    edited_by_user: bool

class JournalUpdateRequest(BaseModel):
    content: str

@router.get("/journal/{date}", response_model=JournalResponse)
async def get_journal(date: str):
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT date, content, generated_at, edited_by_user FROM journals WHERE date = ?",
            (date,)
        )
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, f"No journal for {date}")
    return JournalResponse(**dict(row))

@router.post("/journal/{date}/generate")
async def generate_journal(date: str):
    from brn_daemon.main import app_state
    from datetime import date as date_type
    gen = app_state.get("journal_generator")
    if not gen:
        raise HTTPException(503, "Journal generator not available")
    from datetime import date as dt_date
    target = dt_date.fromisoformat(date)
    content = await gen.generate(target_date=target)
    return {"ok": True, "generated": content is not None}

@router.put("/journal/{date}")
async def update_journal(date: str, body: JournalUpdateRequest):
    from datetime import datetime, timezone
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            """INSERT INTO journals (date, content, generated_at, edited_by_user)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(date) DO UPDATE SET
                 content = excluded.content,
                 edited_by_user = 1""",
            (date, body.content, datetime.now(timezone.utc).isoformat())
        )
        await conn.commit()
    return {"ok": True}
```

- [ ] **Step 6: Create routes/chat_routes.py**

```python
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

router = APIRouter()

class ChatRequest(BaseModel):
    question: str
    date_filter: str | None = None
    category_filter: str | None = None

@router.post("/chat")
async def chat_endpoint(body: ChatRequest):
    from brn_daemon.main import app_state
    service = app_state.get("chat_service")
    if not service:
        async def error_stream():
            yield "data: " + json.dumps({"chunk": "Chat service unavailable."}) + "\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    async def event_stream():
        async for chunk in service.chat(
            question=body.question,
            date_filter=body.date_filter,
            category_filter=body.category_filter,
        ):
            yield "data: " + json.dumps({"chunk": chunk}) + "\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 7: Create routes/settings_routes.py**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from brn_daemon.config import load_config, save_config, get_gateway_token, set_gateway_token
import aiosqlite
from brn_daemon.db import get_db_path

router = APIRouter()

class SettingsResponse(BaseModel):
    gateway_url: str
    capture_interval_seconds: int
    purge_months: int
    paused: bool
    has_token: bool

class SettingsUpdateRequest(BaseModel):
    gateway_url: str | None = None
    gateway_token: str | None = None
    capture_interval_seconds: int | None = None
    purge_months: int | None = None

class ExclusionRequest(BaseModel):
    app_name: str

@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    cfg = load_config()
    return SettingsResponse(
        gateway_url=cfg.gateway_url,
        capture_interval_seconds=cfg.capture_interval_seconds,
        purge_months=cfg.purge_months,
        paused=cfg.paused,
        has_token=bool(get_gateway_token()),
    )

@router.put("/settings")
async def update_settings(body: SettingsUpdateRequest):
    cfg = load_config()
    if body.gateway_url is not None:
        cfg.gateway_url = body.gateway_url
    if body.capture_interval_seconds is not None:
        cfg.capture_interval_seconds = body.capture_interval_seconds
    if body.purge_months is not None:
        cfg.purge_months = body.purge_months
    if body.gateway_token is not None:
        set_gateway_token(body.gateway_token)
    save_config(cfg)
    return {"ok": True}

@router.post("/settings/paused")
async def set_paused(paused: bool):
    from brn_daemon.main import app_state
    cfg = load_config()
    cfg.paused = paused
    save_config(cfg)
    app_state["paused"] = paused
    return {"ok": True, "paused": paused}

@router.get("/settings/exclusions")
async def list_exclusions():
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT app_name, added_at FROM app_exclusions ORDER BY app_name")
        rows = await cur.fetchall()
    return [dict(r) for r in rows]

@router.post("/settings/exclusions")
async def add_exclusion(body: ExclusionRequest):
    async with aiosqlite.connect(get_db_path()) as conn:
        try:
            await conn.execute("INSERT INTO app_exclusions (app_name) VALUES (?)", (body.app_name,))
            await conn.commit()
        except Exception:
            raise HTTPException(409, f"{body.app_name} is already excluded")
    return {"ok": True}

@router.delete("/settings/exclusions/{app_name}")
async def remove_exclusion(app_name: str):
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute("DELETE FROM app_exclusions WHERE app_name = ?", (app_name,))
        await conn.commit()
    return {"ok": True}
```

- [ ] **Step 8: Create routes/insights_routes.py**

```python
from fastapi import APIRouter, Query
import aiosqlite
from brn_daemon.db import get_db_path

router = APIRouter()

@router.get("/insights/daily")
async def daily_insights(date: str = Query(...)):
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            """SELECT task_category, COUNT(*) as count,
               AVG(task_category_confidence) as avg_confidence
               FROM activities WHERE date(started_at) = ?
               GROUP BY task_category ORDER BY count DESC""",
            (date,)
        )
        categories = [{"task_category": r[0], "count": r[1], "avg_confidence": r[2]}
                      for r in await cur.fetchall()]
        cur = await conn.execute(
            """SELECT productivity_state, COUNT(*) as count
               FROM activities WHERE date(started_at) = ?
               GROUP BY productivity_state ORDER BY count DESC""",
            (date,)
        )
        states = [{"productivity_state": r[0], "count": r[1]} for r in await cur.fetchall()]
        cur = await conn.execute(
            """SELECT app_name, COUNT(*) as count FROM captures
               WHERE date(captured_at) = ? AND app_name IS NOT NULL
               GROUP BY app_name ORDER BY count DESC LIMIT 10""",
            (date,)
        )
        top_apps = [{"app_name": r[0], "count": r[1]} for r in await cur.fetchall()]
    return {"date": date, "categories": categories, "productivity_states": states, "top_apps": top_apps}

@router.get("/insights/weekly")
async def weekly_insights(week_start: str = Query(..., description="YYYY-MM-DD of Monday")):
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            """SELECT date(started_at) as day, task_category, COUNT(*) as count
               FROM activities
               WHERE date(started_at) >= ? AND date(started_at) < date(?, '+7 days')
               GROUP BY day, task_category ORDER BY day""",
            (week_start, week_start)
        )
        rows = await cur.fetchall()
    return {"week_start": week_start, "data": [{"day": r[0], "task_category": r[1], "count": r[2]} for r in rows]}
```

- [ ] **Step 9: Create main.py**

Create `daemon/src/brn_daemon/main.py`:
```python
import asyncio
import logging
import signal
from contextlib import asynccontextmanager

from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import date as dt_date

from brn_daemon.db import init_db, get_db_path
from brn_daemon.config import load_config, get_gateway_token
from brn_daemon.gateway import GatewayClient
from brn_daemon.capture import capture_screenshot, get_active_app, save_screenshot
from brn_daemon.dedup import compute_phash, is_duplicate
from brn_daemon.ocr import extract_text, is_text_sparse
from brn_daemon.inference import InferenceQueue
from brn_daemon.embeddings import ChromaStore, EmbeddingService
from brn_daemon.journal import JournalGenerator
from brn_daemon.chat import ChatService
from brn_daemon.purge import purge_old_captures

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Shared mutable state accessible from routes
app_state: dict = {
    "paused": False,
    "capture_count_today": 0,
    "last_captured_at": None,
    "journal_generator": None,
    "chat_service": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    cfg = load_config()
    app_state["paused"] = cfg.paused

    gateway = GatewayClient(base_url=cfg.gateway_url, token=get_gateway_token() or "")
    chroma = ChromaStore()
    inference_queue = InferenceQueue(gateway=gateway, db_path_fn=get_db_path)
    embedding_service = EmbeddingService(gateway=gateway, chroma_store=chroma)
    journal_gen = JournalGenerator(gateway=gateway)
    chat_service = ChatService(gateway=gateway, chroma_store=chroma)

    app_state["journal_generator"] = journal_gen
    app_state["chat_service"] = chat_service

    scheduler = AsyncIOScheduler()
    # End-of-day journal generation at midnight
    scheduler.add_job(
        lambda: asyncio.create_task(journal_gen.generate(target_date=dt_date.today())),
        "cron", hour=0, minute=0, id="journal_daily"
    )
    # Monthly purge check (runs daily)
    scheduler.add_job(
        lambda: asyncio.create_task(purge_old_captures(months=cfg.purge_months)),
        "cron", hour=2, minute=0, id="purge_daily"
    )
    scheduler.start()

    # Start inference queue consumer
    inference_task = asyncio.create_task(inference_queue.run())

    # Start capture loop
    capture_task = asyncio.create_task(
        _capture_loop(cfg, inference_queue)
    )

    yield

    # Shutdown
    capture_task.cancel()
    inference_task.cancel()
    scheduler.shutdown()


async def _capture_loop(cfg, inference_queue: InferenceQueue):
    import aiosqlite
    prev_phash = None
    last_heartbeat = 0.0

    while True:
        try:
            await asyncio.sleep(1)
            now = asyncio.get_event_loop().time()

            if app_state["paused"]:
                continue

            # Check app exclusions
            app_name, window_title = get_active_app()
            async with aiosqlite.connect(get_db_path()) as conn:
                cur = await conn.execute(
                    "SELECT 1 FROM app_exclusions WHERE app_name = ?", (app_name,)
                )
                if await cur.fetchone():
                    continue

            # Capture screenshot
            img = capture_screenshot()
            current_phash = compute_phash(img)

            is_heartbeat = (now - last_heartbeat) >= cfg.capture_interval_seconds
            is_change = not is_duplicate(current_phash, prev_phash, threshold=0.95)

            if not is_heartbeat and not is_change:
                continue

            trigger = "heartbeat" if is_heartbeat else "change"
            file_path = save_screenshot(img)
            ocr_text = extract_text(img) if not is_text_sparse("") else extract_text(img)

            async with aiosqlite.connect(get_db_path()) as conn:
                from datetime import datetime, timezone
                now_iso = datetime.now(timezone.utc).isoformat()
                cur = await conn.execute(
                    "INSERT INTO captures (captured_at, app_name, window_title, file_path, ocr_text, phash, trigger) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (now_iso, app_name, window_title, str(file_path), ocr_text, current_phash, trigger)
                )
                await conn.commit()
                capture_id = cur.lastrowid

            app_state["last_captured_at"] = now_iso
            app_state["capture_count_today"] = app_state.get("capture_count_today", 0) + 1
            prev_phash = current_phash
            if is_heartbeat:
                last_heartbeat = now

            if not is_text_sparse(ocr_text):
                await inference_queue.enqueue(capture_id, app_name, window_title, ocr_text)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Capture loop error: %s", exc)


def create_app() -> FastAPI:
    from brn_daemon.routes import status, captures, activities
    from brn_daemon.routes import journal_routes, chat_routes, settings_routes, insights_routes

    app = FastAPI(title="2brn Daemon", lifespan=lifespan)
    app.include_router(status.router)
    app.include_router(captures.router)
    app.include_router(activities.router)
    app.include_router(journal_routes.router)
    app.include_router(chat_routes.router)
    app.include_router(settings_routes.router)
    app.include_router(insights_routes.router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("brn_daemon.main:app", host="127.0.0.1", port=7842, reload=False)
```

- [ ] **Step 10: Test daemon starts**

```bash
cd daemon && uv run python -m brn_daemon.main
```

Expected: `INFO: Application startup complete.` on port 7842. `Ctrl+C` to stop.

- [ ] **Step 11: Commit**

```bash
git add daemon/src/brn_daemon/routes/ daemon/src/brn_daemon/main.py
git commit -m "feat: FastAPI daemon — all routes, capture loop, scheduler, lifespan wiring"
```

---

## Task 14: Electron Main Process

**Files:**
- Create: `ui/electron/main.ts`
- Create: `ui/electron/preload.ts`
- Create: `ui/vite.config.ts`

- [ ] **Step 1: Create ui/vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import electron from 'vite-plugin-electron'

export default defineConfig({
  plugins: [
    react(),
    electron([
      {
        entry: 'electron/main.ts',
        vite: {
          build: { outDir: 'dist/electron' },
        },
      },
      {
        entry: 'electron/preload.ts',
        onstart(options) {
          options.reload()
        },
        vite: {
          build: { outDir: 'dist/electron' },
        },
      },
    ]),
  ],
})
```

- [ ] **Step 2: Create ui/electron/preload.ts**

```typescript
import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  getDaemonPort: () => ipcRenderer.invoke('get-daemon-port'),
  onDaemonStatus: (callback: (status: string) => void) =>
    ipcRenderer.on('daemon-status', (_event, status) => callback(status)),
})
```

- [ ] **Step 3: Create ui/electron/main.ts**

```typescript
import { app, BrowserWindow, ipcMain } from 'electron'
import { spawn, ChildProcess } from 'child_process'
import * as path from 'path'
import * as http from 'http'

const DAEMON_PORT = 7842
const DAEMON_HOST = '127.0.0.1'
let daemon: ChildProcess | null = null
let mainWindow: BrowserWindow | null = null
let daemonRestartAttempts = 0

function isDev(): boolean {
  return !app.isPackaged
}

function startDaemon(): void {
  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3'
  const daemonArgs = ['-m', 'brn_daemon.main']
  const daemonCwd = isDev()
    ? path.join(__dirname, '../../daemon')
    : path.join(process.resourcesPath, 'daemon')

  daemon = spawn(pythonCmd, daemonArgs, {
    cwd: daemonCwd,
    env: { ...process.env },
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  daemon.stdout?.on('data', (data: Buffer) => {
    console.log('[daemon]', data.toString().trim())
  })

  daemon.stderr?.on('data', (data: Buffer) => {
    console.error('[daemon:err]', data.toString().trim())
  })

  daemon.on('exit', (code) => {
    console.log(`[daemon] exited with code ${code}`)
    if (daemonRestartAttempts < 3) {
      daemonRestartAttempts++
      setTimeout(startDaemon, 10_000)
    } else {
      mainWindow?.webContents.send('daemon-status', 'error')
    }
  })
}

function pollDaemonHealth(): void {
  let failures = 0
  setInterval(() => {
    const req = http.get(
      { hostname: DAEMON_HOST, port: DAEMON_PORT, path: '/status', timeout: 3000 },
      (res) => {
        if (res.statusCode === 200) {
          failures = 0
          daemonRestartAttempts = 0
          mainWindow?.webContents.send('daemon-status', 'ok')
        }
      }
    )
    req.on('error', () => {
      failures++
      if (failures >= 2) {
        mainWindow?.webContents.send('daemon-status', 'offline')
      }
    })
    req.end()
  }, 5000)
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (isDev()) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../index.html'))
  }
}

ipcMain.handle('get-daemon-port', () => DAEMON_PORT)

app.whenReady().then(() => {
  startDaemon()
  createWindow()
  pollDaemonHealth()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('quit', () => {
  daemon?.kill()
})
```

- [ ] **Step 4: Commit**

```bash
git add ui/electron/ ui/vite.config.ts
git commit -m "feat: Electron main process — daemon subprocess management, health polling, window"
```

---

## Task 15: React App Shell + API Client

**Files:**
- Create: `ui/src/api/types.ts`
- Create: `ui/src/api/client.ts`
- Create: `ui/src/App.tsx`
- Create: `ui/src/main.tsx`
- Create: `ui/src/index.css`

- [ ] **Step 1: Create ui/src/api/types.ts**

```typescript
export interface DaemonStatus {
  status: 'capturing' | 'paused' | 'error'
  capture_count_today: number
  last_captured_at: string | null
  daemon_version: string
}

export interface CaptureRecord {
  id: number
  captured_at: string
  app_name: string | null
  window_title: string | null
  file_path: string | null
  trigger: string | null
}

export interface ActivityRecord {
  id: number
  capture_id: number | null
  started_at: string
  ended_at: string | null
  summary: string | null
  tags: string | null
  task_category: string | null
  task_category_confidence: number | null
  productivity_state: string | null
  productivity_confidence: number | null
  category_overridden_by_user: boolean
}

export interface JournalEntry {
  date: string
  content: string | null
  generated_at: string | null
  edited_by_user: boolean
}

export interface DailyInsights {
  date: string
  categories: { task_category: string; count: number; avg_confidence: number }[]
  productivity_states: { productivity_state: string; count: number }[]
  top_apps: { app_name: string; count: number }[]
}

export interface AppSettings {
  gateway_url: string
  capture_interval_seconds: number
  purge_months: number
  paused: boolean
  has_token: boolean
}

export interface AppExclusion {
  app_name: string
  added_at: string
}
```

- [ ] **Step 2: Create ui/src/api/client.ts**

```typescript
import type {
  DaemonStatus, CaptureRecord, ActivityRecord, JournalEntry,
  DailyInsights, AppSettings, AppExclusion
} from './types'

const BASE_URL = 'http://127.0.0.1:7842'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`)
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return res.json()
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`PUT ${path} failed: ${res.status}`)
  return res.json()
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`DELETE ${path} failed: ${res.status}`)
  return res.json()
}

export const api = {
  getStatus: () => get<DaemonStatus>('/status'),
  getCaptures: (date: string) => get<CaptureRecord[]>(`/captures?date=${date}`),
  getActivities: (params: { date?: string; task_category?: string; productivity_state?: string }) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as string[][])
    return get<ActivityRecord[]>(`/activities?${q}`)
  },
  overrideActivity: (id: number, task_category: string, productivity_state: string) =>
    fetch(`${BASE_URL}/activities/${id}/override`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_category, productivity_state }),
    }).then(r => r.json()),
  getJournal: (date: string) => get<JournalEntry>(`/journal/${date}`),
  generateJournal: (date: string) => post(`/journal/${date}/generate`),
  updateJournal: (date: string, content: string) => put(`/journal/${date}`, { content }),
  getSettings: () => get<AppSettings>('/settings'),
  updateSettings: (body: Partial<AppSettings> & { gateway_token?: string }) => put('/settings', body),
  setPaused: (paused: boolean) => post(`/settings/paused?paused=${paused}`),
  getExclusions: () => get<AppExclusion[]>('/settings/exclusions'),
  addExclusion: (app_name: string) => post('/settings/exclusions', { app_name }),
  removeExclusion: (app_name: string) => del(`/settings/exclusions/${encodeURIComponent(app_name)}`),
  getDailyInsights: (date: string) => get<DailyInsights>(`/insights/daily?date=${date}`),

  chatStream: async function* (question: string, date_filter?: string, category_filter?: string) {
    const res = await fetch(`${BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, date_filter, category_filter }),
    })
    if (!res.body) return
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') return
          try {
            const parsed = JSON.parse(data)
            if (parsed.chunk) yield parsed.chunk as string
          } catch { /* skip */ }
        }
      }
    }
  }
}
```

- [ ] **Step 3: Create ui/src/index.css**

```css
@import "tailwindcss";

:root {
  --bg-base: #0d1117;
  --bg-surface: #161b22;
  --bg-elevated: #1e293b;
  --border: #30363d;
  --text-primary: #e6edf3;
  --text-secondary: #8b949e;
  --accent: #58a6ff;
}

body {
  background-color: var(--bg-base);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  margin: 0;
  min-height: 100vh;
}

* { box-sizing: border-box; }

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
```

- [ ] **Step 4: Create ui/src/main.tsx**

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)
```

- [ ] **Step 5: Create ui/src/App.tsx**

```tsx
import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './components/Dashboard'
import Chat from './components/Chat'
import Journal from './components/Journal'
import Timeline from './components/Timeline'
import Insights from './components/Insights'
import Settings from './components/Settings'

const navItems = [
  { to: '/', label: '⌂ Home', end: true },
  { to: '/chat', label: '💬 Chat' },
  { to: '/journal', label: '📔 Journal' },
  { to: '/timeline', label: '⏱ Timeline' },
  { to: '/insights', label: '📊 Insights' },
  { to: '/settings', label: '⚙ Settings' },
]

export default function App() {
  return (
    <div className="flex h-screen overflow-hidden">
      <nav className="w-48 bg-[#0d1117] border-r border-[#30363d] flex flex-col py-4 px-2 gap-1 flex-shrink-0">
        <div className="text-[#58a6ff] font-bold text-lg px-3 mb-4">2brn</div>
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `px-3 py-2 rounded-md text-sm transition-colors ${
                isActive
                  ? 'bg-[#1e3a5f] text-[#93c5fd]'
                  : 'text-[#8b949e] hover:text-[#e6edf3] hover:bg-[#161b22]'
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <main className="flex-1 overflow-auto bg-[#0d1117]">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/journal" element={<Journal />} />
          <Route path="/timeline" element={<Timeline />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}
```

- [ ] **Step 6: Confirm UI compiles**

```bash
cd ui && pnpm dev
```

Expected: Vite dev server starts at `http://localhost:5173`, no TypeScript errors.

- [ ] **Step 7: Commit**

```bash
git add ui/src/
git commit -m "feat: React app shell — routing, API client, TypeScript types, Tailwind CSS"
```

---

## Task 16: Dashboard Component

**Files:**
- Create: `ui/src/components/shared/StatsBar.tsx`
- Create: `ui/src/components/shared/DaemonStatus.tsx`
- Create: `ui/src/components/Dashboard.tsx`

- [ ] **Step 1: Create ui/src/components/shared/DaemonStatus.tsx**

```tsx
import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { DaemonStatus as DaemonStatusType } from '../../api/types'

export default function DaemonStatus() {
  const [status, setStatus] = useState<DaemonStatusType | null>(null)

  useEffect(() => {
    const poll = async () => {
      try {
        const s = await api.getStatus()
        setStatus(s)
      } catch {
        setStatus(null)
      }
    }
    poll()
    const id = setInterval(poll, 5000)
    return () => clearInterval(id)
  }, [])

  if (!status) {
    return (
      <span className="flex items-center gap-1.5 text-xs text-red-400">
        <span className="w-2 h-2 rounded-full bg-red-500" />
        daemon offline
      </span>
    )
  }

  const color = status.status === 'capturing' ? 'bg-green-500' : status.status === 'paused' ? 'bg-yellow-500' : 'bg-red-500'
  const textColor = status.status === 'capturing' ? 'text-green-400' : status.status === 'paused' ? 'text-yellow-400' : 'text-red-400'

  return (
    <span className={`flex items-center gap-1.5 text-xs ${textColor}`}>
      <span className={`w-2 h-2 rounded-full ${color} animate-pulse`} />
      {status.status} · {status.capture_count_today} captures today
    </span>
  )
}
```

- [ ] **Step 2: Create ui/src/components/shared/StatsBar.tsx**

```tsx
import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { DailyInsights } from '../../api/types'

function toDateStr(d: Date) {
  return d.toISOString().split('T')[0]
}

export default function StatsBar() {
  const [insights, setInsights] = useState<DailyInsights | null>(null)

  useEffect(() => {
    api.getDailyInsights(toDateStr(new Date()))
      .then(setInsights)
      .catch(() => setInsights(null))
    const id = setInterval(() => {
      api.getDailyInsights(toDateStr(new Date())).then(setInsights).catch(() => {})
    }, 30000)
    return () => clearInterval(id)
  }, [])

  const topCategory = insights?.categories[0]?.task_category ?? '—'
  const topState = insights?.productivity_states[0]?.productivity_state ?? '—'
  const totalCaptures = insights?.categories.reduce((s, c) => s + c.count, 0) ?? 0
  const productiveCount = insights?.productivity_states
    .filter(s => ['productive', 'focused'].includes(s.productivity_state))
    .reduce((s, c) => s + c.count, 0) ?? 0
  const productivePct = totalCaptures > 0
    ? Math.round((productiveCount / totalCaptures) * 100)
    : 0

  const stateColors: Record<string, string> = {
    productive: 'text-green-400', focused: 'text-green-400',
    chilling: 'text-blue-400', procrastinating: 'text-red-400',
    distracted: 'text-orange-400', 'in-meeting': 'text-purple-400', idle: 'text-gray-400',
  }

  return (
    <div className="flex gap-3">
      {[
        { label: 'now', value: topState, color: stateColors[topState] ?? 'text-gray-400' },
        { label: 'top task', value: topCategory, color: 'text-blue-400' },
        { label: 'productive', value: `${productivePct}%`, color: 'text-green-400' },
      ].map(item => (
        <div key={item.label} className="bg-[#1e293b] rounded-lg px-4 py-3 text-center min-w-[90px]">
          <div className={`text-base font-bold ${item.color}`}>{item.value}</div>
          <div className="text-xs text-[#64748b] mt-0.5">{item.label}</div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Create ui/src/components/Dashboard.tsx**

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import StatsBar from './shared/StatsBar'
import DaemonStatus from './shared/DaemonStatus'
import { api } from '../api/client'

export default function Dashboard() {
  const [question, setQuestion] = useState('')
  const navigate = useNavigate()

  const handleChat = (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim()) return
    navigate('/chat', { state: { initialQuestion: question } })
    setQuestion('')
  }

  const tiles = [
    { label: '📔 Journal', path: '/journal', desc: "Today's narrative" },
    { label: '⏱ Timeline', path: '/timeline', desc: 'Visual activity timeline' },
    { label: '📊 Insights', path: '/insights', desc: 'Productivity analytics' },
    { label: '⚙ Settings', path: '/settings', desc: 'Configure 2brn' },
  ]

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold text-[#e6edf3]">your second brain</h1>
        <DaemonStatus />
      </div>

      <StatsBar />

      <form onSubmit={handleChat} className="mt-8">
        <div className="flex gap-3">
          <input
            className="flex-1 bg-[#1e293b] border border-[#30363d] rounded-xl px-4 py-3 text-[#e6edf3] placeholder-[#64748b] focus:outline-none focus:border-[#58a6ff] text-sm"
            placeholder="Ask your second brain anything..."
            value={question}
            onChange={e => setQuestion(e.target.value)}
          />
          <button
            type="submit"
            className="bg-[#1e40af] hover:bg-[#1d4ed8] text-white px-5 py-3 rounded-xl text-sm font-medium transition-colors"
          >
            Ask
          </button>
        </div>
      </form>

      <div className="grid grid-cols-2 gap-4 mt-8">
        {tiles.map(tile => (
          <button
            key={tile.path}
            onClick={() => navigate(tile.path)}
            className="bg-[#1e293b] hover:bg-[#243447] border border-[#30363d] rounded-xl p-5 text-left transition-colors"
          >
            <div className="text-base font-medium text-[#e6edf3]">{tile.label}</div>
            <div className="text-xs text-[#64748b] mt-1">{tile.desc}</div>
          </button>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add ui/src/components/Dashboard.tsx ui/src/components/shared/
git commit -m "feat: Dashboard — stats bar, daemon status, chat shortcut, quick nav tiles"
```

---

## Task 17: Chat Component

**Files:**
- Create: `ui/src/components/Chat.tsx`

- [ ] **Step 1: Create ui/src/components/Chat.tsx**

```tsx
import { useState, useRef, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { api } from '../api/client'

interface Message {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
}

export default function Chat() {
  const location = useLocation()
  const initialQuestion = (location.state as { initialQuestion?: string })?.initialQuestion ?? ''
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState(initialQuestion)
  const [loading, setLoading] = useState(false)
  const [dateFilter, setDateFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (initialQuestion) {
      handleSend(initialQuestion)
    }
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (question: string = input) => {
    if (!question.trim() || loading) return
    setInput('')
    setLoading(true)
    setMessages(prev => [...prev, { role: 'user', content: question }])
    const assistantIdx = messages.length + 1
    setMessages(prev => [...prev, { role: 'assistant', content: '', streaming: true }])

    try {
      let accumulated = ''
      for await (const chunk of api.chatStream(
        question,
        dateFilter || undefined,
        categoryFilter || undefined,
      )) {
        accumulated += chunk
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: 'assistant', content: accumulated, streaming: true }
          return updated
        })
      }
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = { role: 'assistant', content: accumulated, streaming: false }
        return updated
      })
    } catch (err) {
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = { role: 'assistant', content: 'Sorry, something went wrong.', streaming: false }
        return updated
      })
    } finally {
      setLoading(false)
    }
  }

  const CATEGORIES = ['work', 'research', 'play', 'learning', 'communication', 'creative', 'admin', 'other']

  return (
    <div className="flex flex-col h-full">
      {/* Filter bar */}
      <div className="flex gap-2 p-4 border-b border-[#30363d] flex-wrap">
        <input
          type="date"
          value={dateFilter}
          onChange={e => setDateFilter(e.target.value)}
          className="bg-[#1e293b] border border-[#30363d] rounded-lg px-3 py-1.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff]"
        />
        <select
          value={categoryFilter}
          onChange={e => setCategoryFilter(e.target.value)}
          className="bg-[#1e293b] border border-[#30363d] rounded-lg px-3 py-1.5 text-xs text-[#e6edf3] focus:outline-none focus:border-[#58a6ff]"
        >
          <option value="">All categories</option>
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        {(dateFilter || categoryFilter) && (
          <button
            onClick={() => { setDateFilter(''); setCategoryFilter('') }}
            className="text-xs text-[#64748b] hover:text-[#e6edf3] px-2"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-[#64748b] mt-20 text-sm">
            Ask anything about your past activity...
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[80%] rounded-xl px-4 py-3 text-sm ${
                msg.role === 'user'
                  ? 'bg-[#1e3a5f] text-[#e6edf3]'
                  : 'bg-[#1e293b] text-[#e6edf3]'
              }`}
            >
              {msg.content}
              {msg.streaming && <span className="inline-block w-1.5 h-4 bg-[#58a6ff] ml-1 animate-pulse" />}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={e => { e.preventDefault(); handleSend() }}
        className="p-4 border-t border-[#30363d] flex gap-3"
      >
        <input
          className="flex-1 bg-[#1e293b] border border-[#30363d] rounded-xl px-4 py-3 text-sm text-[#e6edf3] placeholder-[#64748b] focus:outline-none focus:border-[#58a6ff]"
          placeholder="Ask your second brain..."
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="bg-[#1e40af] hover:bg-[#1d4ed8] disabled:opacity-50 text-white px-5 py-3 rounded-xl text-sm font-medium transition-colors"
        >
          {loading ? '...' : '↵'}
        </button>
      </form>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/components/Chat.tsx
git commit -m "feat: Chat component — SSE streaming, date/category filters, conversation thread"
```

---

## Task 18: Journal Component

**Files:**
- Create: `ui/src/components/shared/MarkdownRenderer.tsx`
- Create: `ui/src/components/Journal.tsx`

- [ ] **Step 1: Create ui/src/components/shared/MarkdownRenderer.tsx**

```tsx
import ReactMarkdown from 'react-markdown'

export default function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div className="prose prose-invert prose-sm max-w-none text-[#e6edf3]">
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  )
}
```

- [ ] **Step 2: Create ui/src/components/Journal.tsx**

```tsx
import { useState, useEffect } from 'react'
import { api } from '../api/client'
import type { JournalEntry } from '../api/types'
import MarkdownRenderer from './shared/MarkdownRenderer'

function toDateStr(d: Date) {
  return d.toISOString().split('T')[0]
}

export default function Journal() {
  const [selectedDate, setSelectedDate] = useState(toDateStr(new Date()))
  const [entry, setEntry] = useState<JournalEntry | null>(null)
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setError('')
    api.getJournal(selectedDate)
      .then(e => { setEntry(e); setEditContent(e.content ?? '') })
      .catch(() => { setEntry(null); setEditContent('') })
  }, [selectedDate])

  const handleGenerate = async () => {
    setGenerating(true)
    setError('')
    try {
      await api.generateJournal(selectedDate)
      const refreshed = await api.getJournal(selectedDate)
      setEntry(refreshed)
      setEditContent(refreshed.content ?? '')
    } catch {
      setError('Failed to generate journal entry.')
    } finally {
      setGenerating(false)
    }
  }

  const handleSave = async () => {
    try {
      await api.updateJournal(selectedDate, editContent)
      const refreshed = await api.getJournal(selectedDate)
      setEntry(refreshed)
      setEditing(false)
    } catch {
      setError('Failed to save changes.')
    }
  }

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-[#e6edf3]">Journal</h1>
        <div className="flex items-center gap-3">
          {entry?.edited_by_user && (
            <span className="text-xs text-[#64748b] bg-[#1e293b] px-2 py-1 rounded">edited</span>
          )}
          <input
            type="date"
            value={selectedDate}
            max={toDateStr(new Date())}
            onChange={e => { setSelectedDate(e.target.value); setEditing(false) }}
            className="bg-[#1e293b] border border-[#30363d] rounded-lg px-3 py-1.5 text-sm text-[#e6edf3] focus:outline-none focus:border-[#58a6ff]"
          />
        </div>
      </div>

      {error && <div className="text-red-400 text-sm mb-4">{error}</div>}

      {!entry ? (
        <div className="bg-[#1e293b] rounded-xl p-8 text-center">
          <p className="text-[#64748b] text-sm mb-4">No journal entry for {selectedDate}.</p>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="bg-[#1e40af] hover:bg-[#1d4ed8] disabled:opacity-50 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            {generating ? 'Generating...' : 'Generate Entry'}
          </button>
        </div>
      ) : editing ? (
        <div className="space-y-3">
          <textarea
            value={editContent}
            onChange={e => setEditContent(e.target.value)}
            rows={20}
            className="w-full bg-[#1e293b] border border-[#30363d] rounded-xl px-4 py-3 text-sm text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] font-mono resize-none"
          />
          <div className="flex gap-2 justify-end">
            <button onClick={() => setEditing(false)} className="text-sm text-[#64748b] hover:text-[#e6edf3] px-4 py-2">Cancel</button>
            <button onClick={handleSave} className="bg-[#1e40af] hover:bg-[#1d4ed8] text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors">Save</button>
          </div>
        </div>
      ) : (
        <div className="bg-[#1e293b] rounded-xl p-6">
          <MarkdownRenderer content={entry.content ?? ''} />
          <div className="flex gap-2 mt-6 pt-4 border-t border-[#30363d]">
            <button
              onClick={() => setEditing(true)}
              className="text-sm text-[#64748b] hover:text-[#e6edf3] px-3 py-1.5 rounded-lg hover:bg-[#243447] transition-colors"
            >
              Edit
            </button>
            {!entry.edited_by_user && (
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="text-sm text-[#64748b] hover:text-[#e6edf3] px-3 py-1.5 rounded-lg hover:bg-[#243447] transition-colors disabled:opacity-50"
              >
                {generating ? 'Regenerating...' : 'Regenerate'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/Journal.tsx ui/src/components/shared/MarkdownRenderer.tsx
git commit -m "feat: Journal component — calendar picker, markdown render, edit and regenerate"
```

---

## Task 19: Timeline Component

**Files:**
- Create: `ui/src/components/Timeline.tsx`

- [ ] **Step 1: Create ui/src/components/Timeline.tsx**

```tsx
import { useState, useEffect } from 'react'
import { api } from '../api/client'
import type { ActivityRecord, CaptureRecord } from '../api/types'

function toDateStr(d: Date) { return d.toISOString().split('T')[0] }

const CATEGORY_COLORS: Record<string, string> = {
  work: '#3b82f6', research: '#8b5cf6', play: '#22c55e',
  learning: '#f59e0b', communication: '#06b6d4', creative: '#ec4899',
  admin: '#64748b', other: '#475569',
}

export default function Timeline() {
  const [selectedDate, setSelectedDate] = useState(toDateStr(new Date()))
  const [activities, setActivities] = useState<ActivityRecord[]>([])
  const [captures, setCaptures] = useState<CaptureRecord[]>([])
  const [selected, setSelected] = useState<ActivityRecord | null>(null)

  useEffect(() => {
    Promise.all([
      api.getActivities({ date: selectedDate }),
      api.getCaptures(selectedDate),
    ]).then(([acts, caps]) => {
      setActivities(acts)
      setCaptures(caps)
      setSelected(null)
    }).catch(() => {
      setActivities([])
      setCaptures([])
    })
  }, [selectedDate])

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-[#e6edf3]">Timeline</h1>
        <input
          type="date"
          value={selectedDate}
          max={toDateStr(new Date())}
          onChange={e => setSelectedDate(e.target.value)}
          className="bg-[#1e293b] border border-[#30363d] rounded-lg px-3 py-1.5 text-sm text-[#e6edf3] focus:outline-none focus:border-[#58a6ff]"
        />
      </div>

      {activities.length === 0 ? (
        <div className="text-center text-[#64748b] text-sm mt-20">No activity recorded for {selectedDate}.</div>
      ) : (
        <div className="space-y-2">
          {activities.map(act => {
            const color = CATEGORY_COLORS[act.task_category ?? 'other'] ?? '#475569'
            return (
              <button
                key={act.id}
                onClick={() => setSelected(act === selected ? null : act)}
                className={`w-full text-left bg-[#1e293b] hover:bg-[#243447] border rounded-xl px-4 py-3 transition-colors ${selected?.id === act.id ? 'border-[#58a6ff]' : 'border-[#30363d]'}`}
              >
                <div className="flex items-center gap-3">
                  <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: color }} />
                  <span className="text-xs text-[#64748b] w-16 flex-shrink-0">
                    {new Date(act.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <span className="text-sm text-[#e6edf3] flex-1 truncate">{act.summary ?? '—'}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full flex-shrink-0" style={{ background: color + '33', color }}>
                    {act.task_category ?? 'other'}
                  </span>
                  <span className="text-xs text-[#64748b] flex-shrink-0">{act.productivity_state ?? ''}</span>
                </div>
                {selected?.id === act.id && act.summary && (
                  <div className="mt-3 pt-3 border-t border-[#30363d] text-sm text-[#94a3b8]">
                    {act.summary}
                  </div>
                )}
              </button>
            )
          })}
        </div>
      )}

      <div className="mt-6 text-xs text-[#64748b]">
        {captures.length} captures · {activities.length} activities
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/components/Timeline.tsx
git commit -m "feat: Timeline component — colour-coded activity list by task_category"
```

---

## Task 20: Insights Component

**Files:**
- Create: `ui/src/components/Insights.tsx`

- [ ] **Step 1: Create ui/src/components/Insights.tsx**

```tsx
import { useState, useEffect } from 'react'
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { api } from '../api/client'
import type { DailyInsights } from '../api/types'

function toDateStr(d: Date) { return d.toISOString().split('T')[0] }

const CATEGORY_COLORS: Record<string, string> = {
  work: '#3b82f6', research: '#8b5cf6', play: '#22c55e',
  learning: '#f59e0b', communication: '#06b6d4', creative: '#ec4899',
  admin: '#64748b', other: '#475569',
}

const STATE_COLORS: Record<string, string> = {
  productive: '#22c55e', focused: '#86efac', chilling: '#60a5fa',
  procrastinating: '#ef4444', distracted: '#f97316', 'in-meeting': '#a78bfa', idle: '#64748b',
}

export default function Insights() {
  const [selectedDate, setSelectedDate] = useState(toDateStr(new Date()))
  const [insights, setInsights] = useState<DailyInsights | null>(null)

  useEffect(() => {
    api.getDailyInsights(selectedDate)
      .then(setInsights)
      .catch(() => setInsights(null))
  }, [selectedDate])

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-[#e6edf3]">Insights</h1>
        <input
          type="date"
          value={selectedDate}
          max={toDateStr(new Date())}
          onChange={e => setSelectedDate(e.target.value)}
          className="bg-[#1e293b] border border-[#30363d] rounded-lg px-3 py-1.5 text-sm text-[#e6edf3] focus:outline-none focus:border-[#58a6ff]"
        />
      </div>

      {!insights || insights.categories.length === 0 ? (
        <div className="text-center text-[#64748b] text-sm mt-20">No data for {selectedDate}.</div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Task Category Bar Chart */}
          <div className="bg-[#1e293b] rounded-xl p-5">
            <h2 className="text-sm font-semibold text-[#e6edf3] mb-4">Time by Category</h2>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={insights.categories}>
                <XAxis dataKey="task_category" tick={{ fill: '#64748b', fontSize: 11 }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#0d1117', border: '1px solid #30363d', borderRadius: 8 }}
                  labelStyle={{ color: '#e6edf3' }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {insights.categories.map(entry => (
                    <Cell key={entry.task_category} fill={CATEGORY_COLORS[entry.task_category] ?? '#475569'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Productivity State Donut */}
          <div className="bg-[#1e293b] rounded-xl p-5">
            <h2 className="text-sm font-semibold text-[#e6edf3] mb-4">Productivity Distribution</h2>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={insights.productivity_states}
                  dataKey="count"
                  nameKey="productivity_state"
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                >
                  {insights.productivity_states.map(entry => (
                    <Cell key={entry.productivity_state} fill={STATE_COLORS[entry.productivity_state] ?? '#475569'} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#0d1117', border: '1px solid #30363d', borderRadius: 8 }}
                  labelStyle={{ color: '#e6edf3' }}
                />
                <Legend iconSize={10} wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Top Apps */}
          <div className="bg-[#1e293b] rounded-xl p-5 lg:col-span-2">
            <h2 className="text-sm font-semibold text-[#e6edf3] mb-4">Top Apps</h2>
            <div className="space-y-2">
              {insights.top_apps.slice(0, 8).map(app => {
                const max = insights.top_apps[0]?.count ?? 1
                const pct = Math.round((app.count / max) * 100)
                return (
                  <div key={app.app_name} className="flex items-center gap-3">
                    <span className="text-sm text-[#94a3b8] w-36 truncate flex-shrink-0">{app.app_name || 'Unknown'}</span>
                    <div className="flex-1 bg-[#0d1117] rounded-full h-2">
                      <div className="bg-[#3b82f6] h-2 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-xs text-[#64748b] w-12 text-right flex-shrink-0">{app.count} caps</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/components/Insights.tsx
git commit -m "feat: Insights component — category bar chart, productivity donut, top apps"
```

---

## Task 21: Settings Component

**Files:**
- Create: `ui/src/components/Settings.tsx`

- [ ] **Step 1: Create ui/src/components/Settings.tsx**

```tsx
import { useState, useEffect } from 'react'
import { api } from '../api/client'
import type { AppSettings, AppExclusion } from '../api/types'

export default function Settings() {
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [exclusions, setExclusions] = useState<AppExclusion[]>([])
  const [gatewayUrl, setGatewayUrl] = useState('')
  const [gatewayToken, setGatewayToken] = useState('')
  const [newApp, setNewApp] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    Promise.all([api.getSettings(), api.getExclusions()])
      .then(([s, e]) => {
        setSettings(s)
        setGatewayUrl(s.gateway_url)
        setExclusions(e)
      })
  }, [])

  const handleSaveGateway = async () => {
    setSaving(true)
    try {
      await api.updateSettings({
        gateway_url: gatewayUrl,
        ...(gatewayToken ? { gateway_token: gatewayToken } : {}),
      })
      setGatewayToken('')
      setMessage('Gateway settings saved.')
      const s = await api.getSettings()
      setSettings(s)
    } catch {
      setMessage('Failed to save.')
    } finally {
      setSaving(false)
      setTimeout(() => setMessage(''), 3000)
    }
  }

  const handleTogglePause = async () => {
    if (!settings) return
    await api.setPaused(!settings.paused)
    const s = await api.getSettings()
    setSettings(s)
  }

  const handleAddExclusion = async () => {
    if (!newApp.trim()) return
    await api.addExclusion(newApp.trim())
    setNewApp('')
    setExclusions(await api.getExclusions())
  }

  const handleRemoveExclusion = async (app: string) => {
    await api.removeExclusion(app)
    setExclusions(await api.getExclusions())
  }

  if (!settings) return <div className="p-8 text-[#64748b] text-sm">Loading...</div>

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-8">
      <h1 className="text-xl font-bold text-[#e6edf3]">Settings</h1>

      {message && <div className="text-green-400 text-sm">{message}</div>}

      {/* Capture control */}
      <section className="bg-[#1e293b] rounded-xl p-5">
        <h2 className="text-sm font-semibold text-[#e6edf3] mb-4">Capture</h2>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-[#e6edf3]">{settings.paused ? 'Capture paused' : 'Capture active'}</div>
            <div className="text-xs text-[#64748b] mt-0.5">Toggle background screen capture</div>
          </div>
          <button
            onClick={handleTogglePause}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${settings.paused ? 'bg-green-700 hover:bg-green-600 text-white' : 'bg-red-900 hover:bg-red-800 text-red-200'}`}
          >
            {settings.paused ? 'Resume' : 'Pause'}
          </button>
        </div>
      </section>

      {/* Gateway config */}
      <section className="bg-[#1e293b] rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-[#e6edf3]">JLL GPT Gateway</h2>
        <div>
          <label className="text-xs text-[#64748b] block mb-1">Gateway URL</label>
          <input
            value={gatewayUrl}
            onChange={e => setGatewayUrl(e.target.value)}
            className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-[#e6edf3] focus:outline-none focus:border-[#58a6ff]"
          />
        </div>
        <div>
          <label className="text-xs text-[#64748b] block mb-1">
            Bearer Token {settings.has_token ? '(stored in keychain ✓)' : '(not set)'}
          </label>
          <input
            type="password"
            value={gatewayToken}
            onChange={e => setGatewayToken(e.target.value)}
            placeholder="Enter new token to update..."
            className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-[#e6edf3] focus:outline-none focus:border-[#58a6ff]"
          />
        </div>
        <button
          onClick={handleSaveGateway}
          disabled={saving}
          className="bg-[#1e40af] hover:bg-[#1d4ed8] disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {saving ? 'Saving...' : 'Save Gateway Settings'}
        </button>
      </section>

      {/* App exclusions */}
      <section className="bg-[#1e293b] rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-[#e6edf3]">Excluded Apps</h2>
        <p className="text-xs text-[#64748b]">Apps listed here will never be captured. Add banking, password managers, etc.</p>
        <div className="flex gap-2">
          <input
            value={newApp}
            onChange={e => setNewApp(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleAddExclusion()}
            placeholder="App name (e.g. 1Password)"
            className="flex-1 bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-[#e6edf3] focus:outline-none focus:border-[#58a6ff]"
          />
          <button
            onClick={handleAddExclusion}
            className="bg-[#1e40af] hover:bg-[#1d4ed8] text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            Add
          </button>
        </div>
        {exclusions.length === 0 ? (
          <p className="text-xs text-[#64748b]">No excluded apps.</p>
        ) : (
          <ul className="space-y-2">
            {exclusions.map(ex => (
              <li key={ex.app_name} className="flex items-center justify-between bg-[#0d1117] rounded-lg px-3 py-2">
                <span className="text-sm text-[#e6edf3]">{ex.app_name}</span>
                <button
                  onClick={() => handleRemoveExclusion(ex.app_name)}
                  className="text-xs text-red-400 hover:text-red-300"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Storage */}
      <section className="bg-[#1e293b] rounded-xl p-5 space-y-3">
        <h2 className="text-sm font-semibold text-[#e6edf3]">Storage</h2>
        <p className="text-xs text-[#64748b]">
          Auto-purge: screenshots older than <strong className="text-[#e6edf3]">{settings.purge_months} months</strong> are automatically deleted.
        </p>
        <p className="text-xs text-[#64748b]">Data stored at <code className="text-[#93c5fd]">~/.2brn/</code></p>
      </section>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/components/Settings.tsx
git commit -m "feat: Settings component — gateway config, pause toggle, exclusions, storage info"
```

---

## Task 22: End-to-End Wiring + README

**Files:**
- Modify: `README.md`
- Create: `daemon/src/brn_daemon/routes/__init__.py` (already created in Task 13)

- [ ] **Step 1: Run full daemon test suite**

```bash
cd daemon && uv run pytest tests/ -v
```

Expected: All tests pass. If any fail, fix before continuing.

- [ ] **Step 2: Start the daemon manually**

```bash
cd daemon && uv run python -m brn_daemon.main
```

Expected output:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:7842
```

- [ ] **Step 3: Verify daemon API endpoints**

```bash
curl http://127.0.0.1:7842/status
```

Expected:
```json
{"status":"capturing","capture_count_today":0,"last_captured_at":null,"daemon_version":"0.1.0"}
```

```bash
curl "http://127.0.0.1:7842/activities?date=2026-04-12"
```

Expected: `[]` (empty array, no error)

- [ ] **Step 4: Start the Electron UI in dev mode**

In a second terminal (daemon must be running):
```bash
cd ui && pnpm electron:dev
```

Expected: Electron window opens showing the Dashboard with "daemon offline" resolving to "capturing" within 5 seconds.

- [ ] **Step 5: End-to-end smoke test**

1. Wait 60 seconds for the first heartbeat capture
2. Open the Timeline view — verify a capture appears
3. Open Chat — ask "what was I doing just now?" — verify a response streams back
4. Open Journal — click "Generate Entry" — verify markdown prose is generated and displayed
5. Open Settings — add "1Password" to exclusions — switch to 1Password — wait 60s — verify no new captures from 1Password in Timeline

- [ ] **Step 6: Write README.md**

```markdown
# 2brn — Your Second Brain

A cross-platform desktop app that silently captures what you do on your computer, infers context using AI, and lets you recall anything through natural language chat.

## Features

- 📸 **Passive capture** — hybrid heartbeat (60s) + change detection, perceptual hash dedup
- 🔍 **OCR + AI inference** — Tesseract extracts text; JLL GPT Gateway infers activity summary, task category, and productivity state
- 💬 **Chat interface** — RAG pipeline: ask "what was I doing last Tuesday?" and get accurate answers
- 📔 **Daily journal** — auto-generated first-person narrative of your day, editable
- 📊 **Insights** — time by category, productivity distribution, top apps
- 🔒 **Privacy-first** — raw screenshots never leave your machine; only text summaries sent to gateway

## Requirements

- Python 3.12+
- Node.js 20+ + pnpm
- Tesseract OCR (`brew install tesseract` / `apt install tesseract-ocr`)
- JLL GPT Gateway running at `localhost:8888` (or configured URL)

## Setup

### Daemon
```bash
cd daemon
uv sync
uv run python -m brn_daemon.main
```

### UI (development)
```bash
cd ui
pnpm install
pnpm electron:dev
```

### Configure gateway token
Open Settings in the app and enter your JLL GPT Gateway Bearer token. It is stored securely in the OS keychain.

## Data

All data stored in `~/.2brn/`:
- `2brn.db` — SQLite database
- `screenshots/` — JPEG captures (auto-purged after 6 months)
- `chroma/` — vector embeddings for semantic search
- `config.json` — app configuration (token stored in keychain, not here)
```

- [ ] **Step 7: Final commit**

```bash
git add README.md
git commit -m "docs: add README with setup instructions and feature overview"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ Cross-platform (Electron) — Task 14
- ✅ Screenshot capture hybrid (heartbeat + change) — Task 13 (main.py capture loop)
- ✅ Dedup (perceptual hash) — Task 4
- ✅ OCR pipeline — Task 5
- ✅ Inference (task_category + productivity_state + confidence) — Task 7
- ✅ Async inference queue (non-blocking) — Task 7
- ✅ Embedding service + ChromaDB — Task 9
- ✅ Journal generator (midnight + on-demand, respects user edits) — Task 10
- ✅ Chat RAG pipeline — Task 11
- ✅ Auto-purge (6 months) — Task 12
- ✅ App exclusions — Task 13 routes + Task 21 UI
- ✅ All 7 daemon API route groups — Task 13
- ✅ Dashboard with live stats + chat shortcut — Task 16
- ✅ Chat with SSE streaming + filters — Task 17
- ✅ Journal with edit/regenerate — Task 18
- ✅ Timeline colour-coded by category — Task 19
- ✅ Insights charts — Task 20
- ✅ Settings (gateway, exclusions, pause, storage) — Task 21
- ✅ Bearer token in OS keychain — Task 3
- ✅ Error handling (gateway retry, OCR fallback, disk full) — covered in gateway.py + main.py capture loop
- ✅ Daemon status polling + auto-restart — Task 14 (Electron main.ts)
