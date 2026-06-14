"""Tests for GET /journal/{date}, PUT /journal/{date}, POST /journal/{date}/generate."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def journal_client(tmp_home):
    """FastAPI test client with minimal context stubs for journal routes.

    The populated :class:`AppContext` is attached as ``client.ctx``.
    """
    from brn_daemon.main import create_app
    from brn_daemon.chat import ChatService

    fake_chat_fn = AsyncMock(return_value='{"summary":"x","tags":[],"task_category":"work","task_category_confidence":0.9,"productivity_state":"productive","productivity_confidence":0.9}')
    fake_stream_fn = AsyncMock()
    fake_embed_client = MagicMock()
    fake_embed_client.aclose = AsyncMock()
    fake_chroma = MagicMock()
    fake_chroma.query = AsyncMock(return_value={"documents": [[]], "metadatas": [[]], "distances": [[]]})
    fake_chroma.query_notes = AsyncMock(return_value={"documents": [[]], "metadatas": [[]], "distances": [[]]})

    from brn_daemon.journal import JournalGenerator
    from brn_daemon.blog import BlogGenerator

    app = create_app()
    ctx = app.state.context
    ctx.chat_service = ChatService(
        chat_fn=fake_chat_fn,
        stream_fn=fake_stream_fn,
        embed_client=fake_embed_client,
        chroma_store=fake_chroma,
    )
    ctx.embed_client = fake_embed_client
    ctx.inference_queue = MagicMock()
    ctx.inference_queue._chat_fn = fake_chat_fn
    ctx.inference_queue._embedding_service = MagicMock()
    ctx.plugin_orchestrator = MagicMock()
    ctx.plugin_orchestrator.chat_fn = fake_chat_fn
    ctx.chroma_store = fake_chroma
    ctx.journal_generator = JournalGenerator(chat_fn=fake_chat_fn)
    ctx.blog_generator = BlogGenerator(chat_fn=fake_chat_fn)

    # Init the DB
    from brn_daemon.db import init_db
    await init_db()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.ctx = ctx
        yield client


async def test_get_journal_returns_404_when_not_found(journal_client):
    resp = await journal_client.get("/journal/2026-01-01")
    assert resp.status_code == 404


async def test_put_journal_creates_entry(journal_client):
    resp = await journal_client.put(
        "/journal/2026-05-28",
        json={"content": "My journal entry."},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


async def test_put_journal_then_get_returns_content(journal_client):
    await journal_client.put("/journal/2026-05-28", json={"content": "Written content."})
    resp = await journal_client.get("/journal/2026-05-28")
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "Written content."
    assert data["date"] == "2026-05-28"
    assert data["edited_by_user"] is True


async def test_put_journal_sets_edited_by_user_flag(journal_client):
    await journal_client.put("/journal/2026-05-28", json={"content": "Initial."})
    resp = await journal_client.get("/journal/2026-05-28")
    assert resp.json()["edited_by_user"] is True


async def test_put_journal_upserts_on_conflict(journal_client):
    """Second PUT on the same date must update, not fail."""
    await journal_client.put("/journal/2026-05-28", json={"content": "First."})
    await journal_client.put("/journal/2026-05-28", json={"content": "Second."})
    resp = await journal_client.get("/journal/2026-05-28")
    assert resp.json()["content"] == "Second."


async def test_generate_journal_returns_503_when_no_generator(journal_client):
    """If the journal generator is unset on the context, must return 503."""
    journal_client.ctx.journal_generator = None
    resp = await journal_client.post("/journal/2026-05-28/generate")
    assert resp.status_code == 503


async def test_generate_journal_returns_409_when_already_generating(journal_client):
    """Second concurrent generate for the same date must return 409."""
    journal_client.ctx.journal_generating.add("2026-05-28")
    try:
        resp = await journal_client.post("/journal/2026-05-28/generate")
        assert resp.status_code == 409
    finally:
        journal_client.ctx.journal_generating.discard("2026-05-28")
