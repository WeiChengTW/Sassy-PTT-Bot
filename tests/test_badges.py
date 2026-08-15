"""測試 travel/badges.py。"""
import os
import tempfile
import time
import pytest
from travel.db import init_db, get_conn
from travel.migrations import migrate
from travel.trip_crud import create_trip, add_participants, end_trip


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


def test_compute_rarity_common_short_trip(db):
    from travel.badges import compute_rarity
    trip = {"start_date": 1700000000, "end_date": 1700000000 + 86400, "participants_count": 2, "location": "台北"}
    assert compute_rarity(trip) == "common"


def test_compute_rarity_rare_3_days(db):
    from travel.badges import compute_rarity
    trip = {"start_date": 1700000000, "end_date": 1700000000 + 3 * 86400, "participants_count": 3, "location": "台中"}
    assert compute_rarity(trip) == "rare"


def test_compute_rarity_epic_5_days(db):
    from travel.badges import compute_rarity
    trip = {"start_date": 1700000000, "end_date": 1700000000 + 5 * 86400, "participants_count": 3, "location": "花蓮"}
    assert compute_rarity(trip) == "epic"


def test_compute_rarity_epic_many_participants(db):
    from travel.badges import compute_rarity
    trip = {"start_date": 1700000000, "end_date": 1700000000 + 86400, "participants_count": 6, "location": "台南"}
    assert compute_rarity(trip) == "epic"


def test_compute_rarity_legendary_abroad(db):
    from travel.badges import compute_rarity
    trip = {"start_date": 1700000000, "end_date": 1700000000 + 3 * 86400, "participants_count": 3, "location": "日本大阪"}
    assert compute_rarity(trip) == "legendary"


def test_compute_rarity_uses_ended_at_when_end_date_missing(db):
    """Regression: end_date may be None in production, compute_rarity must use ended_at."""
    from travel.badges import compute_rarity
    trip = {
        "start_date": 1700000000,
        "ended_at": 1700000000 + 3 * 86400,
        "participants_count": 3,
        "location": "台中",
    }
    assert compute_rarity(trip) == "rare"


def test_compute_badge_emoji_beach(db):
    from travel.badges import compute_badge_emoji
    trip = {"location": "墾丁海邊"}
    emoji = compute_badge_emoji(trip, "epic")
    assert emoji == "🏖️🔴"


def test_compute_badge_emoji_fallback(db):
    from travel.badges import compute_badge_emoji
    trip = {"location": "未知地方"}
    emoji = compute_badge_emoji(trip, "common")
    assert emoji == "🗺️🟢"


def test_award_badges_for_trip_writes_db(db):
    from travel.badges import award_badges_for_trip
    trip_id = create_trip("C1", "墾丁三日遊", "墾丁", 1700000000, "beach", "U1")
    add_participants(trip_id, ["U1", "U2"])
    end_trip(trip_id)
    badges = award_badges_for_trip(trip_id)
    assert len(badges) == 2
    with get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM badges WHERE trip_id=? AND user_id IS NOT NULL", (trip_id,)
        ).fetchone()[0]
    assert count == 2


def test_award_badges_idempotent(db):
    from travel.badges import award_badges_for_trip
    trip_id = create_trip("C1", "測試旅行", "台北", 1700000000, None, "U1")
    add_participants(trip_id, ["U1"])
    end_trip(trip_id)
    award_badges_for_trip(trip_id)
    second = award_badges_for_trip(trip_id)
    assert second == []  # already awarded, nothing new

    with get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM badges WHERE trip_id=? AND user_id IS NOT NULL", (trip_id,)
        ).fetchone()[0]
    assert count == 1


def test_get_ended_trips_without_badges(db):
    from travel.badges import get_ended_trips_without_badges
    trip_id = create_trip("C1", "旅行", "台北", 1700000000, None, "U1")
    add_participants(trip_id, ["U1"])
    end_trip(trip_id)
    trips = get_ended_trips_without_badges()
    ids = [t["id"] for t in trips]
    assert trip_id in ids