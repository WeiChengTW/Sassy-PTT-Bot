import os
import tempfile
import time

import pytest

from travel.aggregator import aggregate_daily, aggregate_lifetime
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


def _seed_messages(temp_db, types_per_user):
    init_db()
    now_ms = int(time.time() * 1000)
    msg_id = 1
    for user_id, types in types_per_user.items():
        for t in types:
            insert_message({
                "line_message_id": f"m{msg_id}",
                "group_id": "C1",
                "user_id": user_id,
                "user_name": f"User-{user_id}",
                "type": t,
                "content": "msg" if t == "text" else None,
                "metadata": {},
                "reply_to_message_id": None,
                "timestamp": now_ms,
            })
            msg_id += 1


def test_aggregate_daily_counts_per_type(temp_db):
    _seed_messages(temp_db, {"U1": ["text", "text", "sticker", "image"]})
    today = time.strftime("%Y-%m-%d")
    aggregate_daily(today)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM daily_user_stats WHERE date=? AND user_id='U1'",
            (today,),
        ).fetchone()
    assert row["text_count"] == 2
    assert row["sticker_count"] == 1
    assert row["image_count"] == 1


def test_aggregate_daily_returns_row_count(temp_db):
    _seed_messages(temp_db, {"U1": ["text"], "U2": ["text", "sticker"]})
    today = time.strftime("%Y-%m-%d")
    n = aggregate_daily(today)
    assert n == 2


def test_aggregate_daily_skips_other_dates(temp_db):
    _seed_messages(temp_db, {"U1": ["text"]})
    other = "2020-01-01"
    n = aggregate_daily(other)
    assert n == 0


def test_aggregate_lifetime_computes_totals(temp_db):
    _seed_messages(temp_db, {"U1": ["text", "text", "sticker", "image"]})
    aggregate_lifetime()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM user_lifetime_stats WHERE user_id='U1'"
        ).fetchone()
    assert row["total_messages"] == 4


def test_aggregate_lifetime_tracks_first_and_last_seen(temp_db):
    _seed_messages(temp_db, {"U1": ["text"]})
    aggregate_lifetime()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT first_seen, last_seen FROM user_lifetime_stats WHERE user_id='U1'"
        ).fetchone()
    assert row["first_seen"] is not None
    assert row["last_seen"] is not None
    assert row["first_seen"] <= row["last_seen"]