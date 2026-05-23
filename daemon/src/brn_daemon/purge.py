import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import aiosqlite
from brn_daemon.db import get_db_path

logger = logging.getLogger(__name__)


async def purge_old_captures(months: int = 6) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
    cutoff_str = cutoff.isoformat()
    deleted_count = 0

    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "SELECT id, file_path FROM captures WHERE captured_at < ?",
            (cutoff_str,)
        )
        old_captures = await cur.fetchall()

        for capture_id, file_path in old_captures:
            if file_path:
                try:
                    p = Path(file_path)
                    if p.exists():
                        p.unlink()
                        deleted_count += 1
                except Exception as exc:
                    logger.warning("Could not delete file %s: %s", file_path, exc)

        ids = [row[0] for row in old_captures]
        if ids:
            placeholders = ",".join("?" * len(ids))

            cur = await conn.execute(
                f"SELECT chroma_id FROM activities "
                f"WHERE capture_id IN ({placeholders}) AND chroma_id IS NOT NULL AND chroma_id != ''",
                ids,
            )
            chroma_ids = [row[0] for row in await cur.fetchall()]

            await conn.execute(
                f"DELETE FROM activities WHERE capture_id IN ({placeholders})", ids
            )
            await conn.execute(
                f"DELETE FROM captures WHERE id IN ({placeholders})", ids
            )
            await conn.commit()

            if chroma_ids:
                try:
                    from brn_daemon.embeddings import ChromaStore
                    from brn_daemon.main import app_state
                    chroma = app_state.get("chroma_store")
                    if chroma is None:
                        chroma = ChromaStore()
                    chroma.collection.delete(ids=chroma_ids)
                    logger.info("Removed %d stale embeddings from ChromaDB", len(chroma_ids))
                except Exception as exc:
                    logger.warning("Failed to clean ChromaDB during purge: %s", exc)

    logger.info("Purged %d old captures (cutoff: %s)", len(old_captures), cutoff_str)
    return deleted_count
