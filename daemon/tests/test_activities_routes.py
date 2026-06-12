"""Tests for GET /activities and PATCH /activities/{id}/override."""
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
import pytest
from httpx import ASGITransport, AsyncClient

from brn_daemon.db import get_db_path, init_db


@pytest.fixture
async def activities_client(tmp_home):
    """FastAPI test client with minimal app_state stubs and seeded activity data."""
    from brn_daemon.blog import BlogGenerator
    from brn_daemon.chat import ChatService
    from brn_daemon.journal import JournalGenerator
    from brn_daemon.main import app_state, create_app

    fake_chat_fn = AsyncMock(return_value='{"summary":"x","tags":[],"task_category":"work","task_category_confidence":0.9,"productivity_state":"productive","productivity_confidence":0.9}')
    fake_stream_fn = AsyncMock()
    fake_embed_client = MagicMock()
    fake_embed_client.aclose = AsyncMock()
    fake_chroma = MagicMock()
    fake_chroma.query = AsyncMock(return_value={"documents": [[]], "metadatas": [[]], "distances": [[]]})
    fake_chroma.query_notes = AsyncMock(return_value={"documents": [[]], "metadatas": [[]], "distances": [[]]})

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

    # Init DB and seed a capture + activity
    await init_db()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO captures (id, captured_at, app_name, window_title, file_path, trigger) "
            "VALUES (1, '2026-05-28T10:00:00', 'Safari', 'GitHub', '/tmp/x.jpg', 'heartbeat')"
        )
        await conn.execute(
            "INSERT INTO activities "
            "(id, capture_id, started_at, summary, tags, task_category, "
            "task_category_confidence, productivity_state, productivity_confidence, "
            "category_overridden_by_user) "
            "VALUES (1, 1, '2026-05-28T10:00:00', "
            "'Browsing GitHub', '[]', 'work', 0.9, 'productive', 0.85, 0)"
        )
        await conn.commit()

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_get_activities_returns_seeded_activity(activities_client):
    resp = await activities_client.get("/activities?date=2026-05-28")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["summary"] == "Browsing GitHub"
    assert data[0]["task_category"] == "work"


async def test_get_activities_filters_by_category(activities_client):
    resp = await activities_client.get("/activities?date=2026-05-28&task_category=play")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_patch_override_updates_category_and_state(activities_client):
    resp = await activities_client.patch(
        "/activities/1/override",
        json={"task_category": "research", "productivity_state": "focused"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Verify the DB was actually updated
    get_resp = await activities_client.get("/activities?date=2026-05-28")
    activity = get_resp.json()[0]
    assert activity["task_category"] == "research"
    assert activity["productivity_state"] == "focused"
    assert activity["category_overridden_by_user"] is True


async def test_patch_override_rejects_invalid_category(activities_client):
    resp = await activities_client.patch(
        "/activities/1/override",
        json={"task_category": "invalid_cat", "productivity_state": "productive"},
    )
    assert resp.status_code == 400


async def test_patch_override_rejects_invalid_state(activities_client):
    resp = await activities_client.patch(
        "/activities/1/override",
        json={"task_category": "work", "productivity_state": "invalid_state"},
    )
    assert resp.status_code == 400


async def test_patch_override_unknown_activity_returns_404(activities_client):
    resp = await activities_client.patch(
        "/activities/99999/override",
        json={"task_category": "work", "productivity_state": "focused"},
    )
    assert resp.status_code == 404


async def test_get_activities_returns_empty_for_unknown_date(activities_client):
    resp = await activities_client.get("/activities?date=2000-01-01")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_post_backfill_triggers_inference_backfill(activities_client):
    from brn_daemon.main import app_state
    app_state["inference_queue"].backfill_unclassified = AsyncMock(
        return_value={"queued": 3, "remaining": 1}
    )
    resp = await activities_client.post("/activities/backfill", json={"days": 3})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "queued": 3, "remaining": 1}
    app_state["inference_queue"].backfill_unclassified.assert_awaited_once_with(days=3, include_sparse=False)


async def test_post_backfill_defaults_to_seven_days(activities_client):
    from brn_daemon.main import app_state
    app_state["inference_queue"].backfill_unclassified = AsyncMock(
        return_value={"queued": 0, "remaining": 0}
    )
    resp = await activities_client.post("/activities/backfill")
    assert resp.status_code == 200
    app_state["inference_queue"].backfill_unclassified.assert_awaited_once_with(days=7, include_sparse=False)


async def test_post_backfill_rejects_out_of_range_days(activities_client):
    resp = await activities_client.post("/activities/backfill", json={"days": 0})
    assert resp.status_code == 422


async def test_post_backfill_forwards_include_sparse(activities_client):
    from brn_daemon.main import app_state
    app_state["inference_queue"].backfill_unclassified = AsyncMock(
        return_value={"queued": 0, "remaining": 0, "sparse_cloned": 5, "sparse_queued": 2, "sparse_deferred": 9}
    )
    resp = await activities_client.post(
        "/activities/backfill", json={"days": 7, "include_sparse": True}
    )
    assert resp.status_code == 200
    assert resp.json()["sparse_cloned"] == 5
    app_state["inference_queue"].backfill_unclassified.assert_awaited_once_with(
        days=7, include_sparse=True
    )
