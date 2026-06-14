"""Tests for screenshot encryption."""
import pytest
import aiosqlite

from brn_daemon.db import get_brn_home, get_db_path, init_db
from brn_daemon.encryption import (
    ENCRYPTED_EXT,
    EncryptionState,
    KEY_LENGTH,
    NONCE_LENGTH,
    SALT_LENGTH,
    decrypt_all_screenshots,
    decrypt_bytes,
    delete_encryption_state,
    derive_key,
    encrypt_bytes,
    encrypt_existing_screenshots,
    initialize_encryption,
    is_initialised,
    load_encryption_state,
    re_encrypt_all_screenshots,
    save_encryption_state,
    verify_password,
)
from brn_daemon.repository import mark_captures_decrypted, mark_captures_encrypted


def test_derive_key_produces_32_bytes(tmp_home):
    key = derive_key("hunter2-correct-horse", b"\x00" * SALT_LENGTH)
    assert isinstance(key, bytes)
    assert len(key) == KEY_LENGTH


def test_derive_key_is_deterministic(tmp_home):
    salt = b"\x42" * SALT_LENGTH
    a = derive_key("pw", salt)
    b = derive_key("pw", salt)
    assert a == b


def test_derive_key_changes_with_salt(tmp_home):
    a = derive_key("pw", b"\x00" * SALT_LENGTH)
    b = derive_key("pw", b"\x01" * SALT_LENGTH)
    assert a != b


def test_derive_key_changes_with_password(tmp_home):
    salt = b"\x42" * SALT_LENGTH
    assert derive_key("pw1", salt) != derive_key("pw2", salt)


def test_derive_key_rejects_empty_password(tmp_home):
    with pytest.raises(ValueError):
        derive_key("", b"\x00" * SALT_LENGTH)


def test_encrypt_decrypt_roundtrip(tmp_home):
    key = derive_key("pw", b"\xaa" * SALT_LENGTH)
    plaintext = b"super secret screenshot bytes"
    blob = encrypt_bytes(plaintext, key)
    # Nonce prefix + ciphertext + 16-byte GCM tag
    assert len(blob) == NONCE_LENGTH + len(plaintext) + 16
    assert decrypt_bytes(blob, key) == plaintext


def test_decrypt_rejects_tamper(tmp_home):
    key = derive_key("pw", b"\xaa" * SALT_LENGTH)
    blob = bytearray(encrypt_bytes(b"hello", key))
    blob[-1] ^= 0x01  # flip a tag bit
    with pytest.raises(Exception):
        decrypt_bytes(bytes(blob), key)


def test_decrypt_rejects_wrong_key(tmp_home):
    key1 = derive_key("pw1", b"\xaa" * SALT_LENGTH)
    key2 = derive_key("pw2", b"\xaa" * SALT_LENGTH)
    blob = encrypt_bytes(b"hello", key1)
    with pytest.raises(Exception):
        decrypt_bytes(blob, key2)


def test_encrypt_uses_fresh_nonce_each_call(tmp_home):
    key = derive_key("pw", b"\xaa" * SALT_LENGTH)
    a = encrypt_bytes(b"same", key)
    b = encrypt_bytes(b"same", key)
    assert a != b  # different nonces → different ciphertexts


def test_initialize_encryption_roundtrip(tmp_home):
    assert not is_initialised()
    key = initialize_encryption("hunter22-long-enough")
    assert isinstance(key, bytes) and len(key) == KEY_LENGTH
    assert is_initialised()
    state = load_encryption_state()
    assert state is not None
    assert len(state.salt) == SALT_LENGTH
    # Verifier decrypts back to the canonical plaintext under our derived key
    from brn_daemon.encryption import VERIFIER_PLAINTEXT
    assert decrypt_bytes(state.verifier, key) == VERIFIER_PLAINTEXT


def test_initialize_encryption_refuses_double_init(tmp_home):
    initialize_encryption("pw1-long-pass")
    with pytest.raises(RuntimeError):
        initialize_encryption("pw2-long-pass")


def test_verify_password_correct(tmp_home):
    key1 = initialize_encryption("the-right-password")
    key2 = verify_password("the-right-password")
    assert key2 == key1


def test_verify_password_wrong_returns_none(tmp_home):
    initialize_encryption("the-right-password")
    assert verify_password("the-wrong-password") is None


def test_verify_password_returns_none_when_not_initialised(tmp_home):
    assert verify_password("anything") is None


def test_save_load_encryption_state_roundtrip(tmp_home):
    state = EncryptionState(salt=b"\x01" * SALT_LENGTH, verifier=b"\x02" * 64)
    save_encryption_state(state)
    loaded = load_encryption_state()
    assert loaded is not None
    assert loaded.salt == state.salt
    assert loaded.verifier == state.verifier
    assert loaded.version == 1


def test_delete_encryption_state(tmp_home):
    initialize_encryption("aaaaaaaa12345")
    assert is_initialised()
    delete_encryption_state()
    assert not is_initialised()


def _write_screenshot(name: str = "test.jpg", body: bytes = b"fake-jpeg-bytes") -> str:
    """Helper: write a fake screenshot under the active BRN_HOME and return its path."""
    d = get_brn_home() / "screenshots" / "2026" / "05" / "23"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_bytes(body)
    return str(p)


def test_encrypt_existing_screenshots(tmp_home):
    key = initialize_encryption("aaaaaaaa12345")
    p1 = _write_screenshot("a.jpg", b"contents-a")
    p2 = _write_screenshot("b.jpg", b"contents-b")
    ok, fail = encrypt_existing_screenshots(key)
    assert ok == 2 and fail == 0
    from pathlib import Path
    assert not Path(p1).exists()
    assert Path(p1 + ".enc").exists()
    # Round-trip
    assert decrypt_bytes(Path(p1 + ".enc").read_bytes(), key) == b"contents-a"
    assert decrypt_bytes(Path(p2 + ".enc").read_bytes(), key) == b"contents-b"


def test_decrypt_all_screenshots(tmp_home):
    key = initialize_encryption("aaaaaaaa12345")
    _write_screenshot("a.jpg", b"contents-a")
    encrypt_existing_screenshots(key)
    ok, fail = decrypt_all_screenshots(key)
    assert ok == 1 and fail == 0
    from pathlib import Path
    d = get_brn_home() / "screenshots" / "2026" / "05" / "23"
    assert (d / "a.jpg").exists()
    assert not (d / ("a.jpg" + ENCRYPTED_EXT[4:])).exists()
    assert (d / "a.jpg").read_bytes() == b"contents-a"


def test_re_encrypt_all_screenshots(tmp_home):
    old_key = initialize_encryption("password-the-first")
    _write_screenshot("a.jpg", b"contents-a")
    encrypt_existing_screenshots(old_key)

    # New key, manually derived (would normally be done by change_password endpoint)
    new_key = derive_key("password-the-second", b"\xbb" * SALT_LENGTH)
    ok, fail = re_encrypt_all_screenshots(old_key, new_key)
    assert ok == 1 and fail == 0

    from pathlib import Path
    d = get_brn_home() / "screenshots" / "2026" / "05" / "23"
    enc_path = d / "a.jpg.enc"
    assert enc_path.exists()
    # Old key must no longer work; new key must.
    with pytest.raises(Exception):
        decrypt_bytes(enc_path.read_bytes(), old_key)
    assert decrypt_bytes(enc_path.read_bytes(), new_key) == b"contents-a"


async def test_mark_captures_encrypted_decrypted(tmp_home):
    await init_db()
    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute(
            "INSERT INTO captures (captured_at, trigger, file_path) VALUES ('2026-01-01', 'heartbeat', ?)",
            ("/path/a.jpg",),
        )
        await conn.execute(
            "INSERT INTO captures (captured_at, trigger, file_path) VALUES ('2026-01-01', 'heartbeat', ?)",
            ("/path/b.jpg",),
        )
        await conn.commit()
    rows = await mark_captures_encrypted()
    assert rows == 2
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT file_path FROM captures ORDER BY id")
        paths = [r[0] for r in await cur.fetchall()]
    assert paths == ["/path/a.jpg.enc", "/path/b.jpg.enc"]

    rows = await mark_captures_decrypted()
    assert rows == 2
    async with aiosqlite.connect(get_db_path()) as conn:
        cur = await conn.execute("SELECT file_path FROM captures ORDER BY id")
        paths = [r[0] for r in await cur.fetchall()]
    assert paths == ["/path/a.jpg", "/path/b.jpg"]
