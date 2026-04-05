import json
import pytest
from brn_daemon.config import Config, ScheduleConfig, load_config, save_config


def test_schedule_config_defaults():
    s = ScheduleConfig()
    assert s.hour == 21
    assert s.minute == 0


def test_config_has_schedule_fields():
    cfg = Config()
    assert cfg.journal_schedule.hour == 21
    assert cfg.journal_schedule.minute == 0
    assert cfg.blog_schedule.hour == 21
    assert cfg.blog_schedule.minute == 0


def test_load_config_roundtrip_schedules(tmp_path, monkeypatch):
    monkeypatch.setenv("BRN_HOME", str(tmp_path))
    cfg = Config()
    cfg.journal_schedule = ScheduleConfig(hour=8, minute=30)
    cfg.blog_schedule = ScheduleConfig(hour=23, minute=15)
    save_config(cfg)

    loaded = load_config()
    assert loaded.journal_schedule.hour == 8
    assert loaded.journal_schedule.minute == 30
    assert loaded.blog_schedule.hour == 23
    assert loaded.blog_schedule.minute == 15


def test_load_config_missing_schedule_uses_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("BRN_HOME", str(tmp_path))
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"capture_interval_seconds": 60}))

    loaded = load_config()
    assert loaded.journal_schedule.hour == 21
    assert loaded.journal_schedule.minute == 0
    assert loaded.blog_schedule.hour == 21
    assert loaded.blog_schedule.minute == 0


def test_schedule_config_validates_hour_range(tmp_path, monkeypatch):
    monkeypatch.setenv("BRN_HOME", str(tmp_path))
    with pytest.raises(ValueError, match="hour"):
        ScheduleConfig(hour=25, minute=0)


def test_schedule_config_validates_minute_range(tmp_path, monkeypatch):
    monkeypatch.setenv("BRN_HOME", str(tmp_path))
    with pytest.raises(ValueError, match="minute"):
        ScheduleConfig(hour=21, minute=60)
