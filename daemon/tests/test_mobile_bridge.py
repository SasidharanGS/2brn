"""Tests for the mobile-companion daemon bridge.

Covers the opt-in ``lan_access`` config, the ``/connection-info`` endpoint, the
settings round-trip, and note ingestion (persist / list / delete, plus the
best-effort embedding path).
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from brn_daemon.config import Config, load_config, save_config
from brn_daemon.db import init_db


@pytest.fixture
async def client(tmp_home):
    await init_db()
    from brn_daemon.main import app_state, create_app

    # Start from a known state: no embed client / chroma store unless a test wires
    # them (app_state is a shared module global across the suite).
    app_state["_embed_client_ref"] = None
    app_state["chroma_store"] = None
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app_state["_embed_client_ref"] = None
    app_state["chroma_store"] = None


# ── config ────────────────────────────────────────────────────────────────────

def test_config_lan_access_defaults_false(tmp_home):
    assert load_config().lan_access is False


def test_config_lan_access_round_trips(tmp_home):
    cfg = Config()
    cfg.lan_access = True
    save_config(cfg)
    assert load_config().lan_access is True


# ── /connection-info ────────────────────────────────────────────────────────────

async def test_connection_info_shape(client):
    resp = await client.get("/connection-info")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data) >= {"hostname", "port", "lan_access", "lan_urls"}
    assert data["port"] == 7842
    assert data["lan_access"] is False
    assert isinstance(data["lan_urls"], list)
    for url in data["lan_urls"]:
        assert url.startswith("http://") and url.endswith(":7842")
        assert "127.0.0.1" not in url


# ── /settings lan_access ────────────────────────────────────────────────────────

async def test_settings_exposes_lan_access(client):
    resp = await client.get("/settings")
    assert resp.status_code == 200
    assert resp.json()["lan_access"] is False


async def test_settings_put_toggles_lan_access(client):
    resp = await client.put("/settings", json={"lan_access": True})
    assert resp.status_code == 200
    resp = await client.get("/settings")
    assert resp.json()["lan_access"] is True
    assert load_config().lan_access is True


# ── /ingest/note ────────────────────────────────────────────────────────────────

async def test_ingest_note_persists_without_embedding(client):
    resp = await client.post(
        "/ingest/note",
        json={
            "text": "Remember to read the RAG paper",
            "title": "RAG paper",
            "source_url": "https://example.com/rag",
            "tags": "ml,reading",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["embedded"] is False  # no embed client wired
    assert isinstance(body["id"], int)


async def test_ingest_note_rejects_whitespace_text(client):
    resp = await client.post("/ingest/note", json={"text": "   "})
    assert resp.status_code == 400


async def test_ingest_note_rejects_missing_text(client):
    resp = await client.post("/ingest/note", json={"title": "no text"})
    assert resp.status_code == 422


async def test_list_and_delete_notes(client):
    r1 = await client.post("/ingest/note", json={"text": "first note"})
    r2 = await client.post("/ingest/note", json={"text": "second note"})
    id1, id2 = r1.json()["id"], r2.json()["id"]

    listing = await client.get("/ingest/notes")
    assert listing.status_code == 200
    notes = listing.json()
    assert {n["id"] for n in notes} >= {id1, id2}
    assert notes[0]["id"] == id2  # newest first

    dele = await client.delete(f"/ingest/notes/{id1}")
    assert dele.status_code == 200
    listing2 = await client.get("/ingest/notes")
    assert id1 not in {n["id"] for n in listing2.json()}


async def test_delete_missing_note_404(client):
    resp = await client.delete("/ingest/notes/999999")
    assert resp.status_code == 404


async def test_ingest_note_embeds_when_clients_present(client):
    from brn_daemon.main import app_state

    fake_embed = MagicMock()
    fake_embed.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
    fake_chroma = MagicMock()
    fake_chroma.add_note = AsyncMock()
    app_state["_embed_client_ref"] = fake_embed
    app_state["chroma_store"] = fake_chroma

    resp = await client.post("/ingest/note", json={"text": "embed me", "title": "T"})
    assert resp.status_code == 200
    assert resp.json()["embedded"] is True
    fake_embed.embed.assert_awaited_once()
    fake_chroma.add_note.assert_awaited_once()


# ── pairing helper ──────────────────────────────────────────────────────────────

def test_build_pairing_url_encoding():
    from brn_daemon.pair import build_pairing_url

    url = build_pairing_url("http://192.168.1.23:7842", "tok EN/3")
    assert url.startswith("twobrn://pair?u=")
    assert "u=http%3A%2F%2F192.168.1.23%3A7842" in url
    assert "t=tok%20EN%2F3" in url
