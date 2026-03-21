import os
import aiosqlite
from pathlib import Path

def get_brn_home() -> Path:
    override = os.environ.get("BRN_HOME")
    if override:
        return Path(override)
    return Path.home() / ".2brn"

def get_db_path() -> Path:
    return get_brn_home() / "2brn.db"

async def init_db() -> None:
    home = get_brn_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "screenshots").mkdir(exist_ok=True)

    async with aiosqlite.connect(get_db_path()) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")

        try:
            await conn.execute("ALTER TABLE captures ADD COLUMN monitor_index INTEGER")
            await conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore

        try:
            await conn.execute("ALTER TABLE activities ADD COLUMN app_name_override TEXT")
            await conn.commit()
        except Exception:
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

            CREATE INDEX IF NOT EXISTS idx_captures_captured_at ON captures(captured_at);
            CREATE INDEX IF NOT EXISTS idx_captures_monitor ON captures(monitor_index);
            CREATE INDEX IF NOT EXISTS idx_activities_capture_id ON activities(capture_id);
            CREATE INDEX IF NOT EXISTS idx_activities_started_at ON activities(started_at);
            CREATE INDEX IF NOT EXISTS idx_journals_date ON journals(date ASC);
            CREATE INDEX IF NOT EXISTS idx_blog_posts_date ON blog_posts(date);
        """)
        await conn.commit()
