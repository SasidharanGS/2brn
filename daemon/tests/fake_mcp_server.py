"""Minimal fake MCP server for tests. Speaks line-delimited JSON-RPC 2.0 on stdin/stdout.

Supports:
    initialize       → returns protocolVersion + capabilities
    tools/list       → returns one tool: "echo"
    tools/call       → if name == "echo" returns {"content": [{"type":"text","text":"<json args>"}]}
                       if name == "boom" returns isError=True
                       if name == "slow" sleeps 5s (for timeout tests)

Notifications are accepted but not responded to.

Run: python -m tests.fake_mcp_server
"""
import json
import sys
import time


def _write(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _ok(req_id, result):
    _write({"jsonrpc": "2.0", "id": req_id, "result": result})


def _err(req_id, code, message):
    _write({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params") or {}

        # Notifications have no id; skip silently.
        if req_id is None:
            continue

        if method == "initialize":
            _ok(req_id, {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake-mcp", "version": "0.0.1"},
            })
        elif method == "tools/list":
            _ok(req_id, {"tools": [
                {"name": "echo", "description": "echo args back",
                 "inputSchema": {"type": "object"}},
                {"name": "boom", "description": "always errors",
                 "inputSchema": {"type": "object"}},
                {"name": "slow", "description": "blocks 5s",
                 "inputSchema": {"type": "object"}},
            ]})
        elif method == "tools/call":
            name = params.get("name")
            args = params.get("arguments", {})
            if name == "echo":
                _ok(req_id, {"content": [{"type": "text", "text": json.dumps(args)}]})
            elif name == "boom":
                _ok(req_id, {"isError": True,
                             "content": [{"type": "text", "text": "intentional failure"}]})
            elif name == "slow":
                time.sleep(5)
                _ok(req_id, {"content": [{"type": "text", "text": "done"}]})
            else:
                _err(req_id, -32601, f"unknown tool: {name}")
        else:
            _err(req_id, -32601, f"method not found: {method}")


if __name__ == "__main__":
    main()
