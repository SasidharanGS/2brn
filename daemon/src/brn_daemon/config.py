import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from brn_daemon.db import get_brn_home

logger = logging.getLogger(__name__)

KEYCHAIN_SERVICE = "2brn"
KEYCHAIN_USERNAME = "jll_gateway_token"
KEYCHAIN_CHAT_KEY = "chat_api_key"
KEYCHAIN_EMBED_KEY = "embed_api_key"


@dataclass
class ProviderConfig:
    type: str = "openai_compatible"
    base_url: str = ""
    model: str = ""
    extra_headers: dict = field(default_factory=dict)


@dataclass
class Config:
    chat_provider: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        type="openai_compatible",
        base_url="http://localhost:8889/v1",
        model="GPT_5_2",
    ))
    embed_provider: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        type="jll",
        base_url="http://localhost:8889",
        model="TEXT_EMBEDDING_3_LARGE",
    ))
    capture_interval_seconds: int = 60
    purge_months: int = 6
    paused: bool = False
    excluded_apps: list[str] = field(default_factory=list)
    blog_mirror_enabled: bool = True
    joplin_token: str = ""


def _config_path() -> Path:
    return get_brn_home() / "config.json"


def _parse_provider(data: dict) -> ProviderConfig:
    return ProviderConfig(
        type=data.get("type", "openai_compatible"),
        base_url=data.get("base_url", ""),
        model=data.get("model", ""),
        extra_headers=data.get("extra_headers", {}),
    )


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
            purge_months=data.get("purge_months", 6),
            paused=data.get("paused", False),
            excluded_apps=data.get("excluded_apps", []),
            blog_mirror_enabled=data.get("blog_mirror_enabled", True),
            joplin_token=data.get("joplin_token", ""),
        )
    except (json.JSONDecodeError, KeyError):
        logger.warning("Corrupt config.json — using defaults")
        return Config()


def save_config(cfg: Config) -> None:
    get_brn_home().mkdir(parents=True, exist_ok=True)

    def _provider_dict(p: ProviderConfig) -> dict:
        d = {"type": p.type, "base_url": p.base_url, "model": p.model}
        if p.extra_headers:
            d["extra_headers"] = p.extra_headers
        return d

    data = {
        "chat_provider": _provider_dict(cfg.chat_provider),
        "embed_provider": _provider_dict(cfg.embed_provider),
        "capture_interval_seconds": cfg.capture_interval_seconds,
        "purge_months": cfg.purge_months,
        "paused": cfg.paused,
        "excluded_apps": cfg.excluded_apps,
        "blog_mirror_enabled": cfg.blog_mirror_enabled,
        "joplin_token": cfg.joplin_token,
    }
    _config_path().write_text(json.dumps(data, indent=2))


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


def get_gateway_token() -> str | None:
    try:
        import keyring
        return keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_USERNAME)
    except Exception:
        return os.environ.get("BRN_GATEWAY_TOKEN")


def set_gateway_token(token: str) -> None:
    try:
        import keyring
        keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_USERNAME, token)
    except Exception as exc:
        logger.warning("Failed to save gateway token to keychain: %s", exc)
        raise RuntimeError(f"Could not save token to keychain: {exc}") from exc
