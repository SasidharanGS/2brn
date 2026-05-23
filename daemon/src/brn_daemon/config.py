import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from brn_daemon.db import get_brn_home

logger = logging.getLogger(__name__)

KEYCHAIN_SERVICE = "2brn"
KEYCHAIN_USERNAME = "jll_gateway_token"


@dataclass
class Config:
    gateway_url: str = "http://localhost:8889"
    llm_model: str = "CLAUDE_4_6_SONNET"
    embed_model: str = "TEXT_EMBEDDING_3_LARGE"
    capture_interval_seconds: int = 60
    purge_months: int = 6
    paused: bool = False
    excluded_apps: list[str] = field(default_factory=list)
    blog_mirror_enabled: bool = True
    joplin_token: str = ""


DEFAULT_CONFIG = Config()


def _config_path() -> Path:
    return get_brn_home() / "config.json"


def load_config() -> Config:
    env_llm = os.environ.get("BRN_LLM_MODEL", "GPT_5_2")
    env_embed = os.environ.get("BRN_EMBED_MODEL", "TEXT_EMBEDDING_3_LARGE")
    env_joplin = os.environ.get("JOPLIN_TOKEN", "")

    path = _config_path()
    if not path.exists():
        return Config(llm_model=env_llm, embed_model=env_embed, joplin_token=env_joplin)
    try:
        data = json.loads(path.read_text())
        return Config(
            gateway_url=data.get("gateway_url", DEFAULT_CONFIG.gateway_url),
            llm_model=data.get("llm_model", env_llm),
            embed_model=data.get("embed_model", env_embed),
            capture_interval_seconds=data.get(
                "capture_interval_seconds", DEFAULT_CONFIG.capture_interval_seconds
            ),
            purge_months=data.get("purge_months", DEFAULT_CONFIG.purge_months),
            paused=data.get("paused", DEFAULT_CONFIG.paused),
            excluded_apps=data.get("excluded_apps", []),
            blog_mirror_enabled=data.get("blog_mirror_enabled", DEFAULT_CONFIG.blog_mirror_enabled),
            joplin_token=data.get("joplin_token", env_joplin),
        )
    except (json.JSONDecodeError, KeyError):
        return Config(llm_model=env_llm, embed_model=env_embed, joplin_token=env_joplin)


def save_config(cfg: Config) -> None:
    get_brn_home().mkdir(parents=True, exist_ok=True)
    data = {
        "gateway_url": cfg.gateway_url,
        "llm_model": cfg.llm_model,
        "embed_model": cfg.embed_model,
        "capture_interval_seconds": cfg.capture_interval_seconds,
        "purge_months": cfg.purge_months,
        "paused": cfg.paused,
        "blog_mirror_enabled": cfg.blog_mirror_enabled,
        "joplin_token": cfg.joplin_token,
    }
    _config_path().write_text(json.dumps(data, indent=2))


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
