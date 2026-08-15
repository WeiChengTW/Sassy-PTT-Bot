"""SQLite 連線、schema、CRUD。"""
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "data/chat.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    line_message_id TEXT UNIQUE,
    group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_name TEXT,
    type TEXT,
    content TEXT,
    metadata TEXT,
    reply_to_message_id TEXT,
    timestamp INTEGER NOT NULL,
    is_deleted INTEGER DEFAULT 0,
    is_travel_related INTEGER,
    topics TEXT,
    sentiment REAL,
    locations TEXT,
    summary TEXT,
    keywords TEXT,
    analyzed_at INTEGER,
    created_at INTEGER DEFAULT (strftime('%s','now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_group ON messages(group_id);
CREATE INDEX IF NOT EXISTS idx_messages_travel
    ON messages(is_travel_related) WHERE is_travel_related = 1;
CREATE INDEX IF NOT EXISTS idx_messages_unanalyzed
    ON messages(analyzed_at) WHERE analyzed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_messages_no_keywords
    ON messages(analyzed_at) WHERE analyzed_at IS NOT NULL AND keywords IS NULL;

CREATE TABLE IF NOT EXISTS trips (
    id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    start_date INTEGER,
    end_date INTEGER,
    trip_type TEXT,
    created_by TEXT,
    created_at INTEGER,
    status TEXT DEFAULT 'planning'
);
CREATE INDEX IF NOT EXISTS idx_trips_group ON trips(group_id);

CREATE TABLE IF NOT EXISTS trip_participants (
    trip_id TEXT, user_id TEXT,
    joined_at INTEGER,
    PRIMARY KEY (trip_id, user_id)
);

-- 群組成員名單。未在 messages 說過話者用合成 id 'manual:<uuid8>'，
-- 日後說話時由 reconcile_member() 接回真實 LINE user_id。
CREATE TABLE IF NOT EXISTS members (
    group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    source TEXT DEFAULT 'manual',
    resolved INTEGER DEFAULT 0,
    created_at INTEGER,
    PRIMARY KEY (group_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_members_group ON members(group_id);

CREATE TABLE IF NOT EXISTS badges (
    id TEXT PRIMARY KEY,
    trip_id TEXT REFERENCES trips(id),
    rarity TEXT,
    image_path TEXT,
    prompt TEXT,
    master_ref TEXT,
    generated_at INTEGER,
    approved_by TEXT,
    approved_at INTEGER
);

CREATE TABLE IF NOT EXISTS daily_user_stats (
    date TEXT, user_id TEXT, group_id TEXT,
    text_count INT, sticker_count INT, image_count INT,
    travel_mention_count INT,
    PRIMARY KEY (date, user_id, group_id)
);

CREATE TABLE IF NOT EXISTS user_lifetime_stats (
    user_id TEXT, group_id TEXT,
    total_messages INT, total_trips INT,
    first_seen INTEGER, last_seen INTEGER,
    favorite_locations TEXT,
    PRIMARY KEY (user_id, group_id)
);

CREATE TABLE IF NOT EXISTS daily_stats (
    date TEXT NOT NULL,
    group_id TEXT NOT NULL,
    text_count INTEGER DEFAULT 0,
    sticker_count INTEGER DEFAULT 0,
    image_count INTEGER DEFAULT 0,
    video_count INTEGER DEFAULT 0,
    travel_mentions INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,
    PRIMARY KEY (date, group_id)
);
CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date DESC);
"""


@contextmanager
def get_conn():
    """Context manager for SQLite connection with WAL mode."""
    db_path = os.getenv("DB_PATH", DB_PATH)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create all tables if not exist，並套用 idempotent 欄位 migration。"""
    with get_conn() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(messages)")} \
            if conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
            ).fetchone() else set()
        if cols and "keywords" not in cols:
            conn.execute("ALTER TABLE messages ADD COLUMN keywords TEXT")
        conn.executescript(SCHEMA)


def insert_message(msg: dict) -> bool:
    """Insert message. Return False on duplicate (line_message_id conflict)."""
    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO messages
                   (line_message_id, group_id, user_id, user_name, type,
                    content, metadata, reply_to_message_id, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    msg.get("line_message_id"),
                    msg["group_id"],
                    msg["user_id"],
                    msg.get("user_name"),
                    msg["type"],
                    msg.get("content"),
                    json.dumps(msg.get("metadata", {})),
                    msg.get("reply_to_message_id"),
                    msg["timestamp"],
                ),
            )
        reconcile_member(msg["group_id"], msg["user_id"], msg.get("user_name"))
        return True
    except sqlite3.IntegrityError:
        return False


def reconcile_member(group_id: str, user_id: str, user_name: str | None) -> None:
    """成員說話時把人工新增（合成 id）的名單接回真實 LINE user_id。

    Best-effort：任何錯誤都吞掉，不影響訊息寫入。
    """
    if not group_id or not user_id or not user_name:
        return
    try:
        with get_conn() as conn:
            row = conn.execute(
                """SELECT user_id FROM members
                   WHERE group_id=? AND display_name=? AND resolved=0
                   ORDER BY created_at LIMIT 1""",
                (group_id, user_name),
            ).fetchone()
            if not row:
                return
            synthetic = row["user_id"]
            if synthetic == user_id:
                # 已是真實 id，只需標記 resolved。
                conn.execute(
                    "UPDATE members SET resolved=1, source='auto' WHERE group_id=? AND user_id=?",
                    (group_id, user_id),
                )
                return
            # 若真實 id 已存在於 members，刪掉合成列；否則把合成列改為真實 id。
            exists = conn.execute(
                "SELECT 1 FROM members WHERE group_id=? AND user_id=?",
                (group_id, user_id),
            ).fetchone()
            if exists:
                conn.execute(
                    "DELETE FROM members WHERE group_id=? AND user_id=?",
                    (group_id, synthetic),
                )
                conn.execute(
                    "UPDATE members SET resolved=1, source='auto' WHERE group_id=? AND user_id=?",
                    (group_id, user_id),
                )
            else:
                conn.execute(
                    """UPDATE members SET user_id=?, resolved=1, source='auto'
                       WHERE group_id=? AND user_id=?""",
                    (user_id, group_id, synthetic),
                )
            # 把先前以合成 id 指派的參與者/徽章接回真實 id（忽略 unique 衝突）。
            for table in ("trip_participants", "badges"):
                try:
                    conn.execute(
                        f"UPDATE OR IGNORE {table} SET user_id=? WHERE user_id=?",
                        (user_id, synthetic),
                    )
                except sqlite3.Error:
                    pass
    except sqlite3.Error:
        pass