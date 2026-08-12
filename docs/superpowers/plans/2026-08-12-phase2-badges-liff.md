# Phase 2 — Badges + LIFF + Bot Triggers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 擴充 Sassy PTT Bot 為完整旅行回顧系統：schema migration、emoji 徽章、旅行 CRUD、LIFF API、Vite+Vue 前端、bot bare mention + admin DM → Flex Message LIFF 按鈕。

**Architecture:** Flask app 共用 port 5000，LIFF Blueprint 掛 `/liff/*`；前端 Vite dev server @ :5173，兩條 ngrok tunnel 分開。所有 DB 業務邏輯在 `travel/` 層，`liff_api.py` 只負責 HTTP + 權限。Phase 1 的訊息儲存、APScheduler、CLI 工具全部保留不變。

**Tech Stack:** Python 3.11+、Flask、linebot-sdk v3、SQLite+WAL、APScheduler、Vite 5 + Vue 3.4 + TypeScript + Tailwind 3 + Chart.js 4 + @line/liff 2.22 + Pinia + vue-router 4。

## Global Constraints

- DB_PATH 從 env 讀：測試用 `monkeypatch.setenv("DB_PATH", tmp_path)` 隔離
- `travel/` 層不 import Flask；`liff_api.py` 呼叫 `travel/` 函式
- Admin 判定：`ADMIN_USER_IDS` env 逗號分隔，空字串 → 無 admin
- LIFF user_id 從 request header `X-LIFF-UserId` 取得（前端自動帶）
- Trip CRUD 操作必須驗 group_id 吻合（不允許跨群組）
- Migration idempotent：`schema_version` 表追蹤已套用版本，重跑不重複執行
- 徽章 UNIQUE constraint：`(user_id, trip_id, badge_type)` WHERE user_id IS NOT NULL
- pytest 在專案根目錄執行：`python -m pytest tests/ -v`
- liff 前端：`cd liff && npm run dev`（開發）

## File Map

```
新建：
  travel/migrations.py          schema migration runner
  travel/trip_crud.py           旅行 CRUD 業務邏輯
  travel/badges.py              emoji 徽章邏輯
  travel/stats.py               dashboard / trips / badges 查詢
  telegram_bot/liff_api.py      Flask Blueprint 9 endpoints
  tests/test_migrations.py
  tests/test_trip_crud.py
  tests/test_badges.py
  tests/test_stats.py
  tests/test_liff_api.py
  tests/test_bot_triggers.py
  liff/                         整個 Vite+Vue 3 專案

修改：
  telegram_bot/bot.py           bare mention/admin DM 分支 + blueprint 註冊 + badge scheduler
  travel/aggregator.py          新增 aggregate_daily_stats (group-level)
  scripts/show_stats.py         新增 dashboard 子指令
  .env                          ADMIN_USER_IDS / LIFF_ID
  .gitignore                    liff/node_modules / .env.liff
```

---

## Task 1: Schema Migration（TDD）

**Files:**
- Create: `travel/migrations.py`
- Create: `tests/test_migrations.py`

**Interfaces — Produces:**
- `get_current_version() -> int`
- `migrate() -> None` — 套用所有未套用的 migration，在 bot 啟動時呼叫

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_migrations.py
"""測試 travel/migrations.py。"""
import os
import tempfile
import pytest
from travel.db import init_db, get_conn


@pytest.fixture
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DB_PATH", path)
    yield path
    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


def test_migrate_creates_schema_version_table(temp_db):
    from travel.migrations import migrate
    init_db()
    migrate()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
    assert row is not None


def test_migrate_version_reaches_5(temp_db):
    from travel.migrations import migrate, get_current_version
    init_db()
    migrate()
    assert get_current_version() == 5


def test_migrate_idempotent(temp_db):
    from travel.migrations import migrate, get_current_version
    init_db()
    migrate()
    migrate()  # second run must not raise
    assert get_current_version() == 5


def test_migrate_trips_has_new_columns(temp_db):
    from travel.migrations import migrate
    init_db()
    migrate()
    with get_conn() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(trips)").fetchall()}
    assert "rarity" in cols
    assert "ended_at" in cols
    assert "planning_days" in cols


def test_migrate_creates_daily_stats_table(temp_db):
    from travel.migrations import migrate
    init_db()
    migrate()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_stats'"
        ).fetchone()
    assert row is not None


def test_migrate_badges_has_user_id_column(temp_db):
    from travel.migrations import migrate
    init_db()
    migrate()
    with get_conn() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(badges)").fetchall()}
    assert "user_id" in cols
    assert "badge_name" in cols
```

- [ ] **Step 2: 確認 RED**

```bash
python -m pytest tests/test_migrations.py -v
```

預期：`ModuleNotFoundError: No module named 'travel.migrations'`

- [ ] **Step 3: 實作 `travel/migrations.py`**

```python
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
    (5, [  # messages 複合索引（加速 member 判定）
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
                    # Column already exists is OK (idempotency for partial runs)
                    if "duplicate column name" in str(e).lower():
                        continue
                    raise RuntimeError(f"[MIGRATIONS] v{version} failed: {e}") from e
            conn.execute(
                "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, int(time.time())),
            )

    new_version = get_current_version()
    print(f"[MIGRATIONS] schema at version {new_version}")
```

- [ ] **Step 4: 確認 GREEN**

```bash
python -m pytest tests/test_migrations.py -v
```

預期：6 個測試全綠。

- [ ] **Step 5: Commit**

```bash
git add travel/migrations.py tests/test_migrations.py
git commit -m "feat(travel): add schema migration runner for Phase 2"
```

---

## Task 2: Trip CRUD（TDD）

**Files:**
- Create: `travel/trip_crud.py`
- Create: `tests/test_trip_crud.py`

**Interfaces — Produces:**
- `create_trip(group_id, title, location, start_date, trip_type, created_by) -> str` (trip_id)
- `add_participants(trip_id, user_ids) -> dict[str, int]` — `{"added": N, "total": M}`
- `end_trip(trip_id) -> dict` — `{"trip_id", "status": "ended", "ended_at": int}`
- `get_trip(trip_id) -> dict | None`
- `get_participants(trip_id) -> list[dict]` — each: `{user_id, user_name, role, joined_at}`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_trip_crud.py
"""測試 travel/trip_crud.py。"""
import os
import tempfile
import time
import pytest
from travel.db import init_db, get_conn
from travel.migrations import migrate


@pytest.fixture
def db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DB_PATH", path)
    init_db()
    migrate()
    yield path
    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


def test_create_trip_returns_id(db):
    from travel.trip_crud import create_trip
    trip_id = create_trip(
        group_id="C1", title="墾丁三日遊", location="墾丁",
        start_date=1700000000, trip_type="beach", created_by="U1",
    )
    assert isinstance(trip_id, str) and len(trip_id) > 0


def test_create_trip_persists_in_db(db):
    from travel.trip_crud import create_trip, get_trip
    trip_id = create_trip("C1", "富士山", "日本", 1700000000, "mountain", "U1")
    trip = get_trip(trip_id)
    assert trip is not None
    assert trip["title"] == "富士山"
    assert trip["status"] == "planning"


def test_add_participants_returns_counts(db):
    from travel.trip_crud import create_trip, add_participants
    trip_id = create_trip("C1", "旅行", "台北", 1700000000, None, "U1")
    result = add_participants(trip_id, ["U1", "U2", "U3"])
    assert result["added"] == 3
    assert result["total"] == 3


def test_add_participants_idempotent(db):
    from travel.trip_crud import create_trip, add_participants
    trip_id = create_trip("C1", "旅行", "台北", 1700000000, None, "U1")
    add_participants(trip_id, ["U1", "U2"])
    result = add_participants(trip_id, ["U1", "U3"])  # U1 already exists
    assert result["added"] == 1
    assert result["total"] == 3


def test_end_trip_sets_status(db):
    from travel.trip_crud import create_trip, end_trip, get_trip
    trip_id = create_trip("C1", "旅行", "台北", 1700000000, None, "U1")
    result = end_trip(trip_id)
    assert result["status"] == "ended"
    assert result["ended_at"] is not None
    trip = get_trip(trip_id)
    assert trip["status"] == "ended"


def test_get_participants_returns_list(db):
    from travel.trip_crud import create_trip, add_participants, get_participants
    trip_id = create_trip("C1", "旅行", "台北", 1700000000, None, "U1")
    add_participants(trip_id, ["U1", "U2"])
    participants = get_participants(trip_id)
    assert len(participants) == 2
    user_ids = {p["user_id"] for p in participants}
    assert {"U1", "U2"} == user_ids
```

- [ ] **Step 2: 確認 RED**

```bash
python -m pytest tests/test_trip_crud.py -v
```

- [ ] **Step 3: 實作 `travel/trip_crud.py`**

```python
"""旅行 CRUD 業務邏輯。被 liff_api.py 呼叫，不依賴 Flask。"""
import time
import uuid

from travel.db import get_conn


def create_trip(
    group_id: str,
    title: str,
    location: str,
    start_date: int,
    trip_type: str | None,
    created_by: str,
) -> str:
    """建立旅行，回傳 trip_id（UUID）。"""
    trip_id = str(uuid.uuid4())
    now = int(time.time())
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO trips
               (id, group_id, title, location, start_date, trip_type, created_by, created_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'planning')""",
            (trip_id, group_id, title, location, start_date, trip_type, created_by, now),
        )
    return trip_id


def get_trip(trip_id: str) -> dict | None:
    """取得單一旅行資料，不存在回傳 None。"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
    return dict(row) if row else None


def add_participants(trip_id: str, user_ids: list[str]) -> dict[str, int]:
    """批次加入參與者。回傳 {added, total}。重複 user_id 略過。"""
    now = int(time.time())
    added = 0
    with get_conn() as conn:
        for uid in user_ids:
            try:
                conn.execute(
                    "INSERT INTO trip_participants (trip_id, user_id, joined_at) VALUES (?, ?, ?)",
                    (trip_id, uid, now),
                )
                added += 1
            except Exception:
                pass  # duplicate PRIMARY KEY → skip
        total = conn.execute(
            "SELECT COUNT(*) FROM trip_participants WHERE trip_id = ?", (trip_id,)
        ).fetchone()[0]
    return {"added": added, "total": total}


def end_trip(trip_id: str) -> dict:
    """結束旅行：status='ended'，記錄 ended_at。"""
    ended_at = int(time.time())
    with get_conn() as conn:
        conn.execute(
            "UPDATE trips SET status='ended', ended_at=? WHERE id=?",
            (ended_at, trip_id),
        )
    return {"trip_id": trip_id, "status": "ended", "ended_at": ended_at}


def get_participants(trip_id: str) -> list[dict]:
    """取得旅行所有參與者，嘗試 JOIN messages 拿 user_name。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT tp.user_id, tp.role, tp.joined_at, tp.messages_count,
                      (SELECT user_name FROM messages
                       WHERE user_id = tp.user_id AND user_name IS NOT NULL
                       LIMIT 1) AS user_name
               FROM trip_participants tp
               WHERE tp.trip_id = ?""",
            (trip_id,),
        ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: 確認 GREEN**

```bash
python -m pytest tests/test_trip_crud.py -v
```

- [ ] **Step 5: Commit**

```bash
git add travel/trip_crud.py tests/test_trip_crud.py
git commit -m "feat(travel): add trip CRUD business logic"
```

---

## Task 3: Emoji Badges（TDD）

**Files:**
- Create: `travel/badges.py`
- Create: `tests/test_badges.py`

**Interfaces — Produces:**
- `compute_rarity(trip: dict) -> str` — `"common"|"rare"|"epic"|"legendary"`
- `compute_badge_emoji(trip: dict, rarity: str) -> str` — e.g. `"🏖️🟣"`
- `compute_badge_name(trip: dict, user_name: str, rarity: str) -> str`
- `award_badges_for_trip(trip_id: str) -> list[dict]`
- `get_ended_trips_without_badges() -> list[dict]`
- `process_ended_trips() -> None`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_badges.py
"""測試 travel/badges.py。"""
import os
import tempfile
import time
import pytest
from travel.db import init_db, get_conn
from travel.migrations import migrate
from travel.trip_crud import create_trip, add_participants, end_trip


@pytest.fixture
def db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DB_PATH", path)
    init_db()
    migrate()
    yield path
    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


def test_compute_rarity_common_short_trip(db):
    from travel.badges import compute_rarity
    trip = {"start_date": 1700000000, "end_date": 1700000000 + 86400, "participants_count": 2, "location": "台北"}
    assert compute_rarity(trip) == "common"


def test_compute_rarity_rare_3_days(db):
    from travel.badges import compute_rarity
    trip = {"start_date": 1700000000, "end_date": 1700000000 + 3 * 86400, "participants_count": 3, "location": "台中"}
    assert compute_rarity(trip) == "rare"


def test_compute_rarity_epic_5_days(db):
    from travel.badges import compute_rarity
    trip = {"start_date": 1700000000, "end_date": 1700000000 + 5 * 86400, "participants_count": 3, "location": "花蓮"}
    assert compute_rarity(trip) == "epic"


def test_compute_rarity_epic_many_participants(db):
    from travel.badges import compute_rarity
    trip = {"start_date": 1700000000, "end_date": 1700000000 + 86400, "participants_count": 6, "location": "台南"}
    assert compute_rarity(trip) == "epic"


def test_compute_rarity_legendary_abroad(db):
    from travel.badges import compute_rarity
    trip = {"start_date": 1700000000, "end_date": 1700000000 + 3 * 86400, "participants_count": 3, "location": "日本大阪"}
    assert compute_rarity(trip) == "legendary"


def test_compute_badge_emoji_beach(db):
    from travel.badges import compute_badge_emoji
    trip = {"location": "墾丁海邊"}
    emoji = compute_badge_emoji(trip, "epic")
    assert emoji == "🏖️🟣"


def test_compute_badge_emoji_fallback(db):
    from travel.badges import compute_badge_emoji
    trip = {"location": "未知地方"}
    emoji = compute_badge_emoji(trip, "common")
    assert emoji == "🗺️🟢"


def test_award_badges_for_trip_writes_db(db):
    from travel.badges import award_badges_for_trip
    trip_id = create_trip("C1", "墾丁三日遊", "墾丁", 1700000000, "beach", "U1")
    add_participants(trip_id, ["U1", "U2"])
    end_trip(trip_id)
    badges = award_badges_for_trip(trip_id)
    assert len(badges) == 2
    with get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM badges WHERE trip_id=? AND user_id IS NOT NULL", (trip_id,)
        ).fetchone()[0]
    assert count == 2


def test_award_badges_idempotent(db):
    from travel.badges import award_badges_for_trip
    trip_id = create_trip("C1", "測試旅行", "台北", 1700000000, None, "U1")
    add_participants(trip_id, ["U1"])
    end_trip(trip_id)
    award_badges_for_trip(trip_id)
    second = award_badges_for_trip(trip_id)
    assert second == []  # already awarded, nothing new

    with get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM badges WHERE trip_id=? AND user_id IS NOT NULL", (trip_id,)
        ).fetchone()[0]
    assert count == 1


def test_get_ended_trips_without_badges(db):
    from travel.badges import get_ended_trips_without_badges
    trip_id = create_trip("C1", "旅行", "台北", 1700000000, None, "U1")
    add_participants(trip_id, ["U1"])
    end_trip(trip_id)
    trips = get_ended_trips_without_badges()
    ids = [t["id"] for t in trips]
    assert trip_id in ids
```

- [ ] **Step 2: 確認 RED**

```bash
python -m pytest tests/test_badges.py -v
```

- [ ] **Step 3: 實作 `travel/badges.py`**

```python
"""Emoji 徽章邏輯（Phase 2）。介面預留給 Phase 2.5 fal.ai 替換。"""
import time
import uuid
from typing import Literal

from travel.db import get_conn
from travel.trip_crud import get_trip, get_participants

ABROAD_KEYWORDS = {"日本", "韓國", "泰國", "美國", "歐洲", "海外", "法國", "德國", "義大利", "越南", "菲律賓", "馬來西亞", "新加坡", "澳洲", "英國"}

LOCATION_EMOJI: list[tuple[str, str]] = [
    ("墾丁", "🏖️"), ("海邊", "🏖️"), ("沙灘", "🏖️"), ("海灘", "🏖️"),
    ("山", "🏔️"), ("登山", "🏔️"), ("玉山", "🏔️"), ("合歡", "🏔️"),
    ("溫泉", "♨️"),
    ("露營", "🏕️"),
    ("日本", "✈️"), ("韓國", "✈️"), ("海外", "✈️"), ("出國", "✈️"),
    ("夜市", "🌃"), ("台北", "🌃"), ("城市", "🌃"),
]

RARITY_CIRCLE = {
    "common": "🟢",
    "rare": "🔵",
    "epic": "🟣",
    "legendary": "🟡",
}

RARITY_LABEL = {
    "common": "初心者",
    "rare": "旅行者",
    "epic": "冒險家",
    "legendary": "傳奇旅人",
}


def compute_rarity(trip: dict) -> Literal["common", "rare", "epic", "legendary"]:
    """依旅程天數、參與人數、地點判斷稀有度。"""
    location = trip.get("location") or ""
    if any(kw in location for kw in ABROAD_KEYWORDS):
        return "legendary"

    start = trip.get("start_date") or 0
    end = trip.get("end_date") or start
    days = max(1, round((end - start) / 86400))

    participants = trip.get("participants_count") or 0

    if days >= 5 or participants >= 6:
        return "epic"
    if days >= 3:
        return "rare"
    return "common"


def compute_badge_emoji(trip: dict, rarity: str) -> str:
    """依地點 + 稀有度產生 emoji 組合。"""
    location = trip.get("location") or ""
    loc_emoji = "🗺️"
    for keyword, emoji in LOCATION_EMOJI:
        if keyword in location:
            loc_emoji = emoji
            break
    return f"{loc_emoji}{RARITY_CIRCLE.get(rarity, '🟢')}"


def compute_badge_name(trip: dict, user_name: str, rarity: str) -> str:
    """產生徽章名稱。"""
    label = RARITY_LABEL.get(rarity, "旅行者")
    return f"{trip.get('title', '旅行')}・{user_name}・{label}"


def _insert_badge(
    user_id: str,
    trip_id: str,
    badge_type: str,
    badge_name: str,
    badge_rarity: str,
    badge_image_url: str | None,
    description: str,
    earned_at: int,
) -> str | None:
    """插入徽章，重複則回傳 None（UNIQUE 約束）。"""
    badge_id = str(uuid.uuid4())
    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO badges
                   (id, trip_id, user_id, badge_type, badge_name,
                    badge_rarity, badge_image_url, description, earned_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (badge_id, trip_id, user_id, badge_type, badge_name,
                 badge_rarity, badge_image_url, description, earned_at),
            )
        return badge_id
    except Exception:
        return None


def award_badges_for_trip(trip_id: str) -> list[dict]:
    """對 trip 所有 participants 發 emoji 徽章。回傳新發放清單（已有的跳過）。"""
    trip = get_trip(trip_id)
    if not trip:
        return []
    participants = get_participants(trip_id)
    rarity = compute_rarity(trip)
    emoji = compute_badge_emoji(trip, rarity)
    earned_at = int(time.time())
    new_badges = []
    for p in participants:
        user_id = p["user_id"]
        user_name = p.get("user_name") or user_id
        name = compute_badge_name(trip, user_name, rarity)
        badge_id = _insert_badge(
            user_id=user_id,
            trip_id=trip_id,
            badge_type="trip",
            badge_name=name,
            badge_rarity=rarity,
            badge_image_url=None,
            description=f"{trip['title']} 完成",
            earned_at=earned_at,
        )
        if badge_id:
            new_badges.append({
                "badge_id": badge_id,
                "user_id": user_id,
                "badge_emoji": emoji,
                "badge_rarity": rarity,
                "badge_name": name,
            })
    return new_badges


def get_ended_trips_without_badges() -> list[dict]:
    """回傳 status='ended' 且尚未發過 user-scoped 徽章的旅行。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT t.* FROM trips t
               WHERE t.status = 'ended'
                 AND NOT EXISTS (
                     SELECT 1 FROM badges b
                     WHERE b.trip_id = t.id AND b.user_id IS NOT NULL
                 )"""
        ).fetchall()
    return [dict(r) for r in rows]


def process_ended_trips() -> None:
    """APScheduler 觸發：對所有待發徽章旅行批次發放。"""
    import logging
    logger = logging.getLogger(__name__)
    trips = get_ended_trips_without_badges()
    for trip in trips:
        try:
            new_badges = award_badges_for_trip(trip["id"])
            logger.info(f"[BADGE] trip {trip['id']} 發放 {len(new_badges)} 枚徽章")
        except Exception as e:
            logger.error(f"[BADGE] trip {trip['id']} 失敗: {e}")
```

- [ ] **Step 4: 確認 GREEN**

```bash
python -m pytest tests/test_badges.py -v
```

- [ ] **Step 5: Commit**

```bash
git add travel/badges.py tests/test_badges.py
git commit -m "feat(travel): add emoji badge logic with rarity + award flow"
```

---

## Task 4: Stats Queries（TDD）

**Files:**
- Create: `travel/stats.py`
- Create: `tests/test_stats.py`

**Interfaces — Produces:**
- `get_dashboard_data(group_id, days=30) -> dict`
- `get_trips_list(group_id) -> list[dict]`
- `get_trip_detail(trip_id) -> dict`
- `get_user_badges(user_id, group_id) -> list[dict]`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_stats.py
"""測試 travel/stats.py。"""
import os
import tempfile
import time
import pytest
from travel.db import init_db, insert_message, get_conn
from travel.migrations import migrate
from travel.trip_crud import create_trip, add_participants, end_trip
from travel.badges import award_badges_for_trip


@pytest.fixture
def db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DB_PATH", path)
    init_db()
    migrate()
    yield path
    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


def _seed_messages(group_id="C1", n=5):
    now_ms = int(time.time() * 1000)
    for i in range(n):
        insert_message({
            "line_message_id": f"m{i}",
            "group_id": group_id,
            "user_id": f"U{i % 3 + 1}",
            "user_name": f"User{i % 3 + 1}",
            "type": "text",
            "content": f"msg {i}",
            "metadata": {},
            "reply_to_message_id": None,
            "timestamp": now_ms - i * 60000,
        })


def test_get_dashboard_data_returns_structure(db):
    from travel.stats import get_dashboard_data
    _seed_messages()
    data = get_dashboard_data("C1")
    assert "summary" in data
    assert "top_users" in data
    assert "type_distribution" in data
    assert "daily_counts" in data


def test_get_dashboard_data_summary_counts(db):
    from travel.stats import get_dashboard_data
    _seed_messages(n=5)
    data = get_dashboard_data("C1")
    assert data["summary"]["total_messages"] == 5
    assert data["summary"]["member_count"] >= 1


def test_get_trips_list_returns_list(db):
    from travel.stats import get_trips_list
    create_trip("C1", "墾丁", "墾丁海邊", 1700000000, "beach", "U1")
    trips = get_trips_list("C1")
    assert len(trips) == 1
    assert trips[0]["title"] == "墾丁"


def test_get_trip_detail_returns_detail(db):
    from travel.stats import get_trip_detail
    trip_id = create_trip("C1", "富士山", "日本", 1700000000, "mountain", "U1")
    add_participants(trip_id, ["U1", "U2"])
    detail = get_trip_detail(trip_id)
    assert detail["trip"]["id"] == trip_id
    assert len(detail["participants"]) == 2


def test_get_user_badges_returns_list(db):
    from travel.stats import get_user_badges
    trip_id = create_trip("C1", "旅行", "台北", 1700000000, None, "U1")
    add_participants(trip_id, ["U1"])
    end_trip(trip_id)
    award_badges_for_trip(trip_id)
    badges = get_user_badges("U1", "C1")
    assert len(badges) == 1
    assert badges[0]["badge_rarity"] is not None
```

- [ ] **Step 2: 確認 RED**

```bash
python -m pytest tests/test_stats.py -v
```

- [ ] **Step 3: 實作 `travel/stats.py`**

```python
"""Dashboard / trips / badges 查詢業務邏輯。被 liff_api.py 呼叫。"""
import time

from travel.db import get_conn
from travel.badges import compute_badge_emoji


def get_dashboard_data(group_id: str, days: int = 30) -> dict:
    """回傳群組儀表板資料。"""
    since_ms = int((time.time() - days * 86400) * 1000)
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE group_id=?", (group_id,)
        ).fetchone()[0]
        member_count = conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM messages WHERE group_id=?", (group_id,)
        ).fetchone()[0]
        active_trips = conn.execute(
            "SELECT COUNT(*) FROM trips WHERE group_id=? AND status='planning'", (group_id,)
        ).fetchone()[0]
        active_days = conn.execute(
            """SELECT COUNT(DISTINCT date(timestamp/1000, 'unixepoch'))
               FROM messages WHERE group_id=?""",
            (group_id,),
        ).fetchone()[0]

        top_users = conn.execute(
            """SELECT user_id, user_name, COUNT(*) AS total,
                      COUNT(DISTINCT date(timestamp/1000,'unixepoch')) AS active_days
               FROM messages WHERE group_id=?
               GROUP BY user_id ORDER BY total DESC LIMIT 10""",
            (group_id,),
        ).fetchall()

        type_dist = conn.execute(
            """SELECT type, COUNT(*) AS count FROM messages
               WHERE group_id=? GROUP BY type ORDER BY count DESC""",
            (group_id,),
        ).fetchall()

        daily_counts = conn.execute(
            """SELECT date(timestamp/1000,'unixepoch') AS date, COUNT(*) AS count
               FROM messages WHERE group_id=? AND timestamp >= ?
               GROUP BY date ORDER BY date ASC""",
            (group_id, since_ms),
        ).fetchall()

        heatmap = conn.execute(
            """SELECT CAST(strftime('%w', timestamp/1000,'unixepoch') AS INTEGER) AS day_of_week,
                      CAST(strftime('%H', timestamp/1000,'unixepoch') AS INTEGER) AS hour,
                      COUNT(*) AS count
               FROM messages WHERE group_id=?
               GROUP BY day_of_week, hour""",
            (group_id,),
        ).fetchall()

    return {
        "summary": {
            "total_messages": total,
            "active_days": active_days,
            "member_count": member_count,
            "active_trips": active_trips,
        },
        "top_users": [dict(r) for r in top_users],
        "type_distribution": [dict(r) for r in type_dist],
        "daily_counts": [dict(r) for r in daily_counts],
        "heatmap": [dict(r) for r in heatmap],
    }


def get_trips_list(group_id: str) -> list[dict]:
    """回傳群組所有旅行列表（含 badge_emoji）。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, title, location, start_date, end_date,
                      rarity, status, created_at
               FROM trips WHERE group_id=? ORDER BY created_at DESC""",
            (group_id,),
        ).fetchall()
    result = []
    for r in rows:
        trip = dict(r)
        rarity = trip.get("rarity") or "common"
        trip["badge_emoji"] = compute_badge_emoji(trip, rarity)
        result.append(trip)
    return result


def get_trip_detail(trip_id: str) -> dict:
    """回傳單一旅行詳情（含 participants）。"""
    with get_conn() as conn:
        trip_row = conn.execute(
            "SELECT * FROM trips WHERE id=?", (trip_id,)
        ).fetchone()
        participants_rows = conn.execute(
            """SELECT tp.user_id, tp.role, tp.joined_at, tp.messages_count,
                      (SELECT user_name FROM messages WHERE user_id=tp.user_id LIMIT 1) AS user_name
               FROM trip_participants tp WHERE tp.trip_id=?""",
            (trip_id,),
        ).fetchall()
        msg_count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE group_id=(SELECT group_id FROM trips WHERE id=?) AND timestamp BETWEEN (SELECT start_date*1000 FROM trips WHERE id=?) AND COALESCE((SELECT end_date*1000 FROM trips WHERE id=?), 9999999999999)",
            (trip_id, trip_id, trip_id),
        ).fetchone()[0]

    return {
        "trip": dict(trip_row) if trip_row else {},
        "participants": [dict(r) for r in participants_rows],
        "stats": {"message_count": msg_count},
        "memorable_quotes": [],
    }


def get_user_badges(user_id: str, group_id: str) -> list[dict]:
    """回傳 user 在某群組的所有徽章。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT b.id AS badge_id, b.badge_name, b.badge_rarity,
                      b.badge_image_url, b.earned_at, b.trip_id, b.description,
                      t.location
               FROM badges b
               LEFT JOIN trips t ON t.id = b.trip_id
               WHERE b.user_id=? AND (t.group_id=? OR t.group_id IS NULL)
                 AND b.user_id IS NOT NULL
               ORDER BY b.earned_at DESC""",
            (user_id, group_id),
        ).fetchall()
    result = []
    for r in rows:
        badge = dict(r)
        rarity = badge.get("badge_rarity") or "common"
        trip_info = {"location": badge.get("location") or ""}
        badge["badge_emoji"] = compute_badge_emoji(trip_info, rarity)
        result.append(badge)
    return result
```

- [ ] **Step 4: 確認 GREEN**

```bash
python -m pytest tests/test_stats.py -v
```

- [ ] **Step 5: Commit**

```bash
git add travel/stats.py tests/test_stats.py
git commit -m "feat(travel): add stats query layer for dashboard/trips/badges"
```

---

## Task 5: LIFF Flask Blueprint（TDD）

**Files:**
- Create: `telegram_bot/liff_api.py`
- Create: `tests/test_liff_api.py`
- Modify: `telegram_bot/bot.py` — 在 Flask app 初始化後 `app.register_blueprint(liff_bp)`

**Interfaces — Consumes:** `travel/trip_crud.py`、`travel/stats.py`、`travel/badges.py`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_liff_api.py
"""測試 telegram_bot/liff_api.py Flask Blueprint。"""
import os
import tempfile
import time
import pytest
from flask import Flask
from travel.db import init_db, insert_message
from travel.migrations import migrate
from travel.trip_crud import create_trip, add_participants, end_trip
from travel.badges import award_badges_for_trip


@pytest.fixture
def db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DB_PATH", path)
    monkeypatch.setenv("ADMIN_USER_IDS", "U_ADMIN")
    init_db()
    migrate()
    # seed 一筆 message 讓 U_MEMBER 成為 member
    insert_message({
        "line_message_id": "seed1",
        "group_id": "C1",
        "user_id": "U_MEMBER",
        "user_name": "Member",
        "type": "text",
        "content": "hello",
        "metadata": {},
        "reply_to_message_id": None,
        "timestamp": int(time.time() * 1000),
    })
    yield path
    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


@pytest.fixture
def client(db):
    from telegram_bot.liff_api import liff_bp
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(liff_bp)
    with app.test_client() as c:
        yield c


def _headers(user_id="U_MEMBER"):
    return {"X-LIFF-UserId": user_id, "X-LIFF-GroupId": "C1"}


def test_me_returns_role_member(client):
    r = client.get("/liff/me", headers=_headers("U_MEMBER"))
    assert r.status_code == 200
    data = r.get_json()
    assert data["role"] == "member"


def test_me_returns_role_admin(client):
    r = client.get("/liff/me", headers=_headers("U_ADMIN"))
    assert r.status_code == 200
    assert r.get_json()["role"] == "admin"


def test_dashboard_requires_group_id(client):
    r = client.get("/liff/dashboard", headers=_headers())
    assert r.status_code == 200
    assert "summary" in r.get_json()


def test_trips_returns_list(client, db):
    create_trip("C1", "測試旅行", "台北", 1700000000, None, "U_MEMBER")
    r = client.get("/liff/trips", headers={**_headers(), "X-LIFF-GroupId": "C1"})
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)


def test_badges_returns_list(client, db):
    r = client.get("/liff/badges/U_MEMBER", headers={**_headers(), "X-LIFF-GroupId": "C1"})
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)


def test_admin_create_trip(client):
    r = client.post(
        "/liff/admin/trips",
        json={"title": "新旅行", "location": "花蓮", "start_date": 1700000000},
        headers=_headers("U_ADMIN"),
    )
    assert r.status_code == 200
    data = r.get_json()
    assert "trip_id" in data


def test_admin_create_trip_forbidden_for_non_admin(client):
    r = client.post(
        "/liff/admin/trips",
        json={"title": "新旅行", "location": "花蓮", "start_date": 1700000000},
        headers=_headers("U_MEMBER"),
    )
    assert r.status_code == 403


def test_admin_end_trip(client):
    # setup
    trip_id = create_trip("C1", "t", "loc", 1700000000, None, "U_ADMIN")
    r = client.post(
        f"/liff/admin/trips/{trip_id}/end",
        headers=_headers("U_ADMIN"),
    )
    assert r.status_code == 200
    assert r.get_json()["status"] == "ended"


def test_admin_award_badges(client):
    trip_id = create_trip("C1", "t", "loc", 1700000000, None, "U_ADMIN")
    add_participants(trip_id, ["U_MEMBER"])
    end_trip(trip_id)
    r = client.post(
        f"/liff/admin/trips/{trip_id}/award-badges",
        headers=_headers("U_ADMIN"),
    )
    assert r.status_code == 200
    assert "awarded" in r.get_json()
```

- [ ] **Step 2: 確認 RED**

```bash
python -m pytest tests/test_liff_api.py -v
```

- [ ] **Step 3: 實作 `telegram_bot/liff_api.py`**

```python
"""Flask Blueprint — LIFF API endpoints（一般 + 管理員）。"""
import os

from flask import Blueprint, request, jsonify

from travel.stats import get_dashboard_data, get_trips_list, get_trip_detail, get_user_badges
from travel.trip_crud import create_trip, add_participants, end_trip
from travel.badges import award_badges_for_trip

liff_bp = Blueprint("liff", __name__, url_prefix="/liff")


def _get_liff_user_id() -> str:
    return request.headers.get("X-LIFF-UserId", "")


def _get_liff_group_id() -> str:
    return request.headers.get("X-LIFF-GroupId", request.args.get("group_id", ""))


def _admin_user_ids() -> set[str]:
    raw = os.getenv("ADMIN_USER_IDS", "")
    return {uid.strip() for uid in raw.split(",") if uid.strip()}


def _is_admin(user_id: str) -> bool:
    return user_id in _admin_user_ids()


def _is_member(user_id: str, group_id: str) -> bool:
    """True if user has any message in the group."""
    from travel.db import get_conn
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM messages WHERE user_id=? AND group_id=? LIMIT 1",
            (user_id, group_id),
        ).fetchone()
    return row is not None


def _forbid(reason: str):
    return jsonify({"error": "forbidden", "reason": reason}), 403


# ── 一般 endpoints ──────────────────────────────────────────────────────────

@liff_bp.route("/me")
def me():
    user_id = _get_liff_user_id()
    group_id = _get_liff_group_id()
    role = "admin" if _is_admin(user_id) else "member"
    return jsonify({"user_id": user_id, "role": role, "group_id": group_id})


@liff_bp.route("/dashboard")
def dashboard():
    user_id = _get_liff_user_id()
    group_id = _get_liff_group_id()
    days = int(request.args.get("days", 30))
    data = get_dashboard_data(group_id, days)
    return jsonify(data)


@liff_bp.route("/trips")
def trips():
    group_id = _get_liff_group_id()
    return jsonify(get_trips_list(group_id))


@liff_bp.route("/trips/<trip_id>")
def trip_detail(trip_id):
    return jsonify(get_trip_detail(trip_id))


@liff_bp.route("/badges/<user_id>")
def badges(user_id):
    group_id = _get_liff_group_id()
    return jsonify(get_user_badges(user_id, group_id))


# ── 管理員 endpoints ─────────────────────────────────────────────────────────

@liff_bp.route("/admin/trips", methods=["POST"])
def admin_create_trip():
    user_id = _get_liff_user_id()
    if not _is_admin(user_id):
        return _forbid("not_admin")
    body = request.get_json() or {}
    trip_id = create_trip(
        group_id=body.get("group_id") or _get_liff_group_id(),
        title=body.get("title", ""),
        location=body.get("location", ""),
        start_date=body.get("start_date", 0),
        trip_type=body.get("type"),
        created_by=user_id,
    )
    return jsonify({"trip_id": trip_id, "status": "planning"})


@liff_bp.route("/admin/trips/<trip_id>/participants", methods=["POST"])
def admin_add_participants(trip_id):
    user_id = _get_liff_user_id()
    if not _is_admin(user_id):
        return _forbid("not_admin")
    body = request.get_json() or {}
    result = add_participants(trip_id, body.get("user_ids", []))
    return jsonify(result)


@liff_bp.route("/admin/trips/<trip_id>/end", methods=["POST"])
def admin_end_trip(trip_id):
    user_id = _get_liff_user_id()
    if not _is_admin(user_id):
        return _forbid("not_admin")
    result = end_trip(trip_id)
    return jsonify(result)


@liff_bp.route("/admin/trips/<trip_id>/award-badges", methods=["POST"])
def admin_award_badges(trip_id):
    user_id = _get_liff_user_id()
    if not _is_admin(user_id):
        return _forbid("not_admin")
    awarded = award_badges_for_trip(trip_id)
    return jsonify({"awarded": awarded})
```

- [ ] **Step 4: 在 `telegram_bot/bot.py` 的 Flask app 建立後註冊 blueprint**

找到 `run_line_server` 函式（大約 line 874），在 `app = Flask(__name__)` 建立後加入：

```python
from telegram_bot.liff_api import liff_bp
app.register_blueprint(liff_bp)
logger.info("[LIFF] Blueprint registered at /liff/*")
```

- [ ] **Step 5: 確認 GREEN**

```bash
python -m pytest tests/test_liff_api.py -v
```

- [ ] **Step 6: Commit**

```bash
git add telegram_bot/liff_api.py tests/test_liff_api.py telegram_bot/bot.py
git commit -m "feat: add LIFF Flask Blueprint with 9 endpoints + blueprint registration"
```

---

## Task 6: Bot Trigger Logic（TDD）

**Files:**
- Modify: `telegram_bot/bot.py`
- Create: `tests/test_bot_triggers.py`

修改策略：將 bare mention + admin DM 判斷提取為 module-level 純函式（可獨立測試），並替換現有的「叫我幹嘛，沒事滾開」邏輯。

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_bot_triggers.py
"""測試 bot.py 新增的觸發判定純函式。"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class FakeSource:
    type: str
    user_id: str
    group_id: Optional[str] = None


@dataclass
class FakeMsg:
    text: Optional[str] = ""
    type: str = "text"


@dataclass
class FakeEvent:
    source: FakeSource
    message: FakeMsg
    reply_token: str = "tok001"


def test_bare_mention_group_only_at(monkeypatch):
    from telegram_bot.bot import is_group_bare_mention
    event = FakeEvent(
        source=FakeSource(type="group", user_id="U1", group_id="C1"),
        message=FakeMsg(text="@Sassy"),
    )
    assert is_group_bare_mention(event) is True


def test_bare_mention_with_text_is_false(monkeypatch):
    from telegram_bot.bot import is_group_bare_mention
    event = FakeEvent(
        source=FakeSource(type="group", user_id="U1", group_id="C1"),
        message=FakeMsg(text="@Sassy 你好"),
    )
    assert is_group_bare_mention(event) is False


def test_bare_mention_dm_is_false(monkeypatch):
    from telegram_bot.bot import is_group_bare_mention
    event = FakeEvent(
        source=FakeSource(type="user", user_id="U1"),
        message=FakeMsg(text="@Sassy"),
    )
    assert is_group_bare_mention(event) is False


def test_bare_mention_non_text_is_false(monkeypatch):
    from telegram_bot.bot import is_group_bare_mention
    event = FakeEvent(
        source=FakeSource(type="group", user_id="U1", group_id="C1"),
        message=FakeMsg(text=None),
    )
    assert is_group_bare_mention(event) is False


def test_admin_dm_true_for_admin_in_dm(monkeypatch):
    monkeypatch.setenv("ADMIN_USER_IDS", "U_ADMIN,U_ADMIN2")
    from telegram_bot.bot import is_admin_dm
    event = FakeEvent(
        source=FakeSource(type="user", user_id="U_ADMIN"),
        message=FakeMsg(text="任何訊息"),
    )
    assert is_admin_dm(event) is True


def test_admin_dm_false_for_admin_in_group(monkeypatch):
    monkeypatch.setenv("ADMIN_USER_IDS", "U_ADMIN")
    from telegram_bot.bot import is_admin_dm
    event = FakeEvent(
        source=FakeSource(type="group", user_id="U_ADMIN", group_id="C1"),
        message=FakeMsg(text="在群組裡"),
    )
    assert is_admin_dm(event) is False


def test_admin_dm_false_for_non_admin_in_dm(monkeypatch):
    monkeypatch.setenv("ADMIN_USER_IDS", "U_ADMIN")
    from telegram_bot.bot import is_admin_dm
    event = FakeEvent(
        source=FakeSource(type="user", user_id="U_RANDO"),
        message=FakeMsg(text="私訊"),
    )
    assert is_admin_dm(event) is False
```

- [ ] **Step 2: 確認 RED**

```bash
python -m pytest tests/test_bot_triggers.py -v
```

預期：`ImportError: cannot import name 'is_group_bare_mention' from 'telegram_bot.bot'`

- [ ] **Step 3: 在 `telegram_bot/bot.py` 新增 module-level 純函式和 env 常數**

在 `# --- 3. 配置 ---` 區塊末尾（大約 line 78 之後）加入：

```python
ADMIN_USER_IDS: set[str] = {
    uid.strip()
    for uid in os.getenv("ADMIN_USER_IDS", "").split(",")
    if uid.strip()
}
LIFF_ID = os.getenv("LIFF_ID", "")
LIFF_URL = f"https://liff.line.me/{LIFF_ID}" if LIFF_ID else "https://liff.line.me/placeholder"
```

在 class 定義（`class SassyBrain:`）之前加入：

```python
# ── Bot trigger helpers（module-level 可獨立測試）──────────────────────────

def is_group_bare_mention(event) -> bool:
    """True if group event with only @mention(s) and no other text."""
    if not hasattr(event.source, 'group_id'):
        return False
    msg_text = getattr(event.message, 'text', None)
    if not msg_text:
        return False
    stripped = re.sub(r'@\S+\s*', '', msg_text).strip()
    return stripped == "" and "@" in msg_text


def is_admin_dm(event) -> bool:
    """True if 1:1 DM from a user listed in ADMIN_USER_IDS."""
    if hasattr(event.source, 'group_id'):
        return False
    return getattr(event.source, 'user_id', '') in ADMIN_USER_IDS
```

- [ ] **Step 4: 在 `SassyBrain` class 新增 `_reply_liff_button` + 3 個 wrapper**

在 `SassyBrain.handle_line_event` 之前（class 內）加入：

```python
    def _is_group_bare_mention(self, event) -> bool:
        return is_group_bare_mention(event)

    def _is_admin_dm(self, event) -> bool:
        return is_admin_dm(event)

    def _reply_liff_button(self, event, role: str) -> None:
        """Reply with a Flex Message LIFF button."""
        from linebot.v3.messaging import (
            FlexMessage, FlexBubble, FlexBox, FlexText, FlexButton, URIAction,
        )
        if role == "admin":
            title = "🛠️ 管理員面板"
            subtitle = "點按下方按鈕進入管理後台"
            btn_label = "🛠️ 進入管理面板"
            path = "/admin"
        else:
            title = "🧳 旅行回顧"
            subtitle = "點按查看群組儀表板與徽章"
            btn_label = "🧳 開啟旅行回顧"
            path = "/"

        uri = f"{LIFF_URL}{path}"
        flex_msg = FlexMessage(
            alt_text=title,
            contents=FlexBubble(
                body=FlexBox(
                    layout="vertical",
                    contents=[
                        FlexText(text=title, weight="bold", size="lg"),
                        FlexText(text=subtitle, size="sm", color="#999999"),
                    ],
                ),
                footer=FlexBox(
                    layout="vertical",
                    contents=[
                        FlexButton(
                            action=URIAction(label=btn_label, uri=uri),
                            style="primary",
                        )
                    ],
                ),
            ),
        )
        try:
            self.line_api.reply_message(
                ReplyMessageRequest(reply_token=event.reply_token, messages=[flex_msg]),
                _request_timeout=_LINE_API_TIMEOUT,
            )
            logger.info(f"[LIFF] Flex button 回覆成功 role={role}")
        except Exception as e:
            logger.error(f"[LIFF] Flex button 回覆失敗: {e}")
```

- [ ] **Step 5: 修改 `handle_line_event()` — 加入 P2 分支並替換「叫我幹嘛」**

在 `handle_line_event` 的 `_store_line_event` 呼叫之後、`if not isinstance(event.message, TextMessageContent):` 之前，插入 admin DM 分支：

```python
        # [P2] Admin DM → LIFF 管理面板（任何訊息類型都攔截）
        if self.line_api and self._is_admin_dm(event):
            self._reply_liff_button(event, role="admin")
            return
```

接著找到現有「純 @mention 沒有附文字」的 block（大約 line 352-361）：

```python
        # 純 @mention 沒有附文字，直接嗆回不過 LLM
        if is_mentioned and not clean_text:
            qt = event.message.quote_token
            self.line_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[LineTextMessage(text="叫我幹嘛，沒事滾開。", **({'quote_token': qt} if qt else {}))],
                ),
                _request_timeout=_LINE_API_TIMEOUT,
            )
            return
```

替換為：

```python
        # [P2] 群組 bare @mention → LIFF 旅行回顧按鈕
        if is_mentioned and not clean_text:
            if self.line_api and self._is_group_bare_mention(event):
                self._reply_liff_button(event, role="user")
                return
            # fallback：非群組 bare mention（理論上不會跑到這）
            qt = event.message.quote_token
            self.line_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[LineTextMessage(text="叫我幹嘛，沒事滾開。", **({'quote_token': qt} if qt else {}))],
                ),
                _request_timeout=_LINE_API_TIMEOUT,
            )
            return
```

- [ ] **Step 6: 確認 GREEN**

```bash
python -m pytest tests/test_bot_triggers.py -v
```

- [ ] **Step 7: Commit**

```bash
git add telegram_bot/bot.py tests/test_bot_triggers.py
git commit -m "feat(bot): add bare mention → LIFF button + admin DM → admin panel"
```

---

## Task 7: APScheduler + Aggregator + Stats CLI 更新

**Files:**
- Modify: `telegram_bot/bot.py` — 加 badge_award scheduler job + migrate() 呼叫
- Modify: `travel/aggregator.py` — 加 aggregate_daily_stats (group-level)
- Modify: `scripts/show_stats.py` — 加 dashboard 子指令

- [ ] **Step 1: 在 `bot.py` 的 travel init block 加 migrate() 呼叫**

找到（大約 line 205）：
```python
        if os.getenv("TRAVEL_STORAGE_ENABLED", "true").lower() == "true":
            try:
                from travel.db import init_db
                init_db()
                logger.info("[TRAVEL] SQLite 已初始化")
```

改為：
```python
        if os.getenv("TRAVEL_STORAGE_ENABLED", "true").lower() == "true":
            try:
                from travel.db import init_db
                from travel.migrations import migrate
                init_db()
                migrate()
                logger.info("[TRAVEL] SQLite 已初始化並完成 migration")
```

- [ ] **Step 2: 在 APScheduler 區塊加 badge_award job**

找到 `run_daily_aggregation` job 之後（大約 line 278），加入：

```python
                from travel.badges import process_ended_trips
                self._scheduler.add_job(
                    process_ended_trips,
                    trigger='cron',
                    minute=5,
                    id='badge_award',
                    misfire_grace_time=3600,
                    coalesce=True,
                )
                logger.info("[BADGE] 每小時 :05 徽章發放排程已啟動")
```

- [ ] **Step 3: 在 `travel/aggregator.py` 末尾加 aggregate_daily_stats**

讀現有 [aggregator.py](travel/aggregator.py)，在 `run_daily_aggregation()` 之前加入：

```python
def aggregate_daily_stats(date_str: str | None = None):
    """聚合 group-level daily_stats（Phase 2）。"""
    date_str = date_str or time.strftime("%Y-%m-%d")
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT group_id,
                      SUM(CASE WHEN type='text' THEN 1 ELSE 0 END) AS text_count,
                      SUM(CASE WHEN type='sticker' THEN 1 ELSE 0 END) AS sticker_count,
                      SUM(CASE WHEN type='image' THEN 1 ELSE 0 END) AS image_count,
                      SUM(CASE WHEN type='video' THEN 1 ELSE 0 END) AS video_count,
                      SUM(CASE WHEN is_travel_related=1 THEN 1 ELSE 0 END) AS travel_mentions,
                      COUNT(DISTINCT user_id) AS active_users
               FROM messages
               WHERE date(timestamp/1000, 'unixepoch') = ?
               GROUP BY group_id""",
            (date_str,),
        ).fetchall()
        for r in rows:
            conn.execute(
                """INSERT OR REPLACE INTO daily_stats
                   (date, group_id, text_count, sticker_count, image_count,
                    video_count, travel_mentions, active_users)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (date_str, r["group_id"], r["text_count"] or 0,
                 r["sticker_count"] or 0, r["image_count"] or 0,
                 r["video_count"] or 0, r["travel_mentions"] or 0,
                 r["active_users"] or 0),
            )
    return len(rows)
```

同時更新 `run_daily_aggregation()` 呼叫 aggregate_daily_stats：

找到：
```python
def run_daily_aggregation():
    """每日聚合（被 APScheduler 觸發）。"""
    n1 = aggregate_daily()
    n2 = aggregate_lifetime()
    print(f"[AGGREGATOR] daily={n1}, lifetime={n2}")
```

改為：
```python
def run_daily_aggregation():
    """每日聚合（被 APScheduler 觸發）。"""
    n1 = aggregate_daily()
    n2 = aggregate_lifetime()
    n3 = aggregate_daily_stats()
    print(f"[AGGREGATOR] daily={n1}, lifetime={n2}, group_stats={n3}")
```

- [ ] **Step 4: 在 `scripts/show_stats.py` 加 dashboard 子指令**

在 `COMMANDS` dict 之前加入函式：

```python
def dashboard():
    with get_conn() as conn:
        # group-level daily_stats
        recent = conn.execute("""
            SELECT date, group_id, text_count, sticker_count, image_count,
                   active_users, travel_mentions
            FROM daily_stats
            ORDER BY date DESC LIMIT 14
        """).fetchall()
        groups = conn.execute(
            "SELECT DISTINCT group_id FROM messages"
        ).fetchall()
        trips = conn.execute(
            "SELECT status, COUNT(*) AS n FROM trips GROUP BY status"
        ).fetchall()
        badge_count = conn.execute(
            "SELECT COUNT(*) FROM badges WHERE user_id IS NOT NULL"
        ).fetchone()[0]
    print("=== Dashboard ===")
    print(f"群組數: {len(groups)}")
    for t in trips:
        print(f"  旅行 ({t['status']}): {t['n']}")
    print(f"已發徽章: {badge_count}")
    print("--- 近 14 天 daily_stats ---")
    for r in recent:
        print(f"  {r['date']} [{r['group_id'][:8]}] text={r['text_count']} active={r['active_users']}")
```

在 `COMMANDS` dict 加入：
```python
COMMANDS = {
    "overview": overview,
    "user": user_stats,
    "top-users": top_users,
    "topics": topic_distribution,
    "travel": travel_related,
    "dashboard": dashboard,      # ← 新增
}
```

更新 docstring 加上 `python scripts/show_stats.py dashboard`。

- [ ] **Step 5: 驗證執行**

```bash
python -m pytest tests/ -v
python scripts/show_stats.py dashboard
```

- [ ] **Step 6: Commit**

```bash
git add telegram_bot/bot.py travel/aggregator.py scripts/show_stats.py
git commit -m "feat: add badge_award scheduler, group-level daily_stats, dashboard CLI"
```

---

## Task 8: LIFF Frontend Scaffold

**Files（全部新建）:**
- `liff/package.json`
- `liff/vite.config.ts`
- `liff/tailwind.config.js`
- `liff/postcss.config.js`
- `liff/tsconfig.json`
- `liff/index.html`
- `liff/src/main.ts`
- `liff/src/App.vue`
- `liff/src/router.ts`
- `liff/src/stores/auth.ts`
- `liff/src/api/client.ts`
- `liff/.env.liff.example`

- [ ] **Step 1: 建立目錄結構**

```bash
mkdir -p liff/src/{views,components,stores,api}
mkdir -p liff/public
```

- [ ] **Step 2: 建立 `liff/package.json`**

```json
{
  "name": "sassy-liff",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.0",
    "@line/liff": "^2.22.0",
    "chart.js": "^4.4.0",
    "vue-chartjs": "^5.3.0"
  },
  "devDependencies": {
    "vite": "^5.2.0",
    "typescript": "^5.4.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "@vitejs/plugin-vue": "^5.0.0",
    "vue-tsc": "^2.0.0"
  }
}
```

- [ ] **Step 3: 建立 `liff/vite.config.ts`**

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/liff': 'http://localhost:5000',
    },
  },
})
```

- [ ] **Step 4: 建立 `liff/tailwind.config.js`**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: { extend: {} },
  plugins: [],
}
```

- [ ] **Step 5: 建立 `liff/postcss.config.js`**

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 6: 建立 `liff/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "preserve",
    "strict": true,
    "noUnusedLocals": false,
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src/**/*.ts", "src/**/*.vue"]
}
```

- [ ] **Step 7: 建立 `liff/index.html`**

```html
<!doctype html>
<html lang="zh-TW">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>旅行回顧</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 8: 建立 `liff/src/main.ts`**

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

- [ ] **Step 9: 建立 `liff/src/style.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 10: 建立 `liff/src/api/client.ts`**

```typescript
const API_BASE = '/liff'

let _userId = ''
let _groupId = ''

export function setLiffContext(userId: string, groupId: string) {
  _userId = userId
  _groupId = groupId
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-LIFF-UserId': _userId,
    'X-LIFF-GroupId': _groupId,
    ...((opts.headers as Record<string, string>) || {}),
  }
  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers })
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json() as Promise<T>
}

export const api = {
  me: () => req<{ user_id: string; role: string; group_id: string }>('/me'),
  dashboard: (days = 30) => req<any>(`/dashboard?days=${days}`),
  trips: () => req<any[]>('/trips'),
  tripDetail: (id: string) => req<any>(`/trips/${id}`),
  badges: (userId: string) => req<any[]>(`/badges/${userId}`),
  adminCreateTrip: (body: any) => req<any>('/admin/trips', { method: 'POST', body: JSON.stringify(body) }),
  adminAddParticipants: (tripId: string, userIds: string[]) =>
    req<any>(`/admin/trips/${tripId}/participants`, { method: 'POST', body: JSON.stringify({ user_ids: userIds }) }),
  adminEndTrip: (tripId: string) => req<any>(`/admin/trips/${tripId}/end`, { method: 'POST' }),
  adminAwardBadges: (tripId: string) => req<any>(`/admin/trips/${tripId}/award-badges`, { method: 'POST' }),
}
```

- [ ] **Step 11: 建立 `liff/src/stores/auth.ts`**

```typescript
import { defineStore } from 'pinia'
import liff from '@line/liff'
import { api, setLiffContext } from '@/api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    initialized: false,
    userId: '',
    role: '' as 'admin' | 'member' | '',
    groupId: '',
    isMember: false,
  }),
  actions: {
    async init() {
      if (this.initialized) return
      await liff.init({ liffId: import.meta.env.VITE_LIFF_ID as string })
      if (!liff.isLoggedIn()) {
        liff.login()
        return
      }
      const profile = await liff.getProfile()
      this.userId = profile.userId

      // Try to get groupId from LIFF context
      const ctx = liff.getContext()
      this.groupId = (ctx as any)?.groupId || ''

      setLiffContext(this.userId, this.groupId)

      const me = await api.me()
      this.role = me.role as 'admin' | 'member'
      this.isMember = true
      this.initialized = true
    },
  },
})
```

- [ ] **Step 12: 建立 `liff/src/router.ts`**

```typescript
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('@/views/DashboardView.vue'), meta: { requiresParticipant: true } },
    { path: '/trips', component: () => import('@/views/TripListView.vue'), meta: { requiresParticipant: true } },
    { path: '/trips/:id', component: () => import('@/views/TripDetailView.vue'), meta: { requiresParticipant: true } },
    { path: '/badges', component: () => import('@/views/BadgesView.vue'), meta: { requiresParticipant: true } },
    { path: '/admin', component: () => import('@/views/TripAdminListView.vue'), meta: { requiresAdmin: true } },
    { path: '/admin/trips/new', component: () => import('@/views/TripCreateView.vue'), meta: { requiresAdmin: true } },
    { path: '/admin/trips/:id', component: () => import('@/views/TripManageView.vue'), meta: { requiresAdmin: true } },
    { path: '/403', component: () => import('@/views/ForbiddenView.vue') },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.initialized) {
    try { await auth.init() } catch { return '/403' }
  }
  if (to.meta.requiresAdmin && auth.role !== 'admin') return '/'
  if (to.meta.requiresParticipant && !auth.isMember) return '/403'
})

export default router
```

- [ ] **Step 13: 建立 `liff/src/App.vue`**

```vue
<template>
  <div class="min-h-screen bg-gray-50">
    <nav v-if="auth.initialized" class="bg-white border-b px-4 py-2 flex gap-4 text-sm">
      <router-link to="/" class="hover:text-blue-600">儀表板</router-link>
      <router-link to="/trips" class="hover:text-blue-600">旅行</router-link>
      <router-link to="/badges" class="hover:text-blue-600">徽章</router-link>
      <router-link v-if="auth.role === 'admin'" to="/admin" class="hover:text-red-600 font-medium">管理</router-link>
    </nav>
    <main class="p-4">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
</script>
```

- [ ] **Step 14: 建立 `liff/.env.liff.example`**

```
VITE_LIFF_ID=your-liff-id-here
```

- [ ] **Step 15: 安裝依賴 + 確認 dev server 能啟動**

```bash
cd liff
cp .env.liff.example .env.local
npm install
npm run dev
```

預期：Vite server 在 :5173 啟動，瀏覽器打開 http://localhost:5173 顯示 LIFF init 流程（可能報 LIFF_ID 錯誤，這是正常的 — 需要真實 LIFF_ID）。

- [ ] **Step 16: Commit**

```bash
cd ..
git add liff/
git commit -m "feat(liff): scaffold Vite+Vue3+Tailwind LIFF frontend project"
```

---

## Task 9: LIFF Views

**Files（全部新建）:**
- `liff/src/views/ForbiddenView.vue`
- `liff/src/components/BadgeCard.vue`
- `liff/src/views/DashboardView.vue`
- `liff/src/views/TripListView.vue`
- `liff/src/views/TripDetailView.vue`
- `liff/src/views/BadgesView.vue`

- [ ] **Step 1: `liff/src/views/ForbiddenView.vue`**

```vue
<template>
  <div class="text-center py-16">
    <p class="text-4xl mb-4">🚫</p>
    <h1 class="text-xl font-bold text-gray-700">你不是群組成員</h1>
    <p class="text-gray-500 mt-2">請先加入群組後再使用此功能</p>
  </div>
</template>
```

- [ ] **Step 2: `liff/src/components/BadgeCard.vue`**

```vue
<template>
  <div class="bg-white rounded-xl shadow p-4 flex items-center gap-3">
    <div class="text-4xl">{{ badge.badge_image_url ? '' : badge.badge_emoji }}</div>
    <img v-if="badge.badge_image_url" :src="badge.badge_image_url" class="w-12 h-12 rounded-full object-cover" />
    <div>
      <p class="font-semibold text-sm">{{ badge.badge_name }}</p>
      <p class="text-xs text-gray-400">{{ rarityLabel }}</p>
      <p class="text-xs text-gray-400">{{ earnedDate }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ badge: any }>()

const RARITY_LABEL: Record<string, string> = {
  common: '🟢 一般', rare: '🔵 稀有', epic: '🟣 史詩', legendary: '🟡 傳說',
}

const rarityLabel = computed(() => RARITY_LABEL[props.badge.badge_rarity] || props.badge.badge_rarity)
const earnedDate = computed(() => {
  if (!props.badge.earned_at) return ''
  return new Date(props.badge.earned_at * 1000).toLocaleDateString('zh-TW')
})
</script>
```

- [ ] **Step 3: `liff/src/views/DashboardView.vue`**

```vue
<template>
  <div>
    <h1 class="text-xl font-bold mb-4">📊 群組儀表板</h1>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="data">
      <div class="grid grid-cols-2 gap-3 mb-6">
        <div class="bg-white rounded-xl p-4 shadow text-center">
          <p class="text-2xl font-bold">{{ data.summary.total_messages }}</p>
          <p class="text-xs text-gray-500">總訊息</p>
        </div>
        <div class="bg-white rounded-xl p-4 shadow text-center">
          <p class="text-2xl font-bold">{{ data.summary.member_count }}</p>
          <p class="text-xs text-gray-500">成員數</p>
        </div>
        <div class="bg-white rounded-xl p-4 shadow text-center">
          <p class="text-2xl font-bold">{{ data.summary.active_trips }}</p>
          <p class="text-xs text-gray-500">進行中旅行</p>
        </div>
        <div class="bg-white rounded-xl p-4 shadow text-center">
          <p class="text-2xl font-bold">{{ data.summary.active_days }}</p>
          <p class="text-xs text-gray-500">活躍天數</p>
        </div>
      </div>

      <h2 class="font-semibold mb-2">🏆 Top 話癆</h2>
      <div class="bg-white rounded-xl shadow divide-y mb-6">
        <div v-for="(u, i) in data.top_users.slice(0, 5)" :key="u.user_id"
             class="flex items-center px-4 py-2 gap-3">
          <span class="text-gray-400 text-sm w-5">{{ i + 1 }}</span>
          <span class="flex-1 text-sm">{{ u.user_name || u.user_id }}</span>
          <span class="text-sm font-medium">{{ u.total }}</span>
        </div>
      </div>

      <h2 class="font-semibold mb-2">📨 訊息類型</h2>
      <div class="bg-white rounded-xl shadow divide-y">
        <div v-for="t in data.type_distribution" :key="t.type"
             class="flex items-center px-4 py-2 gap-3">
          <span class="flex-1 text-sm">{{ t.type }}</span>
          <span class="text-sm font-medium">{{ t.count }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'

const data = ref<any>(null)
const loading = ref(true)

onMounted(async () => {
  try { data.value = await api.dashboard() }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
```

- [ ] **Step 4: `liff/src/views/TripListView.vue`**

```vue
<template>
  <div>
    <h1 class="text-xl font-bold mb-4">🧳 旅行列表</h1>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="trips.length === 0" class="text-center py-8 text-gray-400">尚無旅行紀錄</div>
    <div v-else class="space-y-3">
      <router-link v-for="t in trips" :key="t.id" :to="`/trips/${t.id}`"
                   class="block bg-white rounded-xl shadow p-4">
        <div class="flex items-center gap-2">
          <span class="text-2xl">{{ t.badge_emoji }}</span>
          <div class="flex-1">
            <p class="font-semibold">{{ t.title }}</p>
            <p class="text-xs text-gray-400">{{ t.location }}</p>
          </div>
          <span class="text-xs px-2 py-1 rounded-full"
                :class="t.status === 'ended' ? 'bg-gray-100 text-gray-500' : 'bg-blue-100 text-blue-600'">
            {{ t.status === 'ended' ? '已結束' : '進行中' }}
          </span>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'

const trips = ref<any[]>([])
const loading = ref(true)

onMounted(async () => {
  try { trips.value = await api.trips() }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
```

- [ ] **Step 5: `liff/src/views/TripDetailView.vue`**

```vue
<template>
  <div>
    <button @click="$router.back()" class="text-sm text-gray-500 mb-4">← 返回</button>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="detail">
      <div class="bg-white rounded-xl shadow p-4 mb-4">
        <h1 class="text-xl font-bold">{{ detail.trip.title }}</h1>
        <p class="text-gray-500 text-sm">{{ detail.trip.location }}</p>
        <p class="text-xs text-gray-400 mt-1">狀態：{{ detail.trip.status }}</p>
        <p class="text-xs text-gray-400">訊息數：{{ detail.stats.message_count }}</p>
      </div>

      <h2 class="font-semibold mb-2">👥 參與者（{{ detail.participants.length }}）</h2>
      <div class="bg-white rounded-xl shadow divide-y mb-4">
        <div v-for="p in detail.participants" :key="p.user_id" class="px-4 py-2 text-sm">
          {{ p.user_name || p.user_id }}
          <span class="text-xs text-gray-400 ml-2">{{ p.role || '成員' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'

const route = useRoute()
const detail = ref<any>(null)
const loading = ref(true)

onMounted(async () => {
  try { detail.value = await api.tripDetail(route.params.id as string) }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
```

- [ ] **Step 6: `liff/src/views/BadgesView.vue`**

```vue
<template>
  <div>
    <h1 class="text-xl font-bold mb-4">🏅 我的徽章</h1>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="badges.length === 0" class="text-center py-8 text-gray-400">
      尚未獲得徽章
    </div>
    <div v-else class="space-y-3">
      <BadgeCard v-for="b in badges" :key="b.badge_id" :badge="b" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import BadgeCard from '@/components/BadgeCard.vue'

const auth = useAuthStore()
const badges = ref<any[]>([])
const loading = ref(true)

onMounted(async () => {
  try { badges.value = await api.badges(auth.userId) }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
```

- [ ] **Step 7: Commit**

```bash
cd liff && npm run build  # 確認無 TypeScript 錯誤
cd ..
git add liff/src/
git commit -m "feat(liff): add general views (Dashboard/TripList/TripDetail/Badges)"
```

---

## Task 10: LIFF Admin Views

**Files（全部新建）:**
- `liff/src/views/TripAdminListView.vue`
- `liff/src/views/TripCreateView.vue`
- `liff/src/views/TripManageView.vue`

- [ ] **Step 1: `liff/src/views/TripAdminListView.vue`**

```vue
<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-xl font-bold">🛠️ 旅行管理</h1>
      <router-link to="/admin/trips/new"
                   class="bg-blue-600 text-white text-sm px-3 py-1.5 rounded-lg">
        + 新增旅行
      </router-link>
    </div>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else class="space-y-3">
      <router-link v-for="t in trips" :key="t.id" :to="`/admin/trips/${t.id}`"
                   class="block bg-white rounded-xl shadow p-4">
        <div class="flex items-center gap-2">
          <span class="text-2xl">{{ t.badge_emoji }}</span>
          <div class="flex-1">
            <p class="font-semibold">{{ t.title }}</p>
            <p class="text-xs text-gray-400">{{ t.location }}</p>
          </div>
          <span class="text-xs text-gray-500">{{ t.status }}</span>
        </div>
      </router-link>
      <div v-if="trips.length === 0" class="text-center py-8 text-gray-400">尚無旅行</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'

const trips = ref<any[]>([])
const loading = ref(true)

onMounted(async () => {
  try { trips.value = await api.trips() }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
```

- [ ] **Step 2: `liff/src/views/TripCreateView.vue`**

```vue
<template>
  <div>
    <button @click="$router.back()" class="text-sm text-gray-500 mb-4">← 返回</button>
    <h1 class="text-xl font-bold mb-4">🆕 建立旅行</h1>
    <form @submit.prevent="submit" class="space-y-4">
      <div>
        <label class="block text-sm font-medium mb-1">標題 *</label>
        <input v-model="form.title" required
               class="w-full border rounded-lg px-3 py-2 text-sm" placeholder="墾丁三日遊" />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">地點 *</label>
        <input v-model="form.location" required
               class="w-full border rounded-lg px-3 py-2 text-sm" placeholder="墾丁" />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">出發日 *</label>
        <input v-model="form.startDate" type="date" required
               class="w-full border rounded-lg px-3 py-2 text-sm" />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">類型</label>
        <select v-model="form.tripType" class="w-full border rounded-lg px-3 py-2 text-sm">
          <option value="">請選擇</option>
          <option value="beach">海灘</option>
          <option value="mountain">山岳</option>
          <option value="city">城市</option>
          <option value="other">其他</option>
        </select>
      </div>
      <div class="flex gap-2 pt-2">
        <button type="submit" :disabled="loading"
                class="flex-1 bg-blue-600 text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50">
          {{ loading ? '建立中...' : '建立旅行' }}
        </button>
        <button type="button" @click="$router.back()"
                class="flex-1 border rounded-lg py-2 text-sm">取消</button>
      </div>
      <p v-if="error" class="text-red-500 text-sm">{{ error }}</p>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'

const router = useRouter()
const loading = ref(false)
const error = ref('')
const form = ref({ title: '', location: '', startDate: '', tripType: '' })

async function submit() {
  loading.value = true
  error.value = ''
  try {
    const startDate = Math.floor(new Date(form.value.startDate).getTime() / 1000)
    const res = await api.adminCreateTrip({
      title: form.value.title,
      location: form.value.location,
      start_date: startDate,
      type: form.value.tripType || null,
    })
    router.push(`/admin/trips/${res.trip_id}`)
  } catch (e: any) {
    error.value = e.message || '建立失敗'
  } finally {
    loading.value = false
  }
}
</script>
```

- [ ] **Step 3: `liff/src/views/TripManageView.vue`**

```vue
<template>
  <div>
    <button @click="$router.back()" class="text-sm text-gray-500 mb-4">← 返回</button>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="detail">
      <div class="bg-white rounded-xl shadow p-4 mb-4">
        <h1 class="text-xl font-bold">{{ detail.trip.title }}</h1>
        <p class="text-gray-500 text-sm">{{ detail.trip.location }}</p>
        <p class="text-xs mt-1">狀態：
          <span :class="detail.trip.status === 'ended' ? 'text-gray-400' : 'text-blue-600'">
            {{ detail.trip.status === 'ended' ? '已結束' : '進行中' }}
          </span>
        </p>
      </div>

      <div class="bg-white rounded-xl shadow p-4 mb-4">
        <h2 class="font-semibold mb-2">👥 參與者（{{ detail.participants.length }}）</h2>
        <div class="text-sm text-gray-600 mb-3">
          <span v-for="p in detail.participants" :key="p.user_id"
                class="inline-block bg-gray-100 rounded-full px-2 py-0.5 text-xs mr-1 mb-1">
            {{ p.user_name || p.user_id }}
          </span>
        </div>
        <div v-if="detail.trip.status !== 'ended'" class="flex gap-2">
          <input v-model="newParticipant" placeholder="LINE user_id"
                 class="flex-1 border rounded-lg px-3 py-1.5 text-sm" />
          <button @click="addParticipant" :disabled="addLoading"
                  class="bg-gray-800 text-white text-sm px-3 py-1.5 rounded-lg disabled:opacity-50">
            加入
          </button>
        </div>
      </div>

      <div v-if="detail.trip.status !== 'ended'" class="space-y-3">
        <button @click="endTrip" :disabled="actionLoading"
                class="w-full bg-orange-500 text-white rounded-xl py-3 font-medium disabled:opacity-50">
          🏁 結束旅行
        </button>
      </div>
      <div v-if="detail.trip.status === 'ended'" class="space-y-3">
        <button @click="awardBadges" :disabled="actionLoading"
                class="w-full bg-purple-600 text-white rounded-xl py-3 font-medium disabled:opacity-50">
          🏅 發放徽章
        </button>
      </div>

      <p v-if="message" class="text-center mt-3 text-sm text-green-600">{{ message }}</p>
      <p v-if="error" class="text-center mt-3 text-sm text-red-500">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'

const route = useRoute()
const tripId = route.params.id as string

const detail = ref<any>(null)
const loading = ref(true)
const addLoading = ref(false)
const actionLoading = ref(false)
const newParticipant = ref('')
const message = ref('')
const error = ref('')

async function load() {
  loading.value = true
  try { detail.value = await api.tripDetail(tripId) }
  finally { loading.value = false }
}

async function addParticipant() {
  if (!newParticipant.value.trim()) return
  addLoading.value = true
  try {
    await api.adminAddParticipants(tripId, [newParticipant.value.trim()])
    newParticipant.value = ''
    await load()
    message.value = '已加入'
  } catch (e: any) { error.value = e.message }
  finally { addLoading.value = false }
}

async function endTrip() {
  if (!confirm('確定結束旅行？')) return
  actionLoading.value = true
  try {
    await api.adminEndTrip(tripId)
    await load()
    message.value = '旅行已結束'
  } catch (e: any) { error.value = e.message }
  finally { actionLoading.value = false }
}

async function awardBadges() {
  actionLoading.value = true
  try {
    const res = await api.adminAwardBadges(tripId)
    message.value = `已發放 ${res.awarded.length} 枚徽章`
  } catch (e: any) { error.value = e.message }
  finally { actionLoading.value = false }
}

onMounted(load)
</script>
```

- [ ] **Step 4: 驗證 build**

```bash
cd liff && npm run build
```

預期：`dist/` 目錄建立完成，無 TypeScript 錯誤。

- [ ] **Step 5: Commit**

```bash
cd ..
git add liff/src/views/TripAdminListView.vue liff/src/views/TripCreateView.vue liff/src/views/TripManageView.vue
git commit -m "feat(liff): add admin views (TripAdminList/TripCreate/TripManage)"
```

---

## Task 11: Config + .gitignore + E2E 驗證

**Files:**
- Modify: `.env`（新增 ADMIN_USER_IDS / LIFF_ID）
- Modify: `.gitignore`（新增 liff entries）

- [ ] **Step 1: 更新 `.env`**

在 `.env` 加入（`.env` 已 gitignored，不進版控）：

```env
# Phase 2 — Admin
ADMIN_USER_IDS=U你的LINE_USER_ID

# Phase 2 — LIFF
LIFF_ID=your-liff-id-from-line-developers
```

- [ ] **Step 2: 更新 `.gitignore`**

在 `.gitignore` 加入：

```gitignore
# LIFF frontend
liff/node_modules/
liff/dist/
liff/.env.local
liff/.env.liff
```

- [ ] **Step 3: 跑完整測試確認全綠**

```bash
python -m pytest tests/ -v
```

預期：所有測試全綠。

- [ ] **Step 4: E2E Step A — Bot 啟動 + migration**

```bash
python telegram_bot/bot.py
```

確認 log 出現：
- `[TRAVEL] SQLite 已初始化並完成 migration`
- `[MIGRATIONS] schema at version 5`
- `[LIFF] Blueprint registered at /liff/*`
- `[BADGE] 每小時 :05 徽章發放排程已啟動`

- [ ] **Step 5: E2E Step B — 一般使用者 bare mention**

在 LINE 群組打「@bot」（只有 @bot，無其他文字）。確認 bot 回 Flex Message「🧳 開啟旅行回顧」按鈕。

在群組打「@bot 你好」→ 確認回 PTT 風格嘴砲（既有行為不變）。

- [ ] **Step 6: E2E Step C — Admin DM**

管理員（ADMIN_USER_IDS 中的 user_id）私訊 bot 任何訊息 → 確認回「🛠️ 進入管理面板」Flex Message。

非 admin 私訊 bot → 確認回 PTT 嘴砲。

- [ ] **Step 7: E2E Step D — 管理員 LIFF 操作**

啟動 LIFF dev server + ngrok：
```bash
# Terminal 1: Flask
python telegram_bot/bot.py

# Terminal 2: LIFF
cd liff && npm run dev

# Terminal 3: ngrok (Flask)
ngrok http 5000

# Terminal 4: ngrok (LIFF)
ngrok http 5173
```

在 LINE Developers 設定 LIFF Endpoint URL 為 Vite ngrok URL。點管理面板 LIFF 按鈕，完成：
- 建立旅行「測試旅行」 → 確認 DB 有 row（`status='planning'`）
- 加入 2 個參與者（fake user_id）→ 確認 `trip_participants` 有 2 row
- 結束旅行 → 確認 `status='ended', ended_at` 有值

- [ ] **Step 8: E2E Step E — 自動發徽章**

```bash
python -c "
import os; os.environ['DB_PATH']='data/chat.db'
from travel.badges import process_ended_trips
process_ended_trips()
"
```

確認 `badges` 表有 row，emoji metadata 正確。重跑一次確認 UNIQUE 約束生效。

- [ ] **Step 9: E2E Step F — 一般使用者查看 LIFF**

一般成員在群組 `@bot` → 點 LIFF 按鈕。驗證：
- Dashboard 顯示統計數字
- `/trips` 看到測試旅行
- `/trips/:id` 看到參與者
- `/badges` 看到 emoji 徽章

- [ ] **Step 10: E2E Step G — 權限測試**

一般成員嘗試訪問 `/admin/*` → 被 route guard 擋下，導回 `/`。

確認 `GET /liff/admin/trips`（用非 admin header）回 403。

- [ ] **Step 11: Final commit**

```bash
git add .gitignore
git commit -m "chore: add liff/.gitignore entries and Phase 2 E2E verified"
```

---

## 驗證清單（Phase 2 完成時勾選）

- [ ] `python -m pytest tests/ -v` 全綠（含 P2 新增 6 個 test files）
- [ ] Bot 啟動 log 出現 `[MIGRATIONS] schema at version 5`
- [ ] Bot 啟動 log 出現 `[LIFF] Blueprint registered at /liff/*`
- [ ] Bot 啟動 log 出現 `[BADGE] 每小時 :05 徽章發放排程已啟動`
- [ ] 群組 bare `@bot` → Flex Message LIFF 按鈕
- [ ] Admin DM → Flex Message 管理面板按鈕
- [ ] `POST /liff/admin/trips` (admin header) → 201 有 trip_id
- [ ] `POST /liff/admin/trips/<id>/award-badges` → badges 表有 row
- [ ] `liff npm run build` 無 TypeScript 錯誤
- [ ] LIFF Dashboard 載入正常，顯示群組統計
- [ ] LIFF Badges 頁顯示 emoji 徽章
