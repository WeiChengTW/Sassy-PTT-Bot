#!/usr/bin/env python
"""把主群組的 LINE 對話建成向量記憶（Chroma `group_memory` collection）。

與 indexer.py（PTT 語料）不同處：
  - 來源是 SQLite `messages` 表，只取主群組（MAIN_GROUP_ID）的真人文字訊息。
  - 文件單位是「對話視窗」而非單則訊息：把連續訊息（時間間隔 < GAP、每視窗上限
    MAX_MSGS 則）合併成一段多行 `名字: 內容`，這樣「A: 明天去古宇利島？/ B: 好」
    這種可引用的記憶才有檢索價值，單則「好」「哈哈」不會被當獨立文件。
  - deterministic ID（grp_{首則timestamp}）＋ upsert：重跑不會重複；增量時邊界視窗
    會用同一 ID 覆蓋，不留過期殘影。

用法：
    python index_group_memory.py --rebuild      # 全量重建（初次 backfill / 換模型）
    python index_group_memory.py                # 增量：只補水位線之後的新訊息
"""
import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))

from corpus_config import (
    CHROMA_DB_PATH,
    EMBEDDING_MODEL_NAME,
    GROUP_MEMORY_COLLECTION,
    GROUP_MIN_WINDOW_CHARS,
    GROUP_WINDOW_GAP_SEC,
    GROUP_WINDOW_MAX_MSGS,
    KNOWN_BOTS,
    MAIN_GROUP_ID,
)
from travel.db import get_conn, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

_STATE_PATH = _PROJECT_ROOT / "data" / "group_memory_state.json"
_GAP_MS = GROUP_WINDOW_GAP_SEC * 1000


def _load_watermark() -> int:
    try:
        return int(json.loads(_STATE_PATH.read_text(encoding="utf-8")).get("watermark", 0))
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return 0


def _save_watermark(ts: int) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps({"watermark": ts}), encoding="utf-8")


def _fetch_messages(since_ts: int) -> list[dict]:
    """取主群組真人文字訊息，依 timestamp 升序。since_ts=0 代表全量。"""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT user_name, content, timestamp
            FROM messages
            WHERE group_id = ?
              AND type = 'text'
              AND is_deleted = 0
              AND content IS NOT NULL AND content != ''
              AND timestamp >= ?
            ORDER BY timestamp ASC
            """,
            (MAIN_GROUP_ID, since_ts),
        ).fetchall()
    out = []
    for r in rows:
        name = (r["user_name"] or "").strip()
        if not name or name in KNOWN_BOTS:
            continue  # 只排機器人，真人全留
        out.append({"name": name, "content": r["content"].strip(), "ts": int(r["timestamp"])})
    return out


def _build_windows(msgs: list[dict]) -> list[dict]:
    """把連續訊息切成對話視窗。回傳 [{id, document, first_ts, last_ts, participants}]。"""
    windows: list[dict] = []
    cur: list[dict] = []

    def flush():
        if not cur:
            return
        doc = "\n".join(f"{m['name']}: {m['content']}" for m in cur)
        if len(doc.replace("\n", "")) < GROUP_MIN_WINDOW_CHARS:
            return  # 整段太短（純「好」「哈哈」）就丟
        first_ts = cur[0]["ts"]
        # first_ts 只到「分」，同分鐘多個視窗會撞號 → 加內容 hash 保證唯一且 deterministic
        doc_hash = hashlib.sha1(doc.encode("utf-8")).hexdigest()[:8]
        windows.append({
            "id": f"grp_{first_ts}_{doc_hash}",
            "document": doc,
            "first_ts": first_ts,
            "last_ts": cur[-1]["ts"],
            "participants": ",".join(dict.fromkeys(m["name"] for m in cur)),
        })

    for m in msgs:
        if cur and (
            m["ts"] - cur[-1]["ts"] > _GAP_MS or len(cur) >= GROUP_WINDOW_MAX_MSGS
        ):
            flush()
            cur = []
        cur.append(m)
    flush()
    return windows


def run(rebuild: bool = False) -> None:
    init_db()
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL_NAME)
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    if rebuild:
        try:
            client.delete_collection(name=GROUP_MEMORY_COLLECTION)
        except Exception:
            pass
        since_ts = 0
    else:
        # 從水位線 - GAP 重掃，讓邊界視窗完整重組（同 ID upsert，不留殘影）
        since_ts = max(0, _load_watermark() - _GAP_MS)

    collection = client.get_or_create_collection(
        name=GROUP_MEMORY_COLLECTION, embedding_function=emb_fn
    )

    if not rebuild and since_ts > 0:
        # 增量：先刪掉重掃範圍內的舊視窗，避免邊界視窗成長後留下過期殘影
        try:
            collection.delete(where={"first_ts": {"$gte": since_ts}})
        except Exception as e:
            logger.warning(f"清理重掃範圍舊視窗失敗（略過）: {e}")

    msgs = _fetch_messages(since_ts)
    logger.info(f"讀到 {len(msgs)} 則主群真人文字訊息 (since_ts={since_ts})")
    windows = _build_windows(msgs)
    logger.info(f"切出 {len(windows)} 個對話視窗")

    if not windows:
        logger.info("沒有可索引的視窗，結束。")
        return

    batch_size = 64
    for i in range(0, len(windows), batch_size):
        batch = windows[i:i + batch_size]
        try:
            collection.upsert(
                ids=[w["id"] for w in batch],
                documents=[w["document"] for w in batch],
                metadatas=[
                    {"first_ts": w["first_ts"], "last_ts": w["last_ts"], "participants": w["participants"]}
                    for w in batch
                ],
            )
            if i % 640 == 0:
                logger.info(f"已寫入 {i}/{len(windows)} ...")
        except Exception as e:
            logger.error(f"批次 {i} upsert 失敗: {e}")

    _save_watermark(max(m["ts"] for m in msgs))
    logger.info(f"完成，group_memory 目前約 {collection.count()} 筆視窗。")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="全量重建（初次 / 換模型）")
    args = ap.parse_args()
    run(rebuild=args.rebuild)
