#!/usr/bin/env python
"""Seed 群組成員名單到 members 表。

已在 messages 說過話者直接綁真實 LINE user_id（source=auto, resolved=1）；
未說話者用合成 id 'manual:<uuid8>'（source=manual, resolved=0），
日後說話時由 travel.db.reconcile_member() 自動接回真實 id。

成員名單從 `LINE_GROUP_MEMBERS` env 讀，逗號分隔（避免把真人姓名寫進 repo）。
範例：
    LINE_GROUP_MEMBERS=Alice,Bob,Carol

用法：
    DB_PATH=data/chat.db python scripts/seed_members.py

冪等：同群同 display_name 已存在則跳過。
"""
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from travel.db import get_conn  # noqa: E402

GROUP_ID = os.getenv("LINE_GROUP_ID", "").strip()
if not GROUP_ID:
    sys.exit("錯誤：LINE_GROUP_ID 未設定，請在 .env 填入主群 LINE 群組 ID")

_raw = os.getenv("LINE_GROUP_MEMBERS", "").strip()
if not _raw:
    sys.exit(
        "錯誤：LINE_GROUP_MEMBERS 未設定。請在 .env 用逗號分隔列出 display_name，\n"
        "例：LINE_GROUP_MEMBERS=Alice,Bob,Carol"
    )
MEMBERS = [name.strip() for name in _raw.split(",") if name.strip()]


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
