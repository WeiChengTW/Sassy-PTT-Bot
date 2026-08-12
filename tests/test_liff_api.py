"""測試 telegram_bot/liff_api.py Flask Blueprint。"""
import os
import tempfile
import time
import pytest
from flask import Flask
from travel.db import init_db, insert_message
from travel.migrations import migrate
from travel.trip_crud import create_trip, add_participants, end_trip
from travel.badges import award_badges_for_trip


@pytest.fixture
def db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DB_PATH", path)
    monkeypatch.setenv("ADMIN_USER_IDS", "U_ADMIN")
    init_db()
    migrate()
    # seed 一筆 message 讓 U_MEMBER 成為 member
    insert_message({
        "line_message_id": "seed1",
        "group_id": "C1",
        "user_id": "U_MEMBER",
        "user_name": "Member",
        "type": "text",
        "content": "hello",
        "metadata": {},
        "reply_to_message_id": None,
        "timestamp": int(time.time() * 1000),
    })
    yield path
    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


@pytest.fixture
def client(db):
    from telegram_bot.liff_api import liff_bp
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(liff_bp)
    with app.test_client() as c:
        yield c


def _headers(user_id="U_MEMBER"):
    return {"X-LIFF-UserId": user_id, "X-LIFF-GroupId": "C1"}


def test_me_returns_role_member(client):
    r = client.get("/liff/me", headers=_headers("U_MEMBER"))
    assert r.status_code == 200
    data = r.get_json()
    assert data["role"] == "member"


def test_me_returns_role_admin(client):
    r = client.get("/liff/me", headers=_headers("U_ADMIN"))
    assert r.status_code == 200
    assert r.get_json()["role"] == "admin"


def test_dashboard_requires_group_id(client):
    r = client.get("/liff/dashboard", headers=_headers())
    assert r.status_code == 200
    assert "summary" in r.get_json()


def test_trips_returns_list(client, db):
    create_trip("C1", "測試旅行", "台北", 1700000000, None, "U_MEMBER")
    r = client.get("/liff/trips", headers={**_headers(), "X-LIFF-GroupId": "C1"})
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)


def test_badges_returns_list(client, db):
    r = client.get("/liff/badges/U_MEMBER", headers={**_headers(), "X-LIFF-GroupId": "C1"})
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)


def test_admin_create_trip(client):
    r = client.post(
        "/liff/admin/trips",
        json={"title": "新旅行", "location": "花蓮", "start_date": 1700000000},
        headers=_headers("U_ADMIN"),
    )
    assert r.status_code == 200
    data = r.get_json()
    assert "trip_id" in data


def test_admin_create_trip_forbidden_for_non_admin(client):
    r = client.post(
        "/liff/admin/trips",
        json={"title": "新旅行", "location": "花蓮", "start_date": 1700000000},
        headers=_headers("U_MEMBER"),
    )
    assert r.status_code == 403


def test_admin_end_trip(client):
    # setup
    trip_id = create_trip("C1", "t", "loc", 1700000000, None, "U_ADMIN")
    r = client.post(
        f"/liff/admin/trips/{trip_id}/end",
        headers=_headers("U_ADMIN"),
    )
    assert r.status_code == 200
    assert r.get_json()["status"] == "ended"


def test_admin_award_badges(client):
    trip_id = create_trip("C1", "t", "loc", 1700000000, None, "U_ADMIN")
    add_participants(trip_id, ["U_MEMBER"])
    end_trip(trip_id)
    r = client.post(
        f"/liff/admin/trips/{trip_id}/award-badges",
        headers=_headers("U_ADMIN"),
    )
    assert r.status_code == 200
    assert "awarded" in r.get_json()
