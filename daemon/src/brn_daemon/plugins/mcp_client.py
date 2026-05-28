"""Minimal MCP (Model Context Protocol) client over stdio JSON-RPC.

MCP servers communicate via newline-delimited JSON-RPC 2.0 over stdin/stdout.
We support:
    initialize          (handshake)
    tools/list          (discover available tools)
    tools/call          (invoke a tool)

This client deliberately depends only on the Python stdlib — no `mcp` package —
so 2brn stays light. If we ever need streaming notifications, swap to the
official SDK.
"""
import asyncio
import json
import logging
import os
import platform
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_BASE_ENV_KEYS = {
    "PATH", "HOME", "USER", "LOGNAME",
    "LANG", "LC_ALL", "LC_CTYPE",
    "TMPDIR", "TEMP", "TMP",
    "TERM", "COLORTERM",
}
_WINDOWS_ENV_KEYS = {
    "SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC",
    "USERPROFILE", "APPDATA", "LOCALAPPDATA",
}


def _build_subprocess_env(plugin_env: dict[str, str]) -> dict[str, str]:
    """Return a minimal env for an MCP subprocess.

    Whitelists only OS-level vars needed by runtimes (node, python, etc.)
    to locate binaries and temp dirs. Merges plugin_env on top.
    Never passes arbitrary daemon env vars (API keys, tokens, etc.).
    """
    allowed = _BASE_ENV_KEYS | (_WINDOWS_ENV_KEYS if platform.system() == "Windows" else set())
    base = {k: v for k, v in os.environ.items() if k in allowed}
    return {**base, **plugin_env}

# JSON-RPC error code for "method not found" / generic invalid response.
MCP_PROTOCOL_VERSION = "2024-11-05"
DEFAULT_REQUEST_TIMEOUT = 30.0  # seconds


class MCPError(RuntimeError):
    pass


@dataclass
class MCPTool:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


class MCPClient:
    """Manages a single MCP server subprocess and dispatches JSON-RPC calls.

    Not thread-safe; intended to be used from a single asyncio event loop.
    """

    def __init__(
        self,
        command: str,
        args: list[str],
        env: dict[str, str] | None = None,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        self.command = command
        self.args = list(args)
        self.env = dict(env or {})
        self.request_timeout = request_timeout
        self._proc: asyncio.subprocess.Process | None = None
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._initialized = False
        self._tools_cache: list[MCPTool] | None = None

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def start(self) -> None:
        """Spawn the subprocess and perform the MCP handshake."""
        if self.is_running:
            return
        full_env = _build_subprocess_env(self.env)
        try:
            self._proc = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=full_env,
            )
        except FileNotFoundError as exc:
            raise MCPError(f"Command not found: {self.command}") from exc
        except Exception as exc:
            # Keep broad: subprocess.Popen can fail with FileNotFoundError,
            # PermissionError, or OSError depending on OS and PATH state.
            raise MCPError(f"Failed to start MCP server '{self.command}': {exc}") from exc

        self._reader_task = asyncio.create_task(self._read_loop(), name="mcp-stdout")
        self._stderr_task = asyncio.create_task(self._drain_stderr(), name="mcp-stderr")

        # MCP handshake.
        try:
            await self._request("initialize", {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "2brn", "version": "0.1.0"},
            })
            await self._notify("notifications/initialized", {})
            self._initialized = True
        except Exception:
            await self.stop()
            raise

    async def stop(self) -> None:
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.terminate()
                try:
                    await asyncio.wait_for(self._proc.wait(), timeout=2.0)
                except TimeoutError:
                    self._proc.kill()
                    await self._proc.wait()
            except ProcessLookupError:
                pass
        for task in (self._reader_task, self._stderr_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        # Fail any outstanding requests.
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(MCPError("MCP client stopped"))
        self._pending.clear()
        self._proc = None
        self._initialized = False
        self._tools_cache = None

    async def list_tools(self, force_refresh: bool = False) -> list[MCPTool]:
        if self._tools_cache is not None and not force_refresh:
            return self._tools_cache
        result = await self._request("tools/list", {})
        tools_raw = result.get("tools", []) if isinstance(result, dict) else []
        tools = [
            MCPTool(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}) or {},
            )
            for t in tools_raw
            if isinstance(t, dict) and t.get("name")
        ]
        self._tools_cache = tools
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = await self._request("tools/call", {"name": name, "arguments": arguments})
        if isinstance(result, dict) and result.get("isError"):
            content = result.get("content", [])
            text = content[0].get("text", "tool error") if content else "tool error"
            raise MCPError(f"Tool '{name}' returned error: {text}")
        return result if isinstance(result, dict) else {"result": result}

    # ---- internals --------------------------------------------------------

    async def _request(self, method: str, params: dict[str, Any]) -> Any:
        if not self.is_running:
            raise MCPError("MCP server is not running")
        async with self._lock:
            req_id = self._next_id
            self._next_id += 1
        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[req_id] = fut
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        await self._write(msg)
        try:
            return await asyncio.wait_for(fut, timeout=self.request_timeout)
        except TimeoutError as exc:
            self._pending.pop(req_id, None)
            raise MCPError(f"MCP request '{method}' timed out after {self.request_timeout}s") from exc

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        await self._write(msg)

    async def _write(self, msg: dict[str, Any]) -> None:
        if not self._proc or not self._proc.stdin:
            raise MCPError("MCP stdin not available")
        data = (json.dumps(msg) + "\n").encode("utf-8")
        self._proc.stdin.write(data)
        await self._proc.stdin.drain()

    async def _read_loop(self) -> None:
        assert self._proc and self._proc.stdout
        try:
            while True:
                line = await self._proc.stdout.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line.decode("utf-8").strip())
                except json.JSONDecodeError:
                    logger.warning("MCP non-JSON line: %r", line[:200])
                    continue
                self._dispatch(msg)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("MCP read loop crashed")
        # On loop exit, fail pending requests.
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(MCPError("MCP server stream closed"))
        self._pending.clear()

    def _dispatch(self, msg: dict[str, Any]) -> None:
        msg_id = msg.get("id")
        if msg_id is None:
            # Server-initiated notification — ignore for now.
            return
        fut = self._pending.pop(msg_id, None)
        if fut is None or fut.done():
            return
        if "error" in msg:
            err = msg["error"]
            fut.set_exception(MCPError(f"MCP error {err.get('code')}: {err.get('message')}"))
        else:
            fut.set_result(msg.get("result"))

    async def _drain_stderr(self) -> None:
        assert self._proc and self._proc.stderr
        try:
            while True:
                line = await self._proc.stderr.readline()
                if not line:
                    break
                logger.debug("[mcp %s stderr] %s", self.command, line.decode(errors="replace").rstrip())
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("MCP stderr drain crashed")


class MCPClientPool:
    """Caches MCPClient instances per plugin_id, lazy-starts on first use.

    Callers must invoke `close_all()` on shutdown.
    """

    def __init__(self) -> None:
        self._clients: dict[int, MCPClient] = {}
        self._lock = asyncio.Lock()

    async def get(
        self,
        plugin_id: int,
        command: str,
        args: list[str],
        env: dict[str, str],
    ) -> MCPClient:
        async with self._lock:
            existing = self._clients.get(plugin_id)
            if existing and existing.is_running:
                return existing
            # Replace stale (crashed) client.
            if existing:
                await existing.stop()
            client = MCPClient(command=command, args=args, env=env)
            await client.start()
            self._clients[plugin_id] = client
            return client

    async def restart(self, plugin_id: int) -> None:
        async with self._lock:
            client = self._clients.pop(plugin_id, None)
            if client:
                await client.stop()

    async def close_all(self) -> None:
        async with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
        await asyncio.gather(*(c.stop() for c in clients), return_exceptions=True)
