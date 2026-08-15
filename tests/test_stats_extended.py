"""測試 travel/stats_extended.py 分析查詢。"""
import json
import os
import tempfile
import time
import pytest
from travel.db import init_db, get_conn
from travel.migrations import migrate


@pytest.fixture
def temp_db(monkeypatch):
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


def test_topics_weekly_trend(temp_db):
    from travel.stats_extended import get_topics_data
    ts = 1735693200000  # 2025-01-01
    with get_conn() as conn:
        _insert_msg(conn, msg_id="w1", user_id="uA", user_name="A",
                    timestamp=ts, topics=["旅行"])
    data = get_topics_data("g1")
    assert len(data["weekly_trend"]) == 1
    assert "旅行" in data["weekly_trend"][0]["topics"]


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


# ─── 個人頁擴充 ───────────────────────────────────────────────────────────────

# 一天 = 86_400_000 ms。用固定基準日避免跨時區邊界。
_DAY = 86_400_000
_BASE = 1735689600000  # 2025-01-01 00:00 UTC


def test_milestones_streak_and_busiest(temp_db):
    from travel.stats_extended import get_user_milestones
    with get_conn() as conn:
        # Day0: 3 則（單日最高），Day1: 1 則，Day2: 1 則（連續 3 天）；Day5: 1 則（斷開）
        for i in range(3):
            _insert_msg(conn, msg_id=f"d0_{i}", user_id="uA", user_name="A",
                        timestamp=_BASE + 3600000 + i)
        _insert_msg(conn, msg_id="d1", user_id="uA", user_name="A", timestamp=_BASE + _DAY + 3600000)
        _insert_msg(conn, msg_id="d2", user_id="uA", user_name="A", timestamp=_BASE + 2 * _DAY + 3600000)
        _insert_msg(conn, msg_id="d5", user_id="uA", user_name="A", timestamp=_BASE + 5 * _DAY + 3600000)
    m = get_user_milestones("uA", "g1")
    assert m["total"] == 6
    assert m["busiest_day"]["count"] == 3
    assert m["longest_streak"]["days"] == 3
    assert m["nth"] is None  # 未達 100 門檻


def test_milestones_nth_threshold(temp_db):
    from travel.stats_extended import get_user_milestones
    with get_conn() as conn:
        for i in range(105):
            _insert_msg(conn, msg_id=f"x{i}", user_id="uA", user_name="A", timestamp=_BASE + i * 1000)
    m = get_user_milestones("uA", "g1")
    assert m["nth"]["n"] == 100
    assert m["nth"]["timestamp"] == _BASE + 99 * 1000


def test_daily_series_cumulative(temp_db):
    from travel.stats_extended import get_user_daily_series
    with get_conn() as conn:
        _insert_msg(conn, msg_id="s0", user_id="uA", user_name="A", timestamp=_BASE + 3600000, sentiment=0.5)
        _insert_msg(conn, msg_id="s1", user_id="uA", user_name="A", timestamp=_BASE + _DAY + 3600000, sentiment=-0.2)
        _insert_msg(conn, msg_id="s2", user_id="uA", user_name="A", timestamp=_BASE + _DAY + 7200000, sentiment=0.4)
    d = get_user_daily_series("uA", "g1")
    assert [g["cumulative"] for g in d["growth"]] == [1, 3]
    assert len(d["sentiment_series"]) == 2
    assert d["sentiment_series"][1]["avg_sentiment"] == 0.1  # avg(-0.2, 0.4)


def test_social_circle_bidirectional_and_shared_topics(temp_db):
    from travel.stats_extended import get_user_social_circle
    with get_conn() as conn:
        # B 的原訊息，A 回覆 B（A→B）；再 B 回覆 A 的訊息（B→A）→ 合併計 2
        _insert_msg(conn, msg_id="b1", user_id="uB", user_name="Bob", timestamp=_BASE + 1, topics=["旅行"])
        _insert_msg(conn, msg_id="a1", user_id="uA", user_name="Alice", timestamp=_BASE + 2,
                    reply_to="b1", topics=["旅行"])
        _insert_msg(conn, msg_id="b2", user_id="uB", user_name="Bob", timestamp=_BASE + 3,
                    reply_to="a1")
    circle = get_user_social_circle("uA", "g1")
    assert circle[0]["user_id"] == "uB"
    assert circle[0]["count"] == 2
    assert circle[0]["name"] == "Bob"
    assert "旅行" in circle[0]["shared_topics"]


def test_profile_extras_bundles_all_sections(temp_db):
    from travel.stats_extended import get_profile_extras
    with get_conn() as conn:
        _insert_msg(conn, msg_id="e1", user_id="uA", user_name="A", timestamp=_BASE + 1)
    extras = get_profile_extras("uA", "g1")
    for key in ("milestones", "growth", "sentiment_series", "social_circle", "footprints", "badges"):
        assert key in extras
    assert extras["footprints"]["participated"] == 0


# ─── pulse（群組動態）───────────────────────────────────────────────────────

def test_pulse_response_speed(temp_db):
    from travel.stats_extended import get_pulse_data
    with get_conn() as conn:
        _insert_msg(conn, msg_id="b1", user_id="uB", user_name="Bob", timestamp=_BASE)
        # uA 於 5 分鐘後回覆 b1
        _insert_msg(conn, msg_id="a1", user_id="uA", user_name="Alice",
                    timestamp=_BASE + 5 * 60000, reply_to="b1")
        _insert_msg(conn, msg_id="a2", user_id="uA", user_name="Alice",
                    timestamp=_BASE + 15 * 60000, reply_to="b1")
    data = get_pulse_data("g1")
    rs = data["response_speed"]
    assert rs["avg_minutes"] == 10.0  # (5+15)/2
    assert rs["reply_count"] == 2
    assert rs["fastest_responders"][0]["user_id"] == "uA"
    assert rs["fastest_responders"][0]["avg_minutes"] == 10.0


def test_pulse_ignores_self_reply_and_over_24h(temp_db):
    from travel.stats_extended import get_pulse_data
    with get_conn() as conn:
        _insert_msg(conn, msg_id="b1", user_id="uB", user_name="Bob", timestamp=_BASE)
        # 自我回覆（同人）應被忽略
        _insert_msg(conn, msg_id="b2", user_id="uB", user_name="Bob",
                    timestamp=_BASE + 60000, reply_to="b1")
        # 超過 24h 的回覆應被忽略
        _insert_msg(conn, msg_id="a1", user_id="uA", user_name="Alice",
                    timestamp=_BASE + 25 * 3600000, reply_to="b1")
    data = get_pulse_data("g1")
    assert data["response_speed"]["reply_count"] == 0
    assert data["response_speed"]["avg_minutes"] is None


def test_pulse_lurkers(temp_db):
    import time
    from travel.stats_extended import get_pulse_data
    now = int(time.time() * 1000)
    with get_conn() as conn:
        # 名冊三人
        for uid, name in [("uA", "Alice"), ("uB", "Bob"), ("uC", "Carol")]:
            conn.execute(
                "INSERT INTO members (group_id, user_id, display_name) VALUES (?,?,?)",
                ("g1", uid, name),
            )
        # uA 今天發言、uB 10 天前、uC 從未發言
        _insert_msg(conn, msg_id="a1", user_id="uA", user_name="Alice", timestamp=now)
        _insert_msg(conn, msg_id="b1", user_id="uB", user_name="Bob",
                    timestamp=now - 10 * 86400000)
    data = get_pulse_data("g1")
    lurker_ids = {l["user_id"] for l in data["lurkers"]}
    assert lurker_ids == {"uB", "uC"}
    uc = next(l for l in data["lurkers"] if l["user_id"] == "uC")
    assert uc["days_inactive"] is None


def test_pulse_bursts(temp_db):
    from travel.stats_extended import get_pulse_data
    with get_conn() as conn:
        # 同一小時塞 10 則（爆發），另外兩小時各 1 則
        for i in range(10):
            _insert_msg(conn, msg_id=f"burst{i}", user_id="uA", user_name="A",
                        timestamp=_BASE + i)
        _insert_msg(conn, msg_id="q1", user_id="uA", user_name="A",
                    timestamp=_BASE + 3600000)
        _insert_msg(conn, msg_id="q2", user_id="uA", user_name="A",
                    timestamp=_BASE + 2 * 3600000)
    data = get_pulse_data("g1")
    assert data["bursts"]
    assert data["bursts"][0]["count"] == 10


# ─── compare（成員對比）─────────────────────────────────────────────────────

def test_compare_basic(temp_db):
    from travel.stats_extended import get_compare_data
    with get_conn() as conn:
        for i in range(5):
            _insert_msg(conn, msg_id=f"a{i}", user_id="uA", user_name="Alice",
                        timestamp=_BASE + i)
        _insert_msg(conn, msg_id="b0", user_id="uB", user_name="Bob", timestamp=_BASE)
    data = get_compare_data("g1", "uA", "uB")
    assert data["a"]["user_id"] == "uA"
    assert data["a"]["total"] == 5
    assert data["b"]["total"] == 1
    assert 0 <= data["similarity"] <= 100


def test_compare_identical_users_high_similarity(temp_db):
    from travel.stats_extended import get_compare_data
    with get_conn() as conn:
        for i in range(3):
            _insert_msg(conn, msg_id=f"a{i}", user_id="uA", user_name="Alice",
                        timestamp=_BASE + i)
            _insert_msg(conn, msg_id=f"b{i}", user_id="uB", user_name="Bob",
                        timestamp=_BASE + i)
    data = get_compare_data("g1", "uA", "uB")
    # 兩人資料完全對稱 → 相似度應很高
    assert data["similarity"] >= 90
