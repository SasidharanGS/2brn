"""Tests for P2 fixes: API date validation (F-ROUTE-1/2), plugin secret
redaction (F-SEC-5), generated_at on journal edit (F-ROUTE-9), accurate purge
months (F-ROUTE-9), batched resync (F-ROUTE-7), JSON-RPC id normalisation
(F-SEC-9), trigger time bounds (F-SEC-10), and args-schema validation
(F-SEC-7)."""
import json
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
from httpx import ASGITransport, AsyncClient


async def test_captures_rejects_bad_date(tmp_home):
    from brn_daemon.db import init_db
    from brn_daemon.main import create_app
    await init_db()
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        bad = await client.get("/captures?date=not-a-date")
        assert bad.status_code == 400
        ok = await client.get("/captures?date=2026-01-01")
        assert ok.status_code == 200


def test_orchestrator_redacts_plugin_secrets(monkeypatch):
    from brn_daemon.plugins import orchestrator as orch_mod
    from brn_daemon.plugins.orchestrator import PluginOrchestrator

    monkeypatch.setattr(
        orch_mod, "get_plugin_env_value",
        lambda name, key: "supersecret-token" if key == "TOKEN" else None,
    )
    o = PluginOrchestrator(event_bus=MagicMock(), scheduler=MagicMock(), chat_fn=MagicMock())
    rule_row = {"plugin_name": "joplin", "env_keys": '["TOKEN"]'}
    out = o._redact(rule_row, "upstream auth failed: token=supersecret-token (401)")
    assert "supersecret-token" not in out
    assert "***" in out


async def test_put_journal_sets_generated_at(tmp_home):
    """PUT /journal/{date} must refresh generated_at (F-ROUTE-9)."""
    from brn_daemon.blog import BlogGenerator
    from brn_daemon.chat import ChatService
    from brn_daemon.db import get_db_path, init_db
    from brn_daemon.journal import JournalGenerator
    from brn_daemon.main import app_state, create_app

    fake_chat_fn = AsyncMock(return_value="{}")
    fake_embed_client = MagicMock()
    fake_embed_client.aclose = AsyncMock()
    fake_chroma = MagicMock()
    fake_chroma.query = AsyncMock(return_value={"documents": [[]], "metadatas": [[]], "distances": [[]]})
    fake_chroma.query_notes = AsyncMock(return_value={"documents": [[]], "metadatas": [[]], "distances": [[]]})
    app_state["chat_service"] = ChatService(
        chat_fn=fake_chat_fn, stream_fn=AsyncMock(),
        embed_client=fake_embed_client, chroma_store=fake_chroma,
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

    await init_db()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO journals (date, content, generated_at, edited_by_user) "
            "VALUES ('2026-01-15', 'old text', '2020-01-01T00:00:00', 0)"
        )
        await conn.commit()

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.put("/journal/2026-01-15", json={"content": "new text"})
        assert resp.status_code == 200

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT generated_at FROM journals WHERE date = '2026-01-15'")
        row = await cur.fetchone()
    assert row is not None
    assert row[0] != "2020-01-01T00:00:00"


async def test_purge_uses_calendar_months_not_days(tmp_home):
    """purge_old_captures cutoff must use whole calendar months, not months*30 (F-ROUTE-9)."""
    from datetime import UTC, datetime, timedelta

    from brn_daemon.db import get_db_path, init_db
    from brn_daemon.purge import purge_old_captures

    await init_db()
    now = datetime.now(UTC)
    year = now.year - 1 if now.month <= 2 else now.year
    month = (now.month - 2) % 12 + 1
    borderline_ts = now.replace(year=year, month=month, day=now.day) - timedelta(seconds=1)
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO captures (captured_at, trigger) VALUES (?, 'heartbeat')",
            (borderline_ts.isoformat(),),
        )
        await conn.commit()

    purged = await purge_old_captures(months=1, chroma_store=None)
    assert purged == 1, "capture just outside the 1-month window must be purged"


async def test_embed_activities_batch_sets_chroma_id(tmp_home):
    """embed_activities_batch must upsert each item and write chroma_id to the DB (F-ROUTE-7)."""
    from brn_daemon.db import get_db_path, init_db
    from brn_daemon.embeddings import ChromaStore, EmbeddingService

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
            "VALUES (?, datetime('now'), 'batch work', '[]', 'work', 0.9, 'focused', 0.8)",
            (cap_id,),
        )
        await conn.commit()
        cur = await conn.execute("SELECT last_insert_rowid()")
        act_id = (await cur.fetchone())[0]

    mock_embed_client = MagicMock()
    mock_embed_client.embed_batch = AsyncMock(return_value=[[0.1] * 384])
    store = ChromaStore(persist_dir=str(tmp_home / "chroma"))
    service = EmbeddingService(embed_client=mock_embed_client, chroma_store=store)

    count = await service.embed_activities_batch([{
        "activity_id": act_id,
        "summary": "batch work",
        "metadata": {"date": "2026-01-15", "source": "activity"},
    }])
    assert count == 1

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT chroma_id FROM activities WHERE id = ?", (act_id,))
        row = await cur.fetchone()
    assert row is not None
    assert row[0] == f"activity-{act_id}"


def test_normalize_id_coerces_string_and_float():
    """_normalize_id must coerce string/float JSON-RPC ids to int (F-SEC-9)."""
    from brn_daemon.plugins.mcp_client import _normalize_id

    assert _normalize_id("42") == 42
    assert _normalize_id(3.0) == 3
    assert _normalize_id(7) == 7
    assert _normalize_id("not-an-int") == "not-an-int"
    assert _normalize_id(3.7) == 3.7


def test_trigger_rejects_out_of_range_daily_at():
    """daily_at_ with hour > 23 or minute > 59 must raise RuleParseError (F-SEC-10)."""
    import pytest

    from brn_daemon.plugins.rule_parser import RuleParseError, validate_trigger

    with pytest.raises(RuleParseError, match="invalid time"):
        validate_trigger("daily_at_24:00")
    with pytest.raises(RuleParseError, match="invalid time"):
        validate_trigger("daily_at_00:60")
    with pytest.raises(RuleParseError, match="invalid time"):
        validate_trigger("daily_at_25:30")
    validate_trigger("daily_at_23:59")


async def test_parse_rule_rejects_unknown_args_template_keys():
    """parse_rule must reject args_template keys absent from the tool's input schema (F-SEC-7)."""
    import pytest

    from brn_daemon.plugins.rule_parser import RuleParseError, parse_rule

    tools = [{
        "name": "do_thing",
        "description": "Does a thing",
        "input_schema": {"type": "object", "properties": {
            "title": {"type": "string"},
        }},
    }]

    response = json.dumps({
        "trigger": "manual",
        "tool_name": "do_thing",
        "args_template": {"title": "ok", "injected_key": "bad"},
    })

    async def fake_chat(_messages):
        return response

    with pytest.raises(RuleParseError, match="injected_key"):
        await parse_rule("rule text", tools, fake_chat)
