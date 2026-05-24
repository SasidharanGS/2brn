import os
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite


def get_brn_home() -> Path:
    override = os.environ.get("BRN_HOME")
    if override:
        return Path(override)
    return Path.home() / ".2brn"

def get_db_path() -> Path:
    return get_brn_home() / "2brn.db"


@asynccontextmanager
async def get_conn(path: str | Path | None = None):
    """Open an aiosqlite connection with foreign keys + a busy timeout enabled.

    foreign_keys must be set per-connection for ON DELETE CASCADE to fire, and
    busy_timeout lets concurrent writers (inference workers, the capture loop,
    request handlers) wait briefly for the write lock instead of raising
    'database is locked'. WAL itself is already enabled in init_db().
    """
    async with aiosqlite.connect(path or get_db_path()) as conn:
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute("PRAGMA busy_timeout = 5000")
        yield conn


async def init_db() -> None:
    home = get_brn_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "screenshots").mkdir(exist_ok=True)

    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")

        try:
            await conn.execute("ALTER TABLE captures ADD COLUMN monitor_index INTEGER")
            await conn.commit()
        except aiosqlite.OperationalError:
            pass  # Column already exists — safe to ignore

        try:
            await conn.execute("ALTER TABLE activities ADD COLUMN app_name_override TEXT")
            await conn.commit()
        except aiosqlite.OperationalError:
            pass  # Column already exists — safe to ignore

        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS captures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at DATETIME NOT NULL,
                app_name TEXT,
                window_title TEXT,
                file_path TEXT,
                ocr_text TEXT,
                phash TEXT,
                trigger TEXT CHECK(trigger IN ('heartbeat', 'change')),
                monitor_index INTEGER
            );

            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                capture_id INTEGER REFERENCES captures(id),
                started_at DATETIME NOT NULL,
                ended_at DATETIME,
                summary TEXT,
                tags TEXT,
                chroma_id TEXT,
                task_category TEXT CHECK(task_category IN (
                    'work','research','play','learning',
                    'communication','creative','admin','other'
                )),
                task_category_confidence REAL,
                productivity_state TEXT CHECK(productivity_state IN (
                    'productive','focused','chilling','procrastinating',
                    'distracted','in-meeting','idle'
                )),
                productivity_confidence REAL,
                category_overridden_by_user INTEGER DEFAULT 0,
                app_name_override TEXT
            );

            CREATE TABLE IF NOT EXISTS journals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL UNIQUE,
                content TEXT,
                generated_at DATETIME,
                edited_by_user INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS user_instructions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL
            );

            CREATE TABLE IF NOT EXISTS app_exclusions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_name TEXT UNIQUE NOT NULL,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS blog_posts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                date           TEXT NOT NULL,
                content        TEXT,
                generated_at   TEXT NOT NULL,
                edited_by_user INTEGER NOT NULL DEFAULT 0,
                UNIQUE(date)
            );

            CREATE TABLE IF NOT EXISTS plugins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                command TEXT NOT NULL,
                args TEXT NOT NULL DEFAULT '[]',
                env_keys TEXT NOT NULL DEFAULT '[]',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_health_at DATETIME,
                last_health_ok INTEGER,
                last_health_error TEXT
            );

            CREATE TABLE IF NOT EXISTS plugin_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plugin_id INTEGER NOT NULL REFERENCES plugins(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                rule_text TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                trigger TEXT NOT NULL,
                tool_name TEXT,
                args_template TEXT,
                parse_status TEXT NOT NULL DEFAULT 'pending',
                parse_error TEXT,
                parsed_at DATETIME,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS plugin_rule_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER NOT NULL REFERENCES plugin_rules(id) ON DELETE CASCADE,
                started_at DATETIME NOT NULL,
                ended_at DATETIME,
                status TEXT NOT NULL,
                error TEXT,
                payload TEXT,
                result TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_captures_captured_at ON captures(captured_at);
            CREATE INDEX IF NOT EXISTS idx_captures_monitor ON captures(monitor_index);
            CREATE INDEX IF NOT EXISTS idx_activities_capture_id ON activities(capture_id);
            CREATE INDEX IF NOT EXISTS idx_activities_started_at ON activities(started_at);
            CREATE INDEX IF NOT EXISTS idx_activities_task_category ON activities(task_category);
            CREATE INDEX IF NOT EXISTS idx_activities_productivity_state ON activities(productivity_state);
            CREATE INDEX IF NOT EXISTS idx_journals_date ON journals(date ASC);
            CREATE INDEX IF NOT EXISTS idx_blog_posts_date ON blog_posts(date);
            CREATE INDEX IF NOT EXISTS idx_plugin_rules_plugin_id ON plugin_rules(plugin_id);
            CREATE INDEX IF NOT EXISTS idx_plugin_rules_trigger ON plugin_rules(trigger);
            CREATE INDEX IF NOT EXISTS idx_plugin_rule_executions_rule_id ON plugin_rule_executions(rule_id);
            CREATE INDEX IF NOT EXISTS idx_plugin_rule_executions_started_at ON plugin_rule_executions(started_at DESC);
        """)
        await conn.commit()

        # Migration: strip +00:00 suffix from timestamps stored with tz offset.
        # Safe to run multiple times — rows without the suffix are unaffected.
        await conn.execute(
            "UPDATE activities SET started_at = REPLACE(started_at, '+00:00', '') "
            "WHERE started_at LIKE '%+00:00'"
        )
        await conn.execute(
            "UPDATE captures SET captured_at = REPLACE(captured_at, '+00:00', '') "
            "WHERE captured_at LIKE '%+00:00'"
        )
        await conn.commit()

        cur = await conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='activities'"
        )
        activities_ddl = (await cur.fetchone() or ("",))[0]
        if activities_ddl and "ON DELETE CASCADE" not in activities_ddl:
            await conn.executescript("""
                PRAGMA foreign_keys = OFF;

                ALTER TABLE activities RENAME TO activities_old;

                CREATE TABLE activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    capture_id INTEGER REFERENCES captures(id) ON DELETE CASCADE,
                    started_at DATETIME NOT NULL,
                    ended_at DATETIME,
                    summary TEXT,
                    tags TEXT,
                    chroma_id TEXT,
                    task_category TEXT CHECK(task_category IN (
                        'work','research','play','learning',
                        'communication','creative','admin','other'
                    )),
                    task_category_confidence REAL,
                    productivity_state TEXT CHECK(productivity_state IN (
                        'productive','focused','chilling','procrastinating',
                        'distracted','in-meeting','idle'
                    )),
                    productivity_confidence REAL,
                    category_overridden_by_user INTEGER DEFAULT 0,
                    app_name_override TEXT
                );

                INSERT INTO activities SELECT * FROM activities_old;

                DROP TABLE activities_old;

                CREATE INDEX IF NOT EXISTS idx_activities_capture_id ON activities(capture_id);
                CREATE INDEX IF NOT EXISTS idx_activities_started_at ON activities(started_at);
                CREATE INDEX IF NOT EXISTS idx_activities_task_category ON activities(task_category);
                CREATE INDEX IF NOT EXISTS idx_activities_productivity_state ON activities(productivity_state);

                PRAGMA foreign_keys = ON;
            """)
            await conn.commit()
