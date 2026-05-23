import pytest
import asyncio
import aiosqlite
import json
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import date
from brn_daemon.db import init_db, get_db_path
from brn_daemon.journal import (
    build_journal_prompt,
    JournalGenerator,
    JournalMirror,
    ResumeUpdater,
    _date_to_note_title,
    JOPLIN_JOURNAL_NOTEBOOK_ID,
    JOPLIN_MEMORIES_NOTEBOOK_ID,
    RESUME_NOTE_TITLES,
)


# ── build_journal_prompt ───────────────────────────────────────────────────────

def test_build_journal_prompt_includes_summaries():
    summaries = ["Worked on Python code", "Reviewed emails", "Team standup meeting"]
    prompt = build_journal_prompt("2026-04-12", summaries)
    assert "2026-04-12" in prompt
    assert "Python code" in prompt
    assert "emails" in prompt
    assert "standup" in prompt


def test_build_journal_prompt_empty_day():
    prompt = build_journal_prompt("2026-04-12", [])
    assert "2026-04-12" in prompt
    assert "no recorded" in prompt.lower() or "no activities" in prompt.lower() or "unrecorded" in prompt.lower()


# ── _date_to_note_title ────────────────────────────────────────────────────────

def test_date_to_note_title_format():
    d = date(2026, 4, 26)
    assert _date_to_note_title(d) == "26-04-26"


def test_date_to_note_title_zero_pads():
    d = date(2026, 1, 5)
    assert _date_to_note_title(d) == "05-01-26"


# ── JournalGenerator ──────────────────────────────────────────────────────────

async def test_generate_saves_to_db(tmp_home):
    await init_db()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO captures (captured_at, trigger) VALUES ('2026-04-12T10:00:00', 'heartbeat')"
        )
        await conn.commit()
        cur = await conn.execute("SELECT last_insert_rowid()")
        cap_id = (await cur.fetchone())[0]
        await conn.execute(
            "INSERT INTO activities (capture_id, started_at, summary, tags, task_category, "
            "task_category_confidence, productivity_state, productivity_confidence) "
            "VALUES (?, '2026-04-12T10:00:00', 'Worked on Python', '[]', 'work', 0.9, 'focused', 0.85)",
            (cap_id,)
        )
        await conn.commit()

    mock_gateway = MagicMock()
    mock_gateway.chat_complete = AsyncMock(return_value="Today I wrote Python code and focused deeply.")

    gen = JournalGenerator(gateway=mock_gateway)
    await gen.generate(target_date=date(2026, 4, 12))

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT content, edited_by_user FROM journals WHERE date = '2026-04-12'")
        row = await cur.fetchone()
    assert row is not None
    assert "Python" in row[0]
    assert row[1] == 0


async def test_generate_skips_if_user_edited(tmp_home):
    await init_db()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO journals (date, content, edited_by_user) VALUES ('2026-04-12', 'My edit', 1)"
        )
        await conn.commit()

    mock_gateway = MagicMock()
    mock_gateway.chat_complete = AsyncMock(return_value="New content")
    gen = JournalGenerator(gateway=mock_gateway)
    await gen.generate(target_date=date(2026, 4, 12))

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT content FROM journals WHERE date = '2026-04-12'")
        row = await cur.fetchone()
    assert row[0] == "My edit"
    mock_gateway.chat_complete.assert_not_called()


# ── JournalMirror ─────────────────────────────────────────────────────────────

def _make_mirror():
    return JournalMirror(token="test-token", port=41184)


def test_journal_mirror_uses_journal_notebook_id():
    mirror = _make_mirror()
    assert mirror.NOTEBOOK_ID == JOPLIN_JOURNAL_NOTEBOOK_ID


def test_journal_mirror_note_title_format():
    mirror = _make_mirror()
    d = date(2026, 4, 26)
    # write_daily_note should use DD-MM-YY title
    # We verify by patching _find_note and _api and checking what title is searched
    calls = []

    def fake_find(title):
        calls.append(title)
        return None  # force create path

    def fake_api(method, endpoint, body=None):
        calls.append((method, endpoint, body))
        return {"id": "new-note-id"}

    mirror._find_note = fake_find
    mirror._api = fake_api

    mirror.write_daily_note(d, "Journal content here")

    # First call should be _find_note with DD-MM-YY title
    assert calls[0] == "26-04-26"
    # POST call should include parent_id = JOPLIN_JOURNAL_NOTEBOOK_ID
    post_call = next((c for c in calls if isinstance(c, tuple) and c[0] == "POST"), None)
    assert post_call is not None
    assert post_call[2]["parent_id"] == JOPLIN_JOURNAL_NOTEBOOK_ID
    assert post_call[2]["title"] == "26-04-26"


def test_journal_mirror_updates_existing_note():
    mirror = _make_mirror()
    d = date(2026, 4, 26)

    def fake_find(title):
        return "existing-note-id"

    put_calls = []

    def fake_api(method, endpoint, body=None):
        if method == "PUT":
            put_calls.append((endpoint, body))
        return {"id": "existing-note-id", "body": "old content"}

    mirror._find_note = fake_find
    mirror._api = fake_api

    mirror.write_daily_note(d, "New journal content")

    assert len(put_calls) == 1
    assert "existing-note-id" in put_calls[0][0]
    assert "New journal content" in put_calls[0][1]["body"]


def test_journal_mirror_silent_on_joplin_offline():
    mirror = _make_mirror()
    d = date(2026, 4, 26)

    def fake_find(title):
        return None

    def fake_api(method, endpoint, body=None):
        return None  # Joplin offline

    mirror._find_note = fake_find
    mirror._api = fake_api

    # Should not raise
    mirror.write_daily_note(d, "content")


# ── ResumeUpdater ─────────────────────────────────────────────────────────────

def _make_updater(gateway=None):
    if gateway is None:
        gateway = MagicMock()
        gateway.chat_complete = AsyncMock(return_value="NONE")
    return ResumeUpdater(gateway=gateway, token="test-token", port=41184)


async def test_resume_updater_skips_empty_journal():
    updater = _make_updater()
    await updater.update_from_journal("", date(2026, 4, 26))
    updater._gateway.chat_complete.assert_not_called()


async def test_resume_updater_skips_on_none_response():
    gw = MagicMock()
    gw.chat_complete = AsyncMock(return_value="NONE")
    updater = _make_updater(gw)

    find_calls = []
    updater._find_resume_note = lambda t: find_calls.append(t) or None

    await updater.update_from_journal("Did some work today.", date(2026, 4, 26))
    assert find_calls == []  # no note lookups when LLM says NONE


async def test_resume_updater_parses_and_appends():
    gw = MagicMock()
    gw.chat_complete = AsyncMock(
        return_value="Technical Skills | Used DeepEval for LLM evaluation in AgentHub."
    )
    updater = _make_updater(gw)

    found_notes = {"Technical Skills": "skills-note-id"}
    appended = []

    def fake_find(title):
        return found_notes.get(title)

    def fake_append(note_id, bullet, today):
        appended.append((note_id, bullet))

    updater._find_resume_note = fake_find
    updater._append_to_note = fake_append

    await updater.update_from_journal("Used DeepEval today.", date(2026, 4, 26))

    assert len(appended) == 1
    assert appended[0][0] == "skills-note-id"
    assert "DeepEval" in appended[0][1]


async def test_resume_updater_ignores_unknown_note_titles():
    gw = MagicMock()
    gw.chat_complete = AsyncMock(
        return_value="Unknown Note Title | Some bullet text."
    )
    updater = _make_updater(gw)

    appended = []
    updater._find_resume_note = lambda t: "some-id"
    updater._append_to_note = lambda nid, b, d: appended.append((nid, b))

    await updater.update_from_journal("Did work.", date(2026, 4, 26))
    # "Unknown Note Title" is not in RESUME_NOTE_TITLES — should be ignored
    assert appended == []


async def test_resume_updater_handles_gateway_failure():
    gw = MagicMock()
    gw.chat_complete = AsyncMock(side_effect=Exception("gateway down"))
    updater = _make_updater(gw)

    appended = []
    updater._find_resume_note = lambda t: "some-id"
    updater._append_to_note = lambda nid, b, d: appended.append((nid, b))

    # Should not raise
    await updater.update_from_journal("Did work.", date(2026, 4, 26))
    assert appended == []


def test_resume_note_titles_are_defined():
    assert "Technical Skills" in RESUME_NOTE_TITLES
    assert "Work Experience" in RESUME_NOTE_TITLES
    assert "Projects" in RESUME_NOTE_TITLES
