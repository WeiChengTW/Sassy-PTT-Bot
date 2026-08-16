#!/usr/bin/env python
"""解析 LINE 群組匯出 .txt，回填 messages（與 members）表。

匯出檔格式（tab 分隔）：
    儲存日期： 2026/08/16 13:04
    2023/08/01（二）              <- 日期分隔行
    09:51\t洪偉城\t訊息內容        <- 一般訊息
    10:55\t\t⁨⁨Boy⁩⁩已新增⁨⁨范丞皓⁩⁩至群組。  <- 系統訊息（發言者空白）
    續行（無時間戳）              <- 多行訊息的延續，接到上一則

限制（見對話評估）：
  - 只有暱稱、沒有真實 LINE user_id → 用合成 id（同 seed_members 的 manual: 機制）
  - 時間戳只到「分」，同分鐘多則同秒；假設時區 Asia/Taipei
  - 媒體只留標記 [貼圖]/[照片] 等，無實體
  - 分析欄位（keywords/sentiment/...）不填，需另跑 LLM 分析回填

冪等：line_message_id 用 (group_id + timestamp + seq) 決定性合成，重跑不重複。

用法：
    python scripts/import_line_export.py --file "[LINE] ....txt" --dry-run
    DB_PATH=data/chat.db python scripts/import_line_export.py --file "[LINE] ....txt"
"""
import argparse
import hashlib
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from corpus_config import KNOWN_BOTS, MAIN_GROUP_ID

GROUP_ID = MAIN_GROUP_ID
TZ = timezone(timedelta(hours=8))  # Asia/Taipei

# KNOWN_BOTS（已知機器人 / 非真人發言者）由 corpus_config 共用，預設略過除非 --keep-bots

DATE_RE = re.compile(r"^(\d{4})/(\d{2})/(\d{2})（.）\s*$")
MSG_RE = re.compile(r"^(\d{2}):(\d{2})\t([^\t]*)\t(.*)$")

# 內容 → 訊息 type 對照（媒體只留標記）
MEDIA_TYPE = {
    "[貼圖]": "sticker",
    "[照片]": "image",
    "[影片]": "video",
    "[檔案]": "file",
    "[語音訊息]": "audio",
}


def classify(content: str) -> str:
    c = content.strip()
    if c in MEDIA_TYPE:
        return MEDIA_TYPE[c]
    return "text"


def parse(path: str):
    """產出 (messages, system_events)。message dict 含 group_id/user_id 佔位/user_name/
    type/content/timestamp/seq。"""
    messages = []
    system = []
    cur_date = None
    cur_msg = None  # 用於接續多行訊息

    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            dm = DATE_RE.match(line)
            if dm:
                cur_date = (int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
                cur_msg = None
                continue
            mm = MSG_RE.match(line)
            if mm and cur_date:
                hh, mi = int(mm.group(1)), int(mm.group(2))
                name = mm.group(3).strip()
                content = mm.group(4)
                # 毫秒，與 LINE webhook live 訊息一致
                ts = int(datetime(cur_date[0], cur_date[1], cur_date[2],
                                  hh, mi, tzinfo=TZ).timestamp()) * 1000
                if name == "":
                    system.append({"timestamp": ts, "content": content})
                    cur_msg = None
                    continue
                cur_msg = {
                    "user_name": name,
                    "content": content,
                    "timestamp": ts,
                    "type": classify(content),
                }
                messages.append(cur_msg)
                continue
            # 非日期、非訊息行：多行訊息的延續
            if line.strip() and cur_msg is not None:
                cur_msg["content"] += "\n" + line
                cur_msg["type"] = classify(cur_msg["content"])
    return messages, system


def synth_line_id(group_id: str, ts: int, seq: int) -> str:
    h = hashlib.sha1(f"{group_id}|{ts}|{seq}".encode()).hexdigest()[:16]
    return f"import:{h}"


def get_live_cutoff():
    """本群最早的 live 訊息時間戳（毫秒）。回填只匯入此時間之前，重疊區交給 live。
    無 DB / 無資料時回 None（不設限）。"""
    try:
        from travel.db import get_conn
        with get_conn() as conn:
            row = conn.execute(
                "SELECT MIN(timestamp) FROM messages WHERE group_id=? "
                "AND line_message_id NOT LIKE 'import:%'",
                (GROUP_ID,),
            ).fetchone()
        return row[0] if row and row[0] is not None else None
    except Exception:
        return None


def dry_run(messages, system, keep_bots):
    speakers = Counter(m["user_name"] for m in messages)
    kept = [m for m in messages if keep_bots or m["user_name"] not in KNOWN_BOTS]
    cutoff = get_live_cutoff()
    overlap = 0
    if cutoff is not None:
        before = len(kept)
        kept = [m for m in kept if m["timestamp"] < cutoff]
        overlap = before - len(kept)
    types = Counter(m["type"] for m in kept)
    ts_all = [m["timestamp"] for m in kept]
    lo = datetime.fromtimestamp(min(ts_all) / 1000, TZ)
    hi = datetime.fromtimestamp(max(ts_all) / 1000, TZ)

    print("=" * 56)
    print("DRY-RUN — 不寫入資料庫")
    print("=" * 56)
    print(f"總解析訊息：{len(messages)}（保留 {len(kept)} / 略過機器人 {len(messages) - len([m for m in messages if keep_bots or m['user_name'] not in KNOWN_BOTS])}）")
    if cutoff is not None:
        cut_dt = datetime.fromtimestamp(cutoff / 1000, TZ)
        print(f"重疊切點：{cut_dt:%Y-%m-%d %H:%M}（live 起點）— 略過重疊 {overlap} 則，交給 live 資料")
    print(f"系統/收回事件：{len(system)}（不匯入 messages）")
    print(f"時間範圍：{lo:%Y-%m-%d %H:%M} ~ {hi:%Y-%m-%d %H:%M}")
    print(f"型別分布：{dict(types)}")
    print()
    print("發言者（★=將略過的機器人）：")
    for name, cnt in speakers.most_common():
        mark = "★" if name in KNOWN_BOTS else " "
        print(f"  {mark} {name:<10} {cnt:>6}")
    print()
    print("樣本（前 5 則、後 3 則）：")
    for m in kept[:5] + kept[-3:]:
        t = datetime.fromtimestamp(m["timestamp"] / 1000, TZ)
        preview = m["content"].replace("\n", "⏎")[:40]
        print(f"  {t:%Y-%m-%d %H:%M}  {m['user_name']:<8} [{m['type']}] {preview}")


def do_import(messages, keep_bots):
    from travel.db import get_conn, init_db
    init_db()
    kept = [m for m in messages if keep_bots or m["user_name"] not in KNOWN_BOTS]
    cutoff = get_live_cutoff()
    if cutoff is not None:
        before = len(kept)
        kept = [m for m in kept if m["timestamp"] < cutoff]
        print(f"重疊切點：略過 {before - len(kept)} 則（>= live 起點），交給 live 資料")

    # 名字 → user_id（優先沿用真實 id，其次合成；同名共用一個 id）
    import uuid
    name_to_id = {}

    inserted = dup = 0
    seen_ts = Counter()
    with get_conn() as conn:
        # 先讀已存在成員的 name→user_id
        for r in conn.execute(
            "SELECT display_name, user_id FROM members WHERE group_id=?", (GROUP_ID,)
        ):
            name_to_id[r["display_name"]] = r["user_id"]
        # 再用 live messages 的真實 user_id 覆蓋（U 開頭優先於 manual: 合成）
        for r in conn.execute(
            "SELECT user_name, user_id FROM messages WHERE group_id=? "
            "AND line_message_id NOT LIKE 'import:%' AND user_name IS NOT NULL "
            "GROUP BY user_id",
            (GROUP_ID,),
        ):
            existing = name_to_id.get(r["user_name"])
            if existing is None or existing.startswith("manual:"):
                name_to_id[r["user_name"]] = r["user_id"]

        for m in kept:
            name = m["user_name"]
            if name not in name_to_id:
                name_to_id[name] = f"manual:{uuid.uuid4().hex[:8]}"
            uid = name_to_id[name]
            ts = m["timestamp"]
            seq = seen_ts[ts]
            seen_ts[ts] += 1
            lid = synth_line_id(GROUP_ID, ts, seq)
            try:
                conn.execute(
                    """INSERT INTO messages
                       (line_message_id, group_id, user_id, user_name, type,
                        content, metadata, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?, '{}', ?)""",
                    (lid, GROUP_ID, uid, name, m["type"], m["content"], ts),
                )
                inserted += 1
            except Exception:
                dup += 1

        # members upsert（合成 id 者 resolved=0，日後 reconcile 接回）
        import time
        now = int(time.time())
        for name, uid in name_to_id.items():
            if keep_bots is False and name in KNOWN_BOTS:
                continue
            exists = conn.execute(
                "SELECT 1 FROM members WHERE group_id=? AND display_name=?",
                (GROUP_ID, name),
            ).fetchone()
            if exists:
                continue
            resolved = 0 if uid.startswith("manual:") else 1
            source = "manual" if uid.startswith("manual:") else "auto"
            conn.execute(
                """INSERT INTO members
                   (group_id, user_id, display_name, source, resolved, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (GROUP_ID, uid, name, source, resolved, now),
            )
    print(f"匯入完成：inserted={inserted}, 跳過重複={dup}, 保留發言者={len(name_to_id)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-bots", action="store_true", help="連機器人一起匯入")
    args = ap.parse_args()

    messages, system = parse(args.file)
    if args.dry_run:
        dry_run(messages, system, args.keep_bots)
    else:
        do_import(messages, args.keep_bots)


if __name__ == "__main__":
    main()
