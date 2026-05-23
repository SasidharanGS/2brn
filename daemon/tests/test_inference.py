import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from brn_daemon.inference import build_inference_prompt, parse_inference_response, InferenceResult, InferenceQueue

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


def test_parse_response_with_app_name_override():
    raw = json.dumps({
        "summary": "User was watching a video.",
        "tags": ["youtube", "video"],
        "task_category": "play",
        "task_category_confidence": 0.95,
        "productivity_state": "chilling",
        "productivity_confidence": 0.9,
        "app_name": "YouTube"
    })
    result = parse_inference_response(raw)
    assert result.app_name_override == "YouTube"


def test_parse_response_without_app_name_override():
    raw = json.dumps({
        "summary": "User was writing code.",
        "tags": ["coding"],
        "task_category": "work",
        "task_category_confidence": 0.9,
        "productivity_state": "focused",
        "productivity_confidence": 0.85
    })
    result = parse_inference_response(raw)
    assert result.app_name_override is None


def test_parse_response_with_null_app_name_override():
    raw = json.dumps({
        "summary": "User was writing code.",
        "tags": ["coding"],
        "task_category": "work",
        "task_category_confidence": 0.9,
        "productivity_state": "focused",
        "productivity_confidence": 0.85,
        "app_name": None
    })
    result = parse_inference_response(raw)
    assert result.app_name_override is None


async def test_started_at_stored_without_timezone_offset(tmp_home, db):
    """started_at must be stored as naive UTC ISO string (no +00:00 suffix)."""
    import aiosqlite
    from datetime import datetime
    from unittest.mock import patch

    fake_result = type("R", (), {
        "summary": "test summary",
        "tags": ["test"],
        "task_category": "work",
        "task_category_confidence": 0.9,
        "productivity_state": "productive",
        "productivity_confidence": 0.9,
        "app_name_override": None,
    })()

    async def fake_chat(messages):
        return '{"summary": "test", "tags": [], "task_category": "work", "task_category_confidence": 0.9, "productivity_state": "productive", "productivity_confidence": 0.9}'

    from brn_daemon.inference import InferenceQueue
    with patch("brn_daemon.inference.parse_inference_response", return_value=fake_result):
        queue = InferenceQueue(db_path_fn=lambda: str(tmp_home / "2brn.db"), chat_fn=fake_chat)
        await queue._process_one(capture_id=1, app_name="TestApp", window_title="TestWin", ocr_text="hello")

    async with aiosqlite.connect(tmp_home / "2brn.db") as conn:
        cur = await conn.execute("SELECT started_at FROM activities LIMIT 1")
        row = await cur.fetchone()

    assert row is not None
    started_at = row[0]
    assert "+" not in started_at, f"started_at contains offset: {started_at!r}"
    dt = datetime.fromisoformat(started_at)
    assert dt.tzinfo is None, f"expected naive datetime, got: {dt}"


async def test_instructions_cache_is_used_on_second_call(tmp_home, db):
    """Second _load_instructions call within TTL must not re-query the DB."""
    import aiosqlite
    from brn_daemon.inference import InferenceQueue
    from brn_daemon.db import get_db_path

    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO user_instructions (title, body, enabled, created_at) VALUES (?, ?, 1, datetime('now'))",
            ("t", "do X"),
        )
        await conn.commit()

    async def fake_chat(msgs):
        return '{"summary":"s","tags":[],"task_category":"work","task_category_confidence":0.9,"productivity_state":"productive","productivity_confidence":0.9}'

    queue = InferenceQueue(db_path_fn=lambda: str(tmp_home / "2brn.db"), chat_fn=fake_chat)

    first = await queue._load_instructions()
    assert first == ["do X"]
    assert queue._instructions_cache == ["do X"]

    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute("UPDATE user_instructions SET body = 'do Y'")
        await conn.commit()

    second = await queue._load_instructions()
    assert second == ["do X"], "Cache must shield second call within TTL"


async def test_invalidate_instructions_cache_forces_reload(tmp_home, db):
    """invalidate_instructions_cache() must cause next load to re-query DB."""
    import aiosqlite
    from brn_daemon.inference import InferenceQueue
    from brn_daemon.db import get_db_path

    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO user_instructions (title, body, enabled, created_at) VALUES (?, ?, 1, datetime('now'))",
            ("t", "do X"),
        )
        await conn.commit()

    async def fake_chat(msgs):
        return '{"summary":"s","tags":[],"task_category":"work","task_category_confidence":0.9,"productivity_state":"productive","productivity_confidence":0.9}'

    queue = InferenceQueue(db_path_fn=lambda: str(tmp_home / "2brn.db"), chat_fn=fake_chat)
    await queue._load_instructions()

    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute("UPDATE user_instructions SET body = 'do Y'")
        await conn.commit()
    queue.invalidate_instructions_cache()

    result = await queue._load_instructions()
    assert result == ["do Y"], "After invalidation, fresh DB value must be returned"


async def test_process_one_embed_failure_activity_survives(tmp_home, db):
    """If embedding fails, the activity row must still exist in SQLite."""
    from brn_daemon.db import get_db_path

    chat_fn = AsyncMock(return_value='{"summary":"test","tags":[],"task_category":"work","task_category_confidence":0.9,"productivity_state":"productive","productivity_confidence":0.8}')

    mock_embed = MagicMock()
    mock_embed.embed_activity = AsyncMock(side_effect=RuntimeError("embed failed"))

    q = InferenceQueue(chat_fn=chat_fn, db_path_fn=get_db_path, embedding_service=mock_embed)

    await db.execute("INSERT INTO captures (captured_at, app_name) VALUES ('2024-01-01T10:00:00', 'TestApp')")
    await db.commit()
    cur = await db.execute("SELECT last_insert_rowid()")
    row = await cur.fetchone()
    capture_id = row[0]

    await q._process_one(capture_id, "TestApp", "Test Window", "some ocr text")

    cur = await db.execute("SELECT id, chroma_id FROM activities WHERE capture_id = ?", (capture_id,))
    activity = await cur.fetchone()
    assert activity is not None, "activity should exist even after embed failure"
    assert activity[1] is None, "chroma_id should be NULL after embed failure"


async def test_heal_unembedded_re_embeds_null_chroma_id(tmp_home, db):
    """heal_unembedded must call embed_activity for activities with chroma_id IS NULL."""
    from brn_daemon.db import get_db_path

    await db.execute("INSERT INTO captures (captured_at, app_name) VALUES ('2024-01-01T10:00:00', 'App')")
    await db.commit()
    cur = await db.execute("SELECT last_insert_rowid()")
    capture_id = (await cur.fetchone())[0]

    await db.execute(
        "INSERT INTO activities (capture_id, started_at, summary, task_category, productivity_state) VALUES (?, '2024-01-01T10:00:00', 'did stuff', 'work', 'productive')",
        (capture_id,),
    )
    await db.commit()

    mock_embed = MagicMock()
    mock_embed.embed_activity = AsyncMock()

    q = InferenceQueue(chat_fn=AsyncMock(), db_path_fn=get_db_path, embedding_service=mock_embed)
    count = await q.heal_unembedded()

    assert count == 1
    mock_embed.embed_activity.assert_called_once()


async def test_process_one_uses_capture_time_for_started_at(tmp_home, db):
    """started_at must be the capture's own timestamp, not the inference time
    (review finding F-CORE-2): a queue backlog must not re-date activities to
    when they were processed.
    """
    from brn_daemon.db import get_db_path

    chat_fn = AsyncMock(return_value='{"summary":"s","tags":[],"task_category":"work","task_category_confidence":0.9,"productivity_state":"productive","productivity_confidence":0.8}')
    q = InferenceQueue(chat_fn=chat_fn, db_path_fn=get_db_path)

    captured_at = "2024-03-03T08:00:00.000000"
    await db.execute("INSERT INTO captures (captured_at, app_name) VALUES (?, 'App')", (captured_at,))
    await db.commit()
    capture_id = (await (await db.execute("SELECT last_insert_rowid()")).fetchone())[0]

    # captured_at omitted → must fall back to the capture row's own timestamp.
    await q._process_one(capture_id, "App", "Win", "ocr text")

    cur = await db.execute("SELECT started_at FROM activities WHERE capture_id = ?", (capture_id,))
    started_at = (await cur.fetchone())[0]
    assert started_at == captured_at, f"started_at should equal capture time, got {started_at!r}"
