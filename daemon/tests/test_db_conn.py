"""Tests for the shared DB connection helper (review finding A-2)."""


async def test_get_conn_enables_foreign_key_cascade(tmp_home):
    """get_conn() enables foreign_keys so ON DELETE CASCADE actually fires."""
    from brn_daemon.db import get_conn, init_db
    await init_db()
    async with get_conn() as conn:
        cur = await conn.execute(
            "INSERT INTO plugins (name, command) VALUES ('p', '/usr/bin/node')"
        )
        pid = cur.lastrowid
        await conn.execute(
            "INSERT INTO plugin_rules (plugin_id, title, rule_text, trigger) "
            "VALUES (?, 't', 'do it', 'manual')",
            (pid,),
        )
        await conn.commit()
        await conn.execute("DELETE FROM plugins WHERE id = ?", (pid,))
        await conn.commit()
        cur = await conn.execute(
            "SELECT COUNT(*) FROM plugin_rules WHERE plugin_id = ?", (pid,)
        )
        remaining = (await cur.fetchone())[0]
    assert remaining == 0, "ON DELETE CASCADE must remove child plugin_rules"


async def test_get_conn_sets_busy_timeout(tmp_home):
    from brn_daemon.db import get_conn, init_db
    await init_db()
    async with get_conn() as conn:
        cur = await conn.execute("PRAGMA busy_timeout")
        timeout = (await cur.fetchone())[0]
    assert timeout >= 5000
