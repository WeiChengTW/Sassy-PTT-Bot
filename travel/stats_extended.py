"""Phase 3 分析查詢：排行榜、互動關係、話題分析、個人檔案。"""
import json
from travel.db import get_conn


def get_leaderboard_data(group_id: str) -> dict:
    with get_conn() as conn:
        rankings = conn.execute(
            """SELECT user_id, user_name,
                      COUNT(*) AS total,
                      SUM(CASE WHEN type='text'    THEN 1 ELSE 0 END) AS text_count,
                      SUM(CASE WHEN type='sticker' THEN 1 ELSE 0 END) AS sticker_count,
                      SUM(CASE WHEN type='image'   THEN 1 ELSE 0 END) AS image_count
               FROM messages WHERE group_id=?
               GROUP BY user_id ORDER BY total DESC LIMIT 20""",
            (group_id,),
        ).fetchall()

        night_owls = conn.execute(
            """SELECT user_id, user_name, COUNT(*) AS night_count
               FROM messages
               WHERE group_id=?
                 AND CAST(strftime('%H', timestamp/1000, 'unixepoch') AS INTEGER) BETWEEN 0 AND 4
               GROUP BY user_id ORDER BY night_count DESC LIMIT 10""",
            (group_id,),
        ).fetchall()

        type_dist = conn.execute(
            """SELECT type, COUNT(*) AS count FROM messages
               WHERE group_id=? GROUP BY type ORDER BY count DESC""",
            (group_id,),
        ).fetchall()

    return {
        "rankings": [dict(r) for r in rankings],
        "night_owls": [dict(r) for r in night_owls],
        "type_distribution": [dict(r) for r in type_dist],
    }


def get_interaction_data(group_id: str) -> dict:
    with get_conn() as conn:
        # Best pairs via reply JOIN — sort by count DESC, deduplicate (A,B)==(B,A)
        raw_pairs = conn.execute(
            """SELECT a.user_id AS user1_id, a.user_name AS user1_name,
                      b.user_id AS user2_id, b.user_name AS user2_name,
                      COUNT(*) AS count
               FROM messages a
               JOIN messages b ON a.reply_to_message_id = b.line_message_id
               WHERE a.group_id=? AND b.group_id=? AND a.user_id != b.user_id
               GROUP BY a.user_id, b.user_id
               ORDER BY count DESC LIMIT 40""",
            (group_id, group_id),
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

        # Network nodes
        nodes_rows = conn.execute(
            """SELECT user_id AS id, user_name AS name, COUNT(*) AS message_count
               FROM messages WHERE group_id=?
               GROUP BY user_id""",
            (group_id,),
        ).fetchall()

    return {
        "best_pairs": best_pairs,
        "network_nodes": [dict(r) for r in nodes_rows],
        "network_edges": [
            {"source": p["user1_id"], "target": p["user2_id"], "weight": p["count"]}
            for p in best_pairs
        ],
    }


def get_topics_data(group_id: str) -> dict:
    with get_conn() as conn:
        topic_rows = conn.execute(
            """SELECT topics FROM messages
               WHERE group_id=? AND topics IS NOT NULL AND topics != '[]'""",
            (group_id,),
        ).fetchall()

        sentiment_rows = conn.execute(
            """SELECT date(timestamp/1000,'unixepoch') AS date,
                      AVG(sentiment) AS avg_sentiment
               FROM messages
               WHERE group_id=? AND sentiment IS NOT NULL
               GROUP BY date ORDER BY date ASC""",
            (group_id,),
        ).fetchall()

        weekly_rows = conn.execute(
            """SELECT strftime('%Y-W%W', timestamp/1000,'unixepoch') AS week, topics
               FROM messages
               WHERE group_id=? AND topics IS NOT NULL AND topics != '[]'
               ORDER BY week""",
            (group_id,),
        ).fetchall()

    # Aggregate topic counts
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

    # Weekly trend aggregation
    weekly: dict[str, dict[str, int]] = {}
    for r in weekly_rows:
        week = r["week"]
        if week not in weekly:
            weekly[week] = {}
        try:
            for t in json.loads(r["topics"]):
                weekly[week][t] = weekly[week].get(t, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    weekly_trend = [{"week": w, "topics": counts} for w, counts in sorted(weekly.items())]

    return {
        "top_topics": top_topics,
        "weekly_trend": weekly_trend,
        "daily_sentiment": [dict(r) for r in sentiment_rows],
    }


def get_profile_data(user_id: str, group_id: str) -> dict:
    with get_conn() as conn:
        summary_row = conn.execute(
            """SELECT COUNT(*) AS total,
                      COUNT(DISTINCT date(timestamp/1000,'unixepoch')) AS active_days,
                      MIN(timestamp) AS first_seen,
                      MAX(timestamp) AS last_seen
               FROM messages WHERE user_id=? AND group_id=?""",
            (user_id, group_id),
        ).fetchone()

        type_rows = conn.execute(
            """SELECT type, COUNT(*) AS count FROM messages
               WHERE user_id=? AND group_id=? GROUP BY type ORDER BY count DESC""",
            (user_id, group_id),
        ).fetchall()

        hourly_rows = conn.execute(
            """SELECT CAST(strftime('%H', timestamp/1000,'unixepoch') AS INTEGER) AS hour,
                      COUNT(*) AS count
               FROM messages WHERE user_id=? AND group_id=?
               GROUP BY hour ORDER BY hour""",
            (user_id, group_id),
        ).fetchall()

        topic_rows = conn.execute(
            """SELECT topics FROM messages
               WHERE user_id=? AND group_id=?
                 AND topics IS NOT NULL AND topics != '[]'""",
            (user_id, group_id),
        ).fetchall()

        sentiment_row = conn.execute(
            """SELECT AVG(sentiment) AS avg_sentiment FROM messages
               WHERE user_id=? AND group_id=? AND sentiment IS NOT NULL""",
            (user_id, group_id),
        ).fetchone()

    # Time slots
    hour_map: dict[int, int] = {r["hour"]: r["count"] for r in hourly_rows}
    time_slots = {
        "night":   sum(hour_map.get(h, 0) for h in range(0, 5)),    # 0-4
        "morning": sum(hour_map.get(h, 0) for h in range(5, 9)),    # 5-8
        "daytime": sum(hour_map.get(h, 0) for h in range(9, 18)),   # 9-17
        "evening": sum(hour_map.get(h, 0) for h in range(18, 24)),  # 18-23
    }

    # Per-user topic counts
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

    return {
        "summary": {
            "total": total,
            "active_days": active_days,
            "avg_per_day": round(total / active_days, 1) if active_days else 0,
            "first_seen": summary_row["first_seen"],
            "last_seen": summary_row["last_seen"],
        },
        "type_breakdown": [dict(r) for r in type_rows],
        "hourly_distribution": [{"hour": h, "count": hour_map.get(h, 0)} for h in range(24)],
        "time_slots": time_slots,
        "top_topics": top_topics,
        "avg_sentiment": round(avg_sentiment, 3) if avg_sentiment is not None else None,
    }
