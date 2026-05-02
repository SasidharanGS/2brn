"""Natural-language plugin rule → structured plan, via the user's chat LLM.

Parsed once when the rule is saved, then cached as columns on plugin_rules.
At runtime the orchestrator never calls the LLM — it just renders args_template
and invokes the named tool.

Output shape:
    ParsedRule(trigger, tool_name, args_template)

`args_template` is a JSON object whose string leaves may contain `{var}`
placeholders. Allowed variables depend on the trigger (see events.py).
"""
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Any

from brn_daemon.plugins.events import EventNames

logger = logging.getLogger(__name__)

# Triggers the orchestrator understands. Event names use EventNames constants;
# scheduled triggers use `daily_at_HH:MM` or `every_Xs`; `manual` for test/run.
ALLOWED_EVENT_TRIGGERS = set(EventNames.ALL)
SCHEDULED_PATTERNS = (
    re.compile(r"^daily_at_\d{2}:\d{2}$"),
    re.compile(r"^every_\d+s$"),
)
MANUAL_TRIGGER = "manual"
MIN_SCHEDULE_INTERVAL_SECONDS = 60


@dataclass
class ParsedRule:
    trigger: str
    tool_name: str
    args_template: dict[str, Any]

    def to_db_row(self) -> tuple[str, str, str]:
        return (self.trigger, self.tool_name, json.dumps(self.args_template))


class RuleParseError(ValueError):
    pass


# Chat function signature: async (messages: list[dict]) -> str (assistant content).
ChatFn = Callable[[list[dict[str, str]]], Awaitable[str]]


def validate_trigger(trigger: str) -> None:
    if trigger in ALLOWED_EVENT_TRIGGERS or trigger == MANUAL_TRIGGER:
        return
    for pat in SCHEDULED_PATTERNS:
        if pat.match(trigger):
            if trigger.startswith("every_") and trigger.endswith("s"):
                interval = int(trigger[len("every_"):-1])
                if interval < MIN_SCHEDULE_INTERVAL_SECONDS:
                    raise RuleParseError(
                        f"Scheduled trigger '{trigger}' has a minimum interval of "
                        f"{MIN_SCHEDULE_INTERVAL_SECONDS}s to prevent abuse."
                    )
            return
    raise RuleParseError(
        f"Invalid trigger '{trigger}'. Must be one of "
        f"{sorted(ALLOWED_EVENT_TRIGGERS) + [MANUAL_TRIGGER]} "
        f"or match 'daily_at_HH:MM' / 'every_Xs' (minimum {MIN_SCHEDULE_INTERVAL_SECONDS}s)."
    )


def _build_system_prompt(available_tools: list[dict[str, Any]]) -> str:
    tools_block = "\n".join(
        f"- {t['name']}: {t.get('description', '').strip()[:300]}\n"
        f"  arguments schema: {json.dumps(t.get('input_schema', {}))[:600]}"
        for t in available_tools
    ) or "  (no tools available)"

    triggers_list = ", ".join(sorted(ALLOWED_EVENT_TRIGGERS))

    return f"""You translate a user's natural-language automation rule into a structured plan that calls one MCP tool.

Available triggers (when the rule fires):
  Event triggers: {triggers_list}
  Scheduled: daily_at_HH:MM (24h clock), every_Xs (X seconds)
  Manual: manual (only when the user clicks "Run now")

Available tools on this plugin:
{tools_block}

Trigger payload variables you can reference in args_template using {{var}} placeholders:
  journal_generated: {{date}}, {{journal_content}}
  blog_generated:    {{date}}, {{blog_content}}
  capture_inferred:  {{summary}}, {{task_category}}, {{app_name}}, {{timestamp}}, {{tags}}
  scheduled/manual:  {{date}}, {{time}}

Return a single JSON object — no prose, no fences — with exactly these keys:
  "trigger":       string from the allowed set
  "tool_name":     one of the tool names listed above
  "args_template": object matching that tool's input schema; string values may embed {{var}} placeholders

If the rule cannot be expressed with the available tools or triggers, return:
  {{"error": "<short reason>"}}
"""


def _extract_json(text: str) -> dict[str, Any]:
    """Strip code fences if present, then parse JSON."""
    text = text.strip()
    if text.startswith("```"):
        # Drop the opening fence (e.g. ```json) and the closing ```.
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuleParseError(f"LLM did not return valid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise RuleParseError("LLM response was not a JSON object")
    return obj


async def parse_rule(
    rule_text: str,
    available_tools: list[dict[str, Any]],
    chat_fn: ChatFn,
) -> ParsedRule:
    """Ask the LLM to compile `rule_text` into a ParsedRule.

    `available_tools` is a list of dicts: [{"name": str, "description": str, "input_schema": dict}, ...]
    `chat_fn` is the daemon's existing chat function.
    """
    if not rule_text.strip():
        raise RuleParseError("Rule text is empty")
    if not available_tools:
        raise RuleParseError("Plugin exposes no tools — nothing to call")

    system = _build_system_prompt(available_tools)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": rule_text.strip()},
    ]
    raw = await chat_fn(messages)
    obj = _extract_json(raw)

    if "error" in obj:
        raise RuleParseError(f"LLM could not compile rule: {obj['error']}")

    for key in ("trigger", "tool_name", "args_template"):
        if key not in obj:
            raise RuleParseError(f"LLM response missing '{key}'")

    trigger = str(obj["trigger"])
    tool_name = str(obj["tool_name"])
    args_template = obj["args_template"]

    if not isinstance(args_template, dict):
        raise RuleParseError("args_template must be a JSON object")

    validate_trigger(trigger)
    tool_names = {t["name"] for t in available_tools}
    if tool_name not in tool_names:
        raise RuleParseError(
            f"Tool '{tool_name}' not in plugin's tool list: {sorted(tool_names)}"
        )

    return ParsedRule(trigger=trigger, tool_name=tool_name, args_template=args_template)


# ---- Template rendering ----------------------------------------------------


_TEMPLATE_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def render_args(template: Any, payload: dict[str, Any]) -> Any:
    """Recursively substitute {var} placeholders in string leaves of `template`
    using values from `payload`. Missing keys render as empty string and emit
    a warning (we prefer "best effort" over hard failure here so a stale rule
    doesn't crash the orchestrator)."""
    if isinstance(template, str):
        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in payload:
                logger.warning("Rule template references unknown var '{%s}'", key)
                return ""
            val = payload[key]
            if isinstance(val, (list, dict)):
                return json.dumps(val)
            return str(val)
        return _TEMPLATE_RE.sub(repl, template)
    if isinstance(template, list):
        return [render_args(item, payload) for item in template]
    if isinstance(template, dict):
        return {k: render_args(v, payload) for k, v in template.items()}
    return template


def parsed_rule_to_dict(rule: ParsedRule) -> dict[str, Any]:
    return asdict(rule)
