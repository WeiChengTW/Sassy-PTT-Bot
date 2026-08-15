"""旅行 CRUD 業務邏輯。被 liff_api.py 呼叫，不依賴 Flask。"""
import sqlite3
import time
import uuid

from travel.db import get_conn
from travel.trip_types import normalize_trip_types, parse_trip_types


def create_trip(
    group_id: str,
    title: str,
    location: str,
    start_date: int,
    trip_types: list[str] | str | None,
    created_by: str,
) -> str:
    """建立旅行，回傳 trip_id（UUID）。trip_types 正規化成 JSON 陣列字串儲存。"""
    trip_id = str(uuid.uuid4())
    now = int(time.time())
    trip_type = normalize_trip_types(trip_types)
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO trips
               (id, group_id, title, location, start_date, trip_type, created_by, created_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'planning')""",
            (trip_id, group_id, title, location, start_date, trip_type, created_by, now),
        )
    return trip_id


def get_trip(trip_id: str) -> dict | None:
    """取得單一旅行資料，不存在回傳 None。"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
    return dict(row) if row else None


def add_participants(trip_id: str, user_ids: list[str]) -> dict[str, int]:
    """批次加入參與者。回傳 {added, total}。重複 user_id 略過。"""
    now = int(time.time())
    added = 0
    with get_conn() as conn:
        for uid in user_ids:
            try:
                conn.execute(
                    "INSERT INTO trip_participants (trip_id, user_id, joined_at) VALUES (?, ?, ?)",
                    (trip_id, uid, now),
                )
                added += 1
            except sqlite3.IntegrityError:
                pass  # duplicate PRIMARY KEY → skip
        total = conn.execute(
            "SELECT COUNT(*) FROM trip_participants WHERE trip_id = ?", (trip_id,)
        ).fetchone()[0]
    return {"added": added, "total": total}


def end_trip(trip_id: str) -> dict:
    """結束旅行：status='ended'，記錄 ended_at。"""
    ended_at = int(time.time())
    with get_conn() as conn:
        conn.execute(
            "UPDATE trips SET status='ended', ended_at=? WHERE id=?",
            (ended_at, trip_id),
        )
    return {"trip_id": trip_id, "status": "ended", "ended_at": ended_at}


def update_trip(trip_id: str, title: str | None = None, location: str | None = None, rarity: str | None = None) -> dict:
    """更新旅行名稱、地點、稀有度，並同步更新關聯的徽章。"""
    old_trip = get_trip(trip_id)
    if not old_trip:
        raise ValueError("Trip not found")

    updates = []
    params = []
    old_title = old_trip.get("title", "")
    new_title = old_title

    if title is not None:
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("Title cannot be empty")
        updates.append("title = ?")
        params.append(clean_title)
        new_title = clean_title

    if location is not None:
        updates.append("location = ?")
        params.append(location.strip() or None)

    if rarity is not None:
        valid_rarities = {"common", "rare", "super_rare", "epic", "legendary"}
        clean_rarity = rarity.strip()
        if clean_rarity not in valid_rarities:
            raise ValueError(f"Invalid rarity: {rarity}")
        updates.append("rarity = ?")
        params.append(clean_rarity)

    if not updates:
        return {"trip_id": trip_id, "success": True}

    params.append(trip_id)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE trips SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        # 若有修改標題或稀有度，同步更新 badges
        if title is not None and old_title:
            conn.execute(
                "UPDATE badges SET badge_name = REPLACE(badge_name, ?, ?) WHERE trip_id = ?",
                (old_title, new_title, trip_id),
            )
        if rarity is not None:
            conn.execute(
                "UPDATE badges SET badge_rarity = ? WHERE trip_id = ?",
                (rarity.strip(), trip_id),
            )

    updated_trip = get_trip(trip_id)
    return {
        "trip_id": trip_id,
        "title": updated_trip.get("title"),
        "location": updated_trip.get("location"),
        "rarity": updated_trip.get("rarity"),
        "success": True,
    }


def update_trip_title(trip_id: str, title: str) -> dict:
    """相容舊介面：更新旅行名稱。"""
    return update_trip(trip_id, title=title)


def get_anniversary_trips(days_ago: int = 365, window: int = 1) -> list[dict]:
    """Return ended trips whose ended_at falls within [days_ago±window] days from now."""
    now = int(time.time())
    low = now - (days_ago + window) * 86400
    high = now - (days_ago - window) * 86400
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT t.*, COUNT(tp.user_id) AS participants_count
               FROM trips t
               LEFT JOIN trip_participants tp ON tp.trip_id = t.id
               WHERE t.status = 'ended'
                 AND t.ended_at IS NOT NULL
                 AND t.ended_at BETWEEN ? AND ?
               GROUP BY t.id""",
            (low, high),
        ).fetchall()
    return [dict(r) for r in rows]


def get_participants(trip_id: str) -> list[dict]:
    """取得旅行所有參與者，嘗試 JOIN messages 拿 user_name。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT tp.user_id, tp.role, tp.joined_at, tp.messages_count,
                      COALESCE(
                        (SELECT user_name FROM messages
                         WHERE user_id = tp.user_id AND user_name IS NOT NULL
                         LIMIT 1),
                        (SELECT display_name FROM members
                         WHERE user_id = tp.user_id LIMIT 1)
                      ) AS user_name
               FROM trip_participants tp
               WHERE tp.trip_id = ?""",
            (trip_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_user_trips(user_id: str, group_id: str) -> dict:
    """個人旅行足跡：使用者參與過的旅行 + 參與／發起計數。"""
    from travel.badges import compute_badge_emoji

    with get_conn() as conn:
        rows = conn.execute(
            """SELECT t.* FROM trips t
               JOIN trip_participants tp ON tp.trip_id = t.id
               WHERE tp.user_id = ? AND t.group_id = ?
               ORDER BY t.start_date DESC""",
            (user_id, group_id),
        ).fetchall()

    trips = []
    initiated = 0
    for r in rows:
        trip = dict(r)
        rarity = trip.get("rarity") or "common"
        is_creator = trip.get("created_by") == user_id
        if is_creator:
            initiated += 1
        trips.append({
            "id": trip.get("id"),
            "title": trip.get("title"),
            "location": trip.get("location"),
            "start_date": trip.get("start_date"),
            "end_date": trip.get("end_date"),
            "rarity": rarity,
            "status": trip.get("status"),
            "trip_types": parse_trip_types(trip.get("trip_type")),
            "badge_emoji": compute_badge_emoji(trip, rarity),
            "is_creator": is_creator,
        })
    return {"trips": trips, "participated": len(trips), "initiated": initiated}