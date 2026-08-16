"""Emoji 徽章邏輯（Phase 2）。介面預留給 Phase 2.5 fal.ai 替換。"""
import json
import os
import sqlite3
import time
import uuid
from typing import Literal

from travel.db import get_conn
from travel.trip_crud import get_trip, get_participants

ABROAD_KEYWORDS = {"日本", "韓國", "泰國", "美國", "歐洲", "海外", "法國", "德國", "義大利", "越南", "菲律賓", "馬來西亞", "新加坡", "澳洲", "英國"}

# 內建公開主題關鍵字（與地點、活動類型）。
# 群組專屬的私人綽號 / 暗語請放在 `BADGES_THEME_PATH` 指向的 JSON（gitignored），
# 格式：{"themes": [["關鍵字", "emoji"], ...]}
THEME_KEYWORDS_BASE: list[tuple[str, str]] = [
    # 具體活動/主題
    ("火鍋", "🍲"), ("鬆餅", "🥞"), ("美食", "🍜"), ("烤肉", "🍖"), ("吃", "🍽️"),
    ("水槍", "🔫"), ("保齡球", "🎳"), ("拍貼", "📸"), ("動物園", "🦁"), ("牧場", "🐮"), ("牛", "🐮"),
    ("傳單", "📄"), ("醉", "🍺"), ("酒", "🍻"), ("舞會", "💃"), ("變裝", "🎭"),
    ("修抽屜", "🪚"), ("美術", "🎨"),
    ("學測", "📝"), ("考", "✏️"), ("暑輔", "📚"), ("翹課", "🏃"), ("返校", "🏫"),
    ("教室", "💻"), ("google", "🌐"), ("地圖", "🗺️"), ("方向燈", "🚗"), ("車", "🚗"),
    ("火燒車", "🔥"), ("極地", "❄️"), ("求生", "⛺"), ("魔法", "🪄"), ("嚇一跳", "👻"),
    ("立牌", "🧍"), ("愛心", "💌"), ("小卡", "💌"), ("足跡", "👣"), ("疫情", "😷"),
    ("飛機", "✈️"), ("男模", "🕺"), ("教授", "🎓"),
    # 地點關鍵字
    ("墾丁", "🏖️"), ("海邊", "🏖️"), ("沙灘", "🏖️"), ("海灘", "🏖️"), ("南灣", "🏖️"), ("澎湖", "🏝️"),
    ("武嶺", "🏔️"), ("山", "🏔️"), ("登山", "🏔️"), ("玉山", "🏔️"), ("合歡", "🏔️"),
    ("宜蘭", "🦆"), ("溫泉", "♨️"),
    ("露營", "🏕️"),
    ("日本", "✈️"), ("韓國", "✈️"), ("海外", "✈️"), ("出國", "✈️"),
    ("台南", "🏯"), ("夜市", "🌃"), ("台北", "🌃"), ("城市", "🏙️"),
]


def _load_group_themes() -> list[tuple[str, str]]:
    """讀群組專屬主題關鍵字（私人綽號 / 暗語），gitignored 檔案，讀不到就略過。"""
    path = os.getenv("BADGES_THEME_PATH", "data/badges_theme.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    out: list[tuple[str, str]] = []
    for item in data.get("themes", []):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            kw, emoji = str(item[0]), str(item[1])
            if kw:
                out.append((kw, emoji))
    return out


def compute_badge_emoji(trip: dict, rarity: str = "") -> str:
    """優先使用自訂 custom_emoji，否則依旅程標題、地點或類型產生主題 emoji。"""
    if trip.get("custom_emoji"):
        return trip["custom_emoji"]
    title = trip.get("title") or ""
    location = trip.get("location") or ""
    types = trip.get("trip_type") or ""
    combined = f"{title} {location} {types}"

    for keyword, emoji in THEME_KEYWORDS_BASE:
        if keyword in combined:
            return emoji
    for keyword, emoji in _load_group_themes():
        if keyword in combined:
            return emoji
    return "🎒"


RARITY_LABEL = {
    "common": "普通",
    "rare": "稀有",
    "super_rare": "極稀有",
    "epic": "史詩",
    "legendary": "傳說",
}


def compute_rarity(trip: dict) -> Literal["common", "rare", "super_rare", "epic", "legendary"]:
    """依旅程天數、參與人數、地點判斷稀有度。"""
    location = trip.get("location") or ""
    if any(kw in location for kw in ABROAD_KEYWORDS):
        return "legendary"

    start = trip.get("start_date") or 0
    end = trip.get("ended_at") or trip.get("end_date") or start
    days = max(1, round((end - start) / 86400))

    participants = trip.get("participants_count") or 0

    if days >= 5 or participants >= 6:
        return "epic"
    if days >= 3:
        return "rare"
    return "common"


def compute_badge_name(trip: dict, user_name: str, rarity: str) -> str:
    """產生徽章名稱。"""
    label = RARITY_LABEL.get(rarity, "普通")
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
    trip["participants_count"] = len(participants)
    # 優先採用事件本身指定的稀有度（歷史回憶匯入），否則自動推算。
    rarity = trip.get("rarity") or compute_rarity(trip)
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