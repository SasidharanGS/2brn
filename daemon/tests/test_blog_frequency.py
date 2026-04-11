import json
import pytest
from brn_daemon.config import BlogScheduleConfig, Config, load_config, save_config


def test_blog_schedule_config_defaults():
    s = BlogScheduleConfig()
    assert s.frequency == "daily"
    assert s.hour == 21
    assert s.minute == 0
    assert s.day == 1
    assert s.days_of_week == []


def test_config_has_blog_schedule_field():
    cfg = Config()
    assert isinstance(cfg.blog_schedule, BlogScheduleConfig)
    assert cfg.blog_schedule.frequency == "daily"


def test_blog_schedule_config_invalid_frequency():
    with pytest.raises(ValueError, match="frequency"):
        BlogScheduleConfig(frequency="hourly")


def test_blog_schedule_config_invalid_hour():
    with pytest.raises(ValueError, match="hour"):
        BlogScheduleConfig(hour=25)


def test_blog_schedule_config_invalid_minute():
    with pytest.raises(ValueError, match="minute"):
        BlogScheduleConfig(minute=60)


def test_blog_schedule_config_invalid_day():
    with pytest.raises(ValueError, match="day"):
        BlogScheduleConfig(frequency="monthly", day=29)


def test_blog_schedule_config_invalid_days_of_week():
    with pytest.raises(ValueError, match="days_of_week"):
        BlogScheduleConfig(frequency="weekly", days_of_week=["mon", "xyz"])


def test_load_config_roundtrip_daily(tmp_path, monkeypatch):
    monkeypatch.setenv("BRN_HOME", str(tmp_path))
    cfg = Config()
    cfg.blog_schedule = BlogScheduleConfig(frequency="daily", hour=9, minute=30)
    save_config(cfg)
    loaded = load_config()
    assert loaded.blog_schedule.frequency == "daily"
    assert loaded.blog_schedule.hour == 9
    assert loaded.blog_schedule.minute == 30


def test_load_config_roundtrip_monthly(tmp_path, monkeypatch):
    monkeypatch.setenv("BRN_HOME", str(tmp_path))
    cfg = Config()
    cfg.blog_schedule = BlogScheduleConfig(frequency="monthly", day=15, hour=10, minute=0)
    save_config(cfg)
    loaded = load_config()
    assert loaded.blog_schedule.frequency == "monthly"
    assert loaded.blog_schedule.day == 15


def test_load_config_roundtrip_weekly(tmp_path, monkeypatch):
    monkeypatch.setenv("BRN_HOME", str(tmp_path))
    cfg = Config()
    cfg.blog_schedule = BlogScheduleConfig(frequency="weekly", days_of_week=["mon", "fri"], hour=8, minute=0)
    save_config(cfg)
    loaded = load_config()
    assert loaded.blog_schedule.frequency == "weekly"
    assert loaded.blog_schedule.days_of_week == ["mon", "fri"]


def test_load_config_missing_blog_schedule_uses_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("BRN_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps({"capture_interval_seconds": 60}))
    loaded = load_config()
    assert loaded.blog_schedule.frequency == "daily"
    assert loaded.blog_schedule.hour == 21


def test_load_config_legacy_blog_schedule_no_frequency(tmp_path, monkeypatch):
    """Old config.json with only {hour, minute} under blog_schedule must migrate to daily."""
    monkeypatch.setenv("BRN_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps({"blog_schedule": {"hour": 22, "minute": 15}}))
    loaded = load_config()
    assert loaded.blog_schedule.frequency == "daily"
    assert loaded.blog_schedule.hour == 22
    assert loaded.blog_schedule.minute == 15
