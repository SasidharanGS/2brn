import json
import pytest
from brn_daemon.config import load_config, save_config, Config, ProviderConfig


def test_load_config_returns_defaults_when_no_file(tmp_home):
    cfg = load_config()
    assert cfg.chat_provider.base_url == ""
    assert cfg.chat_provider.model == ""
    assert cfg.chat_provider.type == "openai_compatible"
    assert cfg.embed_provider.base_url == ""
    assert cfg.embed_provider.model == ""
    assert cfg.embed_provider.type == "custom"
    assert cfg.capture_interval_seconds == 60
    assert cfg.purge_months == 12
    assert cfg.paused is False


def test_save_and_reload_config(tmp_home):
    cfg = load_config()
    cfg.paused = True
    cfg.chat_provider.model = "gpt-4o"
    save_config(cfg)
    reloaded = load_config()
    assert reloaded.paused is True
    assert reloaded.chat_provider.model == "gpt-4o"


def test_config_file_written_as_json(tmp_home):
    cfg = load_config()
    save_config(cfg)
    config_path = tmp_home / "config.json"
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert "chat_provider" in data
    assert "embed_provider" in data
    assert "gateway_url" not in data
    assert "llm_model" not in data
    assert "embed_model" not in data


def test_config_blog_defaults(tmp_home):
    cfg = load_config()
    assert cfg.blog_mirror_enabled is True


def test_config_blog_fields_persist(tmp_home):
    cfg = load_config()
    cfg.blog_mirror_enabled = False
    save_config(cfg)
    loaded = load_config()
    assert loaded.blog_mirror_enabled is False


def test_provider_config_extra_headers(tmp_home):
    cfg = load_config()
    cfg.chat_provider.extra_headers = {"api-key": "abc123"}
    save_config(cfg)
    reloaded = load_config()
    assert reloaded.chat_provider.extra_headers == {"api-key": "abc123"}


def test_excluded_apps_persist(tmp_home):
    cfg = load_config()
    cfg.excluded_apps = ["1Password", "banking_app"]
    save_config(cfg)
    reloaded = load_config()
    assert reloaded.excluded_apps == ["1Password", "banking_app"]
