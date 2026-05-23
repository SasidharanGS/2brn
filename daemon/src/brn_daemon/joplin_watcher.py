"""
joplin_watcher.py

Polls Joplin's local SQLite database for changed notes and keeps the
note_memories ChromaDB collection in sync.

Design decisions:
- Read-only access to Joplin SQLite (safe for concurrent access)
- Polls every POLL_INTERVAL_SECONDS (default 60) — no watchdog needed
- On daemon startup, bulk-embeds ALL non-empty notes
- On each poll, only re-embeds notes updated since last poll
- doc_id = f"joplin-{note_id}-{chunk_index}" — stable, dedup-safe
- Strips Joplin props block (id:, parent_id:, type_:, etc.) from body
  before embedding, since those lines were left in by the migration script
"""

import asyncio
import hashlib
import logging
import re
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 60
NOTE_COLLECTION = "note_memories"
CHUNK_SIZE = 400  # words per chunk

# Default Joplin SQLite path on macOS/Linux
DEFAULT_JOPLIN_DB = Path.home() / ".config" / "joplin-desktop" / "database.sqlite"

# Regex to strip the Joplin props block at the bottom of migrated notes
# (lines of the form "key: value" after the last blank line separator)
_PROPS_BLOCK_RE = re.compile(
    r'\n\n(?:(?:id|parent_id|created_time|updated_time|user_created_time|'
    r'user_updated_time|is_conflict|latitude|longitude|altitude|author|'
    r'source_url|is_todo|todo_due|todo_completed|source|source_application|'
    r'application_data|order|markup_language|is_shared|share_id|'
    r'conflict_original_id|master_key_id|user_data|deleted_time|'
    r'encryption_cipher_text|encryption_applied|type_): .*\n?)+$',
    re.MULTILINE,
)


def _clean_body(body: str) -> str:
    """Strip Joplin props block that may be present in migrated notes."""
    cleaned = _PROPS_BLOCK_RE.sub("", body).strip()
    return cleaned if cleaned else body.strip()


def chunk_markdown(text: str) -> list[str]:
    """Split markdown into ~400-word chunks, respecting heading boundaries."""
    sections = re.split(r'\n(?=#{1,3} )', text)
    chunks = []
    for section in sections:
        words = section.split()
        for i in range(0, len(words), CHUNK_SIZE):
            chunk = " ".join(words[i : i + CHUNK_SIZE])
            if chunk.strip():
                chunks.append(chunk)
    return chunks or ([text[:2000]] if text.strip() else [])


def _get_notes_since(db_path: Path, since_ms: int) -> list[dict]:
    """
    Read notes updated since `since_ms` from Joplin SQLite (read-only).
    Returns list of {id, title, body, updated_time, parent_id}.
    Excludes conflicts, encrypted notes, and empty notes.
    """
    uri = f"file:{db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT n.id, n.title, n.body, n.updated_time, n.parent_id,
                   f.title AS notebook
            FROM notes n
            LEFT JOIN folders f ON n.parent_id = f.id
            WHERE n.updated_time > ?
              AND n.is_conflict = 0
              AND n.encryption_applied = 0
              AND n.body IS NOT NULL
              AND trim(n.body) != ''
            ORDER BY n.updated_time
            """,
            (since_ms,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as exc:
        logger.error("Failed to read Joplin SQLite: %s", exc)
        return []


def _get_all_notes(db_path: Path) -> list[dict]:
    """Read all non-empty, non-encrypted notes from Joplin SQLite."""
    return _get_notes_since(db_path, since_ms=0)


class JoplinWatcher:
    """
    Polls Joplin's SQLite database and keeps note_memories ChromaDB in sync.

    Usage (mirrors VaultWatcher API so main.py needs minimal changes):
        watcher = JoplinWatcher(gateway=gateway, chroma_client=chroma.chroma_client)
        await watcher.bulk_embed_all()   # call once on startup
        watcher.start(loop)              # starts background polling task
        watcher.stop()                   # call on shutdown
    """

    def __init__(
        self,
        gateway,
        chroma_client,
        db_path: Path | None = None,
    ):
        self._gateway = gateway
        self._chroma_client = chroma_client
        self._db_path = db_path or DEFAULT_JOPLIN_DB
        self._collection = None
        self._last_poll_ms: int = 0
        self._poll_task: asyncio.Task | None = None

    def _get_collection(self):
        if self._collection is None:
            self._collection = self._chroma_client.get_or_create_collection(
                name=NOTE_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    async def bulk_embed_all(self) -> None:
        """Embed all existing Joplin notes on daemon startup."""
        if not self._db_path.exists():
            logger.warning(
                "Joplin DB not found at %s — note embedding disabled", self._db_path
            )
            return

        loop = asyncio.get_running_loop()
        notes = await loop.run_in_executor(None, _get_all_notes, self._db_path)
        logger.info("Bulk-embedding %d Joplin notes on startup", len(notes))
        embedded = 0
        for note in notes:
            try:
                await self._embed_note(note)
                embedded += 1
            except Exception as exc:
                logger.error("Bulk embed failed for note %s: %s", note["id"], exc)

        logger.info("Bulk embed complete: %d/%d notes embedded", embedded, len(notes))

        # Record the latest updated_time so the first poll only picks up new changes
        if notes:
            self._last_poll_ms = max(n["updated_time"] for n in notes)

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start the background polling task."""
        if not self._db_path.exists():
            logger.warning("Joplin DB not found — polling not started")
            return
        self._poll_task = loop.create_task(self._poll_loop())
        logger.info(
            "Joplin watcher started (polling every %ds)", POLL_INTERVAL_SECONDS
        )

    def stop(self) -> None:
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            logger.info("Joplin watcher stopped")

    async def _poll_loop(self) -> None:
        """Poll Joplin SQLite for changed notes at regular intervals."""
        while True:
            try:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                await self._poll_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Joplin poll error: %s", exc)

    async def _poll_once(self) -> None:
        """Check for notes updated since last poll and re-embed them."""
        loop = asyncio.get_running_loop()
        notes = await loop.run_in_executor(None, _get_notes_since, self._db_path, self._last_poll_ms)
        if not notes:
            return

        logger.info("Joplin poll: %d changed notes to embed", len(notes))
        max_embedded_ms = self._last_poll_ms
        for note in notes:
            try:
                await self._embed_note(note)
                # Only advance cursor past notes that were successfully embedded
                max_embedded_ms = max(max_embedded_ms, note["updated_time"])
            except Exception as exc:
                logger.error("Failed to embed note %s: %s — will retry next poll", note["id"], exc)

        self._last_poll_ms = max_embedded_ms

    async def _embed_note(self, note: dict) -> None:
        """Chunk and embed a single Joplin note into note_memories."""
        body = _clean_body(note["body"])
        if not body:
            return

        # Prepend title to first chunk for better search relevance
        title = note.get("title", "").strip()
        text_to_chunk = f"# {title}\n\n{body}" if title else body

        chunks = chunk_markdown(text_to_chunk)
        if not chunks:
            return

        collection = self._get_collection()
        note_id = note["id"]
        notebook = note.get("notebook") or ""

        # Batch-embed all chunks for this note in a single gateway call
        embeddings = await self._gateway.embed_batch(chunks)

        ids = [f"joplin-{note_id}-{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "source": "joplin",
                "note_id": note_id,
                "title": title,
                "notebook": notebook,
                "chunk": i,
            }
            for i in range(len(chunks))
        ]
        collection.upsert(
            ids=ids,
            documents=chunks,
            metadatas=metadatas,
            embeddings=embeddings,
        )

        logger.debug("Embedded %d chunks from Joplin note '%s'", len(chunks), title)
