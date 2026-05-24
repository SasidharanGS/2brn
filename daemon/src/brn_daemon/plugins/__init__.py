"""Plugin system: MCP servers + natural-language rules.

Public API:
    EventBus              — async pub/sub for daemon events
    EventNames            — canonical trigger event names
    MCPClient, MCPClientPool — manage MCP server subprocesses
    parse_rule            — NL rule text → ParsedRule via LLM
    ParsedRule            — structured rule plan (trigger, tool, args)
    PluginOrchestrator    — coordinates events → rules → tool calls
"""
from brn_daemon.plugins.events import EventBus, EventNames
from brn_daemon.plugins.mcp_client import MCPClient, MCPClientPool, MCPError
from brn_daemon.plugins.rule_parser import ParsedRule, parse_rule
from brn_daemon.plugins.orchestrator import PluginOrchestrator

__all__ = [
    "EventBus", "EventNames",
    "MCPClient", "MCPClientPool", "MCPError",
    "ParsedRule", "parse_rule",
    "PluginOrchestrator",
]
