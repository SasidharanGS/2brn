import asyncio
import calendar
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from brn_daemon.db import get_brn_home, get_conn

logger = logging.getLogger(__name__)

_SQLITE_MAX_VARS = 500  # stay well under SQLite's 999-variable limit

_SCREENSHOT_SUFFIXES = (".jpg", ".jpg.enc")


def _batches(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


async def purge_old_captures(months: int = 12, chroma_store=None) -> int:
    """Delete captures older than `months` months.

    Returns the number of capture rows deleted.
    `chroma_store` is an optional ChromaStore instance for removing stale embeddings.
    """
    # Subtract whole calendar months (not months*30 days, which drifts ~5 days/yr).
    now = datetime.now(UTC)
    year, month = now.year, now.month - months
    while month <= 0:
        month += 12
        year -= 1
    day = min(now.day, calendar.monthrange(year, month)[1])
    cutoff = now.replace(year=year, month=month, day=day)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S.%f")
    files_deleted = 0

    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT id, file_path FROM captures WHERE captured_at < ?",
            (cutoff_str,),
        )
        old_captures = list(await cur.fetchall())

        if not old_captures:
            return 0

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

    # Delete screenshot files only AFTER the DB deletions commit. A crash in
    # between leaks a few orphaned files (harmless) rather than leaving DB rows
    # that point at missing files (which would surface as broken images).
    for _capture_id, file_path in old_captures:
        if file_path:
            try:
                p = Path(file_path)
                if p.exists():
                    p.unlink()
                    files_deleted += 1
            except Exception:
                logger.exception("Could not delete file %s", file_path)

    # Remove stale ChromaDB embeddings outside the SQLite transaction
    if chroma_store is not None and chroma_ids:
        try:
            chroma_store.collection.delete(ids=chroma_ids)
            logger.info("Removed %d stale embeddings from ChromaDB", len(chroma_ids))
        except Exception:
            logger.exception("Failed to clean ChromaDB during purge")

    logger.info(
        "Purged %d old captures (%d files deleted, cutoff: %s)",
        len(old_captures), files_deleted, cutoff_str,
    )
    return len(old_captures)


def _sweep_orphans_sync(base: Path, referenced: set[str], cutoff_mtime: float) -> int:
    """Walk the screenshots tree and unlink unreferenced files. Blocking; run off-loop."""
    deleted = 0
    if not base.exists():
        return 0
    for p in base.rglob("*"):
        try:
            if not p.is_file():
                continue
            if not p.name.endswith(_SCREENSHOT_SUFFIXES):
                continue
            if str(p) in referenced:
                continue
            if p.stat().st_mtime >= cutoff_mtime:
                continue
            p.unlink()
            deleted += 1
        except OSError:
            logger.exception("Could not sweep %s", p)
    return deleted


async def sweep_orphaned_screenshots(min_age_seconds: int = 3600) -> int:
    """Delete screenshot files not referenced by any captures row. Best-effort.

    The capture pipeline used to write the screenshot before the dedup filter
    decided whether to keep the frame, so every skipped tick left a uniquely
    named file behind that row-driven purge could never reclaim. This sweep
    cleans that historical debris and any file orphaned by a crash between
    save and DB insert. Only files older than ``min_age_seconds`` are touched
    so an in-flight save can never be swept.
    """
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT file_path FROM captures WHERE file_path IS NOT NULL"
        )
        referenced = {row[0] for row in await cur.fetchall()}

    base = get_brn_home() / "screenshots"
    cutoff = time.time() - min_age_seconds
    loop = asyncio.get_running_loop()
    deleted = await loop.run_in_executor(None, _sweep_orphans_sync, base, referenced, cutoff)
    if deleted:
        logger.info("Swept %d orphaned screenshot files", deleted)
    return deleted
