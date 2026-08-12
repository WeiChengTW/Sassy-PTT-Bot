# Travel Extension — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把現有的 Sassy PTT Bot 擴展為 LINE 群組旅遊回顧系統，分兩階段交付：

- **Phase 1（本計畫）**：訊息儲存 + LLM 分析 + 統計聚合（無 UI）
- **Phase 2（之後另開）**：徽章系統 + LIFF 網頁 + 管理員指令

---

## Architecture

```
LINE Webhook (既有 Flask @ :5000)
    │
    ├── 觸發判定（既有 PTT 風格回應邏輯）
    │
    ├── [Phase 1 新] 訊息儲存 hook
    │   └── 全部訊息 → SQLite (data/chat.db)
    │
    └── APScheduler（既有）
        ├── 每日 09:00  畢業倒數（既有）
        ├── [Phase 1 新] 每月 1 號 03:00  LLM 訊息分析
        └── [Phase 1 新] 每日 04:00  統計聚合

[Phase 2 之後]
├── 管理員指令（建立旅行 / 生成徽章）
├── fal.ai Kontext API 徽章生成
├── ComfyUI 母徽章（一次性）
└── LIFF 前端（Vite + Vue 3 + Tailwind）
```

**Tech Stack 新增（Phase 1）:** 不需要新套件 — 全部用既有（Flask / APScheduler / openai SDK / sqlite3）。
**Tech Stack 新增（Phase 2）:** `fal-client` + Vite/Vue 3/Tailwind/Chart.js。

---

## Design Decisions（已確定，避免遺忘）

| 項目 | 決策 |
|---|---|
| 部署主機 | 這台（有 GPU） |
| 對外 HTTPS | 沿用 `ngrok.yml`（之後仍用它） |
| 訊息永久保存 | ✅ 永久保留（不限期限） |
| 圖片 / 影片 | 只存類型計數，不存 message_id |
| 貼圖 | 存 `sticker_id` + `package_id` |
| `user_id` | 存真實 LINE user_id |
| LLM provider | gemini-3.6-flash-high（既有 Primary）+ gpt-5-mini（既有 Fallback） |
| LLM 分析頻率 | 每月 1 號 03:00（最短月、最長年） |
| LLM 分析類型 | 主題 + 情緒 + 實體（地點、日期）+ 摘要（全做） |
| 部署分支 | `feature/travel-extension`（worktree at `.worktrees/travel-extension/`） |

**Phase 2 才決定的：**
| 項目 | 決策 |
|---|---|
| LIFF 框架 | Vite + Vue 3 + Tailwind CSS |
| LIFF RWD | ✅ 必做 |
| LIFF 權限分級 | ✅ 必做 |
| 旅行參與者 | 管理員手動登記 |
| 徽章稀有度 | 之後另開計畫 |
| 母徽章生成 | ComfyUI 一次性 |
| 執行期生圖 | fal.ai Kontext |
| 徽章觸發 | 管理員在 LINE 群組下指令 |

---

## Phase 1：訊息儲存 + 分析統計（本階段實作）

**目標：** 跑一個月驗證資料流（儲存 → 分析 → 聚合），所有資訊都可從 CLI 查到。
**範圍限制：** 不做管理員指令、不做 LIFF、不改既有 PTT 回應邏輯。

### Task 1.0：環境準備

**Files:**
- Modify: `.env`
- Modify: `requirements.txt`

- [ ] **Step 1: 在 `.env` 加入新變數**

```env
# SQLite 路徑
DB_PATH=data/chat.db

# 訊息儲存總開關（萬一出問題可以快速關掉）
TRAVEL_STORAGE_ENABLED=true
```

> `.env` 已 gitignored，不會進版控。

- [ ] **Step 2: 不需要新套件**

`requirements.txt` 不改。Phase 1 全部用既有依賴（Flask / APScheduler / openai SDK / 內建 sqlite3）。

### Task 1.1：SQLite schema + db.py（TDD）

**Files:**
- Create: `travel/__init__.py`
- Create: `travel/db.py`
- Create: `tests/__init__.py`
- Create: `tests/test_db.py`

**TDD 流程（Red → Green → Refactor）：**

#### 1.1.1 RED — 先寫測試

**Files:**
- Create: `tests/__init__.py`（空）
- Create: `tests/test_db.py`

```python
"""測試 travel/db.py。"""
import os
import tempfile
import pytest
from travel.db import init_db, insert_message, get_conn


@pytest.fixture
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DB_PATH", path)
    yield path
    os.unlink(path)
    if os.path.exists(path + "-wal"):
        os.unlink(path + "-wal")
    if os.path.exists(path + "-shm"):
        os.unlink(path + "-shm")


def test_init_db_creates_messages_table(temp_db):
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
        ).fetchone()
    assert row is not None


def test_init_db_creates_trips_table(temp_db):
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='trips'"
        ).fetchone()
    assert row is not None


def test_insert_message_returns_true_for_new(temp_db):
    init_db()
    result = insert_message({
        "line_message_id": "msg-001",
        "group_id": "C123",
        "user_id": "U001",
        "user_name": "Alice",
        "type": "text",
        "content": "hello",
        "metadata": {},
        "reply_to_message_id": None,
        "timestamp": 1700000000000,
    })
    assert result is True


def test_insert_message_returns_false_for_duplicate(temp_db):
    init_db()
    msg = {
        "line_message_id": "msg-001",
        "group_id": "C123",
        "user_id": "U001",
        "user_name": "Alice",
        "type": "text",
        "content": "hello",
        "metadata": {},
        "reply_to_message_id": None,
        "timestamp": 1700000000000,
    }
    insert_message(msg)
    result = insert_message(msg)
    assert result is False


def test_insert_message_stores_metadata_as_json(temp_db):
    init_db()
    insert_message({
        "line_message_id": "msg-002",
        "group_id": "C123",
        "user_id": "U001",
        "user_name": "Alice",
        "type": "sticker",
        "content": None,
        "metadata": {"sticker_id": "1", "package_id": "2"},
        "reply_to_message_id": None,
        "timestamp": 1700000000000,
    })
    with get_conn() as conn:
        row = conn.execute("SELECT metadata FROM messages WHERE id=1").fetchone()
    import json
    assert json.loads(row["metadata"]) == {"sticker_id": "1", "package_id": "2"}


def test_get_conn_uses_wal_mode(temp_db):
    init_db()
    with get_conn() as conn:
        row = conn.execute("PRAGMA journal_mode").fetchone()
    assert row[0].lower() == "wal"
```

- [ ] **Step 1: 跑測試確認失敗**

```bash
cd /home/william/projects/Sassy-PTT-Bot/.worktrees/travel-extension
source ../../venv/bin/activate
pip install pytest
python -m pytest tests/test_db.py -v
```

預期：`ModuleNotFoundError: No module named 'travel'` — 測試失敗（這是預期的 RED 狀態）。

#### 1.1.2 GREEN — 寫最小實作

**Files:**
- Create: `travel/__init__.py`

```python
"""Travel extension for Sassy PTT Bot (Phase 1: storage + analytics)."""
```

- Create: `travel/db.py`

```python
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
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
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
```

- [ ] **Step 2: 跑測試確認綠**

```bash
python -m pytest tests/test_db.py -v
```

預期：6 個測試全綠。

### Task 1.2：bot.py 訊息儲存 hook

**Files:**
- Modify: `telegram_bot/bot.py`

- [ ] **Step 1: 加入 import + hook**

讀 `telegram_bot/bot.py`，在 `handle_line_event()` 開頭（log 之前）加入：

```python
        # [TRAVEL] 訊息儲存（非阻塞最佳努力）
        if os.getenv("TRAVEL_STORAGE_ENABLED", "true").lower() == "true":
            try:
                self._store_message(event)
            except Exception as e:
                logger.warning(f"[TRAVEL] 訊息儲存失敗（非致命）: {e}")
```

- [ ] **Step 2: 加 `_store_message` helper 到 `SassyBrain` class**

```python
    def _store_message(self, event):
        """從 LINE event 提取資料寫入 SQLite。"""
        from travel.db import insert_message  # 延遲 import 避免測試時報錯

        msg = event.message
        source = event.source

        # user_name：群組用 display_name cache，私訊用 user_id
        user_name = source.user_id
        if source.type == "group" and hasattr(self, '_display_name_cache'):
            user_name = self._display_name_cache.get(source.user_id, source.user_id)

        insert_message({
            "line_message_id": getattr(msg, 'id', None),
            "group_id": getattr(source, 'group_id', 'dm'),
            "user_id": source.user_id,
            "user_name": user_name,
            "type": getattr(msg, 'type', 'unknown'),
            "content": getattr(msg, 'text', None),
            "metadata": self._extract_message_metadata(msg),
            "reply_to_message_id": None,  # TODO Phase 2 支援回覆鏈
            "timestamp": int(getattr(msg, 'timestamp', 0)) or int(time.time() * 1000),
        })
```

- [ ] **Step 3: 加 `_extract_message_metadata` helper**

```python
    @staticmethod
    def _extract_message_metadata(msg) -> dict:
        """提取 sticker_id / package_id 等 metadata。"""
        meta = {}
        msg_type = getattr(msg, 'type', None)
        if msg_type == 'sticker':
            meta['sticker_id'] = getattr(msg, 'sticker_id', None)
            meta['package_id'] = getattr(msg, 'package_id', None)
        return meta
```

- [ ] **Step 4: 在 `__init__()` 末尾加 DB init**

```python
        # [TRAVEL] SQLite 初始化
        if os.getenv("TRAVEL_STORAGE_ENABLED", "true").lower() == "true":
            try:
                from travel.db import init_db
                init_db()
                logger.info("[TRAVEL] SQLite 已初始化")
            except Exception as e:
                logger.error(f"[TRAVEL] SQLite init 失敗: {e}")
```

- [ ] **Step 5: 確認 `import time` 已存在於 bot.py**

如果沒有就加。檢查方法：`grep "^import time" telegram_bot/bot.py` 或 `grep "^from time" telegram_bot/bot.py`。

### Task 1.3：手動驗證訊息儲存

- [ ] **Step 1: 在 worktree 啟動 bot**

```bash
cd /home/william/projects/Sassy-PTT-Bot/.worktrees/travel-extension
source ../../venv/bin/activate
# 修改 port 避免跟 main 衝突
export LINE_WEBHOOK_PORT=5001
export DB_PATH=data/chat_test.db
python telegram_bot/bot.py
```

- [ ] **Step 2: 在 LINE 群組發幾則訊息（純文字 / @bot / 貼圖 各一）**

- [ ] **Step 3: 檢查 SQLite**

```bash
sqlite3 data/chat_test.db "SELECT COUNT(*), type FROM messages GROUP BY type;"
sqlite3 data/chat_test.db "SELECT user_name, content, metadata FROM messages ORDER BY id DESC LIMIT 5;"
```

預期：所有訊息都進資料庫，貼圖的 metadata 有 `sticker_id` + `package_id`。

### Task 1.4：LLM 訊息分析器（TDD）

**Files:**
- Create: `travel/llm_analyzer.py`
- Create: `tests/test_llm_analyzer.py`

#### 1.4.1 RED

```python
"""測試 travel/llm_analyzer.py。"""
from travel.llm_analyzer import build_prompt, parse_llm_response


def test_build_prompt_includes_all_messages():
    messages = [
        {"id": 1, "user_name": "Alice", "content": "周末去墾丁", "timestamp": 1700000000000},
        {"id": 2, "user_name": "Bob", "content": "+1", "timestamp": 1700000001000},
    ]
    prompt = build_prompt(messages)
    assert "Alice" in prompt
    assert "Bob" in prompt
    assert "周末去墾丁" in prompt


def test_build_prompt_handles_none_content():
    messages = [{"id": 1, "user_name": "Alice", "content": None, "timestamp": 1700000000000}]
    prompt = build_prompt(messages)
    assert "Alice" in prompt


def test_parse_llm_response_strips_json_block():
    raw = '```json\n[{"id": 1, "is_travel_related": 1}]\n```'
    result = parse_llm_response(raw)
    assert result == [{"id": 1, "is_travel_related": 1}]


def test_parse_llm_response_handles_plain_json():
    raw = '[{"id": 1, "topics": ["travel"]}]'
    result = parse_llm_response(raw)
    assert result == [{"id": 1, "topics": ["travel"]}]


def test_parse_llm_response_raises_on_invalid():
    import pytest
    with pytest.raises(ValueError):
        parse_llm_response("not json at all")
```

- [ ] **Step 1: 確認 RED**

```bash
python -m pytest tests/test_llm_analyzer.py -v
```

預期：`ModuleNotFoundError: No module named 'travel.llm_analyzer'`。

#### 1.4.2 GREEN

**Files:**
- Create: `travel/llm_analyzer.py`

```python
"""批次 LLM 訊息分析（主題 / 情緒 / 實體 / 摘要）。

每月由 APScheduler 觸發，分析尚未標記的訊息，回填 SQLite。
"""
import json
import os
import time
from typing import Any

from openai import AsyncOpenAI

from travel.db import get_conn

PRIMARY_BASE = os.getenv("CLI_PROXY_BASE_URL", "http://localhost:8317/v1")
PRIMARY_KEY = os.getenv("CLI_PROXY_API_KEY", "")
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "gemini-3.6-flash-high")
FALLBACK_BASE = os.getenv("CGU_LLM_BASE_URL", "https://air.cgu.edu.tw/cgullmapi/v1")
FALLBACK_KEY = os.getenv("CGU_LLM_API_KEY", "")
FALLBACK_MODEL = os.getenv("CGU_LLM_MODEL", "gpt-5-mini")
BATCH_SIZE = 50

PROMPT_TEMPLATE = """分析以下 LINE 群組訊息（多則），每則輸出 JSON。
欄位：
- id（訊息 id，必須保留）
- is_travel_related（0/1，是否跟旅行 / 旅遊 / 行程相關）
- topics（陣列，從這幾個選：travel/food/work/chat/joke/other）
- sentiment（-1 ~ 1，-1 極負面、0 中性、1 極正面）
- locations（地點陣列，可空陣列）
- summary（一句話中文摘要，可空字串）

只輸出合法 JSON 陣列，不要 ```json 包裹。

訊息：
{messages}

JSON："""


def build_prompt(messages: list[dict]) -> str:
    """組 LLM prompt：多則訊息一次分析。"""
    lines = []
    for m in messages:
        ts = time.strftime("%Y-%m-%d", time.localtime(m["timestamp"] / 1000))
        content = m.get("content") or "(non-text)"
        lines.append(f"id={m['id']} [{ts}] {m.get('user_name', '?')}: {content}")
    return PROMPT_TEMPLATE.format(messages="\n".join(lines))


def parse_llm_response(raw: str) -> list[dict[str, Any]]:
    """解析 LLM 回傳為 JSON 陣列。處理 ```json ... ``` 包裹。"""
    s = raw.strip()
    if s.startswith("```"):
        # 去掉開頭 ```json 或 ```
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
        s = s.strip().rstrip("`").strip()
    data = json.loads(s)
    if not isinstance(data, list):
        raise ValueError(f"預期 JSON 陣列，收到 {type(data).__name__}")
    return data


async def analyze_batch(messages: list[dict]) -> list[dict]:
    """呼叫 LLM 分析一批訊息，回傳結構化結果。"""
    prompt = build_prompt(messages)
    last_err = None

    # 先試 Primary
    try:
        client = AsyncOpenAI(base_url=PRIMARY_BASE, api_key=PRIMARY_KEY)
        resp = await client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_completion_tokens=2000,
        )
        return parse_llm_response(resp.choices[0].message.content)
    except Exception as e:
        last_err = e

    # Fallback
    if FALLBACK_KEY:
        client = AsyncOpenAI(base_url=FALLBACK_BASE, api_key=FALLBACK_KEY)
        resp = await client.chat.completions.create(
            model=FALLBACK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_completion_tokens=2000,
        )
        return parse_llm_response(resp.choices[0].message.content)

    raise RuntimeError(f"LLM 全部失敗: {last_err}")


def run_monthly_analysis():
    """主流程：撈未分析訊息 → 批次分析 → 回填 DB。"""
    import asyncio

    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, user_name, content, timestamp
               FROM messages
               WHERE analyzed_at IS NULL
                 AND content IS NOT NULL
                 AND type = 'text'
                 AND length(content) > 1
               ORDER BY timestamp ASC
               LIMIT ?""",
            (BATCH_SIZE,),
        ).fetchall()

    if not rows:
        print("[ANALYZER] 沒有未分析的訊息")
        return

    messages = [dict(r) for r in rows]
    try:
        results = asyncio.run(analyze_batch(messages))
    except Exception as e:
        print(f"[ANALYZER] LLM 失敗：{e}")
        return

    now = int(time.time())
    updated = 0
    with get_conn() as conn:
        for r in results:
            if "id" not in r:
                continue
            conn.execute(
                """UPDATE messages
                   SET is_travel_related=?, topics=?, sentiment=?,
                       locations=?, summary=?, analyzed_at=?
                   WHERE id=?""",
                (
                    r.get("is_travel_related", 0),
                    json.dumps(r.get("topics", []), ensure_ascii=False),
                    r.get("sentiment", 0.0),
                    json.dumps(r.get("locations", []), ensure_ascii=False),
                    r.get("summary", ""),
                    now,
                    r["id"],
                ),
            )
            updated += 1
    print(f"[ANALYZER] 完成 {updated} 則分析（輸入 {len(messages)} 則）")


if __name__ == "__main__":
    run_monthly_analysis()
```

- [ ] **Step 2: 跑測試確認綠**

```bash
python -m pytest tests/test_llm_analyzer.py -v
```

預期：5 個測試全綠。

#### 1.4.3 REFACTOR

抽出常數、簡化 if 邏輯（若有必要）。**注意不要改行為**，只改結構。

### Task 1.5：統計聚合器（TDD）

**Files:**
- Create: `travel/aggregator.py`
- Create: `tests/test_aggregator.py`

#### 1.5.1 RED

```python
"""測試 travel/aggregator.py。"""
import os
import tempfile
import time
import pytest
from travel.db import init_db, insert_message, get_conn
from travel.aggregator import aggregate_daily, aggregate_lifetime


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


def _seed(temp_db):
    init_db()
    today = time.strftime("%Y-%m-%d")
    now_ms = int(time.time() * 1000)
    for i, t in enumerate(["text", "text", "sticker", "image"]):
        insert_message({
            "line_message_id": f"m{i}",
            "group_id": "C1",
            "user_id": "U1",
            "user_name": "Alice",
            "type": t,
            "content": "msg" if t == "text" else None,
            "metadata": {},
            "reply_to_message_id": None,
            "timestamp": now_ms,
        })
    return today


def test_aggregate_daily_counts_per_type(temp_db):
    today = _seed(temp_db)
    aggregate_daily()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM daily_user_stats WHERE date=?", (today,)
        ).fetchone()
    assert row["text_count"] == 2
    assert row["sticker_count"] == 1
    assert row["image_count"] == 1


def test_aggregate_lifetime_computes_totals(temp_db):
    _seed(temp_db)
    aggregate_lifetime()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM user_lifetime_stats WHERE user_id='U1'"
        ).fetchone()
    assert row["total_messages"] == 4
```

- [ ] **Step 1: 確認 RED**

```bash
python -m pytest tests/test_aggregator.py -v
```

#### 1.5.2 GREEN

**Files:**
- Create: `travel/aggregator.py`

```python
"""每日 / 終身統計聚合。"""
import json
import time

from travel.db import get_conn


def aggregate_daily(date_str: str | None = None):
    """聚合指定日期（預設今天）的訊息統計到 daily_user_stats。"""
    date_str = date_str or time.strftime("%Y-%m-%d")
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT user_id, group_id,
                      SUM(CASE WHEN type='text' THEN 1 ELSE 0 END) AS text_count,
                      SUM(CASE WHEN type='sticker' THEN 1 ELSE 0 END) AS sticker_count,
                      SUM(CASE WHEN type='image' THEN 1 ELSE 0 END) AS image_count,
                      SUM(CASE WHEN is_travel_related=1 THEN 1 ELSE 0 END) AS travel_mentions
               FROM messages
               WHERE date(timestamp/1000, 'unixepoch') = ?
               GROUP BY user_id, group_id""",
            (date_str,),
        ).fetchall()
        for r in rows:
            conn.execute(
                """INSERT OR REPLACE INTO daily_user_stats
                   (date, user_id, group_id, text_count, sticker_count,
                    image_count, travel_mention_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (date_str, r["user_id"], r["group_id"],
                 r["text_count"] or 0, r["sticker_count"] or 0,
                 r["image_count"] or 0, r["travel_mentions"] or 0),
            )
    return len(rows)


def aggregate_lifetime():
    """聚合每位使用者的終身統計到 user_lifetime_stats。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT m.user_id, m.group_id,
                      COUNT(*) AS total,
                      MIN(m.timestamp) AS first_seen,
                      MAX(m.timestamp) AS last_seen,
                      (SELECT COUNT(DISTINCT trip_id) FROM trip_participants tp
                       WHERE tp.user_id = m.user_id) AS total_trips
               FROM messages m
               GROUP BY m.user_id, m.group_id"""
        ).fetchall()
        for r in rows:
            # 抓常用 locations
            loc_rows = conn.execute(
                """SELECT locations FROM messages
                   WHERE user_id=? AND locations IS NOT NULL
                     AND locations != '[]'""",
                (r["user_id"],),
            ).fetchall()
            loc_counter: dict[str, int] = {}
            for lr in loc_rows:
                try:
                    locs = json.loads(lr["locations"])
                except (json.JSONDecodeError, TypeError):
                    continue
                for loc in locs:
                    loc_counter[loc] = loc_counter.get(loc, 0) + 1
            top_locs = sorted(loc_counter, key=lambda x: -loc_counter[x])[:5]

            conn.execute(
                """INSERT OR REPLACE INTO user_lifetime_stats
                   (user_id, group_id, total_messages, total_trips,
                    first_seen, last_seen, favorite_locations)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (r["user_id"], r["group_id"], r["total"] or 0,
                 r["total_trips"] or 0, r["first_seen"], r["last_seen"],
                 json.dumps(top_locs, ensure_ascii=False)),
            )
    return len(rows)


def run_daily_aggregation():
    """每日聚合（被 APScheduler 觸發）。"""
    n1 = aggregate_daily()
    n2 = aggregate_lifetime()
    print(f"[AGGREGATOR] daily={n1}, lifetime={n2}")


if __name__ == "__main__":
    run_daily_aggregation()
```

- [ ] **Step 2: 跑測試確認綠**

```bash
python -m pytest tests/test_aggregator.py -v
```

### Task 1.6：CLI 統計檢視工具

**Files:**
- Create: `scripts/show_stats.py`

```python
"""CLI 工具：查看 SQLite 統計。

用法：
    python scripts/show_stats.py overview
    python scripts/show_stats.py user <user_id>
    python scripts/show_stats.py top-users
    python scripts/show_stats.py topics
    python scripts/show_stats.py travel
"""
import json
import sys

from travel.db import get_conn


def overview():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT type, COUNT(*) AS count
            FROM messages
            GROUP BY type
            ORDER BY count DESC
        """).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        analyzed = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE analyzed_at IS NOT NULL"
        ).fetchone()[0]
        travel = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE is_travel_related=1"
        ).fetchone()[0]
    print(f"總訊息：{total}")
    print(f"已分析：{analyzed}")
    print(f"旅行相關：{travel}")
    print("---")
    for r in rows:
        print(f"  {r['type']}: {r['count']}")


def user_stats(user_id: str):
    with get_conn() as conn:
        msgs = conn.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN type='sticker' THEN 1 ELSE 0 END) AS stickers,
                   SUM(CASE WHEN type='image' THEN 1 ELSE 0 END) AS images,
                   SUM(CASE WHEN is_travel_related=1 THEN 1 ELSE 0 END) AS travel
            FROM messages WHERE user_id=?
        """, (user_id,)).fetchone()
        lifetime = conn.execute(
            "SELECT * FROM user_lifetime_stats WHERE user_id=?",
            (user_id,),
        ).fetchone()
        last_5 = conn.execute("""
            SELECT timestamp, type, content
            FROM messages WHERE user_id=?
            ORDER BY timestamp DESC LIMIT 5
        """, (user_id,)).fetchall()
    print(f"使用者 {user_id}")
    print(f"  總訊息: {msgs['total'] or 0}")
    print(f"  貼圖: {msgs['stickers'] or 0}")
    print(f"  圖片: {msgs['images'] or 0}")
    print(f"  旅行相關: {msgs['travel'] or 0}")
    if lifetime:
        locs = json.loads(lifetime["favorite_locations"] or "[]")
        print(f"  常用地點: {', '.join(locs) if locs else '(無)'}")
    print("--- 最近 5 則 ---")
    for m in last_5:
        ts = m['timestamp']
        c = (m['content'] or '')[:40]
        print(f"  [{ts}] {m['type']}: {c}")


def top_users():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT user_name, COUNT(*) AS total
            FROM messages
            WHERE user_name IS NOT NULL
            GROUP BY user_name
            ORDER BY total DESC
            LIMIT 10
        """).fetchall()
    print("Top 10 話癆：")
    for i, r in enumerate(rows, 1):
        print(f"  {i:2d}. {r['user_name']}: {r['total']}")


def topic_distribution():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT topics FROM messages
            WHERE topics IS NOT NULL AND topics != '[]'
        """).fetchall()
    counter: dict[str, int] = {}
    for r in rows:
        try:
            topics = json.loads(r["topics"])
        except (json.JSONDecodeError, TypeError):
            continue
        for t in topics:
            counter[t] = counter.get(t, 0) + 1
    print("主題分佈（僅已分析訊息）：")
    for topic, count in sorted(counter.items(), key=lambda x: -x[1]):
        print(f"  {topic}: {count}")


def travel_related():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT user_name, COUNT(*) AS count
            FROM messages
            WHERE is_travel_related=1 AND user_name IS NOT NULL
            GROUP BY user_name
            ORDER BY count DESC
        """).fetchall()
    print("旅行相關訊息排行：")
    for i, r in enumerate(rows, 1):
        print(f"  {i:2d}. {r['user_name']}: {r['count']}")


COMMANDS = {
    "overview": overview,
    "user": user_stats,
    "top-users": top_users,
    "topics": topic_distribution,
    "travel": travel_related,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print("\n可用指令:", ", ".join(COMMANDS.keys()))
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "user":
        if len(sys.argv) < 3:
            print("用法: python scripts/show_stats.py user <user_id>")
            sys.exit(1)
        COMMANDS[cmd](sys.argv[2])
    else:
        COMMANDS[cmd]()


if __name__ == "__main__":
    main()
```

- [ ] **Step 1: 跑各個指令驗證**

```bash
cd /home/william/projects/Sassy-PTT-Bot/.worktrees/travel-extension
source ../../venv/bin/activate
python scripts/show_stats.py overview
python scripts/show_stats.py top-users
python scripts/show_stats.py topics
python scripts/show_stats.py travel
```

### Task 1.7：APScheduler 整合

**Files:**
- Modify: `telegram_bot/bot.py`

- [ ] **Step 1: 加 import**

```python
from travel.llm_analyzer import run_monthly_analysis
from travel.aggregator import run_daily_aggregation
```

- [ ] **Step 2: 在既有 graduation_countdown job 之後加兩個新 job**

```python
            # 每月 1 號 03:00 訊息 LLM 分析
            self._scheduler.add_job(
                run_monthly_analysis,
                trigger='cron',
                day=1,
                hour=3,
                minute=0,
                id='monthly_llm_analysis',
            )
            logger.info("[ANALYZER] 每月 1 號 03:00 LLM 分析排程已啟動")

            # 每日 04:00 統計聚合
            self._scheduler.add_job(
                run_daily_aggregation,
                trigger='cron',
                hour=4,
                minute=0,
                id='daily_aggregation',
            )
            logger.info("[AGGREGATOR] 每日 04:00 聚合排程已啟動")
```

### Task 1.8：Backfill 驗證流程

- [ ] **Step 1: 啟動 bot 一週**

讓 webhook 自然累積訊息到 `data/chat_test.db`。

- [ ] **Step 2: 手動觸發 LLM 分析 backfill**

```bash
while true; do
  source ../../venv/bin/activate
  python -c "from travel.llm_analyzer import run_monthly_analysis; run_monthly_analysis()"
  REMAINING=$(sqlite3 data/chat_test.db "SELECT COUNT(*) FROM messages WHERE analyzed_at IS NULL AND type='text'")
  echo "剩餘未分析：$REMAINING"
  [ "$REMAINING" = "0" ] && break
  sleep 2
done
```

- [ ] **Step 3: 手動觸發聚合**

```bash
python -c "from travel.aggregator import run_daily_aggregation; run_daily_aggregation()"
```

- [ ] **Step 4: 用 CLI 看統計**

```bash
python scripts/show_stats.py overview
python scripts/show_stats.py top-users
python scripts/show_stats.py topics
python scripts/show_stats.py travel
```

預期：能看到有意義的數字（非全 0）。

---

## Phase 2：徽章系統 + 網頁（之後另開計畫，本檔先列大綱）

**目標：** 旅行 CRUD + 徽章生成 + LIFF 網頁。

**待辦項目（細節之後寫）：**
- [ ] 母徽章生成（ComfyUI 一次性）
- [ ] fal.ai Kontext 客戶端
- [ ] 管理員指令（建立旅行 / 加人 / 結束 / 生成徽章）
- [ ] 權限分級（管理員 / 參與者 / guest）
- [ ] Flask Blueprint LIFF API
- [ ] Vite + Vue 3 + Tailwind 前端
- [ ] LINE Developers 建 LIFF App
- [ ] 部署 ngrok 公開 URL
- [ ] 排程：旅行結束自動觸發徽章生成

**之後做 Phase 2 前，先完成 Phase 1 並 merge 回 main。**

---

## 備份策略

### Backup.1：本地 hot 備份（Gitignored 已存在）

`data/` 整個目錄已 gitignored，無需額外設定。

### Backup.2：每日 SQLite 熱備份腳本（之後再加）

> Phase 1 不急，本機 SSD + gitignore 已足夠防呆。

Phase 2 之前再補：
- `scripts/backup.sh` + cron
- `scripts/export_parquet.py`（Phase 2 之後）

---

## 驗證清單（Phase 1 完成時勾選）

- [ ] `pytest tests/ -v` 全綠
- [ ] bot 啟動 log 出現 `[TRAVEL] SQLite 已初始化`
- [ ] LINE 群組發訊息後 `data/chat_test.db` 有新 row
- [ ] 貼圖的 `metadata` JSON 含 `sticker_id` + `package_id`
- [ ] `python scripts/show_stats.py overview` 有合理數字
- [ ] `python -c "from travel.llm_analyzer import run_monthly_analysis; ..."` 成功跑完
- [ ] `python -c "from travel.aggregator import run_daily_aggregation; ..."` 成功跑完
- [ ] APScheduler log 出現 `[ANALYZER] 每月 1 號 03:00 ...` + `[AGGREGATOR] 每日 04:00 ...`

---

## 開放問題（Phase 2 才處理）

1. 聊天記錄容量爆炸？目前估算 330MB / 10 年，暫不擔心。
2. 管理員名單動態化？寫在 `.env` 即可。
3. 多語言？目前只處理中文。
4. 圖片 / 影片歷史調用？只計數，不拉舊檔。
5. 徽章稀有度邏輯（Phase 8 概念）。
6. 使用者個資刪除請求 — 不做。