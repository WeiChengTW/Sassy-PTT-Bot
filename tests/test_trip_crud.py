"""測試 travel/trip_crud.py。"""
import os
import tempfile
import time
import pytest
from travel.db import init_db, get_conn
from travel.migrations import migrate


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


def test_create_trip_returns_id(db):
    from travel.trip_crud import create_trip
    trip_id = create_trip(
        group_id="C1", title="墾丁三日遊", location="墾丁",
        start_date=1700000000, trip_types=["beach"], created_by="U1",
    )
    assert isinstance(trip_id, str) and len(trip_id) > 0


def test_create_trip_persists_in_db(db):
    from travel.trip_crud import create_trip, get_trip
    trip_id = create_trip("C1", "富士山", "日本", 1700000000, "mountain", "U1")
    trip = get_trip(trip_id)
    assert trip is not None
    assert trip["title"] == "富士山"
    assert trip["status"] == "planning"


def test_add_participants_returns_counts(db):
    from travel.trip_crud import create_trip, add_participants
    trip_id = create_trip("C1", "旅行", "台北", 1700000000, None, "U1")
    result = add_participants(trip_id, ["U1", "U2", "U3"])
    assert result["added"] == 3
    assert result["total"] == 3


def test_add_participants_idempotent(db):
    from travel.trip_crud import create_trip, add_participants
    trip_id = create_trip("C1", "旅行", "台北", 1700000000, None, "U1")
    add_participants(trip_id, ["U1", "U2"])
    result = add_participants(trip_id, ["U1", "U3"])  # U1 already exists
    assert result["added"] == 1
    assert result["total"] == 3


def test_end_trip_sets_status(db):
    from travel.trip_crud import create_trip, end_trip, get_trip
    trip_id = create_trip("C1", "旅行", "台北", 1700000000, None, "U1")
    result = end_trip(trip_id)
    assert result["status"] == "ended"
    assert result["ended_at"] is not None
    trip = get_trip(trip_id)
    assert trip["status"] == "ended"


def test_get_participants_returns_list(db):
    from travel.trip_crud import create_trip, add_participants, get_participants
    trip_id = create_trip("C1", "旅行", "台北", 1700000000, None, "U1")
    add_participants(trip_id, ["U1", "U2"])
    participants = get_participants(trip_id)
    assert len(participants) == 2
    user_ids = {p["user_id"] for p in participants}
    assert {"U1", "U2"} == user_ids


def test_update_trip_details(db):
    from travel.trip_crud import create_trip, update_trip, get_trip
    trip_id = create_trip("C1", "舊名稱", "台北", 1700000000, None, "U1")
    res = update_trip(trip_id, title="新名稱", location="台南", rarity="epic")
    assert res["success"] is True
    trip = get_trip(trip_id)
    assert trip["title"] == "新名稱"
    assert trip["location"] == "台南"
    assert trip["rarity"] == "epic"


def test_update_trip_dates(db):
    from travel.trip_crud import create_trip, update_trip, get_trip
    trip_id = create_trip("C1", "測試", "loc", 1700000000, None, "U1")
    res = update_trip(trip_id, start_date=1700100000, end_date=1700200000)
    assert res["success"] is True
    trip = get_trip(trip_id)
    assert trip["start_date"] == 1700100000
    assert trip["end_date"] == 1700200000


def test_update_trip_clear_end_date(db):
    """管理員可清除 end_date（讓 travel 變回 event）。"""
    from travel.trip_crud import create_trip, update_trip, get_trip
    trip_id = create_trip("C1", "測試", "loc", 1700000000, None, "U1", end_date=1700200000)
    res = update_trip(trip_id, end_date=None)
    assert res["success"] is True
    trip = get_trip(trip_id)
    assert trip["end_date"] is None

def test_get_user_trips_participation_and_initiated(db):
    from travel.trip_crud import create_trip, add_participants, get_user_trips
    # U1 發起 t1 並參與；U2 只參與 t1；t2 由 U2 發起、U1 也參與
    t1 = create_trip("C1", "墾丁", "墾丁", 1700000000, ["beach"], created_by="U1")
    t2 = create_trip("C1", "武嶺", "武嶺", 1700100000, ["mountain"], created_by="U2")
    add_participants(t1, ["U1", "U2"])
    add_participants(t2, ["U1"])

    res = get_user_trips("U1", "C1")
    assert res["participated"] == 2
    assert res["initiated"] == 1  # 只有 t1 是 U1 發起
    # 依 start_date DESC：t2(較晚) 在前
    assert res["trips"][0]["title"] == "武嶺"
    assert res["trips"][0]["is_creator"] is False
    assert all("badge_emoji" in t for t in res["trips"])
