"""Tests for P2 fixes: API date validation (F-ROUTE-1/2) and plugin secret
redaction (F-SEC-5)."""
from unittest.mock import MagicMock

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
