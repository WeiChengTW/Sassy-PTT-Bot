"""測試 line_bot/liff_api.py Flask Blueprint。"""
import os
import tempfile
import time
import pytest
from flask import Flask
from travel.db import init_db, insert_message, get_conn
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
    from line_bot.liff_api import liff_bp
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


def test_badges_without_group_context_returns_user_badges(client, db):
    # 先在 C1 為 U_MEMBER 建立 trip 與發放徽章
    trip_id = create_trip("C1", "花蓮遊", "花蓮", 1700000000, None, "U_ADMIN")
    add_participants(trip_id, ["U_MEMBER"])
    end_trip(trip_id)
    award_badges_for_trip(trip_id)

    # 模擬個人從 1:1 或 Rich Menu 打開 LIFF（無 X-LIFF-GroupId）
    r = client.get("/liff/badges/U_MEMBER", headers={"X-LIFF-UserId": "U_MEMBER"})
    assert r.status_code == 200
    badges = r.get_json()
    assert isinstance(badges, list)
    assert len(badges) >= 1
    assert badges[0]["trip_id"] == trip_id


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


def test_admin_update_trip(client):
    trip_id = create_trip("C1", "舊名稱", "loc", 1700000000, None, "U_ADMIN")
    r = client.post(
        f"/liff/admin/trips/{trip_id}/update",
        json={"title": "更新後的名稱", "location": "花蓮", "rarity": "legendary"},
        headers=_headers("U_ADMIN"),
    )
    assert r.status_code == 200
    assert r.get_json()["title"] == "更新後的名稱"
    assert r.get_json()["location"] == "花蓮"
    assert r.get_json()["rarity"] == "legendary"


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


def test_dashboard_requires_member(client):
    # U_MEMBER 在 C1 有 message,但要求 group_id=C2 → 不算 member
    r = client.get("/liff/dashboard", headers={**_headers("U_MEMBER"), "X-LIFF-GroupId": "C2"})
    assert r.status_code == 403
    assert r.get_json()["reason"] == "not_member"


def test_trips_requires_member(client):
    r = client.get("/liff/trips", headers={**_headers("U_MEMBER"), "X-LIFF-GroupId": "C2"})
    assert r.status_code == 403
    assert r.get_json()["reason"] == "not_member"


def test_trip_detail_cross_group_forbidden(client, db):
    # 在 C1 建一個 trip,C2 的 member 嘗試存取
    insert_message({
        "line_message_id": "seed_c2",
        "group_id": "C2",
        "user_id": "U_MEMBER",
        "user_name": "Member",
        "type": "text",
        "content": "hello c2",
        "metadata": {},
        "reply_to_message_id": None,
        "timestamp": int(time.time() * 1000),
    })
    trip_id = create_trip("C1", "t", "loc", 1700000000, None, "U_ADMIN")
    r = client.get(
        f"/liff/trips/{trip_id}",
        headers={**_headers("U_MEMBER"), "X-LIFF-GroupId": "C2"},
    )
    assert r.status_code == 403


def test_badges_self_or_admin(client, db):
    # 一般 member (U_MEMBER) 要求看 U_OTHER 的 badges → 403
    r = client.get(
        "/liff/badges/U_OTHER",
        headers={**_headers("U_MEMBER"), "X-LIFF-GroupId": "C1"},
    )
    assert r.status_code == 403
    # 改成看自己 → 200
    r = client.get(
        "/liff/badges/U_MEMBER",
        headers={**_headers("U_MEMBER"), "X-LIFF-GroupId": "C1"},
    )
    assert r.status_code == 200
    # admin 看別人 → 200
    r = client.get(
        "/liff/badges/U_OTHER",
        headers={**_headers("U_ADMIN"), "X-LIFF-GroupId": "C1"},
    )
    assert r.status_code == 200


@pytest.fixture
def temp_db(db):
    return db


def test_leaderboard_endpoint_member(client, temp_db, monkeypatch):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (line_message_id, group_id, user_id, user_name, type, timestamp) VALUES (?,?,?,?,?,?)",
            ("ml1", "gTest", "uMember", "Member", "text", 1000000),
        )
    res = client.get("/liff/leaderboard",
                     headers={"X-LIFF-UserId": "uMember", "X-LIFF-GroupId": "gTest"})
    assert res.status_code == 200
    data = res.get_json()
    assert "rankings" in data
    assert "night_owls" in data


def test_leaderboard_endpoint_forbidden(client, temp_db):
    res = client.get("/liff/leaderboard",
                     headers={"X-LIFF-UserId": "stranger", "X-LIFF-GroupId": "gTest"})
    assert res.status_code == 403


def test_interactions_endpoint(client, temp_db):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (line_message_id, group_id, user_id, user_name, type, timestamp) VALUES (?,?,?,?,?,?)",
            ("mi1", "gTest", "uMember", "Member", "text", 1000000),
        )
    res = client.get("/liff/interactions",
                     headers={"X-LIFF-UserId": "uMember", "X-LIFF-GroupId": "gTest"})
    assert res.status_code == 200
    data = res.get_json()
    assert "best_pairs" in data and "network_nodes" in data


def test_topics_endpoint(client, temp_db):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (line_message_id, group_id, user_id, user_name, type, timestamp) VALUES (?,?,?,?,?,?)",
            ("mt1", "gTest", "uMember", "Member", "text", 1000000),
        )
    res = client.get("/liff/topics",
                     headers={"X-LIFF-UserId": "uMember", "X-LIFF-GroupId": "gTest"})
    assert res.status_code == 200
    data = res.get_json()
    assert "top_topics" in data and "daily_sentiment" in data


def test_profile_endpoint_self(client, temp_db):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (line_message_id, group_id, user_id, user_name, type, timestamp) VALUES (?,?,?,?,?,?)",
            ("mp1", "gTest", "uMember", "Member", "text", 1000000),
        )
    res = client.get("/liff/profile/uMember",
                     headers={"X-LIFF-UserId": "uMember", "X-LIFF-GroupId": "gTest"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["summary"]["total"] == 1


def test_profile_endpoint_not_self_forbidden(client, temp_db):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (line_message_id, group_id, user_id, user_name, type, timestamp) VALUES (?,?,?,?,?,?)",
            ("mp2", "gTest", "uMember", "Member", "text", 1000001),
        )
    res = client.get("/liff/profile/uMember",
                     headers={"X-LIFF-UserId": "stranger", "X-LIFF-GroupId": "gTest"})
    assert res.status_code == 403


# ─── pulse / compare endpoints ───────────────────────────────────────────────

def test_pulse_endpoint(client):
    r = client.get("/liff/pulse", headers=_headers("U_MEMBER"))
    assert r.status_code == 200
    data = r.get_json()
    for key in ("response_speed", "bursts", "lurkers"):
        assert key in data


def test_pulse_requires_member(client):
    # 完全沒有任何訊息的陌生人 → 無法 fallback，會被 gate
    r = client.get("/liff/pulse",
                   headers={"X-LIFF-UserId": "U_STRANGER", "X-LIFF-GroupId": "C2"})
    assert r.status_code == 403
    assert r.get_json()["reason"] == "not_member"


def test_compare_missing_users_400(client):
    r = client.get("/liff/compare?a=U_MEMBER", headers=_headers("U_MEMBER"))
    assert r.status_code == 400
    assert r.get_json()["error"] == "missing_users"


def test_compare_endpoint(client):
    # 再塞一位成員 U2 到 C1
    insert_message({
        "line_message_id": "seed2", "group_id": "C1", "user_id": "U2",
        "user_name": "Member2", "type": "text", "content": "hey", "metadata": {},
        "reply_to_message_id": None, "timestamp": int(time.time() * 1000),
    })
    r = client.get("/liff/compare?a=U_MEMBER&b=U2", headers=_headers("U_MEMBER"))
    assert r.status_code == 200
    data = r.get_json()
    assert data["a"]["user_id"] == "U_MEMBER"
    assert data["b"]["user_id"] == "U2"
    assert "similarity" in data


def test_compare_requires_member(client):
    r = client.get("/liff/compare?a=U_MEMBER&b=U2",
                   headers={"X-LIFF-UserId": "U_STRANGER", "X-LIFF-GroupId": "C2"})
    assert r.status_code == 403
