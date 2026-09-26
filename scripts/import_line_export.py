#!/usr/bin/env python
"""解析 LINE 群組匯出 .txt，回填 messages（與 members）表。

匯出檔格式（tab 分隔）：
    儲存日期： 2026/08/16 13:04
    2023/08/01（二）              <- 日期分隔行
    09:51\t<暱稱>\t訊息內容         <- 一般訊息
    10:55\t\t⁨⁨<暱稱>⁩⁩已新增⁨⁨<暱稱>⁩⁩至群組。  <- 系統訊息（發言者空白）
    續行（無時間戳）              <- 多行訊息的延續，接到上一則

限制（見對話評估）：
  - 只有暱稱、沒有真實 LINE user_id → 用合成 id（同 seed_members 的 manual: 機制）
  - 時間戳只到「分」，同分鐘多則同秒；假設時區 Asia/Taipei
  - 媒體只留標記 [貼圖]/[照片] 等，無實體
  - 分析欄位（keywords/sentiment/...）不填，需另跑 LLM 分析回填

冪等：line_message_id 用 (group_id + timestamp + seq + source) 決定性合成，重跑不重複。
      source 為來源檔名 basename（預設空字串），不同來源檔案的同分鐘訊息不會互相碰撞。

用法：
    python scripts/import_line_export.py --file "[LINE] ....txt" --dry-run
    DB_PATH=data/chat.db python scripts/import_line_export.py --file "[LINE] ....txt"
    # MESSENGER 轉 LINE 格式匯入（不過濾 live cutoff、不寫 members）：
    python scripts/import_line_export.py --file "[MESSENGER] ...txt" --no-cutoff --no-members
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
MSG_RE = re.compile(r"^(?:(上午|下午|AM|PM)\s*)?(\d{1,2}):(\d{2})\t([^\t]*)\t(.*)$")

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
                period = mm.group(1)
                hh, mi = int(mm.group(2)), int(mm.group(3))
                if period in ("下午", "PM") and hh < 12:
                    hh += 12
                elif period in ("上午", "AM") and hh == 12:
                    hh = 0
                name = mm.group(4).strip()
                content = mm.group(5)
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


def synth_line_id(group_id: str, ts: int, seq: int, source: str = "") -> str:
    """決定性合成 line_message_id。
    source 傳入來源檔名 basename，讓不同來源檔案的同分鐘訊息有不同 id，避免跨檔碰撞。
    預設空字串使舊版（未傳 source）的行為完全不變。
    """
    h = hashlib.sha1(f"{group_id}|{ts}|{seq}|{source}".encode()).hexdigest()[:16]
    return f"import:{h}"


def get_live_cutoff(target_group_id: str | None = None):
    """本群最早的 live 訊息時間戳（毫秒）。回填只匯入此時間之前，重疊區交給 live。
    無 DB / 無資料時回 None（不設限）。"""
    gid = target_group_id or GROUP_ID
    try:
        from travel.db import get_conn
        with get_conn() as conn:
            row = conn.execute(
                "SELECT MIN(timestamp) FROM messages WHERE group_id=? "
                "AND line_message_id NOT LIKE 'import:%'",
                (gid,),
            ).fetchone()
            if row and row[0] is not None:
                return row[0]
    except Exception:
        pass
    return None


def dry_run(messages, system, keep_bots, no_cutoff=False):
    speakers = Counter(m["user_name"] for m in messages)
    kept = [m for m in messages if keep_bots or m["user_name"] not in KNOWN_BOTS]
    cutoff = None if no_cutoff else get_live_cutoff()
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


def do_import(messages, keep_bots, no_members=False, source: str = "", no_cutoff: bool = False,
              target_group_id: str | None = None):
    from travel.db import get_conn, init_db
    init_db()
    group_id = target_group_id or GROUP_ID
    kept = [m for m in messages if keep_bots or m["user_name"] not in KNOWN_BOTS]
    cutoff = None if no_cutoff else get_live_cutoff(group_id)
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
            "SELECT display_name, user_id FROM members WHERE group_id=?", (group_id,)
        ):
            name_to_id[r["display_name"]] = r["user_id"]
        # 再用 live messages 的真實 user_id 覆蓋（U 開頭優先於 manual:/imported: 合成）
        for r in conn.execute(
            "SELECT user_name, user_id FROM messages WHERE group_id=? "
            "AND line_message_id NOT LIKE 'import:%' AND user_name IS NOT NULL "
            "GROUP BY user_id",
            (group_id,),
        ):
            existing = name_to_id.get(r["user_name"])
            if existing is None or existing.startswith(("manual:", "imported:")):
                name_to_id[r["user_name"]] = r["user_id"]

        for m in kept:
            name = m["user_name"]
            if name not in name_to_id:
                name_to_id[name] = f"imported:{uuid.uuid4().hex[:8]}"
            uid = name_to_id[name]
            ts = m["timestamp"]
            seq = seen_ts[ts]
            seen_ts[ts] += 1
            lid = synth_line_id(group_id, ts, seq, source)
            try:
                conn.execute(
                    """INSERT INTO messages
                       (line_message_id, group_id, user_id, user_name, type,
                        content, metadata, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?, '{}', ?)""",
                    (lid, group_id, uid, name, m["type"], m["content"], ts),
                )
                inserted += 1
            except Exception:
                dup += 1

        # members upsert（若未指定 no_members；合成 id 者 resolved=0，日後 reconcile 接回）
        if not no_members:
            import time
            now = int(time.time())
            for name, uid in name_to_id.items():
                if keep_bots is False and name in KNOWN_BOTS:
                    continue
                exists = conn.execute(
                    "SELECT 1 FROM members WHERE group_id=? AND display_name=?",
                    (group_id, name),
                ).fetchone()
                if exists:
                    continue
                resolved = 0 if uid.startswith(("manual:", "imported:")) else 1
                member_source = "manual" if uid.startswith(("manual:", "imported:")) else "auto"
                conn.execute(
                    """INSERT INTO members
                       (group_id, user_id, display_name, source, resolved, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (group_id, uid, name, member_source, resolved, now),
                )
    print(f"匯入完成：inserted={inserted}, 跳過重複={dup}, 保留發言者={len(name_to_id)}, 寫入members={not no_members}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-bots", action="store_true", help="連機器人一起匯入")
    ap.add_argument("--no-members", action="store_true", help="只匯入訊息進 messages，不將發言者加入 members 名冊")
    ap.add_argument("--no-cutoff", action="store_true",
                    help="跳過 live cutoff 重疊過濾（用於非主群來源，如 MESSENGER 轉檔）")
    ap.add_argument("--group-id", help="指定 group_id（預設為主群組 ID）")
    args = ap.parse_args()

    source = os.path.basename(args.file)
    messages, system = parse(args.file)
    if args.dry_run:
        dry_run(messages, system, args.keep_bots, no_cutoff=args.no_cutoff)
    else:
        do_import(messages, args.keep_bots, args.no_members,
                  source=source, no_cutoff=args.no_cutoff, target_group_id=args.group_id)


if __name__ == "__main__":
    main()
