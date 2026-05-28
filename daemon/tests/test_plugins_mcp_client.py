import sys
from pathlib import Path

import pytest

from brn_daemon.plugins.mcp_client import MCPClient, MCPClientPool, MCPError


FAKE_SERVER = str(Path(__file__).parent / "fake_mcp_server.py")


def _client(timeout: float = 5.0) -> MCPClient:
    # Use the test's interpreter so the subprocess imports identical stdlib.
    return MCPClient(command=sys.executable, args=[FAKE_SERVER], request_timeout=timeout)


async def test_start_and_list_tools():
    client = _client()
    await client.start()
    try:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert {"echo", "boom", "slow"}.issubset(names)
    finally:
        await client.stop()


async def test_call_tool_echo_round_trip():
    client = _client()
    await client.start()
    try:
        result = await client.call_tool("echo", {"hello": "world", "n": 42})
        # Fake server echoes args inside text content.
        text = result["content"][0]["text"]
        assert "world" in text and "42" in text
    finally:
        await client.stop()


async def test_call_tool_returns_error_on_isError():
    client = _client()
    await client.start()
    try:
        with pytest.raises(MCPError, match="intentional failure"):
            await client.call_tool("boom", {})
    finally:
        await client.stop()


async def test_request_timeout():
    client = _client(timeout=0.5)
    await client.start()
    try:
        with pytest.raises(MCPError, match="timed out"):
            await client.call_tool("slow", {})
    finally:
        await client.stop()


async def test_start_with_missing_command_raises():
    client = MCPClient(command="/nonexistent/binary-zzz", args=[])
    with pytest.raises(MCPError, match="not found|Failed to start"):
        await client.start()


async def test_tools_cache_avoids_second_rpc():
    client = _client()
    await client.start()
    try:
        first = await client.list_tools()
        second = await client.list_tools()
        assert first is second  # same cached list object
    finally:
        await client.stop()


async def test_pool_reuses_client_for_same_id():
    pool = MCPClientPool()
    try:
        c1 = await pool.get(1, sys.executable, [FAKE_SERVER], {})
        c2 = await pool.get(1, sys.executable, [FAKE_SERVER], {})
        assert c1 is c2
    finally:
        await pool.close_all()


async def test_pool_close_all_stops_clients():
    pool = MCPClientPool()
    c = await pool.get(1, sys.executable, [FAKE_SERVER], {})
    assert c.is_running
    await pool.close_all()
    assert not c.is_running


async def test_subprocess_env_whitelist_excludes_secrets():
    """_build_subprocess_env must not contain secrets from os.environ."""
    import os
    from brn_daemon.plugins.mcp_client import _build_subprocess_env

    plugin_env = {"PLUGIN_TOKEN": "tok"}

    old = os.environ.get("_BRN_TEST_SENTINEL")
    os.environ["_BRN_TEST_SENTINEL"] = "should-not-leak"
    try:
        result = _build_subprocess_env(plugin_env)
    finally:
        if old is None:
            del os.environ["_BRN_TEST_SENTINEL"]
        else:
            os.environ["_BRN_TEST_SENTINEL"] = old

    assert result["PLUGIN_TOKEN"] == "tok"
    assert "PATH" in result
    assert "_BRN_TEST_SENTINEL" not in result
