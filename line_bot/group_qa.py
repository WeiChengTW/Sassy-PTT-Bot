"""群組問答：`@機器人 ？問題` → 從群組全部聊天紀錄 + 旅行紀錄找答案，先答案再酸一句。

流程：
1. parse_qa_command：`？`/`?` 開頭才算指令；只有問號沒問題 → 直接嗆（empty_question_reply）
2. LLM 第 1 步（build_intent_messages / parse_intent）：整理完整問題 + 產生搜尋關鍵字（含日期同義詞）
3. search_windows：純 SQL 撈全部歷史訊息做關鍵字比對（全群約數萬則，掃一遍幾十毫秒），
   命中點前後各取 RADIUS 則成視窗，合併重疊後依「命中不同關鍵字數、時間新近」排序取前幾段
   （不靠向量索引，當天訊息也找得到）
4. LLM 第 2 步（build_answer_messages）：根據聊天紀錄 + 旅行紀錄（trips 表，日期最準）回答
"""
import json
import os
import random
import re
from datetime import datetime, timedelta, timezone

QA_MODEL = os.getenv("QA_MODEL", "gemini-3.8-flash-high")                    # 回答
QA_INTENT_MODEL = os.getenv("QA_INTENT_MODEL", "gemini-3.5-flash-lite")      # 抽關鍵字，要快

RECENT_MSGS = 15          # 補前後文用的最近訊息數
RADIUS = 8                # 命中點前後各取幾則
MAX_WINDOW_LINES = 60     # 單一視窗上限（避免熱門詞把整段聊天串成一大塊）
MAX_WINDOWS = 6
RECENT_WINDOWS = 3        # 其中保留給最近 RECENT_DAYS 天的名額，避免新計畫被多年前的舊對話擠掉
RECENT_DAYS = 30
MAX_TOTAL_LINES = 300
MAX_KEYWORDS = 10

_TZ = timezone(timedelta(hours=8))
_WEEKDAYS = "一二三四五六日"
_QA_PREFIX_RE = re.compile(r"^[?？]")


def parse_qa_command(text: str) -> str | None:
    """`？問題` / `?問題` → 回傳問題（可能為空字串）；不是問答指令回 None。"""
    text = text.strip()
    if not _QA_PREFIX_RE.match(text):
        return None
    return text.lstrip("?？ 　").strip()


def empty_question_reply() -> str:
    return random.choice([
        "問號是在問三小，問題呢？",
        "？你是按到還是腦袋空白",
        "打個問號就想要答案，你當我通靈喔",
        "問題勒？被你吃掉了？",
    ])


def today_label(now: datetime | None = None) -> str:
    now = now or datetime.now(_TZ)
    return f"{now:%Y/%m/%d}（週{_WEEKDAYS[now.weekday()]}）"


def build_intent_messages(question: str, recent_transcript: str, today: str) -> list[dict]:
    prompt = (
        f"今天是 {today}。LINE 群組有人問機器人問題，請整理成完整問題，並產生用來搜尋群組聊天紀錄的關鍵字。\n"
        f"他問：「{question}」\n\n"
        f"最近的對話（補前後文用）：\n{recent_transcript}\n\n"
        "要求：\n"
        "1. question：把問題補完整（例如把「那天」換成實際日期）。\n"
        f"2. keywords：3～{MAX_KEYWORDS} 個短關鍵字（每個至少 2 個字），是聊天紀錄裡「可能直接出現」的字詞。"
        "日期要列出各種寫法（例：9/28、28號、禮拜一、週一），加上活動名稱與相關動詞（例：烤肉、集合、幾點）。\n"
        '3. 只輸出 JSON：{"question": "...", "keywords": ["...", "..."]}'
    )
    return [{"role": "user", "content": prompt}]


def _fallback_keywords(question: str) -> list[str]:
    """LLM 解析失敗時：取問題中的日期/數字與 2 字以上的中文片段。"""
    parts = re.findall(r"\d+/\d+|\d+號|[一-鿿]{2,}", question)
    return list(dict.fromkeys(parts))[:MAX_KEYWORDS]


def expand_date_keywords(keywords: list[str], question: str, now: datetime | None = None) -> list[str]:
    """問題或關鍵字裡的 M/D 自動補上同義寫法（28號、9月28、禮拜一、週一、星期一），不靠 LLM 每次記得。

    年份取離今天最近的那一年（跨年問 1/3 會算明年）。
    """
    now = now or datetime.now(_TZ)
    out = list(keywords)
    for m, d in re.findall(r"(\d{1,2})/(\d{1,2})", " ".join([question, *keywords])):
        month, day = int(m), int(d)
        candidates = []
        for year in (now.year - 1, now.year, now.year + 1):
            try:
                candidates.append(datetime(year, month, day, tzinfo=now.tzinfo))
            except ValueError:
                pass
        if not candidates:
            continue
        date = min(candidates, key=lambda c: abs((c - now).total_seconds()))
        wd = _WEEKDAYS[date.weekday()]
        names = ["禮拜天", "禮拜日", "週日", "星期日", "星期天"] if wd == "日" else [f"禮拜{wd}", f"週{wd}", f"星期{wd}"]
        out += [f"{month}/{day}", f"{day}號", f"{month}月{day}", *names]
    return list(dict.fromkeys(out))


def parse_intent(raw: str | None, question: str) -> dict:
    """解析第 1 步 JSON；失敗時退回原問題 + 規則抽出的關鍵字。"""
    m = re.search(r"\{.*\}", raw or "", re.DOTALL)
    try:
        data = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        data = {}
    full_q = str(data.get("question") or "").strip() or question
    # 單字關鍵字（約、到）幾乎每段都命中，只會塞雜訊
    kws = [str(k).strip() for k in (data.get("keywords") or []) if len(str(k).strip()) >= 2]
    kws = list(dict.fromkeys(kws))[:MAX_KEYWORDS] or _fallback_keywords(full_q)
    return {"question": full_q, "keywords": kws}


def search_windows(msgs: list[dict], keywords: list[str], recent_since_ms: int | None = None) -> list[list[dict]]:
    """msgs 依時間升序。回傳命中視窗（每段為連續訊息），依時間先後排列。

    recent_since_ms 有給時，先從最後命中在此之後的視窗挑 RECENT_WINDOWS 段，其餘名額再從全部挑。
    """
    kws = [k for k in keywords if k]
    windows: list[dict] = []   # {start, end, kws, last_hit}
    for i, m in enumerate(msgs):
        content = m.get("content") or ""
        hit = {k for k in kws if k in content}
        if not hit:
            continue
        start, end = max(0, i - RADIUS), min(len(msgs) - 1, i + RADIUS)
        w = windows[-1] if windows else None
        if w and start <= w["end"] + 1 and end - w["start"] + 1 <= MAX_WINDOW_LINES:
            w["end"] = max(w["end"], end)
            w["kws"] |= hit
            w["last_hit"] = i
        else:
            windows.append({"start": start, "end": end, "kws": set(hit), "last_hit": i})

    windows.sort(key=lambda w: (len(w["kws"]), w["last_hit"]), reverse=True)
    chosen, total = [], 0

    def take(pool, limit):
        nonlocal total
        for w in pool:
            if len(chosen) >= limit:
                return
            n = w["end"] - w["start"] + 1
            if w in chosen or total + n > MAX_TOTAL_LINES:
                continue
            chosen.append(w)
            total += n

    if recent_since_ms is not None:
        take([w for w in windows if msgs[w["last_hit"]]["timestamp"] >= recent_since_ms], RECENT_WINDOWS)
    take(windows, MAX_WINDOWS)
    chosen.sort(key=lambda w: w["start"])
    return [msgs[w["start"]:w["end"] + 1] for w in chosen]


def fetch_text_messages(group_id: str, before_ts: int) -> list[dict]:
    """發問前的全部文字訊息（升序）。"""
    from travel.db import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT user_name, content, type, timestamp FROM messages
               WHERE group_id = ? AND timestamp < ?
                 AND type = 'text' AND is_deleted = 0
               ORDER BY timestamp""",
            (group_id, before_ts),
        ).fetchall()
    return [dict(r) for r in rows]


_TRIP_STATUS = {"planning": "規劃中", "ongoing": "進行中", "ended": "已結束"}


def format_trip_facts(trips: list[dict]) -> str:
    """trips 表 → 一行一筆：`名稱｜地點｜日期｜狀態`（start/end_date 為秒）。"""
    def day(ts):
        return datetime.fromtimestamp(ts, _TZ).strftime("%Y/%m/%d")
    lines = []
    for t in trips:
        if not t.get("start_date"):
            continue
        when = day(t["start_date"])
        if t.get("end_date") and t["end_date"] != t["start_date"]:
            when += f"～{day(t['end_date'])}"
        status = _TRIP_STATUS.get(t.get("status"), t.get("status") or "")
        lines.append(f"{t['title']}｜{t.get('location') or '—'}｜{when}｜{status}")
    return "\n".join(lines)


def fetch_trips(group_id: str) -> list[dict]:
    from travel.db import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT title, location, start_date, end_date, status FROM trips WHERE group_id = ? ORDER BY start_date",
            (group_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def build_answer_messages(question: str, asker: str, windows_text: str,
                          recent_transcript: str, today: str, trips_text: str = "") -> list[dict]:
    system = (
        "你是這個 LINE 群組裡嘴很賤的 PTT 鄉民老成員「鍵盤俠」，但這次要把問題答對。\n"
        f"今天是 {today}。{asker} 問你問題，請根據下面的旅行紀錄與群組聊天紀錄回答。\n"
        "規則：\n"
        "1. 只能根據紀錄回答，不准編造；引用聊天時講出是誰、哪天說的（例：陳諾威 9/18 說…）。\n"
        "   問到旅行或活動的日期、地點時，以旅行紀錄為準；已經結束的活動就直接說哪天已經去過了。\n"
        "2. 同一件事有不同說法、而且沒人明確說哪個才對時，一律以日期最新的說法回答；"
        "舊說法不用提，除非不提會讓人看不懂。\n"
        "3. 答案跟吐槽融在一起講，2～4 句，像老朋友邊嗆邊回答，不要另起一行單獨酸；"
        "但答案要在第一句就出現，日期、時間、地點、人名一定要講清楚，不能為了嗆而講模糊。\n"
        "4. 紀錄裡找不到答案就直說「紀錄裡沒講」，並叫他去問最常講這件事的人。\n"
        "5. 不要加標題、前言或解釋。"
    )
    user = (
        f"問題：{question}\n\n"
        f"旅行紀錄（名稱｜地點｜日期｜狀態）：\n{trips_text or '（無）'}\n\n"
        f"搜尋到的聊天紀錄：\n{windows_text or '（沒有找到相關紀錄）'}\n\n"
        f"最近的對話：\n{recent_transcript}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
