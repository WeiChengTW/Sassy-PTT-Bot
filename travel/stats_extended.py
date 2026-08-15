"""Phase 3 分析查詢：排行榜、互動關係、話題分析、個人檔案。"""
import json
from travel.db import get_conn
from travel.period import period_filter


def _sentiment_bucket(s: float) -> str:
    if s >= 0.5:
        return "非常正面"
    if s >= 0.2:
        return "正面"
    if s > -0.2:
        return "中性"
    if s > -0.5:
        return "負面"
    return "非常負面"


def get_leaderboard_data(group_id: str, period: str = "all") -> dict:
    pf, pp = period_filter(period)
    with get_conn() as conn:
        rankings = conn.execute(
            f"""SELECT user_id, user_name,
                      COUNT(*) AS total,
                      SUM(CASE WHEN type='text'    THEN 1 ELSE 0 END) AS text_count,
                      SUM(CASE WHEN type='sticker' THEN 1 ELSE 0 END) AS sticker_count,
                      SUM(CASE WHEN type='image'   THEN 1 ELSE 0 END) AS image_count,
                      SUM(CASE WHEN type='video'   THEN 1 ELSE 0 END) AS video_count
               FROM messages WHERE group_id=?{pf}
               GROUP BY user_id ORDER BY total DESC LIMIT 20""",
            (group_id, *pp),
        ).fetchall()

        night_owls = conn.execute(
            f"""SELECT user_id, user_name, COUNT(*) AS night_count
               FROM messages
               WHERE group_id=?{pf}
                 AND CAST(strftime('%H', timestamp/1000, 'unixepoch') AS INTEGER) BETWEEN 0 AND 4
               GROUP BY user_id ORDER BY night_count DESC LIMIT 10""",
            (group_id, *pp),
        ).fetchall()

        type_dist = conn.execute(
            f"""SELECT type, COUNT(*) AS count FROM messages
               WHERE group_id=?{pf} GROUP BY type ORDER BY count DESC""",
            (group_id, *pp),
        ).fetchall()

        badge_rankings = conn.execute(
            """SELECT b.user_id,
                      COALESCE(
                        (SELECT display_name FROM members WHERE user_id=b.user_id LIMIT 1),
                        (SELECT user_name FROM messages WHERE user_id=b.user_id AND user_name IS NOT NULL ORDER BY timestamp DESC LIMIT 1)
                      ) AS user_name,
                      COUNT(*) AS badge_count,
                      SUM(CASE WHEN b.badge_rarity='legendary' THEN 1 ELSE 0 END) AS legendary_count,
                      SUM(CASE WHEN b.badge_rarity='epic' THEN 1 ELSE 0 END) AS epic_count,
                      SUM(CASE WHEN b.badge_rarity='super_rare' THEN 1 ELSE 0 END) AS super_rare_count,
                      SUM(CASE WHEN b.badge_rarity='rare' THEN 1 ELSE 0 END) AS rare_count,
                      SUM(CASE WHEN b.badge_rarity='common' THEN 1 ELSE 0 END) AS common_count,
                      ROUND(
                          SUM(CASE WHEN b.badge_rarity='legendary' THEN 2.0 ELSE 0.0 END) +
                          SUM(CASE WHEN b.badge_rarity='epic' THEN 1.5 ELSE 0.0 END) +
                          SUM(CASE WHEN b.badge_rarity='super_rare' THEN 1.0 ELSE 0.0 END) +
                          SUM(CASE WHEN b.badge_rarity='rare' THEN 0.8 ELSE 0.0 END) +
                          SUM(CASE WHEN b.badge_rarity='common' THEN 0.5 ELSE 0.0 END)
                      , 1) AS score
               FROM badges b
               LEFT JOIN trips t ON t.id = b.trip_id
               WHERE b.user_id IS NOT NULL AND (t.group_id=? OR t.group_id IS NULL)
               GROUP BY b.user_id
               ORDER BY badge_count DESC, legendary_count DESC, epic_count DESC, super_rare_count DESC""",
            (group_id,),
        ).fetchall()

    return {
        "rankings": [dict(r) for r in rankings],
        "night_owls": [dict(r) for r in night_owls],
        "type_distribution": [dict(r) for r in type_dist],
        "badge_rankings": [dict(r) for r in badge_rankings],
    }


def get_interaction_data(group_id: str, period: str = "all") -> dict:
    pf, pp = period_filter(period, "a.timestamp")
    with get_conn() as conn:
        # Best pairs via reply JOIN — sort by count DESC, deduplicate (A,B)==(B,A)
        raw_pairs = conn.execute(
            f"""SELECT a.user_id AS user1_id, a.user_name AS user1_name,
                      b.user_id AS user2_id, b.user_name AS user2_name,
                      COUNT(*) AS count
               FROM messages a
               JOIN messages b ON a.reply_to_message_id = b.line_message_id
               WHERE a.group_id=? AND b.group_id=? AND a.user_id != b.user_id{pf}
               GROUP BY a.user_id, b.user_id
               ORDER BY count DESC LIMIT 40""",
            (group_id, group_id, *pp),
        ).fetchall()

        # Merge (A→B) and (B→A) pairs
        pair_map: dict[tuple, dict] = {}
        for r in raw_pairs:
            key = tuple(sorted([r["user1_id"], r["user2_id"]]))
            if key not in pair_map:
                pair_map[key] = {
                    "user1_id": r["user1_id"], "user1_name": r["user1_name"],
                    "user2_id": r["user2_id"], "user2_name": r["user2_name"],
                    "count": r["count"],
                }
            else:
                pair_map[key]["count"] += r["count"]
        best_pairs = sorted(pair_map.values(), key=lambda x: -x["count"])[:10]

        npf, npp = period_filter(period)
        nodes_rows = conn.execute(
            f"""SELECT user_id AS id, user_name AS name, COUNT(*) AS message_count
               FROM messages WHERE group_id=?{npf}
               GROUP BY user_id""",
            (group_id, *npp),
        ).fetchall()

    return {
        "best_pairs": best_pairs,
        "network_nodes": [dict(r) for r in nodes_rows],
        "network_edges": [
            {"source": p["user1_id"], "target": p["user2_id"], "weight": p["count"]}
            for p in best_pairs
        ],
    }


def get_topics_data(group_id: str, period: str = "all") -> dict:
    pf, pp = period_filter(period)
    with get_conn() as conn:
        topic_rows = conn.execute(
            f"""SELECT topics FROM messages
               WHERE group_id=?{pf} AND topics IS NOT NULL AND topics != '[]'""",
            (group_id, *pp),
        ).fetchall()

        keyword_rows = conn.execute(
            f"""SELECT keywords FROM messages
               WHERE group_id=?{pf} AND keywords IS NOT NULL AND keywords != '[]'""",
            (group_id, *pp),
        ).fetchall()

        sentiment_rows = conn.execute(
            f"""SELECT date(timestamp/1000,'unixepoch') AS date,
                      AVG(sentiment) AS avg_sentiment
               FROM messages
               WHERE group_id=?{pf} AND sentiment IS NOT NULL
               GROUP BY date ORDER BY date ASC""",
            (group_id, *pp),
        ).fetchall()

        weekly_rows = conn.execute(
            f"""SELECT strftime('%Y-W%W', timestamp/1000,'unixepoch') AS week, topics
               FROM messages
               WHERE group_id=?{pf} AND topics IS NOT NULL AND topics != '[]'
               ORDER BY week""",
            (group_id, *pp),
        ).fetchall()

        # 情緒五級分佈
        sent_all = conn.execute(
            f"""SELECT sentiment FROM messages
               WHERE group_id=?{pf} AND sentiment IS NOT NULL""",
            (group_id, *pp),
        ).fetchall()

        # 各話題平均情緒（fixed-bucket topic → avg sentiment）
        topic_sent_rows = conn.execute(
            f"""SELECT topics, sentiment FROM messages
               WHERE group_id=?{pf} AND topics IS NOT NULL AND topics != '[]'
                 AND sentiment IS NOT NULL""",
            (group_id, *pp),
        ).fetchall()

        # 熱門地點
        loc_rows = conn.execute(
            f"""SELECT locations FROM messages
               WHERE group_id=?{pf} AND locations IS NOT NULL AND locations != '[]'""",
            (group_id, *pp),
        ).fetchall()

        # 精選語錄：原話有內容、情緒最鮮明（絕對值最大 = 最正面或最負面）
        quote_rows = conn.execute(
            f"""SELECT user_name, content, summary, sentiment, timestamp FROM messages
               WHERE group_id=?{pf} AND type='text'
                 AND content IS NOT NULL AND length(content) > 1
                 AND sentiment IS NOT NULL
               ORDER BY ABS(sentiment) DESC, timestamp DESC LIMIT 10""",
            (group_id, *pp),
        ).fetchall()

    # topic counts
    topic_counter: dict[str, int] = {}
    for r in topic_rows:
        try:
            for t in json.loads(r["topics"]):
                topic_counter[t] = topic_counter.get(t, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    top_topics = sorted(
        [{"topic": k, "count": v} for k, v in topic_counter.items()],
        key=lambda x: -x["count"],
    )[:20]

    # keyword counts（過濾長度<2 雜訊）
    kw_counter: dict[str, int] = {}
    for r in keyword_rows:
        try:
            for k in json.loads(r["keywords"]):
                k = str(k).strip()
                if len(k) >= 2:
                    kw_counter[k] = kw_counter.get(k, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    top_keywords = sorted(
        [{"keyword": k, "count": v} for k, v in kw_counter.items()],
        key=lambda x: -x["count"],
    )[:30]

    # weekly trend
    weekly: dict[str, dict[str, int]] = {}
    for r in weekly_rows:
        week = r["week"]
        weekly.setdefault(week, {})
        try:
            for t in json.loads(r["topics"]):
                weekly[week][t] = weekly[week].get(t, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    weekly_trend = [{"week": w, "topics": counts} for w, counts in sorted(weekly.items())]

    # sentiment distribution
    dist_counter: dict[str, int] = {}
    for r in sent_all:
        dist_counter[_sentiment_bucket(r["sentiment"])] = \
            dist_counter.get(_sentiment_bucket(r["sentiment"]), 0) + 1
    total_sent = sum(dist_counter.values()) or 1
    order = ["非常正面", "正面", "中性", "負面", "非常負面"]
    sentiment_distribution = [
        {"category": c, "count": dist_counter.get(c, 0),
         "percentage": round(dist_counter.get(c, 0) * 100.0 / total_sent, 1)}
        for c in order if dist_counter.get(c, 0) > 0
    ]

    # topic sentiment
    ts_sum: dict[str, float] = {}
    ts_cnt: dict[str, int] = {}
    for r in topic_sent_rows:
        try:
            topics = json.loads(r["topics"])
        except (json.JSONDecodeError, TypeError):
            continue
        for t in topics:
            ts_sum[t] = ts_sum.get(t, 0.0) + r["sentiment"]
            ts_cnt[t] = ts_cnt.get(t, 0) + 1
    topic_sentiment = sorted(
        [{"topic": t, "avg_sentiment": round(ts_sum[t] / ts_cnt[t], 3), "count": ts_cnt[t]}
         for t in ts_sum],
        key=lambda x: -x["avg_sentiment"],
    )

    # hot locations
    loc_counter: dict[str, int] = {}
    for r in loc_rows:
        try:
            for loc in json.loads(r["locations"]):
                loc = str(loc).strip()
                if loc:
                    loc_counter[loc] = loc_counter.get(loc, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    hot_locations = sorted(
        [{"location": k, "count": v} for k, v in loc_counter.items()],
        key=lambda x: -x["count"],
    )[:15]

    highlight_quotes = [
        {"user_name": r["user_name"], "content": r["content"],
         "summary": r["summary"],
         "sentiment": round(r["sentiment"], 3),
         "tone": "positive" if r["sentiment"] >= 0 else "negative",
         "timestamp": r["timestamp"]}
        for r in quote_rows
    ]

    with get_conn() as conn:
        last_row = conn.execute(
            """SELECT MAX(analyzed_at) AS last_analyzed_at,
                      COUNT(CASE WHEN analyzed_at IS NULL AND content IS NOT NULL AND type='text' AND length(content) > 1 THEN 1 END) AS unanalyzed_count
               FROM messages WHERE group_id=?""",
            (group_id,),
        ).fetchone()
    last_analyzed_at = last_row["last_analyzed_at"] if last_row else None
    unanalyzed_count = last_row["unanalyzed_count"] if last_row else 0

    return {
        "top_topics": top_topics,
        "top_keywords": top_keywords,
        "weekly_trend": weekly_trend,
        "daily_sentiment": [dict(r) for r in sentiment_rows],
        "sentiment_distribution": sentiment_distribution,
        "topic_sentiment": topic_sentiment,
        "hot_locations": hot_locations,
        "highlight_quotes": highlight_quotes,
        "last_analyzed_at": last_analyzed_at,
        "unanalyzed_count": unanalyzed_count,
    }


def _compute_personality(type_breakdown, time_slots, avg_sentiment, total) -> list[dict]:
    """由訊息類型比例、時段、平均情緒推導人格標籤。"""
    if not total:
        return [{"tag": "潛水中", "reason": "還沒有足夠訊息"}]
    counts = {t["type"]: t["count"] for t in type_breakdown}
    sticker = counts.get("sticker", 0)
    image = counts.get("image", 0)
    text = counts.get("text", 0)
    tags = []
    if sticker * 100.0 / total > 50:
        tags.append({"tag": "貼圖狂魔", "reason": f"{round(sticker*100.0/total)}% 都是貼圖"})
    if image * 100.0 / total > 30:
        tags.append({"tag": "攝影大師", "reason": f"{round(image*100.0/total)}% 是圖片"})
    if text * 100.0 / total > 80:
        tags.append({"tag": "文字控", "reason": f"{round(text*100.0/total)}% 是純文字"})

    slot_total = sum(time_slots.values()) or 1
    top_slot = max(time_slots, key=time_slots.get)
    slot_pct = round(time_slots[top_slot] * 100.0 / slot_total)
    if top_slot == "night":
        tags.append({"tag": "夜貓子", "reason": f"{slot_pct}% 在深夜 0-4 點發言"})
    elif top_slot == "daytime":
        tags.append({"tag": "日行性", "reason": f"{slot_pct}% 在白天 9-17 點發言"})

    if avg_sentiment is not None:
        if avg_sentiment > 0.4:
            tags.append({"tag": "正能量大使", "reason": f"平均情緒 {round(avg_sentiment,2)}"})
        elif avg_sentiment < -0.2:
            tags.append({"tag": "毒舌代表", "reason": f"平均情緒 {round(avg_sentiment,2)}"})

    if not tags:
        tags.append({"tag": "均衡型", "reason": "各類訊息比例平均"})
    return tags


def get_profile_data(user_id: str, group_id: str, period: str = "all") -> dict:
    pf, pp = period_filter(period)
    with get_conn() as conn:
        summary_row = conn.execute(
            f"""SELECT COUNT(*) AS total,
                      COUNT(DISTINCT date(timestamp/1000,'unixepoch')) AS active_days,
                      MIN(timestamp) AS first_seen,
                      MAX(timestamp) AS last_seen
               FROM messages WHERE user_id=? AND group_id=?{pf}""",
            (user_id, group_id, *pp),
        ).fetchone()

        type_rows = conn.execute(
            f"""SELECT type, COUNT(*) AS count FROM messages
               WHERE user_id=? AND group_id=?{pf} GROUP BY type ORDER BY count DESC""",
            (user_id, group_id, *pp),
        ).fetchall()

        hourly_rows = conn.execute(
            f"""SELECT CAST(strftime('%H', timestamp/1000,'unixepoch') AS INTEGER) AS hour,
                      COUNT(*) AS count
               FROM messages WHERE user_id=? AND group_id=?{pf}
               GROUP BY hour ORDER BY hour""",
            (user_id, group_id, *pp),
        ).fetchall()

        topic_rows = conn.execute(
            f"""SELECT topics FROM messages
               WHERE user_id=? AND group_id=?{pf}
                 AND topics IS NOT NULL AND topics != '[]'""",
            (user_id, group_id, *pp),
        ).fetchall()

        sentiment_row = conn.execute(
            f"""SELECT AVG(sentiment) AS avg_sentiment FROM messages
               WHERE user_id=? AND group_id=?{pf} AND sentiment IS NOT NULL""",
            (user_id, group_id, *pp),
        ).fetchone()

    hour_map: dict[int, int] = {r["hour"]: r["count"] for r in hourly_rows}
    time_slots = {
        "night":   sum(hour_map.get(h, 0) for h in range(0, 5)),
        "morning": sum(hour_map.get(h, 0) for h in range(5, 9)),
        "daytime": sum(hour_map.get(h, 0) for h in range(9, 18)),
        "evening": sum(hour_map.get(h, 0) for h in range(18, 24)),
    }

    topic_counter: dict[str, int] = {}
    for r in topic_rows:
        try:
            for t in json.loads(r["topics"]):
                topic_counter[t] = topic_counter.get(t, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    top_topics = sorted(
        [{"topic": k, "count": v} for k, v in topic_counter.items()],
        key=lambda x: -x["count"],
    )[:10]

    total = summary_row["total"] or 0
    active_days = summary_row["active_days"] or 1
    avg_sentiment = sentiment_row["avg_sentiment"]
    type_breakdown = [dict(r) for r in type_rows]
    personality = _compute_personality(type_breakdown, time_slots, avg_sentiment, total)

    # 取得使用者名稱（members 表或 messages 最新一則）
    with get_conn() as conn:
        name_row = conn.execute(
            """SELECT COALESCE(
                 (SELECT display_name FROM members WHERE user_id=? LIMIT 1),
                 (SELECT user_name FROM messages WHERE user_id=? AND user_name IS NOT NULL ORDER BY timestamp DESC LIMIT 1)
               ) AS name""",
            (user_id, user_id),
        ).fetchone()
    display_name = name_row["name"] if name_row and name_row["name"] else None

    return {
        "user_id": user_id,
        "display_name": display_name,
        "summary": {
            "total": total,
            "active_days": active_days,
            "avg_per_day": round(total / active_days, 1) if active_days else 0,
            "first_seen": summary_row["first_seen"],
            "last_seen": summary_row["last_seen"],
        },
        "type_breakdown": type_breakdown,
        "hourly_distribution": [{"hour": h, "count": hour_map.get(h, 0)} for h in range(24)],
        "time_slots": time_slots,
        "top_topics": top_topics,
        "avg_sentiment": round(avg_sentiment, 3) if avg_sentiment is not None else None,
        "personality": personality,
    }


# ── 個人頁擴充查詢（不併入 get_profile_data，避免拖慢 bot 戰績卡）──────────

_MILESTONE_THRESHOLDS = [100, 500, 1000, 5000, 10000]


def get_user_milestones(user_id: str, group_id: str, period: str = "all") -> dict:
    """里程碑：第 N 則達成時間、單日最高、最長連續發言天數。"""
    pf, pp = period_filter(period)
    with get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM messages WHERE user_id=? AND group_id=?{pf}",
            (user_id, group_id, *pp),
        ).fetchone()["c"]

        nth = None
        threshold = max((t for t in _MILESTONE_THRESHOLDS if t <= total), default=0)
        if threshold:
            row = conn.execute(
                f"""SELECT timestamp FROM messages
                   WHERE user_id=? AND group_id=?{pf}
                   ORDER BY timestamp LIMIT 1 OFFSET ?""",
                (user_id, group_id, *pp, threshold - 1),
            ).fetchone()
            if row:
                nth = {"n": threshold, "timestamp": row["timestamp"]}

        busiest = conn.execute(
            f"""SELECT date(timestamp/1000,'unixepoch') AS date, COUNT(*) AS count
               FROM messages WHERE user_id=? AND group_id=?{pf}
               GROUP BY date ORDER BY count DESC, date DESC LIMIT 1""",
            (user_id, group_id, *pp),
        ).fetchone()
        busiest_day = dict(busiest) if busiest else None

        date_rows = conn.execute(
            f"""SELECT DISTINCT date(timestamp/1000,'unixepoch') AS date
               FROM messages WHERE user_id=? AND group_id=?{pf}
               ORDER BY date""",
            (user_id, group_id, *pp),
        ).fetchall()

    dates = [r["date"] for r in date_rows if r["date"]]
    longest_streak = _longest_date_streak(dates)

    return {
        "total": total,
        "nth": nth,
        "busiest_day": busiest_day,
        "longest_streak": longest_streak,
    }


def _longest_date_streak(dates: list[str]) -> dict | None:
    """dates 為已排序的 'YYYY-MM-DD' 清單，回傳最長連續天數區間。"""
    from datetime import date as _date, timedelta

    if not dates:
        return None
    best_len, best_start, best_end = 1, dates[0], dates[0]
    cur_len, cur_start, prev = 1, dates[0], _date.fromisoformat(dates[0])
    for d_str in dates[1:]:
        d = _date.fromisoformat(d_str)
        if d - prev == timedelta(days=1):
            cur_len += 1
        else:
            cur_len, cur_start = 1, d_str
        if cur_len > best_len:
            best_len, best_start, best_end = cur_len, cur_start, d_str
        prev = d
    return {"days": best_len, "start": best_start, "end": best_end}


def get_user_daily_series(user_id: str, group_id: str, period: str = "all") -> dict:
    """成長曲線（每日訊息 + 累積）與情緒曲線（每日平均情緒）。"""
    pf, pp = period_filter(period)
    with get_conn() as conn:
        count_rows = conn.execute(
            f"""SELECT date(timestamp/1000,'unixepoch') AS date, COUNT(*) AS count
               FROM messages WHERE user_id=? AND group_id=?{pf}
               GROUP BY date ORDER BY date ASC""",
            (user_id, group_id, *pp),
        ).fetchall()
        sentiment_rows = conn.execute(
            f"""SELECT date(timestamp/1000,'unixepoch') AS date,
                      AVG(sentiment) AS avg_sentiment
               FROM messages WHERE user_id=? AND group_id=?{pf}
                 AND sentiment IS NOT NULL
               GROUP BY date ORDER BY date ASC""",
            (user_id, group_id, *pp),
        ).fetchall()

    growth, cumulative = [], 0
    for r in count_rows:
        cumulative += r["count"]
        growth.append({"date": r["date"], "count": r["count"], "cumulative": cumulative})

    sentiment_series = [
        {"date": r["date"], "avg_sentiment": round(r["avg_sentiment"], 3)}
        for r in sentiment_rows if r["avg_sentiment"] is not None
    ]
    return {"growth": growth, "sentiment_series": sentiment_series}


def get_user_social_circle(user_id: str, group_id: str, period: str = "all") -> list:
    """個人社交圈：最常透過 reply 互動的對象（雙向合併）+ 共同話題。"""
    pf, pp = period_filter(period, "a.timestamp")
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT a.user_id AS a_id, b.user_id AS b_id, COUNT(*) AS count
               FROM messages a
               JOIN messages b ON a.reply_to_message_id = b.line_message_id
               WHERE a.group_id=? AND b.group_id=? AND a.user_id != b.user_id
                 AND (a.user_id=? OR b.user_id=?){pf}
               GROUP BY a.user_id, b.user_id""",
            (group_id, group_id, user_id, user_id, *pp),
        ).fetchall()

        partner_counts: dict[str, int] = {}
        for r in rows:
            partner = r["b_id"] if r["a_id"] == user_id else r["a_id"]
            partner_counts[partner] = partner_counts.get(partner, 0) + r["count"]

        top_partners = sorted(partner_counts.items(), key=lambda x: -x[1])[:5]
        if not top_partners:
            return []

        # 自己的話題集合（用於取交集）
        my_topics = _topic_counter_for(conn, user_id, group_id, period)

        result = []
        for partner_id, count in top_partners:
            name = _resolve_name(conn, partner_id)
            their_topics = _topic_counter_for(conn, partner_id, group_id, period)
            shared = sorted(
                (t for t in their_topics if t in my_topics),
                key=lambda t: -(my_topics[t] + their_topics[t]),
            )[:3]
            result.append({
                "user_id": partner_id, "name": name,
                "count": count, "shared_topics": shared,
            })
        return result


def _topic_counter_for(conn, user_id: str, group_id: str, period: str) -> dict:
    pf, pp = period_filter(period)
    rows = conn.execute(
        f"""SELECT topics FROM messages
           WHERE user_id=? AND group_id=?{pf}
             AND topics IS NOT NULL AND topics != '[]'""",
        (user_id, group_id, *pp),
    ).fetchall()
    counter: dict[str, int] = {}
    for r in rows:
        try:
            for t in json.loads(r["topics"]):
                counter[t] = counter.get(t, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    return counter


def _resolve_name(conn, user_id: str) -> str:
    row = conn.execute(
        """SELECT COALESCE(
             (SELECT display_name FROM members WHERE user_id=? LIMIT 1),
             (SELECT user_name FROM messages WHERE user_id=? AND user_name IS NOT NULL
              ORDER BY timestamp DESC LIMIT 1)
           ) AS name""",
        (user_id, user_id),
    ).fetchone()
    return (row["name"] if row and row["name"] else None) or f"路人{user_id[-6:]}"


def get_profile_extras(user_id: str, group_id: str, period: str = "all") -> dict:
    """個人頁擴充區塊彙整：里程碑 / 成長 / 情緒 / 社交圈 / 足跡 / 徽章。"""
    from travel.trip_crud import get_user_trips
    from travel.stats import get_user_badges

    daily = get_user_daily_series(user_id, group_id, period)
    return {
        "milestones": get_user_milestones(user_id, group_id, period),
        "growth": daily["growth"],
        "sentiment_series": daily["sentiment_series"],
        "social_circle": get_user_social_circle(user_id, group_id, period),
        "footprints": get_user_trips(user_id, group_id),
        "badges": get_user_badges(user_id, group_id),
    }
