"""Tests that PUT /settings with provider fields rebuilds in-memory AI clients."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def test_client(tmp_home):
    """Minimal FastAPI test client with app_state stubs."""
    from brn_daemon.main import create_app, app_state
    from brn_daemon.chat import ChatService
    from brn_daemon.journal import JournalGenerator
    from brn_daemon.blog import BlogGenerator

    fake_chat_fn = AsyncMock(return_value='{"summary":"x","tags":[],"task_category":"work","task_category_confidence":0.9,"productivity_state":"productive","productivity_confidence":0.9}')
    fake_stream_fn = AsyncMock()
    fake_embed_client = MagicMock()
    fake_embed_client.aclose = AsyncMock()
    fake_chroma = MagicMock()
    fake_chroma.query = MagicMock(return_value={"ids": [[]], "documents": [[]], "metadatas": [[]]})
    fake_chroma.query_notes = MagicMock(return_value={"ids": [[]], "documents": [[]], "metadatas": [[]]})

    app_state["chat_service"] = ChatService(
        chat_fn=fake_chat_fn,
        stream_fn=fake_stream_fn,
        embed_client=fake_embed_client,
        chroma_store=fake_chroma,
    )
    app_state["_embed_client_ref"] = fake_embed_client
    app_state["inference_queue"] = MagicMock()
    app_state["inference_queue"]._chat_fn = fake_chat_fn
    app_state["inference_queue"]._embedding_service = MagicMock()
    app_state["journal_generator"] = JournalGenerator(chat_fn=fake_chat_fn)
    app_state["blog_generator"] = BlogGenerator(chat_fn=fake_chat_fn)
    app_state["plugin_orchestrator"] = MagicMock()
    app_state["plugin_orchestrator"].chat_fn = fake_chat_fn
    app_state["chroma_store"] = fake_chroma

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, app_state


async def test_put_settings_with_provider_rebuilds_clients(test_client, tmp_home):
    """PUT /settings with chat_provider must rebuild in-memory AI clients."""
    client, state = test_client
    original_chat_service = state["chat_service"]

    new_chat_fn = AsyncMock(return_value="new")
    new_embed = MagicMock()
    new_embed.aclose = AsyncMock()

    with patch("brn_daemon.main.make_chat_fn", return_value=(new_chat_fn, AsyncMock())) as mock_chat, \
         patch("brn_daemon.main.make_embed_client", return_value=new_embed):
        resp = await client.put("/settings", json={
            "chat_provider": {"type": "openai", "base_url": "http://new", "model": "gpt-4o"}
        })

    assert resp.status_code == 200
    mock_chat.assert_called_once()
    # ChatService must have been replaced with a new instance
    assert state["chat_service"] is not original_chat_service


async def test_put_settings_without_provider_skips_rebuild(test_client, tmp_home):
    """PUT /settings with no provider fields must NOT rebuild AI clients."""
    client, state = test_client
    original = state["chat_service"]

    with patch("brn_daemon.main.make_chat_fn") as mock_chat:
        resp = await client.put("/settings", json={"capture_interval_seconds": 30})

    assert resp.status_code == 200
    mock_chat.assert_not_called()
    assert state["chat_service"] is original
