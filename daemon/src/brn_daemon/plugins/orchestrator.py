"""Plugin orchestrator: routes daemon events → matching rules → MCP tool calls.

Lifecycle:
    start()    — subscribe to event bus, register cron jobs for scheduled rules
    stop()     — unsubscribe, cancel cron jobs, close MCP client pool

Hot reload:
    refresh_rules() — call after CRUD on plugin_rules; re-reads DB and re-binds
                       scheduled jobs without touching event subscriptions.

Execution model is deterministic (no runtime LLM): rules are pre-parsed at save
time, so on event-fire we just render args_template and call the cached tool.
"""
import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from brn_daemon.config import get_plugin_env_value
from brn_daemon.db import get_conn
from brn_daemon.plugins.events import EventBus, EventNames
from brn_daemon.plugins.mcp_client import MCPClient, MCPClientPool, MCPError, MCPTimeoutError
from brn_daemon.plugins.rule_parser import (
    ParsedRule,
    RuleParseError,
    parse_rule,
    render_args,
    validate_trigger,
)

logger = logging.getLogger(__name__)

EXECUTION_LOG_LIMIT = 500  # keep this many most-recent executions per rule
PLUGIN_MAX_CONCURRENCY = 4  # cap concurrent tool calls so an event burst can't pile up


class PluginOrchestrator:
    def __init__(
        self,
        event_bus: EventBus,
        scheduler: AsyncIOScheduler,
        chat_fn,
    ) -> None:
        self.event_bus = event_bus
        self.scheduler = scheduler
        self.chat_fn = chat_fn
        self.pool = MCPClientPool()
        self._scheduled_job_ids: list[str] = []
        self._subscribed = False
        self._exec_sem = asyncio.Semaphore(PLUGIN_MAX_CONCURRENCY)

    # ---- lifecycle --------------------------------------------------------

    async def start(self) -> None:
        if not self._subscribed:
            for evt in EventNames.ALL:
                self.event_bus.subscribe(evt, self._on_event)
            self._subscribed = True
        await self._register_scheduled_rules()

    async def stop(self) -> None:
        for jid in self._scheduled_job_ids:
            try:
                self.scheduler.remove_job(jid)
            except Exception:
                pass
        self._scheduled_job_ids.clear()
        await self.pool.close_all()

    async def refresh_rules(self) -> None:
        """Re-bind scheduled jobs from DB. Event subscriptions are static."""
        for jid in self._scheduled_job_ids:
            try:
                self.scheduler.remove_job(jid)
            except Exception:
                pass
        self._scheduled_job_ids.clear()
        await self._register_scheduled_rules()

    # ---- event handler ----------------------------------------------------

    async def _on_event(self, event_name: str, payload: dict[str, Any]) -> None:
        rules = await self._load_rules_for_trigger(event_name)
        if not rules:
            return
        await asyncio.gather(
            *(self._execute(r, payload) for r in rules),
            return_exceptions=True,
        )

    # ---- scheduled rules --------------------------------------------------

    async def _register_scheduled_rules(self) -> None:
        async with get_conn() as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                """SELECT r.id, r.trigger
                   FROM plugin_rules r JOIN plugins p ON p.id = r.plugin_id
                   WHERE r.enabled = 1 AND p.enabled = 1 AND r.parse_status = 'ok'"""
            )
            rows = await cur.fetchall()
        for row in rows:
            trigger = row["trigger"]
            rule_id = row["id"]
            try:
                if trigger.startswith("daily_at_"):
                    hh, mm = trigger.removeprefix("daily_at_").split(":")
                    job = self.scheduler.add_job(
                        self._run_scheduled, CronTrigger(hour=int(hh), minute=int(mm)),
                        args=[rule_id], id=f"plugin_rule_{rule_id}",
                        replace_existing=True, misfire_grace_time=300,
                    )
                    self._scheduled_job_ids.append(job.id)
                elif trigger.startswith("every_") and trigger.endswith("s"):
                    secs = int(trigger.removeprefix("every_").removesuffix("s"))
                    job = self.scheduler.add_job(
                        self._run_scheduled, IntervalTrigger(seconds=secs),
                        args=[rule_id], id=f"plugin_rule_{rule_id}",
                        replace_existing=True, misfire_grace_time=secs,
                    )
                    self._scheduled_job_ids.append(job.id)
            except Exception:
                logger.exception("Failed to schedule plugin rule id=%s trigger=%s", rule_id, trigger)

    async def _run_scheduled(self, rule_id: int) -> None:
        now = datetime.now(UTC)
        payload = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
        }
        rule = await self._load_rule(rule_id)
        if rule is None:
            return
        await self._execute(rule, payload)

    # ---- DB loaders -------------------------------------------------------

    async def _load_rules_for_trigger(self, trigger: str) -> list[dict[str, Any]]:
        async with get_conn() as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                """SELECT r.id, r.plugin_id, r.tool_name, r.args_template,
                          p.command, p.args AS p_args, p.env_keys, p.name AS plugin_name
                   FROM plugin_rules r JOIN plugins p ON p.id = r.plugin_id
                   WHERE r.trigger = ? AND r.enabled = 1 AND p.enabled = 1
                     AND r.parse_status = 'ok'""",
                (trigger,),
            )
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def _load_rule(self, rule_id: int) -> dict[str, Any] | None:
        async with get_conn() as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                """SELECT r.id, r.plugin_id, r.tool_name, r.args_template, r.trigger,
                          p.command, p.args AS p_args, p.env_keys, p.name AS plugin_name
                   FROM plugin_rules r JOIN plugins p ON p.id = r.plugin_id
                   WHERE r.id = ? AND r.enabled = 1 AND p.enabled = 1
                     AND r.parse_status = 'ok'""",
                (rule_id,),
            )
            row = await cur.fetchone()
        return dict(row) if row else None

    # ---- execution --------------------------------------------------------

    async def _execute(self, rule_row: dict[str, Any], payload: dict[str, Any]) -> None:
        rule_id = rule_row["id"]
        plugin_id = rule_row["plugin_id"]
        plugin_name = rule_row["plugin_name"]
        started = datetime.now(UTC).isoformat()
        try:
            args_template = json.loads(rule_row["args_template"] or "{}")
        except json.JSONDecodeError:
            await self._log_execution(rule_id, started, status="error",
                                      error="args_template is not valid JSON",
                                      payload=payload, result=None)
            return

        rendered = render_args(args_template, payload)
        async with self._exec_sem:
            try:
                client = await self._client_for_plugin(plugin_id, rule_row)
                result = await client.call_tool(rule_row["tool_name"], rendered)
                await self._log_execution(rule_id, started, status="ok",
                                          payload=payload, result=result)
                logger.info("Plugin rule %s (%s.%s) executed", rule_id, plugin_name, rule_row["tool_name"])
            except MCPTimeoutError as exc:
                await self._log_execution(rule_id, started, status="timeout",
                                          error=self._redact(rule_row, str(exc)),
                                          payload=payload, result=None)
                logger.warning("Plugin rule %s timed out", rule_id)
            except MCPError as exc:
                await self._log_execution(rule_id, started, status="error",
                                          error=self._redact(rule_row, str(exc)),
                                          payload=payload, result=None)
                logger.exception("Plugin rule %s failed", rule_id)
            except Exception as exc:
                await self._log_execution(rule_id, started, status="error",
                                          error=self._redact(rule_row, repr(exc)),
                                          payload=payload, result=None)
                logger.exception("Plugin rule %s crashed", rule_id)

    def _redact(self, rule_row: dict[str, Any], text: str) -> str:
        """Scrub the plugin's secret env values out of an error string before it's
        stored in plugin_rule_executions / returned to the UI."""
        if not text:
            return text
        out = text
        for k in json.loads(rule_row.get("env_keys") or "[]"):
            v = get_plugin_env_value(rule_row["plugin_name"], k)
            if v:
                out = out.replace(v, "***")
        return out[:4000]

    async def _client_for_plugin(self, plugin_id: int, rule_row: dict[str, Any]) -> MCPClient:
        env_keys = json.loads(rule_row["env_keys"] or "[]")
        args = json.loads(rule_row["p_args"] or "[]")
        env: dict[str, str] = {}
        for k in env_keys:
            v = get_plugin_env_value(rule_row["plugin_name"], k)
            if v is not None:
                env[k] = v
        return await self.pool.get(plugin_id, rule_row["command"], args, env)

    async def _log_execution(
        self,
        rule_id: int,
        started_at: str,
        *,
        status: str,
        payload: dict[str, Any] | None = None,
        result: Any = None,
        error: str | None = None,
    ) -> None:
        ended = datetime.now(UTC).isoformat()
        async with get_conn() as conn:
            await conn.execute(
                """INSERT INTO plugin_rule_executions
                   (rule_id, started_at, ended_at, status, error, payload, result)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    rule_id, started_at, ended, status, error,
                    json.dumps(payload) if payload is not None else None,
                    json.dumps(result, default=str) if result is not None else None,
                ),
            )
            # Trim execution log per rule.
            await conn.execute(
                """DELETE FROM plugin_rule_executions
                   WHERE rule_id = ?
                     AND id NOT IN (
                       SELECT id FROM plugin_rule_executions
                       WHERE rule_id = ?
                       ORDER BY started_at DESC LIMIT ?
                     )""",
                (rule_id, rule_id, EXECUTION_LOG_LIMIT),
            )
            await conn.commit()

    # ---- public API used by routes ---------------------------------------

    async def list_plugin_tools(
        self,
        plugin_id: int,
        command: str,
        args: list[str],
        env_keys: list[str],
        plugin_name: str,
    ) -> list[dict[str, Any]]:
        env: dict[str, str] = {}
        for k in env_keys:
            v = get_plugin_env_value(plugin_name, k)
            if v is not None:
                env[k] = v
        client = await self.pool.get(plugin_id, command, args, env)
        tools = await client.list_tools(force_refresh=True)
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]

    async def reparse_rule(
        self,
        rule_id: int,
        rule_text: str,
        plugin_id: int,
        command: str,
        args: list[str],
        env_keys: list[str],
        plugin_name: str,
    ) -> ParsedRule:
        tools = await self.list_plugin_tools(plugin_id, command, args, env_keys, plugin_name)
        try:
            parsed = await parse_rule(rule_text, tools, self.chat_fn)
            validate_trigger(parsed.trigger)
            async with get_conn() as conn:
                await conn.execute(
                    """UPDATE plugin_rules
                       SET trigger = ?, tool_name = ?, args_template = ?,
                           parse_status = 'ok', parse_error = NULL,
                           parsed_at = ?
                       WHERE id = ?""",
                    (
                        parsed.trigger, parsed.tool_name,
                        json.dumps(parsed.args_template),
                        datetime.now(UTC).isoformat(),
                        rule_id,
                    ),
                )
                await conn.commit()
            await self.refresh_rules()
            return parsed
        except RuleParseError as exc:
            async with get_conn() as conn:
                await conn.execute(
                    """UPDATE plugin_rules
                       SET parse_status = 'error', parse_error = ?,
                           parsed_at = ?
                       WHERE id = ?""",
                    (str(exc), datetime.now(UTC).isoformat(), rule_id),
                )
                await conn.commit()
            raise

    async def _build_manual_payload(self, trigger: str, date_str: str, time_str: str) -> dict[str, Any]:
        """Return a payload that matches what the real event would carry.

        For journal_generated / blog_generated we fetch today's content from
        the DB so {journal_content} / {blog_content} placeholders resolve.
        For capture_inferred we inject the most-recent activity row.
        For schedule / manual triggers only {date} and {time} are needed.
        """
        base = {"date": date_str, "time": time_str}
        if trigger == EventNames.JOURNAL_GENERATED:
            async with get_conn() as conn:
                conn.row_factory = aiosqlite.Row
                cur = await conn.execute(
                    "SELECT content FROM journals WHERE date = ? ORDER BY generated_at DESC LIMIT 1",
                    (date_str,),
                )
                row = await cur.fetchone()
            base["journal_content"] = row["content"] if row and row["content"] else ""
        elif trigger == EventNames.BLOG_GENERATED:
            async with get_conn() as conn:
                conn.row_factory = aiosqlite.Row
                cur = await conn.execute(
                    "SELECT content FROM blog_posts WHERE date = ? ORDER BY generated_at DESC LIMIT 1",
                    (date_str,),
                )
                row = await cur.fetchone()
            base["blog_content"] = row["content"] if row and row["content"] else ""
        elif trigger == EventNames.CAPTURE_INFERRED:
            async with get_conn() as conn:
                conn.row_factory = aiosqlite.Row
                cur = await conn.execute(
                    """SELECT a.summary, a.task_category, a.productivity_state,
                              a.app_name_override, a.started_at, a.tags,
                              c.app_name
                       FROM activities a
                       LEFT JOIN captures c ON c.id = a.capture_id
                       ORDER BY a.id DESC LIMIT 1""",
                )
                row = await cur.fetchone()
            if row:
                base.update({
                    "summary": row["summary"] or "",
                    "task_category": row["task_category"] or "",
                    "productivity_state": row["productivity_state"] or "",
                    "app_name": row["app_name_override"] or row["app_name"] or "",
                    "timestamp": row["started_at"] or "",
                    "tags": row["tags"] or "[]",
                })
        return base

    async def run_rule_now(self, rule_id: int) -> dict[str, Any]:
        """Trigger a rule manually. Used by the UI 'Run now' button."""
        rule = await self._load_rule(rule_id)
        if rule is None:
            raise ValueError(f"Rule {rule_id} not found, not enabled, or not parsed")
        now = datetime.now(UTC)
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        trigger = rule.get("trigger", "manual")
        payload = await self._build_manual_payload(trigger, date_str, time_str)
        started = now.isoformat()
        try:
            args_template = json.loads(rule["args_template"] or "{}")
            rendered = render_args(args_template, payload)
            client = await self._client_for_plugin(rule["plugin_id"], rule)
            result = await client.call_tool(rule["tool_name"], rendered)
            await self._log_execution(rule_id, started, status="ok",
                                      payload=payload, result=result)
            return {"ok": True, "result": result}
        except MCPTimeoutError as exc:
            msg = self._redact(rule, str(exc))
            await self._log_execution(rule_id, started, status="timeout",
                                      error=msg, payload=payload, result=None)
            return {"ok": False, "error": msg}
        except Exception as exc:
            msg = self._redact(rule, str(exc))
            await self._log_execution(rule_id, started, status="error",
                                      error=msg, payload=payload, result=None)
            return {"ok": False, "error": msg}
