"""Dashboard / trips / badges 查詢業務邏輯。被 liff_api.py 呼叫。"""
import time
from collections import Counter

from travel.db import get_conn
from travel.badges import compute_badge_emoji
from travel.period import period_filter
from travel.trip_types import parse_trip_types


def get_dashboard_data(group_id: str, days: int = 30, period: str = "all") -> dict:
    """回傳群組儀表板資料。period 過濾套用於逐訊息統計。"""
    since_ms = int((time.time() - days * 86400) * 1000)
    pf, pp = period_filter(period)
    with get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM messages WHERE group_id=?{pf}", (group_id, *pp)
        ).fetchone()[0]
        member_count = conn.execute(
            f"SELECT COUNT(DISTINCT user_id) FROM messages WHERE group_id=?{pf}",
            (group_id, *pp),
        ).fetchone()[0]
        active_trips = conn.execute(
            "SELECT COUNT(*) FROM trips WHERE group_id=? AND status='planning'", (group_id,)
        ).fetchone()[0]
        active_days = conn.execute(
            f"""SELECT COUNT(DISTINCT date(timestamp/1000, 'unixepoch'))
               FROM messages WHERE group_id=?{pf}""",
            (group_id, *pp),
        ).fetchone()[0]

        top_users = conn.execute(
            f"""SELECT user_id, user_name, COUNT(*) AS total,
                      COUNT(DISTINCT date(timestamp/1000,'unixepoch')) AS active_days
               FROM messages WHERE group_id=?{pf}
               GROUP BY user_id ORDER BY total DESC LIMIT 10""",
            (group_id, *pp),
        ).fetchall()

        type_dist = conn.execute(
            f"""SELECT type, COUNT(*) AS count FROM messages
               WHERE group_id=?{pf} GROUP BY type ORDER BY count DESC""",
            (group_id, *pp),
        ).fetchall()

        # daily_counts：period 已選時用區間，否則用 days 視窗
        if pf:
            daily_counts = conn.execute(
                f"""SELECT date(timestamp/1000,'unixepoch') AS date, COUNT(*) AS count
                   FROM messages WHERE group_id=?{pf}
                   GROUP BY date ORDER BY date ASC""",
                (group_id, *pp),
            ).fetchall()
        else:
            daily_counts = conn.execute(
                """SELECT date(timestamp/1000,'unixepoch') AS date, COUNT(*) AS count
                   FROM messages WHERE group_id=? AND timestamp >= ?
                   GROUP BY date ORDER BY date ASC""",
                (group_id, since_ms),
            ).fetchall()

        heatmap = conn.execute(
            f"""SELECT CAST(strftime('%w', timestamp/1000,'unixepoch') AS INTEGER) AS day_of_week,
                      CAST(strftime('%H', timestamp/1000,'unixepoch') AS INTEGER) AS hour,
                      COUNT(*) AS count
               FROM messages WHERE group_id=?{pf}
               GROUP BY day_of_week, hour""",
            (group_id, *pp),
        ).fetchall()

        monthly_trend, seasonality = _monthly_and_seasonality(conn, group_id, period)

        # 旅行類型分佈：展開所有 trips 的 trip_type（JSON 陣列）計數
        trip_type_rows = conn.execute(
            "SELECT trip_type FROM trips WHERE group_id=?", (group_id,)
        ).fetchall()

    type_counter: Counter[str] = Counter()
    for tr in trip_type_rows:
        for t in parse_trip_types(tr["trip_type"]):
            type_counter[t] += 1
    trip_type_distribution = [
        {"type": t, "count": c} for t, c in type_counter.most_common()
    ]

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
        "monthly_trend": monthly_trend,
        "seasonality": seasonality,
        "trip_type_distribution": trip_type_distribution,
    }


def _monthly_and_seasonality(conn, group_id: str, period: str):
    """月成長率趨勢 + 季節性（跨年同月）。period=年時月趨勢限該年，季節性一律跨全期。"""
    from travel.period import parse_period
    start, end = parse_period(period)
    # 月趨勢：若 period 指定年，限該年；否則全部
    if start is not None:
        month_rows = conn.execute(
            """SELECT strftime('%Y-%m', timestamp/1000,'unixepoch') AS month,
                      COUNT(*) AS count
               FROM messages WHERE group_id=? AND timestamp >= ? AND timestamp < ?
               GROUP BY month ORDER BY month ASC""",
            (group_id, start, end),
        ).fetchall()
    else:
        month_rows = conn.execute(
            """SELECT strftime('%Y-%m', timestamp/1000,'unixepoch') AS month,
                      COUNT(*) AS count
               FROM messages WHERE group_id=?
               GROUP BY month ORDER BY month ASC""",
            (group_id,),
        ).fetchall()

    monthly_trend = []
    prev = None
    for r in month_rows:
        count = r["count"]
        growth = None
        if prev is not None and prev > 0:
            growth = round((count - prev) * 100.0 / prev, 1)
        monthly_trend.append({"month": r["month"], "count": count, "growth_rate_percent": growth})
        prev = count

    season_rows = conn.execute(
        """SELECT CAST(strftime('%m', timestamp/1000,'unixepoch') AS INTEGER) AS month,
                  COUNT(*) AS count
           FROM messages WHERE group_id=?
           GROUP BY month ORDER BY month ASC""",
        (group_id,),
    ).fetchall()
    seasonality = [{"month": r["month"], "count": r["count"]} for r in season_rows]

    return monthly_trend, seasonality


def get_trips_list(group_id: str) -> list[dict]:
    """回傳群組所有旅行列表（含 badge_emoji）。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, title, location, start_date, end_date,
                      rarity, status, created_at, trip_type
               FROM trips WHERE group_id=? ORDER BY created_at DESC""",
            (group_id,),
        ).fetchall()
    result = []
    for r in rows:
        trip = dict(r)
        rarity = trip.get("rarity") or "common"
        trip["badge_emoji"] = compute_badge_emoji(trip, rarity)
        trip["trip_types"] = parse_trip_types(trip.pop("trip_type", None))
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
                      COALESCE(
                        (SELECT user_name FROM messages WHERE user_id=tp.user_id LIMIT 1),
                        (SELECT display_name FROM members WHERE user_id=tp.user_id LIMIT 1)
                      ) AS user_name
               FROM trip_participants tp WHERE tp.trip_id=?""",
            (trip_id,),
        ).fetchall()
        msg_count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE group_id=(SELECT group_id FROM trips WHERE id=?) AND timestamp BETWEEN (SELECT start_date*1000 FROM trips WHERE id=?) AND COALESCE((SELECT end_date*1000 FROM trips WHERE id=?), 9999999999999)",
            (trip_id, trip_id, trip_id),
        ).fetchone()[0]

    trip = dict(trip_row) if trip_row else {}
    if trip:
        trip["trip_types"] = parse_trip_types(trip.get("trip_type"))

    return {
        "trip": trip,
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