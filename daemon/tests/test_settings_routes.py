"""Tests that PUT /settings with provider fields rebuilds in-memory AI clients."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def test_client(tmp_home):
    """Minimal FastAPI test client with app_state stubs."""
    from brn_daemon.blog import BlogGenerator
    from brn_daemon.chat import ChatService
    from brn_daemon.journal import JournalGenerator
    from brn_daemon.main import app_state, create_app

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


async def test_settings_lan_access_roundtrip(test_client, tmp_home):
    """GET /settings returns lan_access; PUT /settings updates it."""
    client, _ = test_client
    r_get = await client.get("/settings")
    assert "lan_access" in r_get.json()
    original = r_get.json()["lan_access"]

    r_put = await client.put("/settings", json={"lan_access": not original})
    assert r_put.status_code == 200

    r_get2 = await client.get("/settings")
    assert r_get2.json()["lan_access"] == (not original)


# ── capture-loop tuning (issue #52) ─────────────────────────────────────────


async def test_capture_tuning_roundtrip(test_client, tmp_home):
    client, _ = test_client
    resp = await client.put("/settings", json={
        "capture_interval_seconds": 90,
        "change_cooldown_seconds": 10,
        "max_idle_tick_seconds": 30,
        "similarity_threshold": 0.9,
    })
    assert resp.status_code == 200
    got = (await client.get("/settings")).json()
    assert got["capture_interval_seconds"] == 90
    assert got["change_cooldown_seconds"] == 10.0
    assert got["max_idle_tick_seconds"] == 30.0
    assert got["similarity_threshold"] == 0.9


async def test_put_settings_rejects_out_of_range_threshold(test_client, tmp_home):
    client, _ = test_client
    resp = await client.put("/settings", json={"similarity_threshold": 0.4})
    assert resp.status_code == 422


async def test_put_settings_rejects_idle_tick_at_or_above_heartbeat(test_client, tmp_home):
    client, _ = test_client
    resp = await client.put(
        "/settings", json={"capture_interval_seconds": 30, "max_idle_tick_seconds": 30}
    )
    assert resp.status_code == 400
    assert "max_idle_tick_seconds" in resp.json()["detail"]
