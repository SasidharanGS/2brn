import json
import pytest
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
