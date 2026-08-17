"""Phase 3 分析查詢：排行榜、互動關係、話題分析、個人檔案。"""
import json
import re
from travel.db import get_conn
from travel.period import period_filter


# ── 精選語錄選取 ──────────────────────────────────────────────────────────────
# 視窗情緒分析會把同一個對話視窗（10 分鐘內、最多 4 則）共用同一個 sentiment，
# 因此撈金句時需過濾「附和短句／純網址／佔位符」，再對同一時段去重並做正負平衡，
# 避免短句洗版、連環網址、或極端分數全擠在單一情緒側。
_QUOTE_MIN_LEN = 4                  # 至少 4 字，擋掉「真的」「笑死」等短附和
_QUOTE_WINDOW_MS = 600 * 1000       # 同視窗判定：對齊 GROUP_WINDOW_GAP_SEC = 600 秒
_URL_PREFIX_RE = re.compile(r"^https?://", re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r"^\[[^\[\]]{1,8}\]$")
_NOISE_QUOTES = {
    "哈哈哈哈", "呵呵呵呵", "哈哈哈笑死",
    "嗯嗯嗯", "哦哦哦", "好喔好喔", "真的真的",
}


def _is_quote_worthy(content) -> bool:
    """金句基本過濾：有實質文字（≥4 字）、非純網址、非 [貼圖] 佔位符。"""
    if not content:
        return False
    text = content.strip()
    if len(text) < _QUOTE_MIN_LEN:
        return False
    if _URL_PREFIX_RE.match(text):
        return False
    if _PLACEHOLDER_RE.match(text):
        return False
    if text in _NOISE_QUOTES:
        return False
    return True


def _dedup_quote_rows(rows: list) -> list:
    """時間視窗去重：同一時段（10 分鐘內）只留字數最長／最完整的一則。"""
    out: list = []
    for r in sorted(rows, key=lambda x: x["timestamp"]):
        if out and r["timestamp"] - out[-1]["timestamp"] <= _QUOTE_WINDOW_MS:
            if len((r["content"] or "").strip()) > len((out[-1]["content"] or "").strip()):
                out[-1] = r
        else:
            out.append(r)
    return out


def _balance_quotes(rows: list, limit: int = 10) -> list:
    """正負平衡：各挑一半（正／負各 limit//2），不足由另一方補齊。"""
    rows = sorted(rows, key=lambda x: -abs(x["sentiment"]))
    pos = [r for r in rows if r["sentiment"] >= 0]
    neg = [r for r in rows if r["sentiment"] < 0]
    half = limit // 2
    picked = pos[:half] + neg[:half]
    remaining = limit - len(picked)
    if remaining > 0:
        picked += (pos[half:] + neg[half:])[:remaining]
    return picked[:limit]


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
               FROM messages WHERE group_id=?{pf} AND user_id NOT LIKE 'imported:%'
               GROUP BY user_id ORDER BY total DESC LIMIT 20""",
            (group_id, *pp),
        ).fetchall()

        night_owls = conn.execute(
            f"""SELECT user_id, user_name, COUNT(*) AS night_count
               FROM messages
               WHERE group_id=?{pf} AND user_id NOT LIKE 'imported:%'
                 AND CAST(strftime('%H', timestamp/1000, 'unixepoch', 'localtime') AS INTEGER) BETWEEN 0 AND 4
               GROUP BY user_id ORDER BY night_count DESC LIMIT 10""",
            (group_id, *pp),
        ).fetchall()

        type_dist = conn.execute(
            f"""SELECT type, COUNT(*) AS count FROM messages
               WHERE group_id=?{pf} AND user_id NOT LIKE 'imported:%' GROUP BY type ORDER BY count DESC""",
            (group_id, *pp),
        ).fetchall()

        badge_rankings = conn.execute(
            """SELECT b.user_id,
                      COALESCE(
                        (SELECT display_name FROM members WHERE user_id=b.user_id LIMIT 1),
                        (SELECT user_name FROM messages WHERE user_id=b.user_id AND user_name IS NOT NULL AND (group_id=? OR group_id IS NULL) ORDER BY timestamp DESC LIMIT 1)
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
               ORDER BY badge_count DESC, legendary_count DESC, epic_count DESC, super_rare_count DESC, rare_count DESC""",
            (group_id, group_id),
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
               WHERE a.group_id=? AND b.group_id=? AND a.user_id != b.user_id
                 AND a.user_id NOT LIKE 'imported:%' AND b.user_id NOT LIKE 'imported:%'{pf}
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
               FROM messages WHERE group_id=? AND user_id NOT LIKE 'imported:%'{npf}
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
            f"""SELECT date(timestamp/1000,'unixepoch','localtime') AS date,
                      AVG(sentiment) AS avg_sentiment
               FROM messages
               WHERE group_id=?{pf} AND sentiment IS NOT NULL
               GROUP BY date ORDER BY date ASC""",
            (group_id, *pp),
        ).fetchall()

        weekly_rows = conn.execute(
            f"""SELECT strftime('%Y-W%W', timestamp/1000,'unixepoch','localtime') AS week, topics
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

        # 精選語錄：撈取情緒最鮮明的一批候選，在 Python 端做內容過濾、
        # 時間視窗去重與正負平衡（避免同視窗洗榜、純網址、短附和）。
        quote_rows = conn.execute(
            f"""SELECT user_name, content, summary, sentiment, timestamp FROM messages
               WHERE group_id=?{pf} AND type='text'
                 AND content IS NOT NULL AND length(content) > 1
                 AND sentiment IS NOT NULL
                 AND user_id NOT LIKE 'imported:%'
               ORDER BY ABS(sentiment) DESC, timestamp DESC LIMIT 200""",
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

    quote_rows = _dedup_quote_rows(
        [r for r in quote_rows if _is_quote_worthy(r["content"])]
    )
    quote_rows = _balance_quotes(quote_rows, 10)

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
                      COUNT(DISTINCT date(timestamp/1000,'unixepoch','localtime')) AS active_days,
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
            f"""SELECT CAST(strftime('%H', timestamp/1000,'unixepoch','localtime') AS INTEGER) AS hour,
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
            f"""SELECT date(timestamp/1000,'unixepoch','localtime') AS date, COUNT(*) AS count
               FROM messages WHERE user_id=? AND group_id=?{pf}
               GROUP BY date ORDER BY count DESC, date DESC LIMIT 1""",
            (user_id, group_id, *pp),
        ).fetchone()
        busiest_day = dict(busiest) if busiest else None

        date_rows = conn.execute(
            f"""SELECT DISTINCT date(timestamp/1000,'unixepoch','localtime') AS date
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
            f"""SELECT date(timestamp/1000,'unixepoch','localtime') AS date, COUNT(*) AS count
               FROM messages WHERE user_id=? AND group_id=?{pf}
               GROUP BY date ORDER BY date ASC""",
            (user_id, group_id, *pp),
        ).fetchall()
        sentiment_rows = conn.execute(
            f"""SELECT date(timestamp/1000,'unixepoch','localtime') AS date,
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


def get_pulse_data(group_id: str, period: str = "all") -> dict:
    """群組動態：回應速度、訊息爆發時段、潛水員偵測。

    回應速度與訊息爆發套用 period 過濾；潛水員一律以現在時間計算（不套 period）。
    """
    import time as _time

    pf, pp = period_filter(period, "a.timestamp")          # 回應速度用 a.timestamp
    mpf, mpp = period_filter(period)                        # 訊息爆發用 timestamp
    with get_conn() as conn:
        # ── 回應速度：reply self-join，延遲 = a.timestamp - b.timestamp（毫秒）──
        overall_row = conn.execute(
            f"""SELECT AVG(a.timestamp - b.timestamp) AS avg_ms, COUNT(*) AS cnt
               FROM messages a
               JOIN messages b ON a.reply_to_message_id = b.line_message_id
               WHERE a.group_id=? AND b.group_id=? AND a.user_id != b.user_id
                 AND a.timestamp > b.timestamp
                 AND a.timestamp - b.timestamp < 86400000{pf}""",
            (group_id, group_id, *pp),
        ).fetchone()
        avg_minutes = (
            round(overall_row["avg_ms"] / 60000.0, 1)
            if overall_row and overall_row["avg_ms"] is not None else None
        )
        reply_count = overall_row["cnt"] if overall_row else 0

        fast_rows = conn.execute(
            f"""SELECT a.user_id AS user_id,
                      AVG(a.timestamp - b.timestamp) AS avg_ms,
                      COUNT(*) AS reply_count
               FROM messages a
               JOIN messages b ON a.reply_to_message_id = b.line_message_id
               WHERE a.group_id=? AND b.group_id=? AND a.user_id != b.user_id
                 AND a.user_id NOT LIKE 'imported:%' AND b.user_id NOT LIKE 'imported:%'
                 AND a.timestamp > b.timestamp
                 AND a.timestamp - b.timestamp < 86400000{pf}
               GROUP BY a.user_id
               HAVING reply_count >= 2
               ORDER BY avg_ms ASC LIMIT 5""",
            (group_id, group_id, *pp),
        ).fetchall()
        fastest_responders = [
            {
                "user_id": r["user_id"],
                "name": _resolve_name(conn, r["user_id"]),
                "avg_minutes": round(r["avg_ms"] / 60000.0, 1),
                "reply_count": r["reply_count"],
            }
            for r in fast_rows
        ]

        # ── 訊息爆發：每小時 bucket，count > 2×平均 的 top 5 ──
        hourly_rows = conn.execute(
            f"""SELECT strftime('%Y-%m-%d %H', timestamp/1000,'unixepoch','localtime') AS hour,
                      COUNT(*) AS count
               FROM messages WHERE group_id=? AND user_id NOT LIKE 'imported:%'{mpf}
               GROUP BY hour""",
            (group_id, *mpp),
        ).fetchall()
        counts = [r["count"] for r in hourly_rows]
        avg_hourly = sum(counts) / len(counts) if counts else 0.0
        bursts = sorted(
            (
                {
                    "hour": r["hour"],
                    "count": r["count"],
                    "ratio": round(r["count"] / avg_hourly, 1) if avg_hourly else 0.0,
                }
                for r in hourly_rows
                if avg_hourly and r["count"] > avg_hourly * 2
            ),
            key=lambda x: -x["count"],
        )[:5]

        # ── 潛水員：members 名冊 LEFT JOIN 最後發言時間（用現在計算，排除 imported）──
        now_ms = int(_time.time() * 1000)
        lurker_rows = conn.execute(
            """SELECT m.user_id AS user_id, m.display_name AS display_name,
                      (SELECT MAX(timestamp) FROM messages
                       WHERE user_id=m.user_id AND group_id=m.group_id AND user_id NOT LIKE 'imported:%') AS last_seen
               FROM members m WHERE m.group_id=?""",
            (group_id,),
        ).fetchall()
        lurkers = []
        for r in lurker_rows:
            last_seen = r["last_seen"]
            days = (now_ms - last_seen) / 86_400_000 if last_seen else None
            if days is None or days > 7:
                lurkers.append({
                    "user_id": r["user_id"],
                    "name": r["display_name"] or _resolve_name(conn, r["user_id"]),
                    "last_seen": last_seen,
                    "days_inactive": round(days, 1) if days is not None else None,
                })
        lurkers.sort(key=lambda x: (x["days_inactive"] is not None, x["days_inactive"] or 0),
                     reverse=True)

    return {
        "response_speed": {
            "avg_minutes": avg_minutes,
            "reply_count": reply_count,
            "fastest_responders": fastest_responders,
        },
        "bursts": bursts,
        "avg_hourly": round(avg_hourly, 1),
        "lurkers": lurkers,
    }


def _profile_slim(user_id: str, group_id: str, period: str) -> dict:
    """從 get_profile_data 取出對比用的精簡指標。"""
    p = get_profile_data(user_id, group_id, period)
    total = p["summary"]["total"] or 0
    counts = {t["type"]: t["count"] for t in p["type_breakdown"]}
    text_ratio = round(counts.get("text", 0) * 100.0 / total, 1) if total else 0.0
    sticker_ratio = round(counts.get("sticker", 0) * 100.0 / total, 1) if total else 0.0
    slots = p["time_slots"]
    top_slot = max(slots, key=slots.get) if sum(slots.values()) else None
    return {
        "user_id": user_id,
        "name": p["display_name"] or f"路人{user_id[-6:]}",
        "total": total,
        "active_days": p["summary"]["active_days"],
        "avg_per_day": p["summary"]["avg_per_day"],
        "text_ratio": text_ratio,
        "sticker_ratio": sticker_ratio,
        "avg_sentiment": p["avg_sentiment"],
        "top_slot": top_slot,
        "personality": p["personality"],
    }


def get_compare_data(group_id: str, user_a: str, user_b: str, period: str = "all") -> dict:
    """成員對比：兩位成員的並排指標 + 相似度百分比。"""
    a = _profile_slim(user_a, group_id, period)
    b = _profile_slim(user_b, group_id, period)

    # 相似度：各維度正規化後 1 − 平均差異
    diffs = []
    max_total = max(a["total"], b["total"]) or 1
    diffs.append(abs(a["total"] - b["total"]) / max_total)
    diffs.append(abs(a["text_ratio"] - b["text_ratio"]) / 100.0)
    diffs.append(abs(a["sticker_ratio"] - b["sticker_ratio"]) / 100.0)
    if a["avg_sentiment"] is not None and b["avg_sentiment"] is not None:
        diffs.append(abs(a["avg_sentiment"] - b["avg_sentiment"]) / 2.0)  # sentiment ∈ [-1,1]
    diffs.append(0.0 if a["top_slot"] == b["top_slot"] else 1.0)
    similarity = round((1 - sum(diffs) / len(diffs)) * 100)

    return {"a": a, "b": b, "similarity": similarity}


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
