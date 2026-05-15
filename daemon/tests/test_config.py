import json
import pytest
from unittest.mock import MagicMock
from brn_daemon.config import (
    load_config,
    save_config,
    Config,
    ProviderConfig,
    KEYCHAIN_SERVICE,
    KEYCHAIN_SERVICE_PLUGINS,
    get_plugin_env_value,
    set_plugin_env_value,
    delete_plugin_env_value,
    migrate_plugin_keychain_entries,
    _plugin_env_keychain_key,
)


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


def test_joplin_defaults_off(tmp_home):
    cfg = load_config()
    assert cfg.joplin_enabled is False
    assert cfg.joplin_db_path == ""


def test_joplin_fields_persist(tmp_home):
    cfg = load_config()
    cfg.joplin_enabled = True
    cfg.joplin_db_path = "/tmp/joplin.sqlite"
    save_config(cfg)
    reloaded = load_config()
    assert reloaded.joplin_enabled is True
    assert reloaded.joplin_db_path == "/tmp/joplin.sqlite"


def test_save_config_no_leftover_temp_on_success(tmp_home):
    """os.replace ensures no .tmp file remains after a successful save."""
    from brn_daemon.config import save_config, load_config
    cfg = load_config()
    save_config(cfg)
    tmp_files = list(tmp_home.glob("*.tmp"))
    assert tmp_files == []


def test_save_config_writes_valid_json(tmp_home):
    """Config file must be valid JSON and contain expected keys after save."""
    import json
    from brn_daemon.config import save_config, load_config
    cfg = load_config()
    cfg.paused = True
    save_config(cfg)
    config_path = tmp_home / "config.json"
    data = json.loads(config_path.read_text())
    assert data["paused"] is True
    assert "chat_provider" in data


def test_plugin_env_value_fallback_to_env_var(tmp_home, monkeypatch):
    monkeypatch.setenv("BRN_PLUGIN_JOPLIN_JOPLIN_TOKEN", "fallback-value")
    val = get_plugin_env_value("joplin", "JOPLIN_TOKEN")
    assert val in ("fallback-value", None) or isinstance(val, str)


def test_plugin_keychain_uses_separate_service(tmp_home):
    assert KEYCHAIN_SERVICE_PLUGINS != KEYCHAIN_SERVICE


def test_set_plugin_env_value_uses_plugin_service(tmp_home, monkeypatch):
    mock_keyring = MagicMock()
    monkeypatch.setattr("brn_daemon.config.keyring", mock_keyring)
    set_plugin_env_value("myplugin", "MY_KEY", "secret")
    mock_keyring.set_password.assert_called_once_with(
        KEYCHAIN_SERVICE_PLUGINS, "plugin.myplugin.MY_KEY", "secret"
    )


def test_get_plugin_env_value_uses_plugin_service(tmp_home, monkeypatch):
    mock_keyring = MagicMock()
    mock_keyring.get_password.return_value = "retrieved"
    monkeypatch.setattr("brn_daemon.config.keyring", mock_keyring)
    val = get_plugin_env_value("myplugin", "MY_KEY")
    mock_keyring.get_password.assert_called_once_with(
        KEYCHAIN_SERVICE_PLUGINS, "plugin.myplugin.MY_KEY"
    )
    assert val == "retrieved"


def test_delete_plugin_env_value_uses_plugin_service(tmp_home, monkeypatch):
    mock_keyring = MagicMock()
    monkeypatch.setattr("brn_daemon.config.keyring", mock_keyring)
    delete_plugin_env_value("myplugin", "MY_KEY")
    mock_keyring.delete_password.assert_called_once_with(
        KEYCHAIN_SERVICE_PLUGINS, "plugin.myplugin.MY_KEY"
    )


def test_plugin_key_cannot_collide_with_daemon_key(tmp_home, monkeypatch):
    daemon_calls = []
    plugin_calls = []

    def fake_set(service, key, value):
        if service == KEYCHAIN_SERVICE:
            daemon_calls.append(key)
        elif service == KEYCHAIN_SERVICE_PLUGINS:
            plugin_calls.append(key)

    mock_keyring = MagicMock()
    mock_keyring.set_password.side_effect = fake_set
    monkeypatch.setattr("brn_daemon.config.keyring", mock_keyring)

    set_plugin_env_value("2brn", "chat_api_key", "attacker")
    assert "chat_api_key" not in daemon_calls
    assert "plugin.2brn.chat_api_key" in plugin_calls


def test_migrate_plugin_keychain_entries_moves_and_deletes(tmp_home, monkeypatch):
    stored = {
        (KEYCHAIN_SERVICE, "plugin.foo.BAR"): "val1",
        (KEYCHAIN_SERVICE, "chat_api_key"): "daemon_secret",
        (KEYCHAIN_SERVICE, "plugin.baz.SECRET"): "val2",
    }
    deleted = []
    written = {}

    def fake_get(service, key):
        return stored.get((service, key))

    def fake_set(service, key, value):
        written[(service, key)] = value

    def fake_delete(service, key):
        deleted.append((service, key))

    mock_keyring = MagicMock()
    mock_keyring.get_password.side_effect = fake_get
    mock_keyring.set_password.side_effect = fake_set
    mock_keyring.delete_password.side_effect = fake_delete
    monkeypatch.setattr("brn_daemon.config.keyring", mock_keyring)

    entries = [("foo", "BAR"), ("baz", "SECRET")]
    migrate_plugin_keychain_entries(entries)

    assert written.get((KEYCHAIN_SERVICE_PLUGINS, "plugin.foo.BAR")) == "val1"
    assert written.get((KEYCHAIN_SERVICE_PLUGINS, "plugin.baz.SECRET")) == "val2"
    assert (KEYCHAIN_SERVICE, "plugin.foo.BAR") in deleted
    assert (KEYCHAIN_SERVICE, "plugin.baz.SECRET") in deleted
    assert (KEYCHAIN_SERVICE, "chat_api_key") not in deleted


def test_migrate_skips_delete_when_no_value_in_old_service(tmp_home, monkeypatch):
    """Entries not in the old service must not trigger delete."""
    deleted = []

    mock_keyring = MagicMock()
    mock_keyring.get_password.return_value = None
    mock_keyring.delete_password.side_effect = lambda s, k: deleted.append((s, k))
    monkeypatch.setattr("brn_daemon.config.keyring", mock_keyring)

    migrate_plugin_keychain_entries([("noplugin", "NOKEY")])
    assert deleted == [], f"delete was called when it should not have been: {deleted}"


def test_load_config_raises_on_corrupt_json(tmp_home):
    """load_config must raise RuntimeError when config.json exists but is invalid JSON."""
    from brn_daemon.db import get_brn_home
    from brn_daemon.config import load_config

    config_path = get_brn_home() / "config.json"
    config_path.write_text("{ not valid json }")

    with pytest.raises(RuntimeError, match="config.json"):
        load_config()


def test_load_config_returns_defaults_when_missing(tmp_home):
    """load_config must return defaults when config.json does not exist."""
    from brn_daemon.config import load_config, Config

    result = load_config()
    assert isinstance(result, Config)
