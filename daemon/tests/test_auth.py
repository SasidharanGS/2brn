"""Tests for loopback API authentication (review finding F-SEC-1)."""
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


async def test_protected_routes_require_token(tmp_home, monkeypatch):
    from brn_daemon.db import init_db
    await init_db()
    monkeypatch.setitem(main_mod.app_state, "api_token", "secret-token")
    app = main_mod.create_app()
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
    assert main_mod.app_state.get("api_token") in (None, "")
    app = main_mod.create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        assert (await client.get("/captures?date=2026-01-01")).status_code == 200
