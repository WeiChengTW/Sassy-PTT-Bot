"""資料驅動排行榜註冊表（15 種趣味排行榜）。

每個排行榜是一個 BoardSpec；compute 函式吃 (conn, group_id, period) 回傳
{"rows": [...], "highlight": {...} | None}。get_all_boards() 一次跑完所有排行榜、
回傳統一結構，供 LIFF 前端與 LINE Flex 卡片共用。

新增排行榜只需在 BOARDS 加一筆 + 寫一個 compute 函式。
所有時間運算採 epoch 毫秒（date(timestamp/1000,'unixepoch')）；姓名解析用
stats_extended._resolve_name（優先 members.display_name，退回 messages.user_name）。
"""
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from travel.db import get_conn
from travel.period import period_filter
from travel.stats_extended import _resolve_name, _longest_date_streak


@dataclass
class BoardSpec:
    id: str
    title: str
    emoji: str
    unit: str
    subtitle: str
    variant: str          # "rank" | "score" | "radar"
    accent: str           # LINE 卡片主題色
    compute: Callable     # (conn, group_id, period) -> {"rows": [...], "highlight": ...|None}
    sparse: bool = False  # True → reply 依賴、資料量少，前端/卡片標註「僅供參考」

    def run(self, conn, group_id: str, period: str) -> dict:
        try:
            result = self.compute(conn, group_id, period)
        except Exception:
            result = {"rows": [], "highlight": None}
        return {
            "id": self.id, "title": self.title, "emoji": self.emoji,
            "unit": self.unit, "subtitle": self.subtitle, "variant": self.variant,
            "accent": self.accent, "sparse": self.sparse,
            "rows": result.get("rows", []),
            "highlight": result.get("highlight"),
        }


# ── 色票（沿用 stats_cards 風格） ──
BLUE, GOLD, ROSE, ORANGE, PURPLE, GREEN, TEAL, GREY = (
    "#2563eb", "#f59e0b", "#f43f5e", "#f97316", "#a855f7", "#10b981", "#14b8a6", "#64748b")


def _row(conn, uid, value, value_str, detail=None, extra=None) -> dict:
    r = {"user_id": uid, "name": _resolve_name(conn, uid),
         "value": value, "value_str": value_str, "detail": detail}
    if extra:
        r.update(extra)
    return r


# ─────────────────────────── 密集資料排行榜 ───────────────────────────

def _cp_sentiment(conn, group_id, period):
    pf, pp = period_filter(period)
    rows = conn.execute(
        f"""SELECT user_id, AVG(sentiment) AS avg_s, COUNT(*) AS cnt
           FROM messages WHERE group_id=?{pf} AND sentiment IS NOT NULL
           GROUP BY user_id HAVING cnt>=10 ORDER BY avg_s DESC LIMIT 10""",
        (group_id, *pp)).fetchall()
    out = [_row(conn, r["user_id"], round(r["avg_s"], 2),
               f"{r['avg_s']:+.2f}", f"{r['cnt']} 則") for r in rows]
    top = conn.execute(
        f"""SELECT user_id, content, sentiment FROM messages
           WHERE group_id=?{pf} AND sentiment IS NOT NULL AND content IS NOT NULL
           ORDER BY sentiment DESC LIMIT 1""", (group_id, *pp)).fetchone()
    hi = None
    if top:
        hi = {"label": "最正能量的一句", "name": _resolve_name(conn, top["user_id"]),
              "value_str": f"{top['sentiment']:+.2f}",
              "note": (top["content"] or "").strip()[:40]}
    return {"rows": out, "highlight": hi}


def _cp_streak(conn, group_id, period):
    pf, pp = period_filter(period)
    rows = conn.execute(
        f"""SELECT user_id, date(timestamp/1000,'unixepoch') AS d
           FROM messages WHERE group_id=?{pf}
           GROUP BY user_id, d ORDER BY user_id, d""", (group_id, *pp)).fetchall()
    per_user: dict[str, list[str]] = {}
    for r in rows:
        if r["d"]:
            per_user.setdefault(r["user_id"], []).append(r["d"])
    today = datetime.now(timezone.utc).date().isoformat()
    scored = []
    for uid, dates in per_user.items():
        streak = _longest_date_streak(sorted(dates))
        if streak and streak["days"] >= 3:
            scored.append((uid, streak))
    scored.sort(key=lambda x: -x[1]["days"])
    out = [_row(conn, uid, s["days"], f"{s['days']} 天", f"{s['start']}~{s['end']}",
               extra={"ongoing": s["end"] == today}) for uid, s in scored[:10]]
    hi = None
    ongoing = [o for o in out if o.get("ongoing")]
    if ongoing:
        top = max(ongoing, key=lambda o: o["value"])
        hi = {"label": "目前連擊中 🔥", "name": top["name"],
              "value_str": f"第 {top['value']} 天", "note": None}
    return {"rows": out, "highlight": hi}


def _cp_msg_length(conn, group_id, period):
    pf, pp = period_filter(period)
    rows = conn.execute(
        f"""SELECT user_id, AVG(LENGTH(content)) AS avg_len, COUNT(*) AS cnt
           FROM messages WHERE group_id=?{pf} AND type='text' AND content IS NOT NULL
           GROUP BY user_id HAVING cnt>=10 ORDER BY avg_len DESC LIMIT 10""",
        (group_id, *pp)).fetchall()
    out = [_row(conn, r["user_id"], round(r["avg_len"]),
               f"{round(r['avg_len'])} 字", f"{r['cnt']} 則") for r in rows]
    top = conn.execute(
        f"""SELECT user_id, LENGTH(content) AS len, content FROM messages
           WHERE group_id=?{pf} AND type='text' AND content IS NOT NULL
           ORDER BY len DESC LIMIT 1""", (group_id, *pp)).fetchone()
    hi = None
    if top:
        hi = {"label": "史上最長", "name": _resolve_name(conn, top["user_id"]),
              "value_str": f"{top['len']} 字",
              "note": (top["content"] or "").strip()[:30]}
    return {"rows": out, "highlight": hi}


def _cp_sticker(conn, group_id, period):
    pf, pp = period_filter(period)
    rows = conn.execute(
        f"""SELECT user_id,
                  SUM(CASE WHEN type='sticker' THEN 1 ELSE 0 END) AS stk,
                  COUNT(*) AS total
           FROM messages WHERE group_id=?{pf}
           GROUP BY user_id HAVING total>=10
           ORDER BY stk*1.0/total DESC LIMIT 10""", (group_id, *pp)).fetchall()
    out = [_row(conn, r["user_id"], round(r["stk"] * 100.0 / r["total"], 1),
               f"{round(r['stk'] * 100.0 / r['total'], 1)}%", f"{r['stk']}/{r['total']}")
           for r in rows]
    return {"rows": out, "highlight": None}


def _trip_kind_filter() -> str:
    """單一真理來源：旅行 = end_date - start_date >= 86400；事件 = 其他。"""
    return """(
        CASE
          WHEN start_date IS NULL THEN NULL
          WHEN end_date IS NOT NULL AND (end_date - start_date) >= 86400 THEN 'travel'
          ELSE 'event'
        END
    )"""


def _cp_trip(conn, group_id, period):
    # 旅行達人：只算 kind='travel' 的多日旅程
    # trips 以 start_date 計時，與訊息 period 不同步；此榜不套 period（累計）。
    kind_expr = _trip_kind_filter()
    rows = conn.execute(
        f"""SELECT tp.user_id AS uid, COUNT(DISTINCT tp.trip_id) AS trips,
                  SUM(CASE WHEN tp.role='organizer' THEN 1 ELSE 0 END) AS organized
           FROM trip_participants tp JOIN trips t ON t.id = tp.trip_id
           WHERE t.group_id=? AND {kind_expr}='travel'
           GROUP BY tp.user_id
           ORDER BY trips DESC, organized DESC LIMIT 10""", (group_id,)).fetchall()
    out = [_row(conn, r["uid"], r["trips"], f"{r['trips']} 次",
               f"發起 {r['organized']} 次" if r["organized"] else None) for r in rows]
    return {"rows": out, "highlight": None}


def _cp_event(conn, group_id, period):
    # 事件王：對稱結構，統計 kind='event' 的單日/當天事件參與次數
    kind_expr = _trip_kind_filter()
    rows = conn.execute(
        f"""SELECT tp.user_id AS uid, COUNT(DISTINCT tp.trip_id) AS trips,
                  SUM(CASE WHEN tp.role='organizer' THEN 1 ELSE 0 END) AS organized
           FROM trip_participants tp JOIN trips t ON t.id = tp.trip_id
           WHERE t.group_id=? AND {kind_expr}='event'
           GROUP BY tp.user_id
           ORDER BY trips DESC, organized DESC LIMIT 10""", (group_id,)).fetchall()
    out = [_row(conn, r["uid"], r["trips"], f"{r['trips']} 次",
               f"發起 {r['organized']} 次" if r["organized"] else None) for r in rows]
    return {"rows": out, "highlight": None}


def _cp_morning(conn, group_id, period):
    pf, pp = period_filter(period)
    rows = conn.execute(
        f"""SELECT user_id, COUNT(*) AS c FROM messages
           WHERE group_id=?{pf}
             AND CAST(strftime('%H', timestamp/1000, 'unixepoch') AS INTEGER) BETWEEN 5 AND 9
           GROUP BY user_id ORDER BY c DESC LIMIT 10""", (group_id, *pp)).fetchall()
    out = [_row(conn, r["user_id"], r["c"], f"{r['c']} 則") for r in rows]
    return {"rows": out, "highlight": None}


# ─────────────────────────── 稀疏（reply 依賴）排行榜 ───────────────────────────

def _cp_reply_speed(conn, group_id, period):
    pf, pp = period_filter(period, "m1.timestamp")
    rows = conn.execute(
        f"""SELECT m1.user_id AS uid,
                  AVG((m1.timestamp - m2.timestamp)/60000.0) AS avg_min,
                  MIN((m1.timestamp - m2.timestamp)/60000.0) AS fastest,
                  COUNT(*) AS cnt
           FROM messages m1
           JOIN messages m2 ON m1.reply_to_message_id = m2.line_message_id
           WHERE m1.group_id=? AND m2.group_id=? AND m1.user_id != m2.user_id
             AND m1.timestamp >= m2.timestamp{pf}
           GROUP BY m1.user_id HAVING cnt>=3
           ORDER BY avg_min ASC LIMIT 10""", (group_id, group_id, *pp)).fetchall()
    out = [_row(conn, r["uid"], round(r["avg_min"], 1),
               f"{round(r['avg_min'], 1)} 分", f"最快 {round(r['fastest'], 1)} 分 · {r['cnt']} 次")
           for r in rows]
    return {"rows": out, "highlight": None}


SILENCE_MS = 30 * 60 * 1000  # 群組沉默 ≥ 30 分鐘 → 視為話題被終結


def _fmt_gap(ms: int) -> str:
    m = ms / 60000.0
    if m < 60:
        return f"{round(m)} 分鐘"
    h = m / 60.0
    return f"{round(h, 1)} 小時" if h < 24 else f"{round(h / 24, 1)} 天"


def _cp_terminator(conn, group_id, period):
    """冷場王：訊息後整個群組陷入沉默（下一則訊息間隔 ≥ 30 分或無）的比率。

    以時間間隔判定，不依賴稀疏的 reply_to；LEAD() 取每則到下一則群組訊息的間隔。
    """
    pf, pp = period_filter(period)
    rows = conn.execute(
        f"""WITH ordered AS (
               SELECT user_id, timestamp,
                      LEAD(timestamp) OVER (ORDER BY timestamp) AS next_ts
               FROM messages WHERE group_id=?{pf}
             )
             SELECT user_id AS uid,
                    SUM(CASE WHEN next_ts IS NULL OR (next_ts - timestamp) >= ?
                             THEN 1 ELSE 0 END) AS term,
                    COUNT(*) AS total
             FROM ordered GROUP BY user_id HAVING total>=10
             ORDER BY term*1.0/total DESC LIMIT 10""",
        (group_id, *pp, SILENCE_MS)).fetchall()
    out = [_row(conn, r["uid"], round(r["term"] * 100.0 / r["total"], 1),
               f"{round(r['term'] * 100.0 / r['total'], 1)}%", f"{r['term']}/{r['total']} 則冷場")
           for r in rows]
    top = conn.execute(
        f"""WITH ordered AS (
               SELECT user_id, content, timestamp,
                      LEAD(timestamp) OVER (ORDER BY timestamp) AS next_ts
               FROM messages WHERE group_id=?{pf}
             )
             SELECT user_id, content, (next_ts - timestamp) AS gap
             FROM ordered WHERE next_ts IS NOT NULL
             ORDER BY gap DESC LIMIT 1""", (group_id, *pp)).fetchone()
    hi = None
    if top:
        hi = {"label": "最長冷場紀錄", "name": _resolve_name(conn, top["user_id"]),
              "value_str": _fmt_gap(top["gap"]),
              "note": (top["content"] or "").strip()[:30] or None}
    return {"rows": out, "highlight": hi}


def _cp_initiator(conn, group_id, period):
    pf, pp = period_filter(period)
    rows = conn.execute(
        f"""SELECT m.user_id AS uid, COUNT(*) AS initiated,
                  AVG((SELECT COUNT(*) FROM messages r
                       WHERE r.reply_to_message_id=m.line_message_id)) AS avg_replies
           FROM messages m
           WHERE m.group_id=?{pf} AND m.reply_to_message_id IS NULL
           GROUP BY m.user_id ORDER BY initiated DESC LIMIT 10""",
        (group_id, *pp)).fetchall()
    out = [_row(conn, r["uid"], r["initiated"], f"{r['initiated']} 則",
               f"平均獲 {round(r['avg_replies'] or 0, 1)} 則回覆") for r in rows]
    return {"rows": out, "highlight": None}


def _cp_most_replied(conn, group_id, period):
    pf, pp = period_filter(period)
    rows = conn.execute(
        f"""SELECT m.user_id AS uid, COUNT(*) AS total,
                  SUM((SELECT COUNT(*) FROM messages r
                       WHERE r.reply_to_message_id=m.line_message_id)) AS replies
           FROM messages m WHERE m.group_id=?{pf}
           GROUP BY m.user_id HAVING total>=10
           ORDER BY replies*1.0/total DESC LIMIT 10""", (group_id, *pp)).fetchall()
    out = [_row(conn, r["uid"], round((r["replies"] or 0) / r["total"], 2),
               f"{round((r['replies'] or 0) / r['total'], 2)} 則/次",
               f"共 {r['replies'] or 0} 則回覆") for r in rows]
    return {"rows": out, "highlight": None}


# ─────────────────────────── 週期型排行榜 ───────────────────────────

def _cp_growth(conn, group_id, period):
    now = int(time.time() * 1000)
    wk = 7 * 86_400_000
    this_start, last_start = now - wk, now - 2 * wk
    rows = conn.execute(
        """SELECT user_id,
                 SUM(CASE WHEN timestamp>=? THEN 1 ELSE 0 END) AS this_wk,
                 SUM(CASE WHEN timestamp>=? AND timestamp<? THEN 1 ELSE 0 END) AS last_wk
           FROM messages WHERE group_id=? AND timestamp>=?
           GROUP BY user_id HAVING last_wk>0
           ORDER BY (this_wk-last_wk)*1.0/last_wk DESC LIMIT 10""",
        (this_start, last_start, this_start, group_id, last_start)).fetchall()
    out = []
    for r in rows:
        rate = round((r["this_wk"] - r["last_wk"]) * 100.0 / r["last_wk"])
        out.append(_row(conn, r["user_id"], rate, f"{rate:+d}%",
                        f"上週 {r['last_wk']} → 本週 {r['this_wk']} 則"))
    return {"rows": out, "highlight": None}


def _month_top(conn, group_id, ym):
    from travel.period import parse_period
    start, end = parse_period(ym)
    if start is None:
        return []
    return conn.execute(
        """SELECT user_id, COUNT(*) AS c FROM messages
           WHERE group_id=? AND timestamp>=? AND timestamp<?
           GROUP BY user_id ORDER BY c DESC LIMIT 10""",
        (group_id, start, end)).fetchall()


def _cp_seasonal(conn, group_id, period):
    now = datetime.now(timezone.utc)
    this_ym = f"{now.year}-{now.month:02d}"
    prev = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
    prev_ym = f"{prev[0]}-{prev[1]:02d}"
    this_rows = _month_top(conn, group_id, this_ym)
    prev_rows = _month_top(conn, group_id, prev_ym)
    out = [_row(conn, r["user_id"], r["c"], f"{r['c']} 則") for r in this_rows]
    hi = None
    if prev_rows:
        champ = prev_rows[0]
        defended = this_rows and this_rows[0]["user_id"] == champ["user_id"]
        hi = {"label": f"上月冠軍（{prev_ym}）", "name": _resolve_name(conn, champ["user_id"]),
              "value_str": f"{champ['c']} 則",
              "note": "衛冕成功 👑" if defended else "本月換人當家"}
    return {"rows": out, "highlight": hi}


def _cp_achievements(conn, group_id, period):
    pf, pp = period_filter(period)
    day_rows = conn.execute(
        f"""SELECT user_id, date(timestamp/1000,'unixepoch') AS d, COUNT(*) AS c
           FROM messages WHERE group_id=?{pf}
           GROUP BY user_id, d""", (group_id, *pp)).fetchall()
    best: dict[str, tuple[int, str]] = {}
    for r in day_rows:
        if r["d"] and r["c"] > best.get(r["user_id"], (0, ""))[0]:
            best[r["user_id"]] = (r["c"], r["d"])
    ranked = sorted(best.items(), key=lambda x: -x[1][0])[:10]
    out = [_row(conn, uid, c, f"{c} 則", d) for uid, (c, d) in ranked]

    # highlight：最長連擊紀錄
    streak_rows = conn.execute(
        f"""SELECT user_id, date(timestamp/1000,'unixepoch') AS d
           FROM messages WHERE group_id=?{pf}
           GROUP BY user_id, d ORDER BY user_id, d""", (group_id, *pp)).fetchall()
    per_user: dict[str, list[str]] = {}
    for r in streak_rows:
        if r["d"]:
            per_user.setdefault(r["user_id"], []).append(r["d"])
    best_streak = None
    for uid, dates in per_user.items():
        s = _longest_date_streak(sorted(dates))
        if s and (best_streak is None or s["days"] > best_streak[1]["days"]):
            best_streak = (uid, s)
    hi = None
    if best_streak:
        uid, s = best_streak
        hi = {"label": "最長連擊紀錄", "name": _resolve_name(conn, uid),
              "value_str": f"{s['days']} 天", "note": f"{s['start']}~{s['end']}"}
    return {"rows": out, "highlight": hi}


# ─────────────────────────── 綜合型（composite）排行榜 ───────────────────────────

def _user_metrics(conn, group_id, period) -> dict:
    """一次算出每人各維度原始指標，供 contribution / all_rounder 共用。"""
    pf, pp = period_filter(period)
    rows = conn.execute(
        f"""SELECT user_id,
                  COUNT(*) AS msgs,
                  AVG(sentiment) AS avg_s,
                  SUM(CASE WHEN reply_to_message_id IS NULL THEN 1 ELSE 0 END) AS initiated,
                  SUM(CASE WHEN type IN ('image','video') THEN 1 ELSE 0 END) AS media
           FROM messages WHERE group_id=?{pf} GROUP BY user_id""", (group_id, *pp)).fetchall()
    # 被回覆次數（reply self-join，反向）— period 用 m.timestamp 避免與 r 欄位歧義
    mpf, mpp = period_filter(period, "m.timestamp")
    replied = dict(conn.execute(
        f"""SELECT m.user_id, COUNT(r.id) AS c
           FROM messages m JOIN messages r ON r.reply_to_message_id=m.line_message_id
           WHERE m.group_id=?{mpf} GROUP BY m.user_id""", (group_id, *mpp)).fetchall())
    # 旅行次數（區分 travel 與 event）
    kind_expr = _trip_kind_filter()
    trips_all = conn.execute(
        f"""SELECT tp.user_id AS uid, {kind_expr} AS kind, COUNT(DISTINCT tp.trip_id) AS c
           FROM trip_participants tp JOIN trips t ON t.id=tp.trip_id
           WHERE t.group_id=? AND {kind_expr} IS NOT NULL
           GROUP BY tp.user_id, {kind_expr}""", (group_id,)).fetchall()
    trips_total: dict[str, int] = {}
    trips_travel: dict[str, int] = {}
    trips_event: dict[str, int] = {}
    for r in trips_all:
        trips_total[r["uid"]] = trips_total.get(r["uid"], 0) + r["c"]
        if r["kind"] == "travel":
            trips_travel[r["uid"]] = trips_travel.get(r["uid"], 0) + r["c"]
        elif r["kind"] == "event":
            trips_event[r["uid"]] = trips_event.get(r["uid"], 0) + r["c"]
    metrics = {}
    for r in rows:
        uid = r["user_id"]
        metrics[uid] = {
            "msgs": r["msgs"], "avg_s": r["avg_s"] if r["avg_s"] is not None else 0.0,
            "initiated": r["initiated"], "media": r["media"],
            "replied": replied.get(uid, 0),
            "trips": trips_total.get(uid, 0),
            "trips_travel": trips_travel.get(uid, 0),
            "trips_event": trips_event.get(uid, 0),
        }
    return metrics


def _norm(v, mx):
    return min(100.0, v * 100.0 / mx) if mx else 0.0


def _cp_contribution(conn, group_id, period):
    m = _user_metrics(conn, group_id, period)
    m = {u: d for u, d in m.items() if d["msgs"] >= 10}
    if not m:
        return {"rows": [], "highlight": None}
    max_msgs = max(d["msgs"] for d in m.values())
    max_rep = max(d["replied"] for d in m.values()) or 1
    max_init = max(d["initiated"] for d in m.values()) or 1
    out = []
    for uid, d in m.items():
        activity = _norm(d["msgs"], max_msgs)
        response = _norm(d["replied"], max_rep)
        sentiment = max(0.0, min(100.0, (d["avg_s"] + 1) * 50))
        topic = _norm(d["initiated"], max_init)
        score = round(activity * 0.35 + response * 0.25 + sentiment * 0.25 + topic * 0.15)
        out.append(_row(conn, uid, score, f"{score}/100", None, extra={"breakdown": {
            "活躍": round(activity), "回應": round(response),
            "情緒": round(sentiment), "話題": round(topic)}}))
    out.sort(key=lambda r: -r["value"])
    return {"rows": out[:10], "highlight": None}


def _cp_all_rounder(conn, group_id, period):
    m = _user_metrics(conn, group_id, period)
    m = {u: d for u, d in m.items() if d["msgs"] >= 10}
    if not m:
        return {"rows": [], "highlight": None}
    mx = {k: (max(d[k] for d in m.values()) or 1)
          for k in ("msgs", "replied", "initiated", "media", "trips_travel")}
    out = []
    for uid, d in m.items():
        axes = {
            "活躍": round(_norm(d["msgs"], mx["msgs"])),
            "回應": round(_norm(d["replied"], mx["replied"])),
            "情緒": round(max(0.0, min(100.0, (d["avg_s"] + 1) * 50))),
            "話題": round(_norm(d["initiated"], mx["initiated"])),
            "創意": round(_norm(d["media"], mx["media"])),
            "旅行": round(_norm(d["trips_travel"], mx["trips_travel"])),
        }
        total = sum(axes.values())
        out.append(_row(conn, uid, total, f"{round(total / 6)} 分", None,
                        extra={"axes": axes}))
    out.sort(key=lambda r: -r["value"])
    return {"rows": out[:10], "highlight": None}


# ─────────────────────────── 註冊表 ───────────────────────────

BOARDS: list[BoardSpec] = [
    BoardSpec("sentiment", "正能量大使", "😊", "", "平均情緒分數（越正越好）",
              "rank", GREEN, _cp_sentiment),
    BoardSpec("streak", "連擊王", "🔥", "天", "最長連續發言天數",
              "rank", ORANGE, _cp_streak),
    BoardSpec("msg_length", "長文王", "📝", "字", "平均訊息長度",
              "rank", BLUE, _cp_msg_length),
    BoardSpec("sticker", "貼圖狂魔", "🎭", "%", "貼圖佔比（貼圖／總訊息）",
              "rank", ROSE, _cp_sticker),
    BoardSpec("trip", "旅行達人", "✈️", "次", "參與多日旅行次數（≥1 天）",
              "rank", TEAL, _cp_trip),
    BoardSpec("event", "事件王", "🎉", "次", "當日/單日事件參與次數",
              "rank", ROSE, _cp_event),
    BoardSpec("morning", "晨型人", "🌅", "則", "清晨 05:00–09:00 發言排行",
              "rank", GOLD, _cp_morning),
    BoardSpec("reply_speed", "閃電回覆王", "⚡", "分", "平均回應時間（越短越好）",
              "rank", GOLD, _cp_reply_speed, sparse=True),
    BoardSpec("terminator", "冷場王", "🥶", "%", "訊息後群組陷入沉默（≥30 分）的比率",
              "rank", GREY, _cp_terminator),
    BoardSpec("initiator", "話題發起王", "🎬", "則", "發起新話題（非回覆）的次數",
              "rank", PURPLE, _cp_initiator, sparse=True),
    BoardSpec("most_replied", "最受歡迎", "💬", "則/次", "平均被回覆次數",
              "rank", ROSE, _cp_most_replied, sparse=True),
    BoardSpec("growth", "進步最快", "📈", "%", "本週 vs 上週訊息成長",
              "rank", GREEN, _cp_growth),
    BoardSpec("seasonal", "本月活躍王", "🏅", "則", "當月發言排行 + 上月冠軍衛冕",
              "rank", GOLD, _cp_seasonal),
    BoardSpec("achievements", "特殊成就", "🎖️", "則", "單日最高紀錄 + 最長連擊",
              "rank", ORANGE, _cp_achievements),
    BoardSpec("contribution", "群組貢獻王", "🏆", "分", "綜合評分（活躍／回應／情緒／話題）",
              "score", GOLD, _cp_contribution),
    BoardSpec("all_rounder", "全能王", "👑", "分", "六邊形戰士：六維能力綜合",
              "radar", PURPLE, _cp_all_rounder),
]


def get_all_boards(group_id: str, period: str = "all") -> dict:
    with get_conn() as conn:
        return {"boards": [b.run(conn, group_id, period) for b in BOARDS]}


def find_board(keyword: str) -> BoardSpec | None:
    """依關鍵字（id 或標題子字串）找排行榜，供 LINE 指令使用。"""
    k = (keyword or "").strip().lower()
    if not k:
        return None
    for b in BOARDS:
        if k == b.id.lower() or k in b.title.lower() or b.title in keyword:
            return b
    return None


def get_board(keyword: str, group_id: str, period: str = "all") -> dict | None:
    """算單一排行榜（LINE Flex 卡片用）。找不到關鍵字回 None。"""
    b = find_board(keyword)
    if not b:
        return None
    with get_conn() as conn:
        return b.run(conn, group_id, period)


def board_menu() -> list[str]:
    """所有排行榜的 emoji + 標題（quick reply 清單用）。"""
    return [f"{b.emoji} {b.title}" for b in BOARDS]
