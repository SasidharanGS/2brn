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
