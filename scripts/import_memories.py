#!/usr/bin/env python
"""批次匯入群組歷史大事件到 trips 表。

每筆含日期（單日或區間）、標題、稀有度。稀有度直接寫入 trips.rarity，
發徽章時（travel.badges.award_badges_for_trip）會優先採用。

事件清單放在 `MEMORIES_PATH` 指向的 JSON 檔（預設 `data/memories.json`，
gitignored）。格式：
    [{"date": "2021/11/4", "title": "...", "rarity_zh": "稀有"}, ...]

rarity_zh 對照：普通=common / 稀有=rare / 極稀有=super_rare /
史詩=epic / 傳說=legendary。

用法：
    DB_PATH=data/chat.db python scripts/import_memories.py
    MEMORIES_PATH=/path/to/other.json python scripts/import_memories.py

冪等：以 (group_id, title, start_date) 去重，重跑不會重複插入。
"""
import json
import os
import sys
import time
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from travel.db import get_conn  # noqa: E402

GROUP_ID = os.getenv("LINE_GROUP_ID", "").strip()
if not GROUP_ID:
    sys.exit("錯誤：LINE_GROUP_ID 未設定，請在 .env 填入主群 LINE 群組 ID")

MEMORIES_PATH = os.getenv("MEMORIES_PATH", "data/memories.json")

RARITY_ZH = {
    "普通": "common",
    "稀有": "rare",
    "極稀有": "super_rare",
    "史詩": "epic",
    "傳說": "legendary",
}


def _load_memories() -> list[dict]:
    if not os.path.exists(MEMORIES_PATH):
        sys.exit(
            f"找不到 {MEMORIES_PATH}。請建立該檔（內容格式見模組 docstring）或用 "
            "MEMORIES_PATH env 指定其他路徑。"
        )
    with open(MEMORIES_PATH, encoding="utf-8") as f:
        items = json.load(f)
    if not isinstance(items, list):
        sys.exit(f"{MEMORIES_PATH} 必須是 JSON 陣列")
    return items


def _midnight_epoch(year: int, month: int, day: int) -> int:
    """回傳當地時區當日午夜的 epoch 秒。"""
    return int(datetime(year, month, day).timestamp())


def parse_dates(date_str: str) -> tuple[int, int | None]:
    """解析 'YYYY/M/D' 或 'YYYY/M/D-D' / 'YYYY/M/D-M/D'，回傳 (start, end|None)。"""
    if "-" not in date_str:
        y, m, d = (int(x) for x in date_str.split("/"))
        return _midnight_epoch(y, m, d), None

    left, right = date_str.split("-", 1)
    y, m, d = (int(x) for x in left.split("/"))
    start = _midnight_epoch(y, m, d)
    right_parts = [int(x) for x in right.split("/")]
    if len(right_parts) == 1:  # 'YYYY/M/D-D'（同年同月）
        end = _midnight_epoch(y, m, right_parts[0])
    else:  # 'YYYY/M/D-M/D'（同年）
        end = _midnight_epoch(y, right_parts[0], right_parts[1])
    return start, end


def main() -> None:
    memories = _load_memories()
    inserted = skipped = 0
    now = int(time.time())
    with get_conn() as conn:
        for item in memories:
            date_str = item["date"]
            title = item["title"]
            rarity_zh = item["rarity_zh"]
            if rarity_zh not in RARITY_ZH:
                sys.exit(f"未知稀有度 '{rarity_zh}'（title={title}），允許值：{list(RARITY_ZH)}")
            rarity = RARITY_ZH[rarity_zh]
            start, end = parse_dates(date_str)
            exists = conn.execute(
                "SELECT 1 FROM trips WHERE group_id=? AND title=? AND start_date=?",
                (GROUP_ID, title, start),
            ).fetchone()
            if exists:
                skipped += 1
                continue
            conn.execute(
                """INSERT INTO trips
                   (id, group_id, title, location, start_date, end_date,
                    trip_type, rarity, created_by, created_at, status)
                   VALUES (?, ?, ?, NULL, ?, ?, NULL, ?, 'import', ?, 'planning')""",
                (str(uuid.uuid4()), GROUP_ID, title, start, end, rarity, start),
            )
            inserted += 1
    print(f"匯入完成：inserted={inserted}, skipped={skipped}, total={len(memories)}")


if __name__ == "__main__":
    main()
