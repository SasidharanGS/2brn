"""Tests for joplin_watcher.py — note embedding and change tracking."""
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brn_daemon.joplin_watcher import (
    CHUNK_SIZE,
    JoplinWatcher,
    _clean_body,
    _get_all_notes,
    _get_notes_since,
    chunk_markdown,
)


# ── Pure-function tests ───────────────────────────────────────────────────────

def test_clean_body_strips_props_block():
    """_clean_body must remove the Joplin props block appended by migration."""
    body = "Some note content.\n\nid: abc123\nparent_id: xyz\ntype_: 1\n"
    result = _clean_body(body)
    assert result == "Some note content."


def test_clean_body_leaves_normal_body_untouched():
    body = "Normal markdown note.\n\nWith multiple paragraphs."
    assert _clean_body(body) == body


def test_clean_body_returns_original_when_fully_stripped():
    """If the entire body is a props block, return the original stripped text."""
    body = "id: abc\nparent_id: xyz\n"
    # _clean_body: if cleaned is empty, return body.strip()
    result = _clean_body(body)
    assert result  # not empty


def test_chunk_markdown_splits_long_text():
    """chunk_markdown must split text into chunks of at most CHUNK_SIZE words."""
    words = ["word"] * (CHUNK_SIZE * 2 + 10)
    text = " ".join(words)
    chunks = chunk_markdown(text)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk.split()) <= CHUNK_SIZE


def test_chunk_markdown_preserves_heading_boundaries():
    """chunk_markdown must split at headings when possible."""
    text = "# Section A\n\nContent A.\n\n## Section B\n\nContent B."
    chunks = chunk_markdown(text)
    assert any("Section A" in c for c in chunks)
    assert any("Section B" in c for c in chunks)


def test_chunk_markdown_returns_at_least_one_chunk():
    chunks = chunk_markdown("Short text.")
    assert len(chunks) == 1
    assert chunks[0] == "Short text."


def test_chunk_markdown_empty_returns_empty():
    assert chunk_markdown("") == []


# ── SQLite integration tests (in-memory DB, no real Joplin needed) ───────────

def _make_joplin_db(tmp_path: Path) -> Path:
    """Create a minimal Joplin-shaped SQLite DB for testing."""
    db = tmp_path / "database.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE notes (
            id TEXT PRIMARY KEY,
            title TEXT,
            body TEXT,
            updated_time INTEGER,
            parent_id TEXT,
            is_conflict INTEGER DEFAULT 0,
            encryption_applied INTEGER DEFAULT 0
        );
        CREATE TABLE folders (
            id TEXT PRIMARY KEY,
            title TEXT
        );
        INSERT INTO folders VALUES ('folder1', 'My Notebook');
        INSERT INTO notes VALUES
          ('note1', 'First Note', 'Hello world.', 1000, 'folder1', 0, 0),
          ('note2', 'Second Note', 'Goodbye world.', 2000, 'folder1', 0, 0),
          ('note3', 'Empty', '', 3000, 'folder1', 0, 0),
          ('note4', 'Conflict', 'Conflict body.', 4000, 'folder1', 1, 0),
          ('note5', 'Encrypted', 'Enc body.', 5000, 'folder1', 0, 1);
    """)
    conn.commit()
    conn.close()
    return db


def test_get_notes_since_returns_notes_after_timestamp(tmp_path):
    db = _make_joplin_db(tmp_path)
    notes = _get_notes_since(db, since_ms=1000)
    ids = [n["id"] for n in notes]
    # note1 has updated_time=1000 — not > 1000, so excluded
    assert "note1" not in ids
    # note2 has updated_time=2000 — included
    assert "note2" in ids


def test_get_notes_since_excludes_empty_and_conflict_and_encrypted(tmp_path):
    db = _make_joplin_db(tmp_path)
    notes = _get_notes_since(db, since_ms=0)
    ids = [n["id"] for n in notes]
    assert "note3" not in ids   # empty body
    assert "note4" not in ids   # is_conflict=1
    assert "note5" not in ids   # encryption_applied=1


def test_get_all_notes_returns_all_valid(tmp_path):
    db = _make_joplin_db(tmp_path)
    notes = _get_all_notes(db)
    ids = [n["id"] for n in notes]
    assert "note1" in ids
    assert "note2" in ids
    assert len(ids) == 2  # only note1 and note2 are valid


def test_get_notes_since_returns_empty_on_missing_db(tmp_path):
    missing = tmp_path / "nonexistent.sqlite"
    notes = _get_notes_since(missing, since_ms=0)
    assert notes == []


# ── JoplinWatcher integration tests ──────────────────────────────────────────

def _make_watcher(tmp_path: Path, db_path: Path) -> tuple[JoplinWatcher, MagicMock, MagicMock]:
    """Create a JoplinWatcher with mocked embed_client and chroma_client."""
    embed_client = MagicMock()
    embed_client.embed_batch = AsyncMock(return_value=[[0.1] * 4, [0.2] * 4])

    fake_collection = MagicMock()
    chroma_client = MagicMock()
    chroma_client.get_or_create_collection.return_value = fake_collection

    watcher = JoplinWatcher(
        embed_client=embed_client,
        chroma_client=chroma_client,
        db_path=db_path,
    )
    return watcher, embed_client, fake_collection


async def test_bulk_embed_all_embeds_valid_notes(tmp_path):
    db = _make_joplin_db(tmp_path)
    watcher, embed_client, collection = _make_watcher(tmp_path, db)

    await watcher.bulk_embed_all()

    # embed_batch must have been called once per note (note1 and note2)
    assert embed_client.embed_batch.call_count == 2
    # collection.upsert must have been called
    assert collection.upsert.call_count == 2


async def test_bulk_embed_all_advances_last_poll_ms(tmp_path):
    db = _make_joplin_db(tmp_path)
    watcher, _, _ = _make_watcher(tmp_path, db)

    assert watcher._last_poll_ms == 0
    await watcher.bulk_embed_all()
    # Should be set to max(updated_time) = 2000
    assert watcher._last_poll_ms == 2000


async def test_bulk_embed_all_skips_when_db_missing(tmp_path):
    missing = tmp_path / "nope.sqlite"
    embed_client = MagicMock()
    embed_client.embed_batch = AsyncMock(return_value=[])
    chroma_client = MagicMock()

    watcher = JoplinWatcher(
        embed_client=embed_client,
        chroma_client=chroma_client,
        db_path=missing,
    )
    # Should not raise, just log a warning
    await watcher.bulk_embed_all()
    embed_client.embed_batch.assert_not_called()


async def test_poll_once_only_fetches_new_notes(tmp_path):
    db = _make_joplin_db(tmp_path)
    watcher, embed_client, collection = _make_watcher(tmp_path, db)

    # Simulate: last poll was at time 1500, so only note2 (updated_time=2000) is new
    watcher._last_poll_ms = 1500

    await watcher._poll_once()

    assert embed_client.embed_batch.call_count == 1  # only note2
    assert watcher._last_poll_ms == 2000


async def test_poll_once_does_nothing_when_no_new_notes(tmp_path):
    db = _make_joplin_db(tmp_path)
    watcher, embed_client, _ = _make_watcher(tmp_path, db)

    # Set cursor past all notes
    watcher._last_poll_ms = 9999

    await watcher._poll_once()
    embed_client.embed_batch.assert_not_called()


async def test_embed_note_prepends_title_to_first_chunk(tmp_path):
    db = _make_joplin_db(tmp_path)
    watcher, embed_client, collection = _make_watcher(tmp_path, db)

    note = {"id": "n1", "title": "My Title", "body": "Body text.", "notebook": "NB", "updated_time": 100}
    embed_client.embed_batch = AsyncMock(return_value=[[0.1] * 4])

    await watcher._embed_note(note)

    # embed_batch should receive a chunk containing the title
    call_args = embed_client.embed_batch.call_args[0][0]
    assert any("My Title" in chunk for chunk in call_args)


async def test_embed_note_sets_correct_metadata(tmp_path):
    db = _make_joplin_db(tmp_path)
    watcher, embed_client, collection = _make_watcher(tmp_path, db)

    note = {"id": "note-xyz", "title": "Test", "body": "Content.", "notebook": "Books", "updated_time": 500}
    embed_client.embed_batch = AsyncMock(return_value=[[0.0] * 4])

    await watcher._embed_note(note)

    upsert_call = collection.upsert.call_args
    ids = upsert_call.kwargs["ids"]
    metadatas = upsert_call.kwargs["metadatas"]

    assert ids[0] == "joplin-note-xyz-0"
    assert metadatas[0]["source"] == "joplin"
    assert metadatas[0]["note_id"] == "note-xyz"
    assert metadatas[0]["notebook"] == "Books"


async def test_bulk_embed_continues_after_single_note_failure(tmp_path):
    db = _make_joplin_db(tmp_path)
    watcher, embed_client, collection = _make_watcher(tmp_path, db)

    # First call raises, second succeeds
    embed_client.embed_batch = AsyncMock(
        side_effect=[RuntimeError("embed failed"), [[0.1] * 4]]
    )

    # Should not raise; should still process note2
    await watcher.bulk_embed_all()
    assert embed_client.embed_batch.call_count == 2
