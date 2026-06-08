import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from brn_daemon.db import get_brn_home

try:
    import keyring
except ImportError:
    keyring = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

KEYCHAIN_SERVICE = "2brn"
KEYCHAIN_SERVICE_PLUGINS = "2brn-plugins"
KEYCHAIN_USERNAME = "gateway_token"
KEYCHAIN_CHAT_KEY = "chat_api_key"
KEYCHAIN_EMBED_KEY = "embed_api_key"
KEYCHAIN_SCREENSHOT_PASSWORD = "screenshot_password"


@dataclass
class ProviderConfig:
    type: str = "openai_compatible"
    base_url: str = ""
    model: str = ""
    extra_headers: dict = field(default_factory=dict)


@dataclass
class ScheduleConfig:
    hour: int = 21
    minute: int = 0

    def __post_init__(self):
        if not (0 <= self.hour <= 23):
            raise ValueError(f"hour must be 0-23, got {self.hour}")
        if not (0 <= self.minute <= 59):
            raise ValueError(f"minute must be 0-59, got {self.minute}")


VALID_DAYS_OF_WEEK = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


@dataclass
class BlogScheduleConfig:
    frequency: str = "daily"
    hour: int = 21
    minute: int = 0
    day: int = 1
    days_of_week: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.frequency not in ("daily", "monthly", "weekly"):
            raise ValueError(f"frequency must be daily|monthly|weekly, got {self.frequency!r}")
        if not (0 <= self.hour <= 23):
            raise ValueError(f"hour must be 0-23, got {self.hour}")
        if not (0 <= self.minute <= 59):
            raise ValueError(f"minute must be 0-59, got {self.minute}")
        if not (1 <= self.day <= 28):
            raise ValueError(f"day must be 1-28, got {self.day}")
        invalid = set(self.days_of_week) - VALID_DAYS_OF_WEEK
        if invalid:
            raise ValueError(f"days_of_week contains invalid values: {invalid}")


@dataclass
class Config:
    chat_provider: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        type="openai_compatible",
        base_url="",
        model="",
    ))
    embed_provider: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        type="custom",
        base_url="",
        model="",
    ))
    capture_interval_seconds: int = 60
    purge_months: int = 12
    paused: bool = False
    # Opt-in LAN access for the mobile companion. When True the daemon binds
    # 0.0.0.0 instead of loopback so a paired phone on the same network can reach
    # it — still gated by the per-machine bearer token. OFF by default; the bind
    # change takes effect on the next daemon restart.
    lan_access: bool = False
    excluded_apps: list[str] = field(default_factory=list)
    # Optional internal Joplin note-embedding watcher (off by default for OSS users).
    # When True, JoplinWatcher polls joplin_db_path and embeds notes into note_memories.
    joplin_enabled: bool = False
    joplin_db_path: str = ""
    journal_schedule: ScheduleConfig = field(default_factory=lambda: ScheduleConfig(hour=21, minute=0))
    blog_schedule: BlogScheduleConfig = field(default_factory=BlogScheduleConfig)


def _config_path() -> Path:
    return get_brn_home() / "config.json"


def _parse_provider(data: dict) -> ProviderConfig:
    return ProviderConfig(
        type=data.get("type", "openai_compatible"),
        base_url=data.get("base_url", ""),
        model=data.get("model", ""),
        extra_headers=data.get("extra_headers", {}),
    )


def _parse_schedule(data: dict) -> ScheduleConfig:
    kwargs = {k: v for k, v in data.items() if k in ("hour", "minute")}
    return ScheduleConfig(**kwargs)


def _parse_blog_schedule(data: dict) -> BlogScheduleConfig:
    kwargs = {k: v for k, v in data.items()
              if k in ("frequency", "hour", "minute", "day", "days_of_week")}
    if "frequency" not in kwargs:
        kwargs["frequency"] = "daily"
    return BlogScheduleConfig(**kwargs)


def load_config() -> Config:
    path = _config_path()
    if not path.exists():
        return Config()
    try:
        data = json.loads(path.read_text())
        return Config(
            chat_provider=_parse_provider(data.get("chat_provider", {})),
            embed_provider=_parse_provider(data.get("embed_provider", {})),
            capture_interval_seconds=data.get("capture_interval_seconds", 60),
            purge_months=data.get("purge_months", 12),
            paused=data.get("paused", False),
            lan_access=data.get("lan_access", False),
            excluded_apps=data.get("excluded_apps", []),
            joplin_enabled=data.get("joplin_enabled", False),
            joplin_db_path=data.get("joplin_db_path", ""),
            journal_schedule=_parse_schedule(data.get("journal_schedule", {})),
            blog_schedule=_parse_blog_schedule(data.get("blog_schedule", {})),
        )
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise RuntimeError(
            f"config.json at {path} is corrupt and cannot be parsed: {exc}"
        ) from exc


def save_config(cfg: Config) -> None:
    def _provider_dict(p: ProviderConfig) -> dict:
        d: dict = {"type": p.type, "base_url": p.base_url, "model": p.model}
        if p.extra_headers:
            d["extra_headers"] = p.extra_headers
        return d

    data = {
        "chat_provider": _provider_dict(cfg.chat_provider),
        "embed_provider": _provider_dict(cfg.embed_provider),
        "capture_interval_seconds": cfg.capture_interval_seconds,
        "purge_months": cfg.purge_months,
        "paused": cfg.paused,
        "lan_access": cfg.lan_access,
        "excluded_apps": cfg.excluded_apps,
        "joplin_enabled": cfg.joplin_enabled,
        "joplin_db_path": cfg.joplin_db_path,
        "journal_schedule": {"hour": cfg.journal_schedule.hour, "minute": cfg.journal_schedule.minute},
        "blog_schedule": {
            "frequency": cfg.blog_schedule.frequency,
            "hour": cfg.blog_schedule.hour,
            "minute": cfg.blog_schedule.minute,
            "day": cfg.blog_schedule.day,
            "days_of_week": cfg.blog_schedule.days_of_week,
        },
    }
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, suffix=".tmp", delete=False, encoding="utf-8"
    ) as f:
        json.dump(data, f, indent=2)
        tmp_path = f.name
    os.replace(tmp_path, path)


# NOTE: All keychain operations use bare `except Exception` because the keyring
# library's backends (macOS Keychain, Secret Service, fallback) can raise any
# exception type depending on the OS and backend version. Narrowing the type
# here would be brittle across platforms.
def get_api_key(keychain_key: str, env_fallback: str) -> str | None:
    try:
        import keyring
        val = keyring.get_password(KEYCHAIN_SERVICE, keychain_key)
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(env_fallback)


def get_chat_api_key() -> str | None:
    return get_api_key(KEYCHAIN_CHAT_KEY, "BRN_CHAT_API_KEY")


def get_embed_api_key() -> str | None:
    return get_api_key(KEYCHAIN_EMBED_KEY, "BRN_EMBED_API_KEY")


def set_chat_api_key(token: str) -> None:
    try:
        import keyring
        keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_CHAT_KEY, token)
    except Exception as exc:
        raise RuntimeError(f"Could not save chat API key to keychain: {exc}") from exc


def set_embed_api_key(token: str) -> None:
    try:
        import keyring
        keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_EMBED_KEY, token)
    except Exception as exc:
        raise RuntimeError(f"Could not save embed API key to keychain: {exc}") from exc


def get_screenshot_password() -> str | None:
    """Return the screenshot password from the OS keychain (or BRN_SCREENSHOT_PASSWORD env var)."""
    return get_api_key(KEYCHAIN_SCREENSHOT_PASSWORD, "BRN_SCREENSHOT_PASSWORD")


def set_screenshot_password(password: str) -> None:
    try:
        import keyring
        keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_SCREENSHOT_PASSWORD, password)
    except Exception as exc:
        raise RuntimeError(f"Could not save screenshot password to keychain: {exc}") from exc


def delete_screenshot_password() -> None:
    try:
        import keyring
        keyring.delete_password(KEYCHAIN_SERVICE, KEYCHAIN_SCREENSHOT_PASSWORD)
    except Exception:
        # already gone — fine
        pass


def get_gateway_token() -> str | None:
    try:
        import keyring
        val = keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_USERNAME)
        if val:
            return val
    except Exception:
        pass
    return os.environ.get("BRN_GATEWAY_TOKEN")


def set_gateway_token(token: str) -> None:
    try:
        import keyring
        keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_USERNAME, token)
    except Exception as exc:
        logger.exception("Failed to save gateway token to keychain")
        raise RuntimeError(f"Could not save token to keychain: {exc}") from exc


def _plugin_env_keychain_key(plugin_name: str, env_key: str) -> str:
    """Keychain entry name for a plugin's env var value."""
    return f"plugin.{plugin_name}.{env_key}"


def get_plugin_env_value(plugin_name: str, env_key: str) -> str | None:
    """Resolve a plugin env var value: keychain first, then BRN_PLUGIN_<name>_<key> env var."""
    if keyring is not None:
        try:
            val = keyring.get_password(KEYCHAIN_SERVICE_PLUGINS, _plugin_env_keychain_key(plugin_name, env_key))
            if val:
                return val
        except Exception:
            pass
    env_fallback = f"BRN_PLUGIN_{plugin_name.upper()}_{env_key.upper()}"
    return os.environ.get(env_fallback)


def set_plugin_env_value(plugin_name: str, env_key: str, value: str) -> None:
    if keyring is None:
        raise RuntimeError("keyring package not available")
    try:
        keyring.set_password(
            KEYCHAIN_SERVICE_PLUGINS,
            _plugin_env_keychain_key(plugin_name, env_key),
            value,
        )
    except Exception as exc:
        raise RuntimeError(f"Could not save plugin env value to keychain: {exc}") from exc


def delete_plugin_env_value(plugin_name: str, env_key: str) -> None:
    if keyring is None:
        return
    try:
        keyring.delete_password(
            KEYCHAIN_SERVICE_PLUGINS,
            _plugin_env_keychain_key(plugin_name, env_key),
        )
    except Exception:
        # already gone — fine
        pass


def migrate_plugin_keychain_entries(entries: list[tuple[str, str]]) -> None:
    """One-time migration: move plugin secrets from 2brn service to 2brn-plugins.

    Safe to call multiple times (idempotent).
    """
    if keyring is None:
        return
    for plugin_name, env_key in entries:
        old_key = _plugin_env_keychain_key(plugin_name, env_key)
        try:
            value = keyring.get_password(KEYCHAIN_SERVICE, old_key)
            if value:
                keyring.set_password(KEYCHAIN_SERVICE_PLUGINS, old_key, value)
                keyring.delete_password(KEYCHAIN_SERVICE, old_key)
        except Exception:
            pass
