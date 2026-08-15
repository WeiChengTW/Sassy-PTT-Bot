#!/usr/bin/env python
"""Seed 群組成員名單（14 位真人，排除機器人）到 members 表。

已在 messages 說過話者直接綁真實 LINE user_id（source=auto, resolved=1）；
未說話者用合成 id 'manual:<uuid8>'（source=manual, resolved=0），
日後說話時由 travel.db.reconcile_member() 自動接回真實 id。

用法：
    DB_PATH=data/chat.db python scripts/seed_members.py

冪等：同群同 display_name 已存在則跳過。
"""
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from travel.db import get_conn  # noqa: E402

GROUP_ID = "Cba567481e809e13952a49947ad6afea2"

MEMBERS = [
    "洪偉城", "Boy", "尹玟馨", "李孟倢", "楊哲嘉", "楊子賢", "王弈尹",
    "范丞皓", "連定烊", "鈞", "陳彥中", "陳諾威", "霈姍", "黃正杰",
]


def main() -> None:
    now = int(time.time())
    inserted = skipped = linked = 0
    with get_conn() as conn:
        for name in MEMBERS:
            exists = conn.execute(
                "SELECT 1 FROM members WHERE group_id=? AND display_name=?",
                (GROUP_ID, name),
            ).fetchone()
            if exists:
                skipped += 1
                continue
            row = conn.execute(
                """SELECT user_id FROM messages
                   WHERE group_id=? AND user_name=? AND user_name IS NOT NULL
                   ORDER BY timestamp LIMIT 1""",
                (GROUP_ID, name),
            ).fetchone()
            if row:
                user_id, source, resolved = row["user_id"], "auto", 1
                linked += 1
            else:
                user_id, source, resolved = f"manual:{uuid.uuid4().hex[:8]}", "manual", 0
            conn.execute(
                """INSERT INTO members
                   (group_id, user_id, display_name, source, resolved, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (GROUP_ID, user_id, name, source, resolved, now),
            )
            inserted += 1
    print(f"Seed 完成：inserted={inserted}（其中 linked={linked}）, skipped={skipped}, total={len(MEMBERS)}")


if __name__ == "__main__":
    main()
