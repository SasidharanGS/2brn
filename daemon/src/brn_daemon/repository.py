"""Thin data-access layer.

Plain async functions over :func:`brn_daemon.db.get_conn` that own a piece of
schema knowledge, so callers don't reach into table/column conventions
directly. Not an ORM — just the seam where SQL lives.

Seeded with the capture file-path bookkeeping that previously lived in
``encryption.py`` (which should stay pure crypto + file I/O, not know about the
``captures`` table). Future per-aggregate query extraction can land here.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

from brn_daemon.db import get_conn


def _hash_token(token: str) -> str:
    """SHA-256 hex of a bearer token.

    Device tokens are 256-bit random (``secrets.token_urlsafe(32)``), so a plain
    SHA-256 is enough to make the stored value useless to an attacker — there is
    nothing to brute-force. No salt/KDF needed (those defend low-entropy
    passwords, not random tokens).
    """
    return hashlib.sha256(token.encode()).hexdigest()


async def create_device(name: str) -> tuple[int, str]:
    """Mint a per-device LAN token, store its hash, return ``(id, token)``.

    The plaintext token is returned **once** (for the pairing QR / manual entry)
    and never persisted — only its hash is.
    """
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC).isoformat()
    async with get_conn() as conn:
        cur = await conn.execute(
            "INSERT INTO devices (name, token_hash, created_at) VALUES (?, ?, ?)",
            (name.strip() or "device", _hash_token(token), now),
        )
        await conn.commit()
        return cur.lastrowid or 0, token


async def list_devices() -> list[dict]:
    """Paired devices, newest first. Never exposes the token (or its hash)."""
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT id, name, created_at, last_seen_at FROM devices ORDER BY id DESC"
        )
        rows = await cur.fetchall()
    return [
        {"id": r[0], "name": r[1], "created_at": r[2], "last_seen_at": r[3]}
        for r in rows
    ]


async def device_id_for_token(token: str) -> int | None:
    """Return the device id whose stored hash matches ``token``, else ``None``."""
    if not token:
        return None
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT id FROM devices WHERE token_hash = ?", (_hash_token(token),)
        )
        row = await cur.fetchone()
    return row[0] if row else None


async def touch_device(device_id: int) -> None:
    """Best-effort update of a device's ``last_seen_at`` (callers throttle)."""
    now = datetime.now(UTC).isoformat()
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE devices SET last_seen_at = ? WHERE id = ?", (now, device_id)
        )
        await conn.commit()


async def delete_device(device_id: int) -> bool:
    """Revoke a device. Returns ``True`` if a row was removed."""
    async with get_conn() as conn:
        cur = await conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        await conn.commit()
        return (cur.rowcount or 0) > 0


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
