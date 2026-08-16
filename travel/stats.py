"""Dashboard / trips / badges 查詢業務邏輯。被 liff_api.py 呼叫。"""
import json
import time
from collections import Counter

from travel.db import get_conn
from travel.badges import compute_badge_emoji
from travel.period import period_filter
from travel.trip_types import parse_trip_types


def get_dashboard_data(group_id: str, days: int = 30, period: str = "all") -> dict:
    """回傳群組儀表板資料。period 過濾套用於逐訊息統計，排除非正式成員的純記憶匯入訊息。"""
    since_ms = int((time.time() - days * 86400) * 1000)
    pf, pp = period_filter(period)
    with get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM messages WHERE group_id=?{pf} AND user_id NOT LIKE 'imported:%'", (group_id, *pp)
        ).fetchone()[0]
        member_count = conn.execute(
            f"SELECT COUNT(DISTINCT user_id) FROM messages WHERE group_id=?{pf} AND user_id NOT LIKE 'imported:%'",
            (group_id, *pp),
        ).fetchone()[0]
        active_trips = conn.execute(
            "SELECT COUNT(*) FROM trips WHERE group_id=? AND status='planning'", (group_id,)
        ).fetchone()[0]
        active_days = conn.execute(
            f"""SELECT COUNT(DISTINCT date(timestamp/1000, 'unixepoch'))
               FROM messages WHERE group_id=?{pf} AND user_id NOT LIKE 'imported:%'""",
            (group_id, *pp),
        ).fetchone()[0]

        top_users = conn.execute(
            f"""SELECT user_id, user_name, COUNT(*) AS total,
                      COUNT(DISTINCT date(timestamp/1000,'unixepoch')) AS active_days
               FROM messages WHERE group_id=?{pf} AND user_id NOT LIKE 'imported:%'
               GROUP BY user_id ORDER BY total DESC LIMIT 10""",
            (group_id, *pp),
        ).fetchall()

        type_dist = conn.execute(
            f"""SELECT type, COUNT(*) AS count FROM messages
               WHERE group_id=?{pf} AND user_id NOT LIKE 'imported:%' GROUP BY type ORDER BY count DESC""",
            (group_id, *pp),
        ).fetchall()

        # daily_counts：period 已選時用區間，否則用 days 視窗
        if pf:
            daily_counts = conn.execute(
                f"""SELECT date(timestamp/1000,'unixepoch') AS date, COUNT(*) AS count
                   FROM messages WHERE group_id=?{pf} AND user_id NOT LIKE 'imported:%'
                   GROUP BY date ORDER BY date ASC""",
                (group_id, *pp),
            ).fetchall()
        else:
            daily_counts = conn.execute(
                """SELECT date(timestamp/1000,'unixepoch') AS date, COUNT(*) AS count
                   FROM messages WHERE group_id=? AND timestamp >= ? AND user_id NOT LIKE 'imported:%'
                   GROUP BY date ORDER BY date ASC""",
                (group_id, since_ms),
            ).fetchall()

        heatmap = conn.execute(
            f"""SELECT CAST(strftime('%w', timestamp/1000,'unixepoch') AS INTEGER) AS day_of_week,
                      CAST(strftime('%H', timestamp/1000,'unixepoch') AS INTEGER) AS hour,
                      COUNT(*) AS count
               FROM messages WHERE group_id=?{pf} AND user_id NOT LIKE 'imported:%'
               GROUP BY day_of_week, hour""",
            (group_id, *pp),
        ).fetchall()

        # 近期以日期維度的每日 24 小時熱力分佈 (供精確日期檢視)
        recent_date_heatmap = conn.execute(
            f"""SELECT date(timestamp/1000,'unixepoch') AS date,
                      CAST(strftime('%H', timestamp/1000,'unixepoch') AS INTEGER) AS hour,
                      COUNT(*) AS count
               FROM messages WHERE group_id=?{pf} AND user_id NOT LIKE 'imported:%'
               GROUP BY date, hour ORDER BY date DESC, hour ASC""",
            (group_id, *pp),
        ).fetchall()

        monthly_trend, seasonality = _monthly_and_seasonality(conn, group_id, period)

        health = _compute_group_health(conn, group_id, pf, pp)
        weekly_trend = _compute_weekly_trend(conn, group_id)

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
        "recent_date_heatmap": [dict(r) for r in recent_date_heatmap],
        "monthly_trend": monthly_trend,
        "seasonality": seasonality,
        "trip_type_distribution": trip_type_distribution,
        "health": health,
        "weekly_trend": weekly_trend,
    }


def _compute_group_health(conn, group_id: str, pf: str, pp: list) -> dict:
    """群組健康度：活躍度 / 多樣性 / 情緒 / 參與度 綜合 0-100 分。

    情緒分項在無 sentiment 資料時自動略過（不列入加權）。分項門檻產生中文建議。
    活躍度、多樣性、參與度皆套用傳入的 period 過濾（pf/pp）。
    """
    total = conn.execute(
        f"SELECT COUNT(*) FROM messages WHERE group_id=?{pf}", (group_id, *pp)
    ).fetchone()[0]
    active_days = conn.execute(
        f"""SELECT COUNT(DISTINCT date(timestamp/1000,'unixepoch'))
           FROM messages WHERE group_id=?{pf}""",
        (group_id, *pp),
    ).fetchone()[0] or 0
    active_senders = conn.execute(
        f"SELECT COUNT(DISTINCT user_id) FROM messages WHERE group_id=?{pf}",
        (group_id, *pp),
    ).fetchone()[0] or 0

    # 活躍度：活躍日的日均訊息
    daily_avg = total / active_days if active_days else 0.0
    activity_score = min(100.0, daily_avg * 10)

    # 多樣性：不同話題數（解析 topics JSON）
    topic_rows = conn.execute(
        f"""SELECT topics FROM messages
           WHERE group_id=?{pf} AND topics IS NOT NULL AND topics != '[]'""",
        (group_id, *pp),
    ).fetchall()
    distinct_topics: set[str] = set()
    for r in topic_rows:
        try:
            for t in json.loads(r["topics"]):
                distinct_topics.add(t)
        except (json.JSONDecodeError, TypeError):
            pass
    diversity_score = min(100.0, len(distinct_topics) * 10)

    # 情緒：AVG(sentiment) → 0-100（無資料則 None）
    avg_sentiment = conn.execute(
        f"""SELECT AVG(sentiment) FROM messages
           WHERE group_id=?{pf} AND sentiment IS NOT NULL""",
        (group_id, *pp),
    ).fetchone()[0]
    sentiment_score = (avg_sentiment + 1) * 50 if avg_sentiment is not None else None

    # 參與度：活躍發言者 / 名冊總數（名冊為空時退回以發言者為分母 → 100%）
    roster = conn.execute(
        "SELECT COUNT(*) FROM members WHERE group_id=?", (group_id,)
    ).fetchone()[0] or 0
    denom = roster if roster else active_senders
    participation_score = (active_senders / denom * 100) if denom else 0.0

    # 加權（情緒缺席時按比例重新分配權重）
    weights = {"activity": 0.30, "diversity": 0.25, "sentiment": 0.25, "participation": 0.20}
    scores = {
        "activity": activity_score,
        "diversity": diversity_score,
        "sentiment": sentiment_score,
        "participation": participation_score,
    }
    present = {k: v for k, v in scores.items() if v is not None}
    wsum = sum(weights[k] for k in present) or 1.0
    overall = sum(scores[k] * weights[k] for k in present) / wsum

    suggestions: list[str] = []
    if participation_score < 60:
        suggestions.append("多鼓勵潛水員發言")
    if diversity_score < 50:
        suggestions.append("增加話題多樣性")
    if sentiment_score is not None and sentiment_score < 50:
        suggestions.append("群組氣氛偏低，試著帶點正能量")
    if activity_score < 40:
        suggestions.append("互動偏少，試著開啟新話題")
    if not suggestions:
        suggestions.append("群組狀態健康，繼續保持！")

    return {
        "overall": round(overall),
        "activity": round(activity_score),
        "diversity": round(diversity_score),
        "sentiment": round(sentiment_score) if sentiment_score is not None else None,
        "participation": round(participation_score),
        "suggestions": suggestions,
    }


def _compute_weekly_trend(conn, group_id: str, weeks: int = 8) -> dict:
    """最近 N 週的每週訊息量與活躍人數 + 本週 vs 上週成長率。

    以現在往回推的滾動視窗（不套 period），缺資料的週補 0。
    """
    now_ms = int(time.time() * 1000)
    day_ms = 86_400_000
    since = now_ms - weeks * 7 * day_ms
    rows = conn.execute(
        """SELECT strftime('%Y-%W', timestamp/1000,'unixepoch') AS week,
                  COUNT(*) AS count,
                  COUNT(DISTINCT user_id) AS active_users
           FROM messages WHERE group_id=? AND timestamp >= ?
           GROUP BY week ORDER BY week ASC""",
        (group_id, since),
    ).fetchall()

    series = [
        {"week": r["week"], "count": r["count"], "active_users": r["active_users"]}
        for r in rows
    ]
    this_week = series[-1]["count"] if series else 0
    last_week = series[-2]["count"] if len(series) >= 2 else 0
    growth = (
        round((this_week - last_week) * 100.0 / last_week, 1) if last_week > 0 else None
    )

    return {
        "weeks": series,
        "this_week": this_week,
        "last_week": last_week,
        "growth_percent": growth,
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
                      rarity, status, created_at, trip_type, custom_emoji
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
                        (SELECT user_name FROM messages WHERE user_id=tp.user_id AND group_id=t.group_id LIMIT 1),
                        (SELECT display_name FROM members WHERE user_id=tp.user_id LIMIT 1)
                      ) AS user_name
               FROM trip_participants tp
               JOIN trips t ON t.id = tp.trip_id
               WHERE tp.trip_id=?""",
            (trip_id,),
        ).fetchall()
        
        trip = dict(trip_row) if trip_row else {}
        gid = trip.get("group_id")
        st = trip.get("start_date")
        et = trip.get("end_date")

        if gid and st:
            if et:
                # end_date 當天 23:59:59
                end_ts_ms = (et + 86400) * 1000 - 1
            elif trip.get("status") == "ended":
                # 單日事件若已結束但無 end_date，計算出發日當天 24 小時內訊息
                end_ts_ms = (st + 86400) * 1000 - 1
            else:
                # 進行中的旅行
                end_ts_ms = int(time.time() * 1000)

            start_ts_ms = st * 1000
            msg_count = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE group_id=? AND timestamp BETWEEN ? AND ?",
                (gid, start_ts_ms, end_ts_ms),
            ).fetchone()[0]
        else:
            msg_count = 0

    if trip:
        trip["trip_types"] = parse_trip_types(trip.get("trip_type"))

    return {
        "trip": trip,
        "participants": [dict(r) for r in participants_rows],
        "stats": {"message_count": msg_count},
        "memorable_quotes": [],
    }


def get_user_badges(user_id: str, group_id: str | None = None) -> list[dict]:
    """回傳 user 在某群組（若有指定）或全部的所有徽章。"""
    with get_conn() as conn:
        if group_id:
            rows = conn.execute(
                """SELECT b.id AS badge_id, b.badge_name, b.badge_rarity,
                          b.badge_image_url, b.earned_at, b.trip_id, b.description,
                          t.title, t.location, t.trip_type, t.start_date, t.end_date, t.custom_emoji
                   FROM badges b
                   LEFT JOIN trips t ON t.id = b.trip_id
                   WHERE b.user_id=? AND (t.group_id=? OR t.group_id IS NULL)
                     AND b.user_id IS NOT NULL
                   ORDER BY COALESCE(t.start_date, b.earned_at) DESC""",
                (user_id, group_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT b.id AS badge_id, b.badge_name, b.badge_rarity,
                          b.badge_image_url, b.earned_at, b.trip_id, b.description,
                          t.title, t.location, t.trip_type, t.start_date, t.end_date, t.custom_emoji
                   FROM badges b
                   LEFT JOIN trips t ON t.id = b.trip_id
                   WHERE b.user_id=? AND b.user_id IS NOT NULL
                   ORDER BY COALESCE(t.start_date, b.earned_at) DESC""",
                (user_id,),
            ).fetchall()
    result = []
    for r in rows:
        badge = dict(r)
        rarity = badge.get("badge_rarity") or "common"
        trip_info = {
            "title": badge.get("title") or "",
            "location": badge.get("location") or "",
            "trip_type": badge.get("trip_type") or "",
            "custom_emoji": badge.get("custom_emoji") or "",
        }
        badge["badge_emoji"] = compute_badge_emoji(trip_info, rarity)
        result.append(badge)
    return result