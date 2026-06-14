import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def client(tmp_home, db):
    from brn_daemon.main import create_app

    mock_orch = MagicMock()
    mock_orch.reparse_rule = AsyncMock()
    mock_orch.refresh_rules = AsyncMock()
    mock_orch.pool = MagicMock()
    mock_orch.pool.restart = AsyncMock()

    app = create_app()
    app.state.context.plugin_orchestrator = mock_orch
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c.ctx = app.state.context
        yield c


async def test_rule_text_max_length_rejected(client, tmp_home, db):
    """rule_text longer than 2000 chars must be rejected with 422."""
    resp = await client.post("/plugins", json={
        "name": "test-plugin",
        "command": "echo",
        "args": [],
        "env": {},
    })
    assert resp.status_code == 201
    plugin_id = resp.json()["id"]

    long_text = "x" * 2001
    resp = await client.post("/plugin-rules", json={
        "plugin_id": plugin_id,
        "title": "Test Rule",
        "rule_text": long_text,
        "enabled": True,
    })
    assert resp.status_code == 422


async def test_rule_text_at_limit_accepted(client, tmp_home, db):
    """rule_text of exactly 2000 chars must be accepted."""
    resp = await client.post("/plugins", json={
        "name": "test-plugin2",
        "command": "echo",
        "args": [],
        "env": {},
    })
    assert resp.status_code == 201
    plugin_id = resp.json()["id"]

    text_2000 = "x" * 2000
    resp = await client.post("/plugin-rules", json={
        "plugin_id": plugin_id,
        "title": "Test Rule",
        "rule_text": text_2000,
        "enabled": True,
    })
    assert resp.status_code == 201


@pytest.mark.parametrize("bad_command", [
    "some\x00command",
    "../../../bin/sh",
    "/usr/../etc/passwd",
    "a" * 513,
])
async def test_plugin_command_validation_rejects_bad(client, tmp_home, db, bad_command):
    """Commands with null bytes, path traversal, or length > 512 must be rejected."""
    resp = await client.post("/plugins", json={
        "name": "bad-cmd-plugin",
        "command": bad_command,
        "args": [],
        "env": {},
    })
    assert resp.status_code == 422, f"Expected 422 for command={bad_command!r}"


async def test_plugin_command_valid_absolute_path(client, tmp_home, db):
    """A normal absolute path command must be accepted."""
    resp = await client.post("/plugins", json={
        "name": "good-plugin",
        "command": "/usr/local/bin/node",
        "args": [],
        "env": {},
    })
    assert resp.status_code == 201


async def test_update_plugin_deletes_removed_env_keys(client, tmp_home, db):
    """Keys removed from env on plugin update must be deleted from keychain."""
    with patch("brn_daemon.routes.plugins_routes.set_plugin_env_value"):
        resp = await client.post("/plugins", json={
            "name": "env-test-plugin",
            "command": "echo",
            "args": [],
            "env": {"KEY_A": "value_a", "KEY_B": "value_b"},
        })
    assert resp.status_code == 201
    plugin_id = resp.json()["id"]

    with patch("brn_daemon.routes.plugins_routes.set_plugin_env_value"), \
         patch("brn_daemon.routes.plugins_routes.delete_plugin_env_value") as mock_delete:
        resp = await client.put(f"/plugins/{plugin_id}", json={
            "env": {"KEY_A": "new_value_a"},
        })
    assert resp.status_code == 200
    mock_delete.assert_called_once_with("env-test-plugin", "KEY_B")
