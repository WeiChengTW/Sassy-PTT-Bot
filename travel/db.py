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
    """Create all tables if not exist."""
    with get_conn() as conn:
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
        return True
    except sqlite3.IntegrityError:
        return False