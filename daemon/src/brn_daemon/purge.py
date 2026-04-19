import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite

from brn_daemon.db import get_db_path

logger = logging.getLogger(__name__)

_SQLITE_MAX_VARS = 500  # stay well under SQLite's 999-variable limit


def _batches(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


async def purge_old_captures(months: int = 12, chroma_store=None) -> int:
    """Delete captures older than `months` months.

    Returns the number of capture rows deleted.
    `chroma_store` is an optional ChromaStore instance for removing stale embeddings.
    """
    cutoff = datetime.now(UTC) - timedelta(days=months * 30)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S.%f")
    files_deleted = 0

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "SELECT id, file_path FROM captures WHERE captured_at < ?",
            (cutoff_str,),
        )
        old_captures = list(await cur.fetchall())

        if not old_captures:
            return 0

        for _capture_id, file_path in old_captures:
            if file_path:
                try:
                    p = Path(file_path)
                    if p.exists():
                        p.unlink()
                        files_deleted += 1
                except Exception as exc:
                    logger.warning("Could not delete file %s: %s", file_path, exc)

        ids = [row[0] for row in old_captures]

        # Collect chroma IDs before deleting activities
        chroma_ids: list[str] = []
        if chroma_store is not None:
            for batch in _batches(ids, _SQLITE_MAX_VARS):
                placeholders = ",".join("?" * len(batch))
                cur = await conn.execute(
                    f"SELECT chroma_id FROM activities "
                    f"WHERE capture_id IN ({placeholders}) "
                    f"AND chroma_id IS NOT NULL AND chroma_id != ''",
                    batch,
                )
                chroma_ids.extend(row[0] for row in await cur.fetchall())

        # Delete in batches to respect SQLite's variable limit
        for batch in _batches(ids, _SQLITE_MAX_VARS):
            placeholders = ",".join("?" * len(batch))
            await conn.execute(
                f"DELETE FROM activities WHERE capture_id IN ({placeholders})", batch
            )
            await conn.execute(
                f"DELETE FROM captures WHERE id IN ({placeholders})", batch
            )
        await conn.commit()

    # Remove stale ChromaDB embeddings outside the SQLite transaction
    if chroma_store is not None and chroma_ids:
        try:
            chroma_store.collection.delete(ids=chroma_ids)
            logger.info("Removed %d stale embeddings from ChromaDB", len(chroma_ids))
        except Exception as exc:
            logger.warning("Failed to clean ChromaDB during purge: %s", exc)

    logger.info(
        "Purged %d old captures (%d files deleted, cutoff: %s)",
        len(old_captures), files_deleted, cutoff_str,
    )
    return len(old_captures)
