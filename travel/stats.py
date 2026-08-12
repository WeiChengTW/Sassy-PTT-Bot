"""Dashboard / trips / badges 查詢業務邏輯。被 liff_api.py 呼叫。"""
import time

from travel.db import get_conn
from travel.badges import compute_badge_emoji


def get_dashboard_data(group_id: str, days: int = 30) -> dict:
    """回傳群組儀表板資料。"""
    since_ms = int((time.time() - days * 86400) * 1000)
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE group_id=?", (group_id,)
        ).fetchone()[0]
        member_count = conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM messages WHERE group_id=?", (group_id,)
        ).fetchone()[0]
        active_trips = conn.execute(
            "SELECT COUNT(*) FROM trips WHERE group_id=? AND status='planning'", (group_id,)
        ).fetchone()[0]
        active_days = conn.execute(
            """SELECT COUNT(DISTINCT date(timestamp/1000, 'unixepoch'))
               FROM messages WHERE group_id=?""",
            (group_id,),
        ).fetchone()[0]

        top_users = conn.execute(
            """SELECT user_id, user_name, COUNT(*) AS total,
                      COUNT(DISTINCT date(timestamp/1000,'unixepoch')) AS active_days
               FROM messages WHERE group_id=?
               GROUP BY user_id ORDER BY total DESC LIMIT 10""",
            (group_id,),
        ).fetchall()

        type_dist = conn.execute(
            """SELECT type, COUNT(*) AS count FROM messages
               WHERE group_id=? GROUP BY type ORDER BY count DESC""",
            (group_id,),
        ).fetchall()

        daily_counts = conn.execute(
            """SELECT date(timestamp/1000,'unixepoch') AS date, COUNT(*) AS count
               FROM messages WHERE group_id=? AND timestamp >= ?
               GROUP BY date ORDER BY date ASC""",
            (group_id, since_ms),
        ).fetchall()

        heatmap = conn.execute(
            """SELECT CAST(strftime('%w', timestamp/1000,'unixepoch') AS INTEGER) AS day_of_week,
                      CAST(strftime('%H', timestamp/1000,'unixepoch') AS INTEGER) AS hour,
                      COUNT(*) AS count
               FROM messages WHERE group_id=?
               GROUP BY day_of_week, hour""",
            (group_id,),
        ).fetchall()

    return {
        "summary": {
            "total_messages": total,
            "active_days": active_days,
            "member_count": member_count,
            "active_trips": active_trips,
        },
        "top_users": [dict(r) for r in top_users],
        "type_distribution": [dict(r) for r in type_dist],
        "daily_counts": [dict(r) for r in daily_counts],
        "heatmap": [dict(r) for r in heatmap],
    }


def get_trips_list(group_id: str) -> list[dict]:
    """回傳群組所有旅行列表（含 badge_emoji）。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, title, location, start_date, end_date,
                      rarity, status, created_at
               FROM trips WHERE group_id=? ORDER BY created_at DESC""",
            (group_id,),
        ).fetchall()
    result = []
    for r in rows:
        trip = dict(r)
        rarity = trip.get("rarity") or "common"
        trip["badge_emoji"] = compute_badge_emoji(trip, rarity)
        result.append(trip)
    return result


def get_trip_detail(trip_id: str) -> dict:
    """回傳單一旅行詳情（含 participants）。"""
    with get_conn() as conn:
        trip_row = conn.execute(
            "SELECT * FROM trips WHERE id=?", (trip_id,)
        ).fetchone()
        participants_rows = conn.execute(
            """SELECT tp.user_id, tp.role, tp.joined_at, tp.messages_count,
                      (SELECT user_name FROM messages WHERE user_id=tp.user_id LIMIT 1) AS user_name
               FROM trip_participants tp WHERE tp.trip_id=?""",
            (trip_id,),
        ).fetchall()
        msg_count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE group_id=(SELECT group_id FROM trips WHERE id=?) AND timestamp BETWEEN (SELECT start_date*1000 FROM trips WHERE id=?) AND COALESCE((SELECT end_date*1000 FROM trips WHERE id=?), 9999999999999)",
            (trip_id, trip_id, trip_id),
        ).fetchone()[0]

    return {
        "trip": dict(trip_row) if trip_row else {},
        "participants": [dict(r) for r in participants_rows],
        "stats": {"message_count": msg_count},
        "memorable_quotes": [],
    }


def get_user_badges(user_id: str, group_id: str) -> list[dict]:
    """回傳 user 在某群組的所有徽章。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT b.id AS badge_id, b.badge_name, b.badge_rarity,
                      b.badge_image_url, b.earned_at, b.trip_id, b.description,
                      t.location
               FROM badges b
               LEFT JOIN trips t ON t.id = b.trip_id
               WHERE b.user_id=? AND (t.group_id=? OR t.group_id IS NULL)
                 AND b.user_id IS NOT NULL
               ORDER BY b.earned_at DESC""",
            (user_id, group_id),
        ).fetchall()
    result = []
    for r in rows:
        badge = dict(r)
        rarity = badge.get("badge_rarity") or "common"
        trip_info = {"location": badge.get("location") or ""}
        badge["badge_emoji"] = compute_badge_emoji(trip_info, rarity)
        result.append(badge)
    return result