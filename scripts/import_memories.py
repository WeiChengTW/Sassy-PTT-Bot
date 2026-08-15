#!/usr/bin/env python
"""批次匯入群組歷史大事件（44 筆）到 trips 表。

每筆含日期（單日或區間）、標題、稀有度。稀有度直接寫入 trips.rarity，
發徽章時（travel.badges.award_badges_for_trip）會優先採用。

用法：
    DB_PATH=data/chat.db python scripts/import_memories.py

冪等：以 (group_id, title, start_date) 去重，重跑不會重複插入。
"""
import os
import sys
import time
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from travel.db import get_conn  # noqa: E402

GROUP_ID = "Cba567481e809e13952a49947ad6afea2"

RARITY_ZH = {
    "普通": "common",
    "稀有": "rare",
    "極稀有": "super_rare",
    "史詩": "epic",
    "傳說": "legendary",
}

# (日期字串, 標題, 稀有度中文)
MEMORIES: list[tuple[str, str, str]] = [
    ("2021/11/4", "秋煌小嚇一跳", "稀有"),
    ("2022/1/7", "柏哥google map", "史詩"),
    ("2022/3/28", "人形立牌", "傳說"),
    ("2022/3/29", "愛心小卡掉不下來", "史詩"),
    ("2022/3/30", "南灣足跡重疊", "極稀有"),
    ("2022/3/31", "抓到魔牆人偶", "史詩"),
    ("2022/4/16", "疫情大爆發", "稀有"),
    ("2022/4/29", "google classroom高朋滿座", "普通"),
    ("2022/6/16", "彥中哥的杯杯", "普通"),
    ("2022/6/17", "世紀大騙局", "極稀有"),
    ("2022/7/29", "暑輔大翹課", "稀有"),
    ("2022/8/17", "初見游媽媽", "普通"),
    ("2022/11/5", "反轉趣味競賽", "普通"),
    ("2022/12/2", "水晶綠光戰警", "傳說"),
    ("2022/12/30", "軍武課火燒車", "稀有"),
    ("2023/1/18", "彥中哥動物園狩獵", "極稀有"),
    ("2023/2/1-2/2", "牛牛牧場", "極稀有"),
    ("2023/2/21", "OK幫出動", "普通"),
    ("2023/3/1", "楊子賢仙人跳", "稀有"),
    ("2023/3/3", "合作社開張", "極稀有"),
    ("2023/3/4", "匾額", "傳說"),
    ("2023/3/8", "講了多少遍，故意的", "極稀有"),
    ("2023/3/9", "楊哲嘉獲得教授稱號", "稀有"),
    ("2023/4/14", "美術課修抽屜", "普通"),
    ("2023/5/12", "變裝（性）畢業舞會", "傳說"),
    ("2023/5/17", "火鍋", "傳說"),
    ("2023/5/25", "鬆餅", "傳說"),
    ("2023/6/1", "水槍大戰", "極稀有"),
    ("2023/8/2-8/3", "宜蘭初體驗", "傳說"),
    ("2023/8/30", "芭比+柏哥方向燈沒關", "稀有"),
    ("2023/11/4", "返校+宏論T的起點", "極稀有"),
    ("2024/2/4", "保齡球+動物園派貼機", "極稀有"),
    ("2024/8/20-8/22", "宜蘭復仇局", "傳說"),
    ("2024/11/2", "返校", "稀有"),
    ("2025/1/17", "楊哲嘉的男模們", "極稀有"),
    ("2025/1/19", "王弈尹考學測", "極稀有"),
    ("2025/2/4-2/6", "武嶺極地求生", "傳說"),
    ("2025/6/25-6/28", "勃哥的澎湖", "史詩"),
    ("2025/8/27-8/29", "宜蘭魔法大戰", "傳說"),
    ("2025/9/6", "彥中哥酩酊大醉", "極稀有"),
    ("2025/11/1", "返校+烤肉", "極稀有"),
    ("2026/1/19", "陳挪威發傳單", "史詩"),
    ("2026/2/1-2/4", "台南國旅最終章", "傳說"),
    ("2026/8/7-8/9", "墾丁一日遊", "傳說"),
]


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
    inserted = skipped = 0
    now = int(time.time())
    with get_conn() as conn:
        for date_str, title, rarity_zh in MEMORIES:
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
    print(f"匯入完成：inserted={inserted}, skipped={skipped}, total={len(MEMORIES)}")


if __name__ == "__main__":
    main()
