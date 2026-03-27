import json
import pytest

from brn_daemon.plugins.rule_parser import (
    ParsedRule,
    RuleParseError,
    parse_rule,
    render_args,
    validate_trigger,
)


TOOLS = [
    {
        "name": "create_note",
        "description": "Create a new Joplin note",
        "input_schema": {"type": "object", "properties": {
            "title": {"type": "string"}, "body": {"type": "string"}, "notebook": {"type": "string"}
        }, "required": ["title", "body"]},
    },
    {
        "name": "append_to_note",
        "description": "Append markdown to an existing note",
        "input_schema": {"type": "object", "properties": {
            "id_or_title": {"type": "string"}, "content": {"type": "string"}
        }},
    },
]


def _fake_chat(response_text: str):
    async def chat(_messages):
        return response_text
    return chat


def test_validate_trigger_accepts_known_events():
    validate_trigger("journal_generated")
    validate_trigger("blog_generated")
    validate_trigger("capture_inferred")
    validate_trigger("manual")
    validate_trigger("daily_at_21:00")
    validate_trigger("every_3600s")


def test_validate_trigger_rejects_unknown():
    with pytest.raises(RuleParseError):
        validate_trigger("on_startup")
    with pytest.raises(RuleParseError):
        validate_trigger("daily_at_99:99XX")


async def test_parse_rule_happy_path():
    response = json.dumps({
        "trigger": "journal_generated",
        "tool_name": "create_note",
        "args_template": {"title": "Daily {date}", "body": "{journal_content}", "notebook": "Journal"},
    })
    parsed = await parse_rule(
        "After the journal is generated each night, save it as a Joplin note in the Journal notebook titled with the date.",
        TOOLS,
        _fake_chat(response),
    )
    assert parsed == ParsedRule(
        trigger="journal_generated",
        tool_name="create_note",
        args_template={"title": "Daily {date}", "body": "{journal_content}", "notebook": "Journal"},
    )


async def test_parse_rule_strips_code_fences():
    response = "```json\n" + json.dumps({
        "trigger": "manual",
        "tool_name": "create_note",
        "args_template": {"title": "x", "body": "y"},
    }) + "\n```"
    parsed = await parse_rule("manual rule", TOOLS, _fake_chat(response))
    assert parsed.trigger == "manual"


async def test_parse_rule_rejects_unknown_tool():
    response = json.dumps({
        "trigger": "manual",
        "tool_name": "send_email",
        "args_template": {},
    })
    with pytest.raises(RuleParseError, match="not in plugin's tool list"):
        await parse_rule("rule", TOOLS, _fake_chat(response))


async def test_parse_rule_rejects_bad_trigger():
    response = json.dumps({
        "trigger": "on_startup",
        "tool_name": "create_note",
        "args_template": {"title": "x", "body": "y"},
    })
    with pytest.raises(RuleParseError, match="Invalid trigger"):
        await parse_rule("rule", TOOLS, _fake_chat(response))


async def test_parse_rule_rejects_when_llm_returns_error():
    response = json.dumps({"error": "rule asks for tool we don't have"})
    with pytest.raises(RuleParseError, match="could not compile"):
        await parse_rule("send a text message", TOOLS, _fake_chat(response))


async def test_parse_rule_rejects_invalid_json():
    with pytest.raises(RuleParseError, match="valid JSON"):
        await parse_rule("rule", TOOLS, _fake_chat("not json at all"))


async def test_parse_rule_rejects_missing_keys():
    response = json.dumps({"trigger": "manual"})
    with pytest.raises(RuleParseError, match="missing"):
        await parse_rule("rule", TOOLS, _fake_chat(response))


async def test_parse_rule_requires_tools():
    with pytest.raises(RuleParseError, match="no tools"):
        await parse_rule("rule", [], _fake_chat("{}"))


# ---- render_args ----------------------------------------------------------

def test_render_args_substitutes_strings():
    out = render_args({"title": "Daily {date}", "body": "{content}"},
                      {"date": "2026-05-23", "content": "hello"})
    assert out == {"title": "Daily 2026-05-23", "body": "hello"}


def test_render_args_handles_nested_structures():
    out = render_args(
        {"tags": ["{category}", "auto"], "meta": {"when": "{time}"}},
        {"category": "work", "time": "21:00"},
    )
    assert out == {"tags": ["work", "auto"], "meta": {"when": "21:00"}}


def test_render_args_missing_var_yields_empty_string():
    out = render_args({"title": "{missing}!"}, {"date": "x"})
    assert out == {"title": "!"}


def test_render_args_serialises_list_values():
    out = render_args({"tags_csv": "{tags}"}, {"tags": ["a", "b"]})
    assert out == {"tags_csv": '["a", "b"]'}


def test_render_args_preserves_non_string_leaves():
    out = render_args({"count": 5, "flag": True}, {})
    assert out == {"count": 5, "flag": True}
