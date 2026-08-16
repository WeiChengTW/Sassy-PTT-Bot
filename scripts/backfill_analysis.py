#!/usr/bin/env python
"""並發回填 LLM 分析：把 analyzed_at IS NULL 的 text 訊息批次送 LLM，寫回結果。

重用 travel.llm_analyzer.analyze_batch 的 prompt / 呼叫 / 解析邏輯；差別在
並發多批（Semaphore 限流）並顯示進度。可隨時中斷續跑（只挑未分析的）。

用法：
    DB_PATH=data/chat.db python scripts/backfill_analysis.py
    DB_PATH=data/chat.db python scripts/backfill_analysis.py --concurrency 8 --limit 500
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

from travel.db import get_conn  # noqa: E402
from travel.llm_analyzer import analyze_batch, BATCH_SIZE  # noqa: E402


def fetch_pending(limit: int | None):
    q = """SELECT id, user_name, content, timestamp
           FROM messages
           WHERE analyzed_at IS NULL AND content IS NOT NULL
             AND type='text' AND length(content) > 1
           ORDER BY timestamp ASC"""
    if limit:
        q += f" LIMIT {int(limit)}"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q)]


def write_results(results: list[dict]) -> int:
    now = int(time.time())
    updated = 0
    with get_conn() as conn:
        for r in results:
            if "id" not in r:
                continue
            conn.execute(
                """UPDATE messages
                   SET is_travel_related=?, topics=?, keywords=?, sentiment=?,
                       locations=?, summary=?, analyzed_at=?
                   WHERE id=?""",
                (
                    r.get("is_travel_related", 0),
                    json.dumps(r.get("topics", []), ensure_ascii=False),
                    json.dumps(r.get("keywords", []), ensure_ascii=False),
                    r.get("sentiment", 0.0),
                    json.dumps(r.get("locations", []), ensure_ascii=False),
                    r.get("summary", ""),
                    now,
                    r["id"],
                ),
            )
            updated += 1
    return updated


async def main_async(concurrency: int, limit: int | None):
    pending = fetch_pending(limit)
    total = len(pending)
    if not total:
        print("沒有待分析訊息。")
        return
    batches = [pending[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    print(f"待分析 {total} 則 → {len(batches)} 批（每批 {BATCH_SIZE}，並發 {concurrency}）")

    sem = asyncio.Semaphore(concurrency)
    done = {"msgs": 0, "batches": 0, "fail": 0}
    t0 = time.time()

    async def worker(batch):
        async with sem:
            try:
                results = await analyze_batch(batch)
            except Exception as e:
                done["fail"] += 1
                print(f"  ⚠️ 批次失敗（{len(batch)} 則跳過續跑）：{e}")
                return
        # 寫 DB（同步）放到執行緒避免卡事件迴圈
        updated = await asyncio.to_thread(write_results, results)
        done["msgs"] += updated
        done["batches"] += 1
        if done["batches"] % 10 == 0 or done["batches"] == len(batches):
            el = time.time() - t0
            rate = done["msgs"] / el if el else 0
            eta = (total - done["msgs"]) / rate if rate else 0
            print(f"  進度 {done['batches']}/{len(batches)} 批 | "
                  f"{done['msgs']}/{total} 則 | {rate:.0f} 則/s | ETA {eta/60:.1f} 分")

    await asyncio.gather(*(worker(b) for b in batches))
    el = time.time() - t0
    print(f"完成：分析 {done['msgs']} 則，失敗批 {done['fail']}，耗時 {el/60:.1f} 分。")
    if done["fail"]:
        print("有失敗批次 — 重跑本腳本即可續跑剩餘未分析訊息。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None, help="只處理前 N 則（測試用）")
    args = ap.parse_args()
    asyncio.run(main_async(args.concurrency, args.limit))


if __name__ == "__main__":
    main()
