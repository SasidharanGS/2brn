"""Tests for the device-management endpoints (per-device LAN tokens, #99).

These run on the default ASGITransport client (127.0.0.1 → loopback) with the
master token, matching how the desktop UI calls them. The loopback/LAN
enforcement itself is covered in ``test_auth.py``.
"""
from httpx import ASGITransport, AsyncClient

from brn_daemon import main as main_mod
from brn_daemon.db import init_db

_AUTH = {"Authorization": "Bearer secret-token"}


async def _make_client(tmp_home):
    await init_db()
    app = main_mod.create_app()
    app.state.context.api_token = "secret-token"
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def test_create_list_revoke_roundtrip(tmp_home):
    async with await _make_client(tmp_home) as client:
        created = await client.post("/devices", json={"name": "Pixel"}, headers=_AUTH)
        assert created.status_code == 200
        body = created.json()
        assert body["name"] == "Pixel"
        assert len(body["token"]) > 20  # token returned once, plaintext
        device_id = body["id"]

        listing = await client.get("/devices", headers=_AUTH)
        assert listing.status_code == 200
        rows = listing.json()
        assert any(r["id"] == device_id and r["name"] == "Pixel" for r in rows)
        # The token (and its hash) must never appear in the listing.
        assert all("token" not in r and "token_hash" not in r for r in rows)

        dele = await client.delete(f"/devices/{device_id}", headers=_AUTH)
        assert dele.status_code == 200
        assert dele.json()["deleted"] is True

        rows2 = (await client.get("/devices", headers=_AUTH)).json()
        assert device_id not in {r["id"] for r in rows2}


async def test_revoke_missing_device_reports_false(tmp_home):
    async with await _make_client(tmp_home) as client:
        resp = await client.delete("/devices/999999", headers=_AUTH)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is False


async def test_blank_name_falls_back_to_default(tmp_home):
    async with await _make_client(tmp_home) as client:
        created = await client.post("/devices", json={"name": "   "}, headers=_AUTH)
        assert created.status_code == 200
        assert created.json()["name"] == "device"


async def test_token_is_stored_hashed_not_plaintext(tmp_home):
    """The DB holds a 64-char SHA-256 hex, never the plaintext token."""
    from brn_daemon.db import get_conn
    from brn_daemon.repository import create_device

    await init_db()
    _id, token = await create_device("phone")
    async with get_conn() as conn:
        cur = await conn.execute("SELECT token_hash FROM devices WHERE id = ?", (_id,))
        row = await cur.fetchone()
    assert row is not None
    assert token not in row[0]
    assert len(row[0]) == 64
