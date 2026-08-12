"""測試 travel/stats_extended.py 分析查詢。"""
import json
import os
import tempfile
import time
import pytest
from travel.db import init_db, get_conn


@pytest.fixture
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DB_PATH", path)
    init_db()
    yield path
    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


def _insert_msg(conn, *, msg_id, group_id="g1", user_id, user_name,
                msg_type="text", timestamp, reply_to=None,
                topics=None, sentiment=None):
    conn.execute(
        """INSERT INTO messages
           (line_message_id, group_id, user_id, user_name, type,
            timestamp, reply_to_message_id, topics, sentiment)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (msg_id, group_id, user_id, user_name, msg_type,
         timestamp, reply_to,
         json.dumps(topics) if topics else None, sentiment),
    )


# ─── leaderboard ─────────────────────────────────────────────────────────────

def test_leaderboard_rankings_order(temp_db):
    from travel.stats_extended import get_leaderboard_data
    now = int(time.time() * 1000)
    with get_conn() as conn:
        for i in range(3):
            _insert_msg(conn, msg_id=f"m{i}", user_id="uA", user_name="Alice", timestamp=now - i * 1000)
        _insert_msg(conn, msg_id="m3", user_id="uB", user_name="Bob", timestamp=now)
    data = get_leaderboard_data("g1")
    assert data["rankings"][0]["user_id"] == "uA"
    assert data["rankings"][0]["total"] == 3
    assert data["rankings"][1]["user_id"] == "uB"


def test_leaderboard_night_owl(temp_db):
    from travel.stats_extended import get_leaderboard_data
    # 凌晨 2 點 UTC = 2025-01-01 02:00:00 → timestamp in ms
    night_ts = 1735693200000  # 2025-01-01 02:00 UTC
    day_ts   = 1735722000000  # 2025-01-01 10:00 UTC
    with get_conn() as conn:
        _insert_msg(conn, msg_id="n1", user_id="uA", user_name="Alice", timestamp=night_ts)
        _insert_msg(conn, msg_id="n2", user_id="uA", user_name="Alice", timestamp=night_ts + 60000)
        _insert_msg(conn, msg_id="n3", user_id="uB", user_name="Bob",   timestamp=day_ts)
    data = get_leaderboard_data("g1")
    owls = data["night_owls"]
    assert owls[0]["user_id"] == "uA"
    assert owls[0]["night_count"] == 2


def test_leaderboard_type_distribution(temp_db):
    from travel.stats_extended import get_leaderboard_data
    now = int(time.time() * 1000)
    with get_conn() as conn:
        _insert_msg(conn, msg_id="t1", user_id="uA", user_name="A", msg_type="text",    timestamp=now)
        _insert_msg(conn, msg_id="t2", user_id="uA", user_name="A", msg_type="sticker", timestamp=now + 1)
        _insert_msg(conn, msg_id="t3", user_id="uA", user_name="A", msg_type="sticker", timestamp=now + 2)
    data = get_leaderboard_data("g1")
    dist = {d["type"]: d["count"] for d in data["type_distribution"]}
    assert dist["sticker"] == 2
    assert dist["text"] == 1


# ─── interactions ─────────────────────────────────────────────────────────────

def test_interaction_best_pairs(temp_db):
    from travel.stats_extended import get_interaction_data
    now = int(time.time() * 1000)
    with get_conn() as conn:
        _insert_msg(conn, msg_id="base1", user_id="uB", user_name="Bob",   timestamp=now)
        _insert_msg(conn, msg_id="rep1",  user_id="uA", user_name="Alice", timestamp=now + 1, reply_to="base1")
        _insert_msg(conn, msg_id="base2", user_id="uB", user_name="Bob",   timestamp=now + 2)
        _insert_msg(conn, msg_id="rep2",  user_id="uA", user_name="Alice", timestamp=now + 3, reply_to="base2")
    data = get_interaction_data("g1")
    pairs = data["best_pairs"]
    assert len(pairs) >= 1
    assert pairs[0]["count"] == 2
    ids = {pairs[0]["user1_id"], pairs[0]["user2_id"]}
    assert ids == {"uA", "uB"}


def test_interaction_network_nodes_and_edges(temp_db):
    from travel.stats_extended import get_interaction_data
    now = int(time.time() * 1000)
    with get_conn() as conn:
        _insert_msg(conn, msg_id="b1", user_id="uA", user_name="Alice", timestamp=now)
        _insert_msg(conn, msg_id="r1", user_id="uB", user_name="Bob",   timestamp=now + 1, reply_to="b1")
    data = get_interaction_data("g1")
    node_ids = {n["id"] for n in data["network_nodes"]}
    assert "uA" in node_ids and "uB" in node_ids
    assert len(data["network_edges"]) >= 1


# ─── topics ──────────────────────────────────────────────────────────────────

def test_topics_top_topics(temp_db):
    from travel.stats_extended import get_topics_data
    now = int(time.time() * 1000)
    with get_conn() as conn:
        _insert_msg(conn, msg_id="tp1", user_id="uA", user_name="A",
                    timestamp=now, topics=["旅行", "美食"])
        _insert_msg(conn, msg_id="tp2", user_id="uA", user_name="A",
                    timestamp=now + 1, topics=["旅行"])
    data = get_topics_data("g1")
    top = {t["topic"]: t["count"] for t in data["top_topics"]}
    assert top["旅行"] == 2
    assert top["美食"] == 1


def test_topics_daily_sentiment(temp_db):
    from travel.stats_extended import get_topics_data
    ts = 1735693200000  # 2025-01-01
    with get_conn() as conn:
        _insert_msg(conn, msg_id="s1", user_id="uA", user_name="A",
                    timestamp=ts, sentiment=0.8)
        _insert_msg(conn, msg_id="s2", user_id="uA", user_name="A",
                    timestamp=ts + 1000, sentiment=0.4)
    data = get_topics_data("g1")
    assert len(data["daily_sentiment"]) == 1
    assert abs(data["daily_sentiment"][0]["avg_sentiment"] - 0.6) < 0.01


# ─── profile ─────────────────────────────────────────────────────────────────

def test_profile_summary(temp_db):
    from travel.stats_extended import get_profile_data
    now = int(time.time() * 1000)
    with get_conn() as conn:
        for i in range(5):
            _insert_msg(conn, msg_id=f"p{i}", user_id="uA", user_name="A",
                        timestamp=now + i * 1000)
    data = get_profile_data("uA", "g1")
    assert data["summary"]["total"] == 5


def test_profile_time_slots(temp_db):
    from travel.stats_extended import get_profile_data
    # 凌晨 2 點 (hour=2)，白天 10 點 (hour=10)
    night_ts = 1735693200000  # 02:00 UTC
    day_ts   = 1735722000000  # 10:00 UTC
    with get_conn() as conn:
        _insert_msg(conn, msg_id="ps1", user_id="uA", user_name="A", timestamp=night_ts)
        _insert_msg(conn, msg_id="ps2", user_id="uA", user_name="A", timestamp=day_ts)
    data = get_profile_data("uA", "g1")
    slots = data["time_slots"]
    assert slots["night"] == 1    # 0-4
    assert slots["daytime"] == 1  # 9-17


def test_profile_top_topics(temp_db):
    from travel.stats_extended import get_profile_data
    now = int(time.time() * 1000)
    with get_conn() as conn:
        _insert_msg(conn, msg_id="pt1", user_id="uA", user_name="A",
                    timestamp=now, topics=["旅行"])
        _insert_msg(conn, msg_id="pt2", user_id="uA", user_name="A",
                    timestamp=now + 1, topics=["旅行", "美食"])
    data = get_profile_data("uA", "g1")
    topics = {t["topic"]: t["count"] for t in data["top_topics"]}
    assert topics["旅行"] == 2
