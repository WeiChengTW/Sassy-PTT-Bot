"""Schema migration runner for Phase 2."""
import time

from travel.db import get_conn

MIGRATIONS: list[tuple[int, list[str]]] = [
    (1, [  # trips 擴充
        "ALTER TABLE trips ADD COLUMN rarity TEXT",
        "ALTER TABLE trips ADD COLUMN badge_image_url TEXT",
        "ALTER TABLE trips ADD COLUMN badge_video_url TEXT",
        "ALTER TABLE trips ADD COLUMN planning_days INTEGER",
        "ALTER TABLE trips ADD COLUMN total_messages INTEGER DEFAULT 0",
        "ALTER TABLE trips ADD COLUMN participants_count INTEGER",
        "ALTER TABLE trips ADD COLUMN budget_total REAL",
        "ALTER TABLE trips ADD COLUMN key_messages TEXT",
        "ALTER TABLE trips ADD COLUMN memorable_quotes TEXT",
        "ALTER TABLE trips ADD COLUMN photo_urls TEXT",
        "ALTER TABLE trips ADD COLUMN ended_at INTEGER",
        "ALTER TABLE trips ADD COLUMN updated_at INTEGER DEFAULT (strftime('%s','now'))",
    ]),
    (2, [  # trip_participants 擴充
        "ALTER TABLE trip_participants ADD COLUMN role TEXT",
        "ALTER TABLE trip_participants ADD COLUMN messages_count INTEGER DEFAULT 0",
        "ALTER TABLE trip_participants ADD COLUMN photos_shared INTEGER DEFAULT 0",
    ]),
    (3, [  # badges 新增 user-scoped 欄位
        "ALTER TABLE badges ADD COLUMN user_id TEXT",
        "ALTER TABLE badges ADD COLUMN badge_type TEXT",
        "ALTER TABLE badges ADD COLUMN badge_name TEXT",
        "ALTER TABLE badges ADD COLUMN badge_rarity TEXT",
        "ALTER TABLE badges ADD COLUMN badge_image_url TEXT",
        "ALTER TABLE badges ADD COLUMN earned_at INTEGER",
        "ALTER TABLE badges ADD COLUMN description TEXT",
        "ALTER TABLE badges ADD COLUMN metadata TEXT",
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_badges_unique
           ON badges(user_id, trip_id, badge_type)
           WHERE user_id IS NOT NULL""",
    ]),
    (4, [  # group-level daily_stats
        """CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT NOT NULL,
            group_id TEXT NOT NULL,
            text_count INTEGER DEFAULT 0,
            sticker_count INTEGER DEFAULT 0,
            image_count INTEGER DEFAULT 0,
            video_count INTEGER DEFAULT 0,
            travel_mentions INTEGER DEFAULT 0,
            active_users INTEGER DEFAULT 0,
            PRIMARY KEY (date, group_id)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date DESC)",
    ]),
    (5, [  # messages 複合索引
        "CREATE INDEX IF NOT EXISTS idx_messages_user_group ON messages(user_id, group_id)",
    ]),
]


def get_current_version() -> int:
    """Return the highest applied migration version (0 if none)."""
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
            return row[0] or 0
    except Exception:
        return 0


def migrate() -> None:
    """Apply all pending migrations in order. Idempotent."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at INTEGER NOT NULL
            )
        """)

    current = get_current_version()
    for version, statements in MIGRATIONS:
        if version <= current:
            continue
        with get_conn() as conn:
            for sql in statements:
                try:
                    conn.execute(sql)
                except Exception as e:
                    if "duplicate column name" in str(e).lower():
                        continue
                    raise RuntimeError(f"[MIGRATIONS] v{version} failed: {e}") from e
            conn.execute(
                "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, int(time.time())),
            )

    new_version = get_current_version()
    print(f"[MIGRATIONS] schema at version {new_version}")