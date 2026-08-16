#!/usr/bin/env python
"""視窗式情緒分析：把訊息切成對話視窗、用強模型判整段情緒，寫回每則訊息 sentiment。

為什麼不逐則：短訊息（「好」「哈哈」「幹」）孤立打分是雜訊，且台灣語助詞/反諷需要
上下文。改以「對話視窗」（10 分鐘內、最多 8 則）帶上下文打一個情緒，套回該視窗
每則訊息的 sentiment 欄位——既有 AVG(sentiment) WHERE NOT NULL 的聚合自動變乾淨。

- 純事務/無明顯情緒的視窗 → sentiment 留 NULL（不再塞 0，避免稀釋平均）。
- 模型：預設 gemini-3.1-pro-low（Gemini pro 階，語感優於 flash）。
- 冪等/可續跑：--only-null 只補尚未被視窗覆蓋的；預設全量覆寫。

用法：
    DB_PATH=data/chat.db python scripts/backfill_sentiment.py --sample 15
    DB_PATH=data/chat.db python scripts/backfill_sentiment.py --concurrency 12
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from openai import AsyncOpenAI  # noqa: E402
from travel.db import get_conn  # noqa: E402
from corpus_config import (  # noqa: E402
    MAIN_GROUP_ID, GROUP_WINDOW_GAP_SEC, GROUP_WINDOW_MAX_MSGS, GROUP_MIN_WINDOW_CHARS,
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


def build_windows(group_id: str):
    """回傳 [{'id', 'msg_ids': [...], 'text': '對話文字'}]。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, user_name, content, type, timestamp
               FROM messages WHERE group_id=? ORDER BY timestamp""",
            (group_id,),
        ).fetchall()
    windows = []
    cur = []
    last_ts = None

    def flush():
        if not cur:
            return
        lines = []
        chars = 0
        for m in cur:
            c = (m["content"] or "").strip()
            if not c:
                c = f"[{m['type']}]"
            else:
                chars += len(c)
            lines.append(f"{m['user_name']}: {c}")
        windows.append({
            "id": len(windows),
            "msg_ids": [m["id"] for m in cur],
            "text": "\n".join(lines),
            "chars": chars,
        })

    for m in rows:
        gap = (m["timestamp"] - last_ts) / 1000 if last_ts is not None else 0
        if cur and (gap > GROUP_WINDOW_GAP_SEC or len(cur) >= GROUP_WINDOW_MAX_MSGS):
            flush()
            cur = []
        cur.append(m)
        last_ts = m["timestamp"]
    flush()
    # 內容太短（純貼圖/單字）直接視為中性、不送模型
    return [w for w in windows if w["chars"] >= GROUP_MIN_WINDOW_CHARS]


async def score_batch(client, batch):
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


def write_scores(id_to_msgids: dict, results: list[dict]) -> int:
    n = 0
    with get_conn() as conn:
        for r in results:
            wid = r.get("id")
            if wid is None or wid not in id_to_msgids:
                continue
            s = r.get("sentiment")
            if s is None:
                continue  # 中性視窗留 NULL
            try:
                s = max(-1.0, min(1.0, float(s)))
            except (TypeError, ValueError):
                continue
            conn.executemany(
                "UPDATE messages SET sentiment=? WHERE id=?",
                [(s, mid) for mid in id_to_msgids[wid]],
            )
            n += len(id_to_msgids[wid])
    return n


async def main_async(args):
    windows = build_windows(MAIN_GROUP_ID)
    if args.sample:
        windows = windows[: args.sample]
    total = len(windows)
    print(f"視窗 {total} 個（模型 {MODEL}，每呼叫 {WINDOWS_PER_CALL} 視窗，並發 {args.concurrency}）")
    id_to_msgids = {w["id"]: w["msg_ids"] for w in windows}
    batches = [windows[i:i + WINDOWS_PER_CALL] for i in range(0, total, WINDOWS_PER_CALL)]

    client = AsyncOpenAI(base_url=BASE, api_key=KEY)
    sem = asyncio.Semaphore(args.concurrency)
    done = {"win": 0, "msg": 0, "fail": 0}
    t0 = time.time()

    async def worker(batch):
        async with sem:
            try:
                results = await score_batch(client, batch)
            except Exception as e:
                done["fail"] += 1
                print(f"  ⚠️ 批次失敗（{len(batch)} 視窗跳過）：{e}")
                return
        if args.sample:
            by_id = {w["id"]: w for w in batch}
            for r in results:
                w = by_id.get(r.get("id"))
                if not w:
                    continue
                print(f"\n[{r.get('sentiment')} · {r.get('label')}]")
                print("  " + w["text"].replace("\n", "\n  ")[:300])
            return
        n = await asyncio.to_thread(write_scores, id_to_msgids, results)
        done["win"] += len(batch)
        done["msg"] += n
        if done["win"] % (WINDOWS_PER_CALL * 10) < WINDOWS_PER_CALL:
            el = time.time() - t0
            rate = done["win"] / el if el else 0
            print(f"  {done['win']}/{total} 視窗 | 寫 {done['msg']} 則 | {rate:.0f} 視窗/s | "
                  f"ETA {(total-done['win'])/rate/60:.1f} 分")

    await asyncio.gather(*(worker(b) for b in batches))
    if not args.sample:
        print(f"完成：{done['win']} 視窗 → 寫入 {done['msg']} 則 sentiment，失敗批 {done['fail']}，"
              f"耗時 {(time.time()-t0)/60:.1f} 分")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0, help="只試打前 N 視窗、印結果、不寫 DB")
    ap.add_argument("--concurrency", type=int, default=10)
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
