"""測試 travel/db.py。"""
import json
import os
import tempfile

import pytest

from travel.db import get_conn, init_db, insert_message


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


def test_init_db_creates_messages_table(temp_db):
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
        ).fetchone()
    assert row is not None


def test_init_db_creates_trips_table(temp_db):
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='trips'"
        ).fetchone()
    assert row is not None


def test_insert_message_returns_true_for_new(temp_db):
    init_db()
    result = insert_message({
        "line_message_id": "msg-001",
        "group_id": "C123",
        "user_id": "U001",
        "user_name": "Alice",
        "type": "text",
        "content": "hello",
        "metadata": {},
        "reply_to_message_id": None,
        "timestamp": 1700000000000,
    })
    assert result is True


def test_insert_message_returns_false_for_duplicate(temp_db):
    init_db()
    msg = {
        "line_message_id": "msg-001",
        "group_id": "C123",
        "user_id": "U001",
        "user_name": "Alice",
        "type": "text",
        "content": "hello",
        "metadata": {},
        "reply_to_message_id": None,
        "timestamp": 1700000000000,
    }
    insert_message(msg)
    result = insert_message(msg)
    assert result is False


def test_insert_message_stores_metadata_as_json(temp_db):
    init_db()
    insert_message({
        "line_message_id": "msg-002",
        "group_id": "C123",
        "user_id": "U001",
        "user_name": "Alice",
        "type": "sticker",
        "content": None,
        "metadata": {"sticker_id": "1", "package_id": "2"},
        "reply_to_message_id": None,
        "timestamp": 1700000000000,
    })
    with get_conn() as conn:
        row = conn.execute("SELECT metadata FROM messages WHERE id=1").fetchone()
    assert json.loads(row["metadata"]) == {"sticker_id": "1", "package_id": "2"}


def test_get_conn_uses_wal_mode(temp_db):
    init_db()
    with get_conn() as conn:
        row = conn.execute("PRAGMA journal_mode").fetchone()
    assert row[0].lower() == "wal"