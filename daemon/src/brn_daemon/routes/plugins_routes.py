"""HTTP API for plugin and rule CRUD + introspection.

Plugins represent MCP servers (command + args + env_keys). Rules attach to a
plugin and describe — in natural language — what to do when a trigger fires.

The orchestrator is read from main.app_state and re-parses rules / refreshes
scheduled jobs as a side effect of mutating endpoints.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from brn_daemon.config import (
    delete_plugin_env_value,
    set_plugin_env_value,
)
from brn_daemon.db import get_db_path

router = APIRouter()
logger = logging.getLogger(__name__)


# ---- Pydantic models ------------------------------------------------------

_SAFE_ID_RE = re.compile(r'^[A-Za-z0-9_-]+$')


def _validate_env_keys(v: dict[str, str] | None) -> dict[str, str] | None:
    if v is None:
        return v
    for key in v:
        if not _SAFE_ID_RE.match(key):
            raise ValueError(f"Env key '{key}' must match ^[A-Za-z0-9_-]+$")
    return v


class PluginOut(BaseModel):
    id: int
    name: str
    command: str
    args: list[str]
    env_keys: list[str]
    enabled: bool
    created_at: str
    last_health_at: str | None = None
    last_health_ok: bool | None = None
    last_health_error: str | None = None


class PluginCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    command: str = Field(..., min_length=1)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Env var values (stored in keychain). Keys recorded on the plugin.",
    )

    @field_validator("name")
    @classmethod
    def name_safe(cls, v: str) -> str:
        if not _SAFE_ID_RE.match(v):
            raise ValueError("Plugin name must match ^[A-Za-z0-9_-]+$")
        return v

    @field_validator("env")
    @classmethod
    def env_keys_safe(cls, v: dict[str, str]) -> dict[str, str]:
        for key in v:
            if not _SAFE_ID_RE.match(key):
                raise ValueError(f"Env key '{key}' must match ^[A-Za-z0-9_-]+$")
        return v


class PluginUpdate(BaseModel):
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    enabled: bool | None = None

    @field_validator("env")
    @classmethod
    def env_keys_safe(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        return _validate_env_keys(v)


class RuleOut(BaseModel):
    id: int
    plugin_id: int
    title: str
    rule_text: str
    enabled: bool
    trigger: str
    tool_name: str | None
    args_template: dict | None
    parse_status: str
    parse_error: str | None
    parsed_at: str | None
    created_at: str


class RuleCreate(BaseModel):
    plugin_id: int
    title: str = Field(..., min_length=1, max_length=120)
    rule_text: str = Field(..., min_length=1)
    enabled: bool = True


class RuleUpdate(BaseModel):
    title: str | None = None
    rule_text: str | None = None
    enabled: bool | None = None


class ExecutionOut(BaseModel):
    id: int
    rule_id: int
    started_at: str
    ended_at: str | None
    status: str
    error: str | None
    payload: dict | None
    result: dict | None


class ToolOut(BaseModel):
    name: str
    description: str
    input_schema: dict


# ---- helpers --------------------------------------------------------------


def _get_orchestrator():
    """Late-import to break circular dependency with main.py."""
    from brn_daemon.main import app_state
    orch = app_state.get("plugin_orchestrator")
    if orch is None:
        raise HTTPException(503, "Plugin orchestrator not initialised")
    return orch


def _row_to_plugin(row: aiosqlite.Row) -> PluginOut:
    return PluginOut(
        id=row["id"],
        name=row["name"],
        command=row["command"],
        args=json.loads(row["args"] or "[]"),
        env_keys=json.loads(row["env_keys"] or "[]"),
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        last_health_at=row["last_health_at"],
        last_health_ok=bool(row["last_health_ok"]) if row["last_health_ok"] is not None else None,
        last_health_error=row["last_health_error"],
    )


def _row_to_rule(row: aiosqlite.Row) -> RuleOut:
    args_tpl = None
    if row["args_template"]:
        try:
            args_tpl = json.loads(row["args_template"])
        except json.JSONDecodeError:
            args_tpl = None
    return RuleOut(
        id=row["id"],
        plugin_id=row["plugin_id"],
        title=row["title"],
        rule_text=row["rule_text"],
        enabled=bool(row["enabled"]),
        trigger=row["trigger"],
        tool_name=row["tool_name"],
        args_template=args_tpl,
        parse_status=row["parse_status"],
        parse_error=row["parse_error"],
        parsed_at=row["parsed_at"],
        created_at=row["created_at"],
    )


async def _fetch_plugin(conn: aiosqlite.Connection, plugin_id: int) -> aiosqlite.Row:
    cur = await conn.execute("SELECT * FROM plugins WHERE id = ?", (plugin_id,))
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(404, "Plugin not found")
    return row


async def _fetch_rule(conn: aiosqlite.Connection, rule_id: int) -> aiosqlite.Row:
    cur = await conn.execute("SELECT * FROM plugin_rules WHERE id = ?", (rule_id,))
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(404, "Rule not found")
    return row


# ---- Plugin CRUD ----------------------------------------------------------


@router.get("/plugins", response_model=list[PluginOut])
async def list_plugins():
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM plugins ORDER BY created_at ASC")
        rows = await cur.fetchall()
    return [_row_to_plugin(r) for r in rows]


@router.post("/plugins", response_model=PluginOut, status_code=201)
async def create_plugin(body: PluginCreate):
    env_keys = sorted(body.env.keys())
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        try:
            cur = await conn.execute(
                """INSERT INTO plugins (name, command, args, env_keys, enabled)
                   VALUES (?, ?, ?, ?, 1)""",
                (body.name, body.command, json.dumps(body.args), json.dumps(env_keys)),
            )
        except aiosqlite.IntegrityError:
            raise HTTPException(409, f"Plugin '{body.name}' already exists")
        plugin_id: int = cur.lastrowid  # type: ignore[assignment]
        await conn.commit()
        row = await _fetch_plugin(conn, plugin_id)

    for k, v in body.env.items():
        try:
            set_plugin_env_value(body.name, k, v)
        except RuntimeError as exc:
            logger.warning("Could not save env %s for plugin %s: %s", k, body.name, exc)

    return _row_to_plugin(row)


@router.put("/plugins/{plugin_id}", response_model=PluginOut)
async def update_plugin(plugin_id: int, body: PluginUpdate):
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        row = await _fetch_plugin(conn, plugin_id)
        new_command = body.command if body.command is not None else row["command"]
        new_args = json.dumps(body.args) if body.args is not None else row["args"]
        new_enabled = int(body.enabled) if body.enabled is not None else row["enabled"]
        if body.env is not None:
            new_env_keys = json.dumps(sorted(body.env.keys()))
        else:
            new_env_keys = row["env_keys"]
        await conn.execute(
            """UPDATE plugins
               SET command = ?, args = ?, env_keys = ?, enabled = ?
               WHERE id = ?""",
            (new_command, new_args, new_env_keys, new_enabled, plugin_id),
        )
        await conn.commit()
        row = await _fetch_plugin(conn, plugin_id)
        plugin_name = row["name"]

    if body.env is not None:
        for k, v in body.env.items():
            try:
                set_plugin_env_value(plugin_name, k, v)
            except RuntimeError as exc:
                logger.warning("Could not save env %s for plugin %s: %s", k, plugin_name, exc)

    # Restart subprocess so it picks up new command/args/env, and refresh schedule.
    orch = _get_orchestrator()
    await orch.pool.restart(plugin_id)
    await orch.refresh_rules()
    return _row_to_plugin(row)


@router.delete("/plugins/{plugin_id}", status_code=204)
async def delete_plugin(plugin_id: int):
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        row = await _fetch_plugin(conn, plugin_id)
        env_keys = json.loads(row["env_keys"] or "[]")
        plugin_name = row["name"]
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute("DELETE FROM plugins WHERE id = ?", (plugin_id,))
        await conn.commit()

    for k in env_keys:
        delete_plugin_env_value(plugin_name, k)

    orch = _get_orchestrator()
    await orch.pool.restart(plugin_id)
    await orch.refresh_rules()


@router.get("/plugins/{plugin_id}/tools", response_model=list[ToolOut])
async def list_plugin_tools(plugin_id: int):
    """Connect to the MCP server and list its tools. Used by the UI when authoring rules."""
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        row = await _fetch_plugin(conn, plugin_id)
    orch = _get_orchestrator()
    try:
        tools = await orch.list_plugin_tools(
            plugin_id=plugin_id,
            command=row["command"],
            args=json.loads(row["args"] or "[]"),
            env_keys=json.loads(row["env_keys"] or "[]"),
            plugin_name=row["name"],
        )
        # Mark plugin healthy.
        now = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(get_db_path()) as conn:
            await conn.execute(
                "UPDATE plugins SET last_health_at = ?, last_health_ok = 1, last_health_error = NULL WHERE id = ?",
                (now, plugin_id),
            )
            await conn.commit()
        return [ToolOut(**t) for t in tools]
    except Exception as exc:
        now = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(get_db_path()) as conn:
            await conn.execute(
                "UPDATE plugins SET last_health_at = ?, last_health_ok = 0, last_health_error = ? WHERE id = ?",
                (now, str(exc), plugin_id),
            )
            await conn.commit()
        raise HTTPException(502, f"MCP server unreachable: {exc}")


# ---- Rule CRUD ------------------------------------------------------------


@router.get("/plugin-rules", response_model=list[RuleOut])
async def list_rules(plugin_id: int | None = None):
    sql = "SELECT * FROM plugin_rules"
    params: tuple = ()
    if plugin_id is not None:
        sql += " WHERE plugin_id = ?"
        params = (plugin_id,)
    sql += " ORDER BY created_at ASC"
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(sql, params)
        rows = await cur.fetchall()
    return [_row_to_rule(r) for r in rows]


@router.post("/plugin-rules", response_model=RuleOut, status_code=201)
async def create_rule(body: RuleCreate):
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        plugin_row = await _fetch_plugin(conn, body.plugin_id)
        cur = await conn.execute(
            """INSERT INTO plugin_rules
               (plugin_id, title, rule_text, enabled, trigger, parse_status)
               VALUES (?, ?, ?, ?, 'manual', 'pending')""",
            (body.plugin_id, body.title, body.rule_text, int(body.enabled)),
        )
        rule_id: int = cur.lastrowid  # type: ignore[assignment]
        await conn.commit()

    orch = _get_orchestrator()
    # Try to parse immediately. Failures are stored on the row; we still return 201.
    try:
        await orch.reparse_rule(
            rule_id=rule_id,
            rule_text=body.rule_text,
            plugin_id=body.plugin_id,
            command=plugin_row["command"],
            args=json.loads(plugin_row["args"] or "[]"),
            env_keys=json.loads(plugin_row["env_keys"] or "[]"),
            plugin_name=plugin_row["name"],
        )
    except Exception as exc:
        logger.info("Rule %s saved but parse failed: %s", rule_id, exc)

    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        row = await _fetch_rule(conn, rule_id)
    return _row_to_rule(row)


@router.put("/plugin-rules/{rule_id}", response_model=RuleOut)
async def update_rule(rule_id: int, body: RuleUpdate):
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        rule = await _fetch_rule(conn, rule_id)
        plugin = await _fetch_plugin(conn, rule["plugin_id"])
        new_title = body.title if body.title is not None else rule["title"]
        new_text = body.rule_text if body.rule_text is not None else rule["rule_text"]
        new_enabled = int(body.enabled) if body.enabled is not None else rule["enabled"]
        await conn.execute(
            "UPDATE plugin_rules SET title = ?, rule_text = ?, enabled = ? WHERE id = ?",
            (new_title, new_text, new_enabled, rule_id),
        )
        if body.rule_text is not None and body.rule_text != rule["rule_text"]:
            # Mark for re-parse.
            await conn.execute(
                "UPDATE plugin_rules SET parse_status = 'pending', parse_error = NULL WHERE id = ?",
                (rule_id,),
            )
        await conn.commit()

    orch = _get_orchestrator()
    if body.rule_text is not None and body.rule_text != rule["rule_text"]:
        try:
            await orch.reparse_rule(
                rule_id=rule_id,
                rule_text=new_text,
                plugin_id=rule["plugin_id"],
                command=plugin["command"],
                args=json.loads(plugin["args"] or "[]"),
                env_keys=json.loads(plugin["env_keys"] or "[]"),
                plugin_name=plugin["name"],
            )
        except Exception as exc:
            logger.info("Rule %s re-parse failed: %s", rule_id, exc)
    else:
        await orch.refresh_rules()

    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        row = await _fetch_rule(conn, rule_id)
    return _row_to_rule(row)


@router.delete("/plugin-rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: int):
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        await _fetch_rule(conn, rule_id)
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute("DELETE FROM plugin_rules WHERE id = ?", (rule_id,))
        await conn.commit()
    orch = _get_orchestrator()
    await orch.refresh_rules()


@router.post("/plugin-rules/{rule_id}/reparse", response_model=RuleOut)
async def reparse_rule(rule_id: int):
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        rule = await _fetch_rule(conn, rule_id)
        plugin = await _fetch_plugin(conn, rule["plugin_id"])
    orch = _get_orchestrator()
    try:
        await orch.reparse_rule(
            rule_id=rule_id,
            rule_text=rule["rule_text"],
            plugin_id=rule["plugin_id"],
            command=plugin["command"],
            args=json.loads(plugin["args"] or "[]"),
            env_keys=json.loads(plugin["env_keys"] or "[]"),
            plugin_name=plugin["name"],
        )
    except Exception as exc:
        # Status is already persisted as 'error' inside reparse_rule.
        logger.info("Re-parse rule %s failed: %s", rule_id, exc)
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        row = await _fetch_rule(conn, rule_id)
    return _row_to_rule(row)


@router.post("/plugin-rules/{rule_id}/run")
async def run_rule(rule_id: int):
    orch = _get_orchestrator()
    try:
        return await orch.run_rule_now(rule_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/plugin-rules/{rule_id}/executions", response_model=list[ExecutionOut])
async def list_executions(rule_id: int, limit: int = 50):
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        await _fetch_rule(conn, rule_id)
        cur = await conn.execute(
            """SELECT * FROM plugin_rule_executions
               WHERE rule_id = ?
               ORDER BY started_at DESC
               LIMIT ?""",
            (rule_id, min(max(limit, 1), 500)),
        )
        rows = await cur.fetchall()

    def _parse(s: str | None):
        if not s:
            return None
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return None

    return [
        ExecutionOut(
            id=r["id"],
            rule_id=r["rule_id"],
            started_at=r["started_at"],
            ended_at=r["ended_at"],
            status=r["status"],
            error=r["error"],
            payload=_parse(r["payload"]),
            result=_parse(r["result"]),
        )
        for r in rows
    ]
