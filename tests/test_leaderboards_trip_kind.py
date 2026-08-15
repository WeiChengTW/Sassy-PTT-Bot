"""測試 travel/leaderboards.py 旅行 vs 事件分類邏輯。"""
import os
import tempfile
import time
import pytest
from travel.db import init_db, get_conn
from travel.migrations import migrate
from travel.trip_crud import create_trip, add_participants
from travel.leaderboards import _cp_trip, _cp_event, _trip_kind_filter


@pytest.fixture
def db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DB_PATH", path)
    init_db()
    migrate()
    yield path
    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


def _make_trip(group_id, start_date, end_date, title="t"):
    trip_id = create_trip(
        group_id=group_id, title=title, location="loc",
        start_date=start_date, trip_types=None, created_by="U_ADMIN",
        end_date=end_date,
    )
    add_participants(trip_id, ["U1"])
    return trip_id


def test_same_day_is_event(db):
    start = end = 1700000000
    _make_trip("C1", start, end, "當天事件")
    with get_conn() as conn:
        rows_t = _cp_trip(conn, "C1", "all")["rows"]
        rows_e = _cp_event(conn, "C1", "all")["rows"]
    # 旅行榜無結果，事件榜有 1 次
    assert rows_t == []
    assert len(rows_e) == 1 and rows_e[0]["value"] == 1


def test_one_day_span_is_event(db):
    start = 1700000000
    end = start + 86400 - 1  # 不到 1 天
    _make_trip("C1", start, end)
    with get_conn() as conn:
        rows_t = _cp_trip(conn, "C1", "all")["rows"]
        rows_e = _cp_event(conn, "C1", "all")["rows"]
    assert rows_t == []
    assert len(rows_e) == 1


def test_two_day_span_is_travel(db):
    start = 1700000000
    end = start + 86400 * 2  # 2 天
    _make_trip("C1", start, end, "兩天一夜")
    with get_conn() as conn:
        rows_t = _cp_trip(conn, "C1", "all")["rows"]
        rows_e = _cp_event(conn, "C1", "all")["rows"]
    assert len(rows_t) == 1 and rows_t[0]["value"] == 1
    assert rows_e == []


def test_seven_day_span_is_travel(db):
    start = 1700000000
    end = start + 86400 * 7
    _make_trip("C1", start, end, "七日遊")
    with get_conn() as conn:
        rows_t = _cp_trip(conn, "C1", "all")["rows"]
        rows_e = _cp_event(conn, "C1", "all")["rows"]
    assert len(rows_t) == 1
    assert rows_e == []


def test_null_end_date_is_event(db):
    start = 1700000000
    _make_trip("C1", start, None, "無結束日")
    with get_conn() as conn:
        rows_t = _cp_trip(conn, "C1", "all")["rows"]
        rows_e = _cp_event(conn, "C1", "all")["rows"]
    assert rows_t == []
    assert len(rows_e) == 1


def test_null_start_date_is_skipped(db):
    # 直接 SQL 強制 NULL start_date
    _make_trip("C1", 1700000000, 1700000000 + 86400 * 3)
    with get_conn() as conn:
        conn.execute("UPDATE trips SET start_date=NULL WHERE title='t'")
        conn.commit()
        kind_expr = _trip_kind_filter()
        rows_t = _cp_trip(conn, "C1", "all")["rows"]
        rows_e = _cp_event(conn, "C1", "all")["rows"]
        raw = conn.execute(
            f"SELECT {kind_expr} AS kind FROM trips").fetchall()
    # NULL start_date 應被排除，不計入 travel 也不計入 event
    assert rows_t == []
    assert rows_e == []
    assert all(r["kind"] is None for r in raw)