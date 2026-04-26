"""Screenshot encryption.

Design
------
- AES-256-GCM (authenticated encryption — both confidentiality and tamper detection).
- PBKDF2-HMAC-SHA256, 600,000 iterations (OWASP recommendation as of 2023) for password-based
  key derivation. Argon2id would be stronger but PBKDF2 is built into the `cryptography` library
  we already depend on, and 600k iterations on SHA256 is acceptable for a desktop-app threat model.
- Per-file random 12-byte nonce. Standard for AES-GCM.
- 16-byte random salt, generated once and stored in `~/.2brn/encryption.json`. The salt is not
  secret — its only job is to make rainbow tables useless.
- Password verifier: a known plaintext encrypted with the derived key, stored in encryption.json.
  On startup, the daemon attempts to decrypt the verifier. If the GCM tag check fails the password
  is wrong; otherwise the derived key is correct and cached in memory.

File format
-----------
Encrypted screenshots: ``[12-byte nonce][ciphertext][16-byte GCM tag]``
(``AESGCM.encrypt`` returns ``ciphertext || tag`` already concatenated, so we just prepend
the nonce.)

File extension convention
-------------------------
- Plain JPEG: ``<timestamp>.jpg``
- Encrypted JPEG: ``<timestamp>.jpg.enc``

Threat model
------------
- Attacker who copies the screenshots folder (cloud sync, backup leak, malware exfiltration)
  cannot view the captured images without the password.
- The user's OS account is trusted — the password is stored in the OS keychain (accessible to
  the user's daemon process when the keychain is unlocked).
"""
from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from brn_daemon.db import get_brn_home

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

KDF_ITERATIONS = 600_000
KEY_LENGTH = 32          # AES-256
NONCE_LENGTH = 12        # GCM standard
SALT_LENGTH = 16
GCM_TAG_LENGTH = 16
VERIFIER_PLAINTEXT = b"2brn-screenshot-verifier-v1"
ENCRYPTED_EXT = ".jpg.enc"


# ── State persisted on disk ──────────────────────────────────────────────────

@dataclass
class EncryptionState:
    salt: bytes
    verifier: bytes      # nonce(12) + ciphertext + tag(16) of VERIFIER_PLAINTEXT
    version: int = 1


def _state_path() -> Path:
    return get_brn_home() / "encryption.json"


def load_encryption_state() -> EncryptionState | None:
    path = _state_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return EncryptionState(
            salt=base64.b64decode(data["salt"]),
            verifier=base64.b64decode(data["verifier"]),
            version=data.get("version", 1),
        )
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.error("Corrupt encryption.json — encryption disabled: %s", exc)
        return None


def save_encryption_state(state: EncryptionState) -> None:
    get_brn_home().mkdir(parents=True, exist_ok=True)
    _state_path().write_text(json.dumps({
        "version": state.version,
        "salt": base64.b64encode(state.salt).decode("ascii"),
        "verifier": base64.b64encode(state.verifier).decode("ascii"),
    }, indent=2))


def delete_encryption_state() -> None:
    path = _state_path()
    if path.exists():
        path.unlink()


# ── Key derivation & primitives ──────────────────────────────────────────────

def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte AES key from the password using PBKDF2-HMAC-SHA256."""
    if not password:
        raise ValueError("password must not be empty")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_bytes(plaintext: bytes, key: bytes) -> bytes:
    """Return ``nonce || ciphertext || tag``."""
    nonce = os.urandom(NONCE_LENGTH)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext, associated_data=None)
    return nonce + ct


def decrypt_bytes(blob: bytes, key: bytes) -> bytes:
    """Reverse of :func:`encrypt_bytes`. Raises on tamper / wrong key."""
    if len(blob) < NONCE_LENGTH + GCM_TAG_LENGTH:
        raise ValueError("ciphertext too short")
    nonce, ct = blob[:NONCE_LENGTH], blob[NONCE_LENGTH:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, associated_data=None)


# ── High-level password lifecycle ────────────────────────────────────────────

def initialize_encryption(password: str) -> bytes:
    """Set up encryption for the first time.

    Generates a fresh salt + verifier, persists them to ``encryption.json``,
    returns the derived 32-byte key for the caller to cache in memory.
    Raises ``RuntimeError`` if encryption is already initialised.
    """
    if load_encryption_state() is not None:
        raise RuntimeError("encryption already initialised; use change_password or disable first")
    salt = os.urandom(SALT_LENGTH)
    key = derive_key(password, salt)
    verifier = encrypt_bytes(VERIFIER_PLAINTEXT, key)
    save_encryption_state(EncryptionState(salt=salt, verifier=verifier))
    return key


def verify_password(password: str, state: EncryptionState | None = None) -> bytes | None:
    """Derive a key from the password and verify it against the stored verifier.

    Returns the key bytes on success, ``None`` if password is wrong or encryption isn't set up.
    """
    if state is None:
        state = load_encryption_state()
    if state is None:
        return None
    try:
        key = derive_key(password, state.salt)
        pt = decrypt_bytes(state.verifier, key)
        if pt != VERIFIER_PLAINTEXT:
            return None
        return key
    except Exception:
        # Keep broad: can be OSError (missing file), json.JSONDecodeError, or
        # unexpected crypto errors — all mean "no valid metadata, disable encryption"
        return None


def is_initialised() -> bool:
    return load_encryption_state() is not None


# ── Bulk file operations ─────────────────────────────────────────────────────

def _iter_screenshots(suffix: str) -> list[Path]:
    root = get_brn_home() / "screenshots"
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file() and str(p).endswith(suffix)]


def encrypt_existing_screenshots(key: bytes) -> tuple[int, int]:
    """Encrypt every plaintext ``.jpg`` under ``~/.2brn/screenshots/``.

    Returns (success_count, failure_count). On success, the plaintext file is deleted and a
    new ``.jpg.enc`` sibling is created. The DB rows still point at the old ``.jpg`` path —
    callers must update the DB separately.
    """
    success = failed = 0
    for jpg in _iter_screenshots(".jpg"):
        if jpg.name.endswith(ENCRYPTED_EXT):
            continue
        enc = jpg.with_suffix(".jpg" + ENCRYPTED_EXT[4:])  # → .jpg.enc
        try:
            blob = encrypt_bytes(jpg.read_bytes(), key)
            enc.write_bytes(blob)
            jpg.unlink()
            success += 1
        except (OSError, ValueError) as exc:
            logger.warning("Could not encrypt %s: %s", jpg, exc)
            if enc.exists():
                enc.unlink()  # don't leave a half-written file
            failed += 1
    return success, failed


def decrypt_all_screenshots(key: bytes) -> tuple[int, int]:
    """Decrypt every ``.jpg.enc`` back to plaintext ``.jpg`` (delete the ``.enc``)."""
    success = failed = 0
    for enc in _iter_screenshots(ENCRYPTED_EXT):
        jpg = enc.with_suffix("")  # strips ".enc" → .jpg
        try:
            pt = decrypt_bytes(enc.read_bytes(), key)
            jpg.write_bytes(pt)
            enc.unlink()
            success += 1
        except (OSError, ValueError) as exc:
            logger.warning("Could not decrypt %s: %s", enc, exc)
            failed += 1
    return success, failed


def re_encrypt_all_screenshots(old_key: bytes, new_key: bytes) -> tuple[int, int]:
    """Decrypt with ``old_key`` and re-encrypt with ``new_key`` in place."""
    success = failed = 0
    for enc in _iter_screenshots(ENCRYPTED_EXT):
        try:
            pt = decrypt_bytes(enc.read_bytes(), old_key)
            enc.write_bytes(encrypt_bytes(pt, new_key))
            success += 1
        except (OSError, ValueError) as exc:
            logger.warning("Could not re-encrypt %s: %s", enc, exc)
            failed += 1
    return success, failed


# ── DB helpers ────────────────────────────────────────────────────────────────

async def mark_captures_encrypted() -> int:
    """Append ``.enc`` to every ``captures.file_path`` that ends in ``.jpg``.

    Run after :func:`encrypt_existing_screenshots`. Returns the row count.
    """
    import aiosqlite

    from brn_daemon.db import get_db_path
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "UPDATE captures SET file_path = file_path || '.enc' "
            "WHERE file_path LIKE '%.jpg'",
        )
        await conn.commit()
        return cur.rowcount or 0


async def mark_captures_decrypted() -> int:
    """Strip trailing ``.enc`` from every ``captures.file_path``.

    Run after :func:`decrypt_all_screenshots`. Returns the row count.
    """
    import aiosqlite

    from brn_daemon.db import get_db_path
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute(
            "UPDATE captures SET file_path = SUBSTR(file_path, 1, LENGTH(file_path) - 4) "
            "WHERE file_path LIKE '%.jpg.enc'",
        )
        await conn.commit()
        return cur.rowcount or 0
