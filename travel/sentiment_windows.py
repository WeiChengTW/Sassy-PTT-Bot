"""視窗式情緒分析（治本版）。

逐則對短訊息打情緒分數雜訊過高，且台灣語助詞/反諷需要上下文。改以「對話視窗」
（預設 10 分鐘內、最多 8 則）帶上下文，用 pro 階模型判整段情緒，寫回該視窗每則
訊息的 sentiment 欄位。純事務/無情緒的視窗留 NULL（不塞 0，避免稀釋平均）。

- run_sentiment_backfill(group_id=None, only_null=True, ...)：排程與腳本共用入口。
  only_null=True 時只處理「整個視窗都尚未評分」的視窗 → 增量、冪等、便宜。
- 模型由 SENTIMENT_MODEL 環境變數決定（預設 gemini-3.1-pro-low）。
"""
import asyncio
import json
import os
import time

from openai import AsyncOpenAI

from travel.db import get_conn
from corpus_config import (
    GROUP_WINDOW_GAP_SEC, GROUP_WINDOW_MAX_MSGS, GROUP_MIN_WINDOW_CHARS,
)

BASE = os.getenv("CLI_PROXY_BASE_URL", "http://localhost:8317/v1")
KEY = os.getenv("CLI_PROXY_API_KEY", "")
MODEL = os.getenv("SENTIMENT_MODEL", "gemini-3.1-pro-low")
WINDOWS_PER_CALL = 12

PROMPT = """你是台灣年輕人 LINE 群組的情緒分析員。以下是多段連續對話（同一時段的視窗）。
判斷「每一段」整體的情緒，逐段輸出 JSON。

欄位：
- id（視窗 id，必須保留）
- sentiment（-1~1 浮點；-1 極負面、0 中性、1 極正面。若整段只是中性/事務性/貼圖閒聊/無明顯情緒，給 null）
- label（"positive"/"negative"/"neutral"）

台灣語感重點：
- 「幹」「靠」「屌」「誇張」常是語助詞或驚嘆，不必然負面，看語境。
- 要判讀反諷與玩笑的真實情緒（表面罵、實則鬧著玩 → 正面/中性）。
- 罵人、抱怨、吵架、失望才算負面；玩鬧、興奮、稱讚、期待算正面。

只輸出合法 JSON 陣列，不要 ```json 包裹。

對話：
{blocks}

JSON："""


def _all_group_ids() -> list[str]:
    with get_conn() as conn:
        return [r["group_id"] for r in conn.execute(
            "SELECT group_id FROM messages GROUP BY group_id")]


def build_windows(group_id: str, only_null: bool) -> list[dict]:
    """切視窗。only_null=True 時只保留「所有成員 sentiment 皆為 NULL」的視窗（增量）。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, user_name, content, type, timestamp, sentiment_at
               FROM messages WHERE group_id=? ORDER BY timestamp""",
            (group_id,),
        ).fetchall()
    windows, cur, last_ts = [], [], None

    def flush():
        if not cur:
            return
        lines, chars, processed = [], 0, False
        for m in cur:
            c = (m["content"] or "").strip() or f"[{m['type']}]"
            if m["content"]:
                chars += len((m["content"] or "").strip())
            if m["sentiment_at"] is not None:
                processed = True  # 已被視窗情緒處理過（不論結果正負或中性）
            lines.append(f"{m['user_name']}: {c}")
        windows.append({
            "id": len(windows),
            "msg_ids": [m["id"] for m in cur],
            "text": "\n".join(lines),
            "chars": chars,
            "processed": processed,
        })

    for m in rows:
        gap = (m["timestamp"] - last_ts) / 1000 if last_ts is not None else 0
        if cur and (gap > GROUP_WINDOW_GAP_SEC or len(cur) >= GROUP_WINDOW_MAX_MSGS):
            flush()
            cur = []
        cur.append(m)
        last_ts = m["timestamp"]
    flush()

    out = [w for w in windows if w["chars"] >= GROUP_MIN_WINDOW_CHARS]
    if only_null:
        out = [w for w in out if not w["processed"]]
    return out


async def _score_batch(client, batch):
    blocks = "\n\n".join(f"=== 視窗 id={w['id']} ===\n{w['text']}" for w in batch)
    resp = await client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": PROMPT.format(blocks=blocks)}],
        temperature=0.2,
        max_completion_tokens=2000,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip().rstrip("`").strip()
    return json.loads(raw)


def _write(id_to_msgids, results) -> int:
    """寫入情緒。每個模型有回傳的視窗都標記 sentiment_at（含中性/null，避免下次重掃）；
    非 null 者另寫 sentiment 值。回傳實際寫入分數的訊息數。"""
    now = int(time.time())
    n = 0
    with get_conn() as conn:
        for r in results:
            wid = r.get("id")
            if wid is None or wid not in id_to_msgids:
                continue
            mids = id_to_msgids[wid]
            s = r.get("sentiment")
            try:
                s = None if s is None else max(-1.0, min(1.0, float(s)))
            except (TypeError, ValueError):
                s = None
            if s is None:
                conn.executemany("UPDATE messages SET sentiment_at=? WHERE id=?",
                                 [(now, mid) for mid in mids])
            else:
                conn.executemany(
                    "UPDATE messages SET sentiment=?, sentiment_at=? WHERE id=?",
                    [(s, now, mid) for mid in mids])
                n += len(mids)
    return n


async def _run_group(group_id: str, only_null: bool, concurrency: int) -> dict:
    windows = build_windows(group_id, only_null)
    if not windows:
        return {"group": group_id, "windows": 0, "written": 0}
    id_to_msgids = {w["id"]: w["msg_ids"] for w in windows}
    batches = [windows[i:i + WINDOWS_PER_CALL] for i in range(0, len(windows), WINDOWS_PER_CALL)]
    client = AsyncOpenAI(base_url=BASE, api_key=KEY)
    sem = asyncio.Semaphore(concurrency)
    done = {"written": 0}

    async def worker(batch):
        async with sem:
            try:
                results = await _score_batch(client, batch)
            except Exception:
                return
        done["written"] += await asyncio.to_thread(_write, id_to_msgids, results)

    await asyncio.gather(*(worker(b) for b in batches))
    return {"group": group_id, "windows": len(windows), "written": done["written"]}


def run_sentiment_backfill(group_id: str | None = None, only_null: bool = True,
                           concurrency: int = 8) -> int:
    """情緒回填入口（同步）。group_id=None → 所有群。回傳寫入訊息數。

    only_null=True（排程預設）：只評分尚未有任何 sentiment 的視窗，增量且冪等。
    """
    groups = [group_id] if group_id else _all_group_ids()
    total = 0
    t0 = time.time()
    for g in groups:
        res = asyncio.run(_run_group(g, only_null, concurrency))
        total += res["written"]
        print(f"[SENTIMENT] {res['group'][:12]}… 視窗 {res['windows']} → 寫 {res['written']} 則")
    print(f"[SENTIMENT] 完成，共寫 {total} 則，耗時 {(time.time()-t0)/60:.1f} 分（模型 {MODEL}）")
    return total
