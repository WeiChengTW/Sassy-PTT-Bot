"""聊天摘要：群組內 @機器人「現在是怎樣」→ 摘要「這一輪」對話，給爬樓爬不完的人。

「一輪」＝從最新訊息往回走，碰到停頓超過 ROUND_GAP_MS 就停，同一輪不設則數上限。
發問者本身若是沉寂許久後第一個開口的，發問訊息不算在內，自然會落到上一輪。
一輪少於 MIN_MSGS 則不摘要，直接嗆回去。
"""
import os
import random
import re
from datetime import datetime, timedelta, timezone

SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "gemini-3.8-flash-high")

SUMMARY_TRIGGER = "現在是怎樣"
_TRAILING_PUNCT_RE = re.compile(r"[\s?？!！.。~～]+$")

ROUND_GAP_MS = 30 * 60 * 1000       # 停頓超過 30 分鐘視為新的一輪
MIN_MSGS = 10                        # 一輪少於此數不摘要，直接嗆「不會自己看喔」
FETCH_LIMIT = 2000                   # 撈 DB 的保險上限（實際一輪最長約數百則）
MAX_CONTENT_CHARS = 200

_TZ = timezone(timedelta(hours=8))
_MEDIA_LABELS = {
    "sticker": "[貼圖]", "image": "[照片]", "video": "[影片]",
    "audio": "[語音]", "file": "[檔案]", "location": "[位置]",
}


def is_summary_request(text: str) -> bool:
    """只認「現在是怎樣」整句（@機器人 已先去掉），句尾可帶問號、驚嘆號等。"""
    return _TRAILING_PUNCT_RE.sub("", text.strip()) == SUMMARY_TRIGGER


def select_round(msgs: list[dict]) -> list[dict]:
    """msgs 依 timestamp 升序（不含發問那則）。回傳最後一輪：往回走到第一個超過 ROUND_GAP_MS 的停頓為止。"""
    if not msgs:
        return []
    start = len(msgs) - 1
    while start > 0 and msgs[start]["timestamp"] - msgs[start - 1]["timestamp"] <= ROUND_GAP_MS:
        start -= 1
    return msgs[start:]


def too_short_reply(n: int) -> str:
    return random.choice([
        f"才 {n} 則是不會自己往上滑喔 🙄",
        f"{n} 則而已，手指斷了？自己看啦",
        f"就 {n} 則你也要懶人包，懶到一個境界",
    ])


def fetch_messages(group_id: str, before_ts: int) -> list[dict]:
    """撈發問之前的訊息（升序），量足夠 select_round 做判斷即可。"""
    from travel.db import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT user_name, content, type, timestamp FROM messages
               WHERE group_id = ? AND timestamp < ? AND is_deleted = 0
               ORDER BY timestamp DESC LIMIT ?""",
            (group_id, before_ts, FETCH_LIMIT),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def _fmt_time(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, _TZ).strftime("%H:%M")


def format_transcript(msgs: list[dict]) -> str:
    lines = []
    for m in msgs:
        content = (m.get("content") or "").replace("\n", " ").strip()
        if m.get("type") != "text":
            content = _MEDIA_LABELS.get(m.get("type"), f"[{m.get('type')}]")
        lines.append(f"{_fmt_time(m['timestamp'])} {m['user_name']}: {content[:MAX_CONTENT_CHARS]}")
    return "\n".join(lines)


def summary_header(msgs: list[dict]) -> str:
    start, end = msgs[0]["timestamp"], msgs[-1]["timestamp"]
    day = datetime.fromtimestamp(start / 1000, _TZ)
    today = datetime.now(_TZ).date()
    date_part = "" if day.date() == today else day.strftime("%m/%d ")
    return f"📋 {date_part}{_fmt_time(start)}～{_fmt_time(end)}，共 {len(msgs)} 則"


def build_messages(transcript: str, asker: str) -> list[dict]:
    system = (
        "你是這個 LINE 群組裡嘴很賤的 PTT 鄉民老成員「鍵盤俠」。"
        f"{asker} 剛回來，爬樓爬不完，請你幫他整理剛剛的對話。\n"
        "規則：\n"
        "1. 用 3～6 點條列，每點以「・」開頭，一點一行，交代誰說了什麼、吵了什麼、結論是什麼。\n"
        "2. 一定要點名（用對話裡的名字），可以帶一點酸，但事實不能亂編。\n"
        "3. 貼圖、照片只是氣氛，不用特別提。\n"
        "4. 最後一行用一句話酸總結，以「總之：」開頭。\n"
        "5. 只輸出條列和總結，不要加標題、前言或解釋。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"對話紀錄：\n{transcript}"},
    ]
