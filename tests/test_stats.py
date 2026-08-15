"""測試 travel/stats.py。"""
import os
import tempfile
import time
import pytest
from travel.db import init_db, get_conn, insert_message
from travel.migrations import migrate
from travel.trip_crud import create_trip, add_participants, end_trip
from travel.badges import award_badges_for_trip


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


def _seed_messages(group_id="C1", n=5):
    now_ms = int(time.time() * 1000)
    for i in range(n):
        insert_message({
            "line_message_id": f"m{i}",
            "group_id": group_id,
            "user_id": f"U{i % 3 + 1}",
            "user_name": f"User{i % 3 + 1}",
            "type": "text",
            "content": f"msg {i}",
            "metadata": {},
            "reply_to_message_id": None,
            "timestamp": now_ms - i * 60000,
        })


def test_get_dashboard_data_returns_structure(db):
    from travel.stats import get_dashboard_data
    _seed_messages()
    data = get_dashboard_data("C1")
    assert "summary" in data
    assert "top_users" in data
    assert "type_distribution" in data
    assert "daily_counts" in data


def test_get_dashboard_data_summary_counts(db):
    from travel.stats import get_dashboard_data
    _seed_messages(n=5)
    data = get_dashboard_data("C1")
    assert data["summary"]["total_messages"] == 5
    assert data["summary"]["member_count"] >= 1


def test_get_trips_list_returns_list(db):
    from travel.stats import get_trips_list
    create_trip("C1", "墾丁", "墾丁海邊", 1700000000, "beach", "U1")
    trips = get_trips_list("C1")
    assert len(trips) == 1
    assert trips[0]["title"] == "墾丁"


def test_get_trip_detail_returns_detail(db):
    from travel.stats import get_trip_detail
    trip_id = create_trip("C1", "富士山", "日本", 1700000000, "mountain", "U1")
    add_participants(trip_id, ["U1", "U2"])
    detail = get_trip_detail(trip_id)
    assert detail["trip"]["id"] == trip_id
    assert len(detail["participants"]) == 2


def test_get_user_badges_returns_list(db):
    from travel.stats import get_user_badges
    trip_id = create_trip("C1", "旅行", "台北", 1700000000, None, "U1")
    add_participants(trip_id, ["U1"])
    end_trip(trip_id)
    award_badges_for_trip(trip_id)
    badges = get_user_badges("U1", "C1")
    assert len(badges) == 1
    assert badges[0]["badge_rarity"] is not None

# ─── 群組健康度 / 預測 ───────────────────────────────────────────────────────

def test_dashboard_includes_health_and_weekly_trend(db):
    from travel.stats import get_dashboard_data
    _seed_messages(n=10)
    data = get_dashboard_data("C1")
    assert "health" in data and "weekly_trend" in data
    h = data["health"]
    for key in ("overall", "activity", "diversity", "sentiment", "participation", "suggestions"):
        assert key in h
    assert 0 <= h["overall"] <= 100
    assert isinstance(h["suggestions"], list) and h["suggestions"]


def test_health_sentiment_none_when_unanalyzed(db):
    from travel.stats import get_dashboard_data
    _seed_messages(n=5)  # 無 sentiment 欄位
    h = get_dashboard_data("C1")["health"]
    assert h["sentiment"] is None
    # sentiment 缺席時 overall 仍應為有效數值
    assert 0 <= h["overall"] <= 100


def test_weekly_trend_structure(db):
    import time
    from travel.db import insert_message
    from travel.stats import get_dashboard_data
    now = int(time.time() * 1000)
    day = 86400 * 1000
    # 本週 5 則、上週 2 則
    for i in range(5):
        insert_message({
            "line_message_id": f"tw{i}", "group_id": "C1", "user_id": "U1",
            "user_name": "U1", "type": "text", "content": "hi", "metadata": {},
            "reply_to_message_id": None, "timestamp": now - i * 3600 * 1000,
        })
    for i in range(2):
        insert_message({
            "line_message_id": f"lw{i}", "group_id": "C1", "user_id": "U1",
            "user_name": "U1", "type": "text", "content": "hi", "metadata": {},
            "reply_to_message_id": None, "timestamp": now - 8 * day - i * 3600 * 1000,
        })
    wt = get_dashboard_data("C1")["weekly_trend"]
    assert "weeks" in wt
    assert wt["this_week"] >= 0
    assert isinstance(wt["weeks"], list)
