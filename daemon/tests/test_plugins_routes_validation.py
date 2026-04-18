import pytest
from pydantic import ValidationError
from brn_daemon.routes.plugins_routes import PluginCreate, PluginUpdate


def test_plugin_name_rejects_dots():
    with pytest.raises(ValidationError):
        PluginCreate(name="bad.name", command="node", args=[], env={})


def test_plugin_name_rejects_slash():
    with pytest.raises(ValidationError):
        PluginCreate(name="bad/name", command="node", args=[], env={})


def test_plugin_name_accepts_valid():
    p = PluginCreate(name="my-plugin_01", command="node", args=[], env={})
    assert p.name == "my-plugin_01"


def test_plugin_env_key_rejects_dots():
    with pytest.raises(ValidationError):
        PluginCreate(name="ok", command="node", args=[], env={"bad.key": "val"})


def test_plugin_env_key_rejects_equals():
    with pytest.raises(ValidationError):
        PluginCreate(name="ok", command="node", args=[], env={"bad=key": "val"})


def test_plugin_env_key_accepts_valid():
    p = PluginCreate(name="ok", command="node", args=[], env={"MY_SECRET_KEY": "val"})
    assert "MY_SECRET_KEY" in p.env


def test_plugin_update_env_key_rejects_dots():
    with pytest.raises(ValidationError):
        PluginUpdate(env={"bad.key": "val"})


def test_plugin_update_env_key_accepts_valid():
    p = PluginUpdate(env={"VALID_KEY": "val"})
    assert p.env["VALID_KEY"] == "val"


def test_plugin_update_env_none_is_allowed():
    p = PluginUpdate(env=None)
    assert p.env is None
