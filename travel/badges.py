"""Emoji 徽章邏輯（Phase 2）。介面預留給 Phase 2.5 fal.ai 替換。"""
import sqlite3
import time
import uuid
from typing import Literal

from travel.db import get_conn
from travel.trip_crud import get_trip, get_participants

ABROAD_KEYWORDS = {"日本", "韓國", "泰國", "美國", "歐洲", "海外", "法國", "德國", "義大利", "越南", "菲律賓", "馬來西亞", "新加坡", "澳洲", "英國"}

LOCATION_EMOJI: list[tuple[str, str]] = [
    ("墾丁", "🏖️"), ("海邊", "🏖️"), ("沙灘", "🏖️"), ("海灘", "🏖️"),
    ("山", "🏔️"), ("登山", "🏔️"), ("玉山", "🏔️"), ("合歡", "🏔️"),
    ("溫泉", "♨️"),
    ("露營", "🏕️"),
    ("日本", "✈️"), ("韓國", "✈️"), ("海外", "✈️"), ("出國", "✈️"),
    ("夜市", "🌃"), ("台北", "🌃"), ("城市", "🌃"),
]

RARITY_CIRCLE = {
    "common": "🟢",
    "rare": "🔵",
    "epic": "🟣",
    "legendary": "🟡",
}

RARITY_LABEL = {
    "common": "初心者",
    "rare": "旅行者",
    "epic": "冒險家",
    "legendary": "傳奇旅人",
}


def compute_rarity(trip: dict) -> Literal["common", "rare", "epic", "legendary"]:
    """依旅程天數、參與人數、地點判斷稀有度。"""
    location = trip.get("location") or ""
    if any(kw in location for kw in ABROAD_KEYWORDS):
        return "legendary"

    start = trip.get("start_date") or 0
    end = trip.get("end_date") or start
    days = max(1, round((end - start) / 86400))

    participants = trip.get("participants_count") or 0

    if days >= 5 or participants >= 6:
        return "epic"
    if days >= 3:
        return "rare"
    return "common"


def compute_badge_emoji(trip: dict, rarity: str) -> str:
    """依地點 + 稀有度產生 emoji 組合。"""
    location = trip.get("location") or ""
    loc_emoji = "🗺️"
    for keyword, emoji in LOCATION_EMOJI:
        if keyword in location:
            loc_emoji = emoji
            break
    return f"{loc_emoji}{RARITY_CIRCLE.get(rarity, '🟢')}"


def compute_badge_name(trip: dict, user_name: str, rarity: str) -> str:
    """產生徽章名稱。"""
    label = RARITY_LABEL.get(rarity, "旅行者")
    return f"{trip.get('title', '旅行')}・{user_name}・{label}"


def _insert_badge(
    user_id: str,
    trip_id: str,
    badge_type: str,
    badge_name: str,
    badge_rarity: str,
    badge_image_url: str | None,
    description: str,
    earned_at: int,
) -> str | None:
    """插入徽章，重複則回傳 None（UNIQUE 約束）。"""
    badge_id = str(uuid.uuid4())
    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO badges
                   (id, trip_id, user_id, badge_type, badge_name,
                    badge_rarity, badge_image_url, description, earned_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (badge_id, trip_id, user_id, badge_type, badge_name,
                 badge_rarity, badge_image_url, description, earned_at),
            )
        return badge_id
    except sqlite3.IntegrityError:
        return None


def award_badges_for_trip(trip_id: str) -> list[dict]:
    """對 trip 所有 participants 發 emoji 徽章。回傳新發放清單（已有的跳過）。"""
    trip = get_trip(trip_id)
    if not trip:
        return []
    participants = get_participants(trip_id)
    rarity = compute_rarity(trip)
    emoji = compute_badge_emoji(trip, rarity)
    earned_at = int(time.time())
    new_badges = []
    for p in participants:
        user_id = p["user_id"]
        user_name = p.get("user_name") or "旅伴"
        name = compute_badge_name(trip, user_name, rarity)
        badge_id = _insert_badge(
            user_id=user_id,
            trip_id=trip_id,
            badge_type="trip",
            badge_name=name,
            badge_rarity=rarity,
            badge_image_url=None,
            description=f"{trip['title']} 完成",
            earned_at=earned_at,
        )
        if badge_id:
            new_badges.append({
                "badge_id": badge_id,
                "user_id": user_id,
                "badge_emoji": emoji,
                "badge_rarity": rarity,
                "badge_name": name,
            })
    return new_badges


def get_ended_trips_without_badges() -> list[dict]:
    """回傳 status='ended' 且尚未發過 user-scoped 徽章的旅行。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT t.* FROM trips t
               WHERE t.status = 'ended'
                 AND NOT EXISTS (
                     SELECT 1 FROM badges b
                     WHERE b.trip_id = t.id AND b.user_id IS NOT NULL
                 )"""
        ).fetchall()
    return [dict(r) for r in rows]


def process_ended_trips() -> None:
    """APScheduler 觸發：對所有待發徽章旅行批次發放。"""
    import logging
    logger = logging.getLogger(__name__)
    trips = get_ended_trips_without_badges()
    for trip in trips:
        try:
            new_badges = award_badges_for_trip(trip["id"])
            logger.info(f"[BADGE] trip {trip['id']} 發放 {len(new_badges)} 枚徽章")
        except (sqlite3.Error, OSError) as e:
            logger.exception(f"[BADGE] trip {trip['id']} 失敗: {e}")