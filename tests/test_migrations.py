"""測試 travel/migrations.py。"""
import os
import tempfile
import pytest
from travel.db import init_db, get_conn


@pytest.fixture
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DB_PATH", path)
    yield path
    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


def test_migrate_creates_schema_version_table(temp_db):
    from travel.migrations import migrate
    init_db()
    migrate()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
    assert row is not None


def test_migrate_version_reaches_latest(temp_db):
    from travel.migrations import migrate, get_current_version, MIGRATIONS
    init_db()
    migrate()
    latest = max(v for v, _ in MIGRATIONS)
    assert get_current_version() == latest


def test_migrate_idempotent(temp_db):
    from travel.migrations import migrate, get_current_version, MIGRATIONS
    init_db()
    migrate()
    migrate()  # second run must not raise
    assert get_current_version() == max(v for v, _ in MIGRATIONS)


def test_migrate_trips_has_new_columns(temp_db):
    from travel.migrations import migrate
    init_db()
    migrate()
    with get_conn() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(trips)").fetchall()}
    assert "rarity" in cols
    assert "ended_at" in cols
    assert "planning_days" in cols


def test_migrate_creates_daily_stats_table(temp_db):
    from travel.migrations import migrate
    init_db()
    migrate()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_stats'"
        ).fetchone()
    assert row is not None


def test_migrate_badges_has_user_id_column(temp_db):
    from travel.migrations import migrate
    init_db()
    migrate()
    with get_conn() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(badges)").fetchall()}
    assert "user_id" in cols
    assert "badge_name" in cols