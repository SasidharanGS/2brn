import logging
import pytest
from httpx import AsyncClient, ASGITransport
from brn_daemon.log_buffer import log_buffer
from brn_daemon.main import app


@pytest.fixture(autouse=True)
def clear_log_buffer():
    """Clear the module-level log_buffer before each test."""
    log_buffer._buf.clear()
    yield
    log_buffer._buf.clear()


@pytest.mark.asyncio
async def test_get_logs_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/logs")
    assert resp.status_code == 200
    data = resp.json()
    assert "lines" in data
    assert isinstance(data["lines"], list)


@pytest.mark.asyncio
async def test_get_logs_returns_recent_lines():
    # Seed the buffer directly
    for msg in ["alpha", "beta", "gamma"]:
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None
        )
        log_buffer.append(record)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/logs?limit=10")
    assert resp.status_code == 200
    msgs = [l["msg"] for l in resp.json()["lines"]]
    assert "alpha" in msgs
    assert "gamma" in msgs


@pytest.mark.asyncio
async def test_get_logs_level_filter():
    for level, msg in [
        (logging.INFO, "info line"),
        (logging.WARNING, "warn line"),
        (logging.ERROR, "error line"),
    ]:
        record = logging.LogRecord(
            name="test", level=level, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None
        )
        log_buffer.append(record)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/logs?level=WARNING")
    lines = resp.json()["lines"]
    assert all(l["level"] in ("WARNING", "ERROR") for l in lines)
    assert not any(l["msg"] == "info line" for l in lines)


@pytest.mark.asyncio
async def test_get_debug_status_shape():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/debug/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "daemon" in data
    assert "gateway" in data
    assert "chroma" in data
    assert "last_error" in data
    assert "status" in data["daemon"]
    assert "reachable" in data["gateway"]
    assert "activity_memories" in data["chroma"]
    assert "note_memories" in data["chroma"]
