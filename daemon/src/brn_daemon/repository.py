"""Thin data-access layer.

Plain async functions over :func:`brn_daemon.db.get_conn` that own a piece of
schema knowledge, so callers don't reach into table/column conventions
directly. Not an ORM — just the seam where SQL lives.

Seeded with the capture file-path bookkeeping that previously lived in
``encryption.py`` (which should stay pure crypto + file I/O, not know about the
``captures`` table). Future per-aggregate query extraction can land here.
"""
from __future__ import annotations

from brn_daemon.db import get_conn


async def mark_captures_encrypted() -> int:
    """Append ``.enc`` to every ``captures.file_path`` that ends in ``.jpg``.

    Run after :func:`brn_daemon.encryption.encrypt_existing_screenshots`.
    Returns the number of rows updated.
    """
    async with get_conn() as conn:
        cur = await conn.execute(
            "UPDATE captures SET file_path = file_path || '.enc' "
            "WHERE file_path LIKE '%.jpg'",
        )
        await conn.commit()
        return cur.rowcount or 0


async def mark_captures_decrypted() -> int:
    """Strip trailing ``.enc`` from every ``captures.file_path``.

    Run after :func:`brn_daemon.encryption.decrypt_all_screenshots`.
    Returns the number of rows updated.
    """
    async with get_conn() as conn:
        cur = await conn.execute(
            "UPDATE captures SET file_path = SUBSTR(file_path, 1, LENGTH(file_path) - 4) "
            "WHERE file_path LIKE '%.jpg.enc'",
        )
        await conn.commit()
        return cur.rowcount or 0
