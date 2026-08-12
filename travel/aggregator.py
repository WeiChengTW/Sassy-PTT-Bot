"""每日 / 終身統計聚合。"""
import json
import time

from travel.db import get_conn


def aggregate_daily(date_str: str | None = None) -> int:
    """聚合指定日期（預設今天）的訊息統計到 daily_user_stats。

    回傳聚合的 user 數。
    """
    date_str = date_str or time.strftime("%Y-%m-%d")
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT user_id, group_id,
                      SUM(CASE WHEN type='text' THEN 1 ELSE 0 END) AS text_count,
                      SUM(CASE WHEN type='sticker' THEN 1 ELSE 0 END) AS sticker_count,
                      SUM(CASE WHEN type='image' THEN 1 ELSE 0 END) AS image_count,
                      SUM(CASE WHEN type='video' THEN 1 ELSE 0 END) AS video_count,
                      SUM(CASE WHEN is_travel_related=1 THEN 1 ELSE 0 END) AS travel_mentions
               FROM messages
               WHERE date(timestamp/1000, 'unixepoch') = ?
               GROUP BY user_id, group_id""",
            (date_str,),
        ).fetchall()
        for r in rows:
            conn.execute(
                """INSERT OR REPLACE INTO daily_user_stats
                   (date, user_id, group_id, text_count, sticker_count,
                    image_count, travel_mention_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (date_str, r["user_id"], r["group_id"],
                 r["text_count"] or 0, r["sticker_count"] or 0,
                 r["image_count"] or 0, r["travel_mentions"] or 0),
            )
    return len(rows)


def aggregate_lifetime() -> int:
    """聚合每位使用者的終身統計到 user_lifetime_stats。

    回傳聚合的 user 數。
    """
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT m.user_id, m.group_id,
                      COUNT(*) AS total,
                      MIN(m.timestamp) AS first_seen,
                      MAX(m.timestamp) AS last_seen,
                      (SELECT COUNT(DISTINCT trip_id) FROM trip_participants tp
                       WHERE tp.user_id = m.user_id) AS total_trips
               FROM messages m
               GROUP BY m.user_id, m.group_id"""
        ).fetchall()
        for r in rows:
            loc_rows = conn.execute(
                """SELECT locations FROM messages
                   WHERE user_id=? AND locations IS NOT NULL
                     AND locations != '[]'""",
                (r["user_id"],),
            ).fetchall()
            loc_counter: dict[str, int] = {}
            for lr in loc_rows:
                try:
                    locs = json.loads(lr["locations"])
                except (json.JSONDecodeError, TypeError):
                    continue
                for loc in locs:
                    loc_counter[loc] = loc_counter.get(loc, 0) + 1
            top_locs = sorted(loc_counter, key=lambda x: -loc_counter[x])[:5]

            conn.execute(
                """INSERT OR REPLACE INTO user_lifetime_stats
                   (user_id, group_id, total_messages, total_trips,
                    first_seen, last_seen, favorite_locations)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (r["user_id"], r["group_id"], r["total"] or 0,
                 r["total_trips"] or 0, r["first_seen"], r["last_seen"],
                 json.dumps(top_locs, ensure_ascii=False)),
            )
    return len(rows)


def run_daily_aggregation():
    """每日聚合（被 APScheduler 觸發）。"""
    n1 = aggregate_daily()
    n2 = aggregate_lifetime()
    print(f"[AGGREGATOR] daily={n1}, lifetime={n2}")


if __name__ == "__main__":
    run_daily_aggregation()