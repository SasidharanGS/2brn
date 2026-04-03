"""End-to-end orchestrator tests using the fake MCP server.

Verifies: event fires → matching rule loads → MCP tool called → execution logged.
"""
import json
import sys
from pathlib import Path

import aiosqlite
import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from brn_daemon.db import get_db_path
from brn_daemon.plugins.events import EventBus, EventNames
from brn_daemon.plugins.orchestrator import PluginOrchestrator


FAKE_SERVER = str(Path(__file__).parent / "fake_mcp_server.py")


async def _seed_plugin_with_rule(
    *,
    plugin_name: str = "fake",
    trigger: str,
    tool_name: str = "echo",
    args_template: dict | None = None,
    parse_status: str = "ok",
) -> tuple[int, int]:
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "INSERT INTO plugins (name, command, args, env_keys) VALUES (?, ?, ?, ?)",
            (plugin_name, sys.executable, json.dumps([FAKE_SERVER]), json.dumps([])),
        )
        plugin_id = cur.lastrowid
        cur = await conn.execute(
            """INSERT INTO plugin_rules
               (plugin_id, title, rule_text, trigger, tool_name, args_template, parse_status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                plugin_id, "test rule", "test text", trigger, tool_name,
                json.dumps(args_template or {"hello": "{date}"}),
                parse_status,
            ),
        )
        rule_id = cur.lastrowid
        await conn.commit()
    return plugin_id, rule_id


async def _executions_for(rule_id: int) -> list[dict]:
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT * FROM plugin_rule_executions WHERE rule_id = ? ORDER BY id",
            (rule_id,),
        )
        return [dict(r) for r in await cur.fetchall()]


def _orchestrator(bus: EventBus) -> PluginOrchestrator:
    scheduler = AsyncIOScheduler()
    scheduler.start(paused=True)  # tests don't need real timing

    async def fake_chat(_messages):
        return "{}"

    return PluginOrchestrator(event_bus=bus, scheduler=scheduler, chat_fn=fake_chat)


async def test_event_triggers_matching_rule(db):
    _, rule_id = await _seed_plugin_with_rule(
        trigger=EventNames.JOURNAL_GENERATED,
        args_template={"date_echo": "{date}"},
    )
    bus = EventBus()
    orch = _orchestrator(bus)
    try:
        await orch.start()
        await bus.emit(EventNames.JOURNAL_GENERATED,
                       {"date": "2026-05-23", "journal_content": "hello"})
        execs = await _executions_for(rule_id)
        assert len(execs) == 1
        assert execs[0]["status"] == "ok"
        # The fake server echoes args back as JSON text — verify our rendered template was sent.
        result = json.loads(execs[0]["result"])
        text = result["content"][0]["text"]
        assert "2026-05-23" in text
    finally:
        await orch.stop()


async def test_disabled_rule_is_ignored(db):
    _, rule_id = await _seed_plugin_with_rule(trigger=EventNames.JOURNAL_GENERATED)
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute("UPDATE plugin_rules SET enabled = 0 WHERE id = ?", (rule_id,))
        await conn.commit()
    bus = EventBus()
    orch = _orchestrator(bus)
    try:
        await orch.start()
        await bus.emit(EventNames.JOURNAL_GENERATED, {"date": "2026-05-23"})
        assert await _executions_for(rule_id) == []
    finally:
        await orch.stop()


async def test_unparsed_rule_is_ignored(db):
    _, rule_id = await _seed_plugin_with_rule(
        trigger=EventNames.JOURNAL_GENERATED, parse_status="pending",
    )
    bus = EventBus()
    orch = _orchestrator(bus)
    try:
        await orch.start()
        await bus.emit(EventNames.JOURNAL_GENERATED, {"date": "x"})
        assert await _executions_for(rule_id) == []
    finally:
        await orch.stop()


async def test_disabled_plugin_skips_all_its_rules(db):
    plugin_id, rule_id = await _seed_plugin_with_rule(trigger=EventNames.JOURNAL_GENERATED)
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute("UPDATE plugins SET enabled = 0 WHERE id = ?", (plugin_id,))
        await conn.commit()
    bus = EventBus()
    orch = _orchestrator(bus)
    try:
        await orch.start()
        await bus.emit(EventNames.JOURNAL_GENERATED, {"date": "x"})
        assert await _executions_for(rule_id) == []
    finally:
        await orch.stop()


async def test_run_rule_now_executes_with_synthetic_payload(db):
    _, rule_id = await _seed_plugin_with_rule(
        trigger="manual", args_template={"now": "{time}"},
    )
    bus = EventBus()
    orch = _orchestrator(bus)
    try:
        await orch.start()
        result = await orch.run_rule_now(rule_id)
        assert result["ok"] is True
        execs = await _executions_for(rule_id)
        assert len(execs) == 1 and execs[0]["status"] == "ok"
    finally:
        await orch.stop()


async def test_run_rule_now_journal_payload_injects_journal_content(db):
    """run_rule_now on a journal_generated rule must fetch today's journal from
    the DB and pass {journal_content} — not raise 'unknown var' warning."""
    # Seed a journal entry for today.
    from datetime import date
    today = date.today().isoformat()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO journals (date, content, generated_at) VALUES (?, ?, datetime('now'))",
            (today, "Today I worked on the plugin system."),
        )
        await conn.commit()

    _, rule_id = await _seed_plugin_with_rule(
        trigger=EventNames.JOURNAL_GENERATED,
        args_template={"body": "{journal_content}", "title": "{date}"},
    )
    bus = EventBus()
    orch = _orchestrator(bus)
    import logging
    warning_messages: list[str] = []

    class WarningCapture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.levelno == logging.WARNING:
                warning_messages.append(record.getMessage())

    handler = WarningCapture()
    logging.getLogger("brn_daemon.plugins.rule_parser").addHandler(handler)
    try:
        await orch.start()
        result = await orch.run_rule_now(rule_id)
        assert result["ok"] is True
        # No 'unknown var' warnings should have been emitted.
        assert not any("unknown var" in m for m in warning_messages), (
            f"Unexpected warnings: {warning_messages}"
        )
        # The rendered body should contain the journal text.
        execs = await _executions_for(rule_id)
        assert execs[0]["status"] == "ok"
        rendered_payload = json.loads(execs[0]["result"])
        echoed = rendered_payload["content"][0]["text"]
        assert "plugin system" in echoed
    finally:
        logging.getLogger("brn_daemon.plugins.rule_parser").removeHandler(handler)
        await orch.stop()


async def test_run_rule_now_capture_inferred_injects_activity_fields(db):
    """run_rule_now on a capture_inferred rule must inject activity fields
    from the most recent activity — not leave {summary} etc. unresolved."""
    # Seed a capture + activity.
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "INSERT INTO captures (captured_at, app_name, trigger) VALUES (datetime('now'), 'Chrome', 'heartbeat')"
        )
        cap_id = cur.lastrowid
        await conn.execute(
            """INSERT INTO activities
               (capture_id, started_at, summary, task_category, task_category_confidence,
                productivity_state, productivity_confidence)
               VALUES (?, datetime('now'), 'writing tests for the plugin fix', 'work', 0.9, 'productive', 0.9)""",
            (cap_id,),
        )
        await conn.commit()

    _, rule_id = await _seed_plugin_with_rule(
        trigger=EventNames.CAPTURE_INFERRED,
        args_template={"text": "{summary} via {app_name}"},
    )
    bus = EventBus()
    orch = _orchestrator(bus)
    import logging
    warning_messages: list[str] = []

    class WarningCapture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.levelno == logging.WARNING:
                warning_messages.append(record.getMessage())

    handler = WarningCapture()
    logging.getLogger("brn_daemon.plugins.rule_parser").addHandler(handler)
    try:
        await orch.start()
        result = await orch.run_rule_now(rule_id)
        assert result["ok"] is True
        assert not any("unknown var" in m for m in warning_messages), (
            f"Unexpected warnings: {warning_messages}"
        )
        execs = await _executions_for(rule_id)
        assert execs[0]["status"] == "ok"
        echoed = json.loads(execs[0]["result"])["content"][0]["text"]
        assert "plugin fix" in echoed
        assert "Chrome" in echoed
    finally:
        logging.getLogger("brn_daemon.plugins.rule_parser").removeHandler(handler)
        await orch.stop()


async def test_run_rule_now_records_error_when_tool_fails(db):
    _, rule_id = await _seed_plugin_with_rule(
        trigger="manual", tool_name="boom", args_template={},
    )
    bus = EventBus()
    orch = _orchestrator(bus)
    try:
        await orch.start()
        result = await orch.run_rule_now(rule_id)
        assert result["ok"] is False
        execs = await _executions_for(rule_id)
        assert execs[0]["status"] == "error"
        assert "intentional failure" in execs[0]["error"]
    finally:
        await orch.stop()
