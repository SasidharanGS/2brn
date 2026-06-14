"""Tests for loopback API authentication (review finding F-SEC-1)."""
import pytest
from httpx import ASGITransport, AsyncClient

from brn_daemon import main as main_mod
from brn_daemon.auth import load_or_create_token


def test_token_is_created_stable_and_0600(tmp_home):
    token = load_or_create_token()
    assert token
    path = tmp_home / "api_token"
    assert path.exists()
    assert load_or_create_token() == token, "token must be stable across calls"
    assert (path.stat().st_mode & 0o777) == 0o600


def test_env_token_overrides_file(tmp_home, monkeypatch):
    monkeypatch.setenv("BRN_API_TOKEN", "env-token-123")
    assert load_or_create_token() == "env-token-123"


async def test_protected_routes_require_token(tmp_home):
    from brn_daemon.db import init_db
    await init_db()
    app = main_mod.create_app()
    app.state.context.api_token = "secret-token"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        # Liveness probe is always reachable (used by the Electron health probe).
        assert (await client.get("/status")).status_code == 200
        # Protected route: missing / wrong token → 401.
        assert (await client.get("/captures?date=2026-01-01")).status_code == 401
        assert (
            await client.get(
                "/captures?date=2026-01-01", headers={"Authorization": "Bearer wrong"}
            )
        ).status_code == 401
        # Correct token → passes auth.
        ok = await client.get(
            "/captures?date=2026-01-01", headers={"Authorization": "Bearer secret-token"}
        )
        assert ok.status_code == 200


async def test_auth_inert_when_no_token_loaded(tmp_home):
    """Default state (and the test harness, which doesn't run the lifespan) has no
    token loaded, so auth is inert and the rest of the suite is unaffected.
    """
    from brn_daemon.db import init_db
    await init_db()
    app = main_mod.create_app()
    assert app.state.context.api_token in (None, "")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        assert (await client.get("/captures?date=2026-01-01")).status_code == 200


def _lan_transport(app):
    """ASGITransport whose client looks like a LAN peer (not loopback)."""
    return ASGITransport(app=app, client=("192.168.1.50", 5555))


async def test_master_token_rejected_over_lan(tmp_home):
    """The master token authenticates only on loopback — never over the LAN."""
    from brn_daemon.db import init_db
    await init_db()
    app = main_mod.create_app()
    app.state.context.api_token = "secret-token"
    async with AsyncClient(transport=_lan_transport(app), base_url="http://t") as client:
        resp = await client.get(
            "/captures?date=2026-01-01", headers={"Authorization": "Bearer secret-token"}
        )
        assert resp.status_code == 401


async def test_device_token_accepted_over_lan_then_revoked(tmp_home):
    """A per-device token works over the LAN and stops working once revoked."""
    from brn_daemon.db import init_db
    from brn_daemon.repository import create_device, delete_device
    await init_db()
    app = main_mod.create_app()
    app.state.context.api_token = "secret-token"
    device_id, device_token = await create_device("phone")

    async with AsyncClient(transport=_lan_transport(app), base_url="http://t") as client:
        ok = await client.get(
            "/captures?date=2026-01-01",
            headers={"Authorization": f"Bearer {device_token}"},
        )
        assert ok.status_code == 200

        assert await delete_device(device_id) is True
        revoked = await client.get(
            "/captures?date=2026-01-01",
            headers={"Authorization": f"Bearer {device_token}"},
        )
        assert revoked.status_code == 401


async def test_device_cannot_manage_devices_over_lan(tmp_home):
    """A valid device token still can't touch /devices* (loopback + master only)."""
    from brn_daemon.db import init_db
    from brn_daemon.repository import create_device
    await init_db()
    app = main_mod.create_app()
    app.state.context.api_token = "secret-token"
    _id, device_token = await create_device("phone")
    async with AsyncClient(transport=_lan_transport(app), base_url="http://t") as client:
        resp = await client.get("/devices", headers={"Authorization": f"Bearer {device_token}"})
        assert resp.status_code == 403


async def test_master_manages_devices_on_loopback(tmp_home):
    """The desktop (loopback + master token) can list devices."""
    from brn_daemon.db import init_db
    await init_db()
    app = main_mod.create_app()
    app.state.context.api_token = "secret-token"
    # Default ASGITransport client is 127.0.0.1 → loopback.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get("/devices", headers={"Authorization": "Bearer secret-token"})
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.parametrize("method,path,body", [
    ("GET",    "/connection-info",  None),
    ("POST",   "/ingest/note",      {"text": "hi"}),
    ("GET",    "/ingest/notes",     None),
    ("DELETE", "/ingest/notes/1",   None),
])
async def test_mobile_endpoints_require_token(tmp_home, method, path, body):
    """Every new mobile-bridge endpoint returns 401 when no token is provided."""
    from brn_daemon.db import init_db

    await init_db()
    app = main_mod.create_app()
    app.state.context.api_token = "secret-token"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        if method == "GET":
            resp = await client.get(path)
        elif method == "POST":
            resp = await client.post(path, json=body)
        else:
            resp = await client.delete(path)
        assert resp.status_code == 401, (
            f"{method} {path} returned {resp.status_code}, expected 401"
        )
