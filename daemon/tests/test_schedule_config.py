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


import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock
from brn_daemon.main import _journal_job, _blog_job, _startup_backfill_journal, _startup_backfill_blog


async def test_journal_job_calls_generate_and_emits_event(tmp_path, monkeypatch):
    monkeypatch.setenv("BRN_HOME", str(tmp_path))
    from brn_daemon.db import init_db
    await init_db()

    journal_gen = MagicMock()
    journal_gen.generate = AsyncMock(return_value="Today I worked on X")
    event_bus = MagicMock()
    event_bus.emit = AsyncMock()

    await _journal_job(journal_gen, event_bus)
    journal_gen.generate.assert_called_once_with(target_date=date.today())
    event_bus.emit.assert_called_once()


async def test_blog_job_calls_generate(tmp_path, monkeypatch):
    monkeypatch.setenv("BRN_HOME", str(tmp_path))
    from brn_daemon.db import init_db
    await init_db()

    blog_gen = MagicMock()
    blog_gen.generate = AsyncMock(return_value="Blog post content")
    event_bus = MagicMock()
    event_bus.emit = AsyncMock()

    await _blog_job(blog_gen, event_bus)
    blog_gen.generate.assert_called_once_with(target_date=date.today())
    event_bus.emit.assert_called_once()


async def test_blog_job_does_not_emit_when_no_content(tmp_path, monkeypatch):
    monkeypatch.setenv("BRN_HOME", str(tmp_path))
    from brn_daemon.db import init_db
    await init_db()

    blog_gen = MagicMock()
    blog_gen.generate = AsyncMock(return_value=None)
    event_bus = MagicMock()
    event_bus.emit = AsyncMock()

    await _blog_job(blog_gen, event_bus)
    blog_gen.generate.assert_called_once()
    event_bus.emit.assert_not_called()


async def test_startup_backfill_journal_skips_if_not_past_schedule(tmp_path, monkeypatch):
    monkeypatch.setenv("BRN_HOME", str(tmp_path))
    from brn_daemon.db import init_db
    await init_db()

    journal_gen = MagicMock()
    journal_gen.generate = AsyncMock(return_value=None)
    event_bus = MagicMock()
    event_bus.emit = AsyncMock()

    schedule = ScheduleConfig(hour=23, minute=59)
    await _startup_backfill_journal(journal_gen, event_bus, schedule)
    journal_gen.generate.assert_not_called()
