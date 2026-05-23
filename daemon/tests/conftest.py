import pytest
import aiosqlite
from brn_daemon.db import init_db, get_db_path

@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("BRN_HOME", str(tmp_path))
    return tmp_path

@pytest.fixture
async def db(tmp_home):
    await init_db()
    path = get_db_path()
    async with aiosqlite.connect(path) as conn:
        yield conn
