import json
import pytest
from brn_daemon.config import load_config, save_config, Config, DEFAULT_CONFIG

def test_load_config_returns_defaults_when_no_file(tmp_home):
    cfg = load_config()
    assert cfg.gateway_url == "http://localhost:8889"
    assert cfg.capture_interval_seconds == 60
    assert cfg.purge_months == 6
    assert cfg.paused is False

def test_save_and_reload_config(tmp_home):
    cfg = load_config()
    cfg.paused = True
    save_config(cfg)
    reloaded = load_config()
    assert reloaded.paused is True

def test_config_file_written_as_json(tmp_home):
    cfg = load_config()
    save_config(cfg)
    config_path = tmp_home / "config.json"
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert "gateway_url" in data
    assert "gateway_token" not in data  # token stored in keychain, not file

def test_config_blog_defaults(tmp_home):
    from brn_daemon.config import load_config
    cfg = load_config()
    assert cfg.blog_mirror_enabled is True


def test_config_blog_fields_persist(tmp_home):
    from brn_daemon.config import load_config, save_config
    cfg = load_config()
    cfg.blog_mirror_enabled = False
    save_config(cfg)
    loaded = load_config()
    assert loaded.blog_mirror_enabled is False
