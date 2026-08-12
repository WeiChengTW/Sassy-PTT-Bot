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
        start_date=1700000000, trip_type="beach", created_by="U1",
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