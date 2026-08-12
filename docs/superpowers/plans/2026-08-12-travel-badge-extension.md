# Travel Badge Extension — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把現有的 Sassy PTT Bot 擴展為 LINE 群組旅遊回顧系統：管理員登記旅行 → AI 生成風格一致的徽章 → LIFF 頁面展示個人 / 群組統計 + 徽章牆 → 定期 LLM 分析群組訊息（主題、情緒、實體、摘要）豐富回顧內容。

**Architecture:**

```
LINE Webhook (既有 Flask @ :5000)
    │
    ├── 觸發判定（既有 PTT 風格回應邏輯）
    │
    ├── 管理員指令解析（新）
    │   ├── 建立旅行 / 結束旅行 / 生成徽章
    │   └── 統計 / 我的徽章 → 回 LIFF URL（Flex Message）
    │
    ├── 訊息儲存（新）
    │   └── 全部訊息 → SQLite (data/chat.db)
    │
    └── APScheduler（既有）
        ├── 每日 09:00  畢業倒數（既有）
        ├── 每月 1 號 03:00  LLM 訊息分析（新）
        └── 每日 04:00  統計聚合（新）

LIFF 前端（Vite + Vue 3 + Tailwind，RWD）
    ├── 首頁：個人徽章牆
    ├── 旅行詳情：徽章 + 參與者 + 訊息摘要
    └── 統計儀表板：Chart.js 圖表

fal.ai Kontext API：執行期生圖（無 GPU 也能跑）
ComfyUI（一次性）：在這台機器生 4 張母徽章當風格參考
```

**Tech Stack 新增:**
- `fal-client` — fal.ai SDK
- `pyarrow` — Parquet 匯出
- `pandas`（已有就跳過）— 訊息分析彙整
- 前端：Vite + Vue 3 + Tailwind CSS + Chart.js + LIFF SDK

---

## Design Decisions（已確定，避免遺忘）

| 項目 | 決策 |
|---|---|
| 部署主機 | 這台（有 GPU） |
| 對外 HTTPS | 沿用 `ngrok.yml`（之後仍用它） |
| LIFF 框架 | Vite + Vue 3 + Tailwind CSS |
| LIFF RWD | ✅ 必做（手機優先） |
| LIFF 權限分級 | ✅ 必做（管理員 / 參與者 / 一般） |
| 訊息永久保存 | ✅ 永久保留（不限期限） |
| 圖片 / 影片 | 只存類型計數，不存 message_id（LINE 只保留幾天） |
| 貼圖 | 存 `sticker_id` + `package_id`（可統計角色） |
| `user_id` | 存真實 LINE user_id |
| Opt-out 機制 | 暫不做 |
| 旅行參與者 | 管理員手動登記 |
| 徽章稀有度 | **Phase 8 再實作，本計畫先跳過** |
| LLM provider | gemini-3.6-flash-high（既有 Primary）+ gpt-5-mini（既有 Fallback） |
| LLM 分析頻率 | 每月 1 號 03:00（最短月、最長年） |
| LLM 分析類型 | 主題 + 情緒 + 實體（地點、日期）+ 摘要（全做） |
| 母徽章生成 | 這台跑 ComfyUI（一次性） |
| 執行期生圖 | fal.ai Kontext API |
| 徽章觸發 | 管理員在 LINE 群組下指令 |

---

## File Map

| 動作 | 路徑 | 說明 |
|------|------|------|
| Create | `travel/__init__.py` | 模組入口 |
| Create | `travel/db.py` | SQLite 連線 + schema + CRUD |
| Create | `travel/models.py` | Trip / Badge / Message dataclass |
| Create | `travel/llm_analyzer.py` | 批次 LLM 分析（Gemini / GPT-mini） |
| Create | `travel/badge_generator.py` | fal.ai Kontext 客戶端 |
| Create | `travel/aggregator.py` | 每日 / 每月統計聚合 |
| Create | `travel/routes_liff.py` | LIFF 後端 API（Flask Blueprint） |
| Create | `travel/admin_commands.py` | 解析管理員指令 |
| Create | `travel/permissions.py` | 權限分級邏輯 |
| Create | `liff/index.html` | LIFF 首頁 |
| Create | `liff/trip_detail.html` | 旅行詳情 |
| Create | `liff/stats.html` | 統計儀表板 |
| Create | `liff/package.json` | Vite + Vue 3 + Tailwind |
| Create | `liff/vite.config.js` |  |
| Create | `liff/src/main.js` | LIFF init + Vue app |
| Create | `liff/src/App.vue` | 根元件 + router |
| Create | `liff/src/views/Home.vue` | 徽章牆 |
| Create | `liff/src/views/TripDetail.vue` | 旅行詳情 |
| Create | `liff/src/views/Stats.vue` | 統計圖表 |
| Create | `liff/src/api.js` | 後端 fetch wrapper |
| Create | `data/masters/README.md` | 母徽章 metadata |
| Create | `scripts/backup.sh` | 每日 cron 備份 |
| Create | `scripts/export_parquet.py` | 每月 Parquet 匯出 |
| Create | `scripts/gen_master_badges.md` | ComfyUI 生圖 SOP |
| Modify | `telegram_bot/bot.py` | 加訊息儲存 hook + 管理員指令 + APScheduler jobs |
| Modify | `.env` | 加 FAL_KEY、LIFF_ID、ADMIN_USER_IDS、DB_PATH 等 |
| Modify | `requirements.txt` | 加 fal-client、pyarrow |

---

## Phase 0：環境準備（一次性）

### Task 0.1：安裝新依賴

**Files:**
- Modify: `requirements.txt`
- Run in: `/home/william/projects/Sassy-PTT-Bot/`

- [ ] **Step 1: 啟動 venv 安裝套件**

```bash
cd /home/william/projects/Sassy-PTT-Bot
source venv/bin/activate
pip install fal-client pyarrow
pip freeze | grep -E "^(fal-client|pyarrow)=" >> requirements.txt
```

- [ ] **Step 2: 確認可 import**

```bash
python -c "import fal_client; import pyarrow; print('OK')"
```

預期：`OK`

### Task 0.2：環境變數設定

**Files:**
- Modify: `.env`

- [ ] **Step 1: 在 `.env` 末尾加入新變數**

```env
# fal.ai 執行期生圖
FAL_KEY=your_fal_api_key_here

# LIFF（之後在 LINE Developers 建 LIFF App 後填入）
LIFF_ID_HOME=
LIFF_ID_TRIP=
LIFF_ID_STATS=

# 管理員 user_id（多個用逗號分隔）
ADMIN_USER_IDS=Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# SQLite 路徑
DB_PATH=data/chat.db

# 徽章母版路徑
BADGES_DIR=data/badges
MASTERS_DIR=data/masters
```

- [ ] **Step 2: 從 fal.ai dashboard 取得 API key 填入 `FAL_KEY`**

### Task 0.3：建立目錄結構

**Files:**
- Create: 多個目錄

- [ ] **Step 1: 建立新模組目錄**

```bash
cd /home/william/projects/Sassy-PTT-Bot
mkdir -p travel liff/src/views liff/src/assets data/badges data/masters scripts docs/superpowers/specs
```

- [ ] **Step 2: 建立 `travel/__init__.py`**

```python
"""Travel badge extension for Sassy PTT Bot."""
```

- [ ] **Step 3: 建立 `liff/.gitkeep`（之後放 build 產物）**

```bash
touch liff/.gitkeep
```

---

## Phase 1：訊息儲存（最小驗證）

**目標：** 跑一週驗證所有 LINE 群組訊息正確累積到 SQLite，**完全不改既有 PTT 回應邏輯**。

### Task 1.1：建立 SQLite schema

**Files:**
- Create: `travel/db.py`

- [ ] **Step 1: 建立 `travel/db.py` 雛型**

```python
"""SQLite 連線、schema、CRUD。"""
import os
import sqlite3
import json
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
    metadata JSON,
    reply_to_message_id TEXT,
    timestamp INTEGER NOT NULL,
    is_deleted INTEGER DEFAULT 0,
    is_travel_related INTEGER,
    topics JSON,
    sentiment REAL,
    locations JSON,
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
CREATE INDEX IF NOT EXISTS idx_trips_status ON trips(status);

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
    favorite_locations JSON,
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
    """Insert message, return False if duplicate (line_message_id conflict)."""
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

- [ ] **Step 2: 初始化 DB 並驗證**

```bash
cd /home/william/projects/Sassy-PTT-Bot
source venv/bin/activate
python -c "from travel.db import init_db; init_db(); print('OK')"
sqlite3 data/chat.db ".schema messages" | head -20
```

預期看到 `messages` 表建立成功，schema 正確。

### Task 1.2：在 bot.py 加訊息儲存 hook

**Files:**
- Modify: `telegram_bot/bot.py`（`handle_line_event()` 內）

> 先讀 `telegram_bot/bot.py` 找出 `handle_line_event` 的完整簽名，定位插入點。

- [ ] **Step 1: 加入 import**

在檔案頂部 import 區加入：

```python
from travel.db import init_db, insert_message
```

- [ ] **Step 2: 在 `__init__()` 末尾（既有 scheduler 設定之後）初始化 DB**

找到 `logger.info("LINE Bot 已啟用")` 之後的區塊，加入：

```python
        # 訊息儲存初始化
        init_db()
        logger.info("[TRAVEL] SQLite 已初始化")
```

- [ ] **Step 3: 在 `handle_line_event()` 開頭加儲存 hook**

> 找到方法簽名後，在函式本體開頭（log 之前）加入：

```python
        # 訊息儲存（非阻塞最佳努力）
        try:
            user_name = getattr(event.source, 'user_id', 'unknown')
            if event.source.type == "group":
                # 從既有 cache 取 display_name（既有邏輯已有 lazy fetch）
                user_name = self._display_name_cache.get(
                    event.source.user_id, event.source.user_id
                )
            insert_message({
                "line_message_id": getattr(event.message, 'id', None),
                "group_id": getattr(event.source, 'group_id', 'dm'),
                "user_id": event.source.user_id,
                "user_name": user_name,
                "type": getattr(event.message, 'type', 'unknown'),
                "content": getattr(event.message, 'text', None),
                "metadata": {},  # 之後 Phase 1.4 補上 sticker_id 等
                "reply_to_message_id": None,
                "timestamp": int(getattr(event.message, 'timestamp', 0)) or int(
                    __import__('time').time() * 1000
                ),
            })
        except Exception as e:
            logger.warning(f"[TRAVEL] 訊息儲存失敗（非致命）: {e}")
```

> **注意：** 若 `handle_line_event` 已有相同的 user_name 計算邏輯，重用既有變數避免重複 fetch。

### Task 1.3：手動驗證訊息儲存

**Files:**
- Run in: `/home/william/projects/Sassy-PTT-Bot/`

- [ ] **Step 1: 重啟 bot**

```bash
source venv/bin/activate
python telegram_bot/bot.py
```

- [ ] **Step 2: 在 LINE 群組發幾則訊息（純文字、@bot、貼圖各一）**

- [ ] **Step 3: 檢查 SQLite**

```bash
sqlite3 data/chat.db "SELECT COUNT(*), type FROM messages GROUP BY type;"
sqlite3 data/chat.db "SELECT user_name, content FROM messages ORDER BY id DESC LIMIT 5;"
```

預期：所有訊息（含 bot 回應）都進資料庫，user_name 正確。

### Task 1.4：補上貼圖 / 圖片 metadata

**Files:**
- Modify: `telegram_bot/bot.py`（Task 1.2 Step 3 的 metadata 區塊）

- [ ] **Step 1: 擴展 metadata 提取**

把 Task 1.2 Step 3 的 `metadata: {}` 改成：

```python
                "metadata": self._extract_message_metadata(event.message),
```

- [ ] **Step 2: 在 `SassyBrain` class 內加入 helper**

```python
    @staticmethod
    def _extract_message_metadata(msg) -> dict:
        """提取 sticker_id / package_id 等 metadata。"""
        meta = {}
        if getattr(msg, 'type', None) == 'sticker':
            meta['sticker_id'] = getattr(msg, 'sticker_id', None)
            meta['package_id'] = getattr(msg, 'package_id', None)
        return meta
```

- [ ] **Step 3: 重啟 bot，發貼圖，驗證**

```bash
sqlite3 data/chat.db "SELECT metadata FROM messages WHERE type='sticker' LIMIT 3;"
```

預期：metadata 欄含 `sticker_id` + `package_id`。

---

## Phase 2：旅行 CRUD（管理員指令）

**目標：** 管理員在 LINE 群組用指令建立 / 結束旅行，資料進 SQLite。

### Task 2.1：管理員判定工具

**Files:**
- Create: `travel/permissions.py`

- [ ] **Step 1: 建立 `permissions.py`**

```python
"""權限分級邏輯：管理員 / 參與者 / 一般。"""
import os
import sqlite3
from travel.db import get_conn

ADMIN_USER_IDS = {
    uid.strip()
    for uid in os.getenv("ADMIN_USER_IDS", "").split(",")
    if uid.strip()
}


def is_admin(user_id: str) -> bool:
    return user_id in ADMIN_USER_IDS


def is_trip_participant(trip_id: str, user_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM trip_participants WHERE trip_id=? AND user_id=?",
            (trip_id, user_id),
        ).fetchone()
    return row is not None


def get_role(trip_id: str | None, user_id: str) -> str:
    """回傳 'admin' / 'participant' / 'guest'。"""
    if is_admin(user_id):
        return "admin"
    if trip_id and is_trip_participant(trip_id, user_id):
        return "participant"
    return "guest"
```

### Task 2.2：管理員指令解析

**Files:**
- Create: `travel/admin_commands.py`

- [ ] **Step 1: 建立 `admin_commands.py`**

```python
"""解析管理員指令，回傳動作 handler 或 None。"""
import re
import uuid
from datetime import datetime
from travel.db import get_conn
from travel.permissions import is_admin

CMD_PATTERN = re.compile(r"@bot\s+(\S+)\s*(.*)")


def parse_command(text: str) -> tuple[str, str] | None:
    """回傳 (action, args) 或 None。"""
    m = CMD_PATTERN.match(text.strip())
    if not m:
        return None
    return m.group(1), m.group(2).strip()


def handle_create_trip(args: str, user_id: str, group_id: str) -> str:
    """建立旅行。Args 格式：標題=<標題> 地點=<地點> 開始=<YYYY-MM-DD> 結束=<YYYY-MM-DD>"""
    if not is_admin(user_id):
        return "你不是管理員，別亂搞。"
    params = dict(re.findall(r"(\S+)=(\S+)", args))
    if not params.get("標題"):
        return "格式：@bot 建立旅行 標題=<標題> 地點=<地點> 開始=YYYY-MM-DD 結束=YYYY-MM-DD"

    trip_id = str(uuid.uuid4())[:8]
    try:
        start_ts = int(datetime.fromisoformat(params["開始"]).timestamp()) if "開始" in params else None
        end_ts = int(datetime.fromisoformat(params["結束"]).timestamp()) if "結束" in params else None
    except ValueError:
        return "日期格式錯誤，要 YYYY-MM-DD"

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO trips
               (id, group_id, title, location, start_date, end_date,
                trip_type, created_by, created_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'planning')""",
            (
                trip_id, group_id, params["標題"], params.get("地點"),
                start_ts, end_ts, params.get("類型", "other"),
                user_id, int(datetime.now().timestamp()),
            ),
        )
    return f"✅ 旅行 #{trip_id}「{params['標題']}」已建立。\n用 @bot 加人 #{trip_id} <user_id 或名稱> 來登記參與者。"


def handle_end_trip(args: str, user_id: str) -> str:
    if not is_admin(user_id):
        return "你不是管理員。"
    trip_id = args.strip().lstrip("#")
    with get_conn() as conn:
        conn.execute(
            "UPDATE trips SET status='completed' WHERE id=?",
            (trip_id,),
        )
    return f"✅ 旅行 #{trip_id} 已標記完成。\n用 @bot 生成徽章 #{trip_id} 來生圖。"


COMMANDS = {
    "建立旅行": handle_create_trip,
    "結束旅行": handle_end_trip,
}


def dispatch(action: str, args: str, user_id: str, group_id: str) -> str | None:
    handler = COMMANDS.get(action)
    if not handler:
        return None
    return handler(args, user_id, group_id)
```

### Task 2.3：掛上指令 dispatcher

**Files:**
- Modify: `telegram_bot/bot.py`

- [ ] **Step 1: 加 import**

```python
from travel.admin_commands import parse_command, dispatch
```

- [ ] **Step 2: 在 `handle_line_event()` 內，偵測到 @bot 且 `is_mentioned=True` 時**

> 找到既有 `if is_mentioned:` 區塊，在裡面加：

```python
        # 管理員指令（優先於 PTT 回應邏輯）
        cmd_result = None
        parsed = parse_command(clean_text)
        if parsed:
            action, args = parsed
            cmd_result = dispatch(action, args, event.source.user_id, getattr(event.source, 'group_id', 'dm'))
        if cmd_result:
            self.line_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[LineTextMessage(text=cmd_result)],
                )
            )
            return  # 不進入 PTT 回應邏輯
```

### Task 2.4：實測旅行 CRUD

- [ ] **Step 1: 重啟 bot**

- [ ] **Step 2: 在群組測試指令**

```
@bot 建立旅行 標題=墾丁三日 地點=墾丁 開始=2026-09-01 結束=2026-09-03
@bot 結束旅行 #<trip_id>
```

- [ ] **Step 3: 驗證 DB**

```bash
sqlite3 data/chat.db "SELECT id, title, status FROM trips;"
```

預期：兩筆資料都正確。

---

## Phase 3：母徽章生成（一次性，ComfyUI）

**目標：** 用 ComfyUI 生成 4 張母徽章當風格參考。

### Task 3.1：ComfyUI SOP 文件

**Files:**
- Create: `scripts/gen_master_badges.md`

- [ ] **Step 1: 寫 SOP**

```markdown
# 母徽章生成 SOP（一次性）

## 工具
- ComfyUI（這台已有）
- 模型：Flux / SDXL（看哪個效果好）

## 母徽章清單（4 張）

存到 `data/masters/`：

1. `common_base.png` — 普通（簡潔線條）
2. `rare_base.png` — 稀有（金邊 + 星光）
3. `epic_base.png` — 史詩（立體浮雕感）
4. `legendary_base.png` — 傳說（動態光效）

## Prompt 模板
```
flat design travel badge, centered composition, circular shape,
pastel colors with gold accents, thin gold border,
featuring [generic travel motif like compass/suitcase],
high quality, detailed, vector style
```

## 注意事項（給 fal.ai Kontext 用）
- ✅ 主體輪廓清晰
- ✅ 配色用色塊（避免漸層）
- ❌ 避免細小文字（Kontext 會糊）
- ❌ 避免複雜背景紋理

## 驗證
生完後人工挑 1 張最滿意的當 `common_base.png`，其餘 3 張依稀有度風格變化。

## 設定檔
把 prompt + seed + 設定值寫到 `data/masters/metadata.json`：
```json
{
  "common_base.png": {"prompt": "...", "seed": 12345, "model": "flux-dev"},
  "rare_base.png": {...}
}
```
```

- [ ] **Step 2: 在這台機器用 ComfyUI 跑一次，產生 4 張**

（手動執行，記錄步驟在 SOP）

### Task 3.2：建立 metadata 索引

**Files:**
- Create: `data/masters/metadata.json`（手動填入）

```json
{
  "common_base.png": {
    "prompt": "...",
    "seed": 12345,
    "model": "flux-dev",
    "rarity": "common"
  },
  "rare_base.png": {...}
}
```

---

## Phase 4：fal.ai 徽章生成

**目標：** 管理員下 `@bot 生成徽章 #<trip_id>`，呼叫 fal.ai Kontext，圖存本地，push 到群組。

### Task 4.1：fal.ai 客戶端

**Files:**
- Create: `travel/badge_generator.py`

- [ ] **Step 1: 安裝與測試連線**

```bash
source venv/bin/activate
python -c "import fal_client; fal_client.subscribe('fal-ai/flux-kontext', arguments={'prompt': 'test'}, with_logs=True)"
```

確認 API key 可用。

- [ ] **Step 2: 建立 `badge_generator.py`**

```python
"""fal.ai Kontext 徽章生成。"""
import os
import uuid
from pathlib import Path

import fal_client

MASTERS_DIR = Path(os.getenv("MASTERS_DIR", "data/masters"))
BADGES_DIR = Path(os.getenv("BADGES_DIR", "data/badges"))


def generate_badge(
    trip_title: str,
    trip_location: str,
    trip_type: str,
    rarity: str = "common",
    master_filename: str = "common_base.png",
) -> str:
    """生成徽章，回傳 image_path。"""
    os.environ["FAL_KEY"] = os.getenv("FAL_KEY", "")

    master_path = MASTERS_DIR / master_filename
    if not master_path.exists():
        raise FileNotFoundError(f"母徽章不存在：{master_path}")

    prompt = (
        f"travel badge for {trip_location}, "
        f"{trip_type} theme, {rarity} rarity style, "
        f"flat design, centered composition, "
        f"high quality, detailed"
    )

    BADGES_DIR.mkdir(parents=True, exist_ok=True)
    output_filename = f"{uuid.uuid4().hex[:12]}.png"
    output_path = BADGES_DIR / output_filename

    with open(master_path, "rb") as f:
        result = fal_client.subscribe(
            "fal-ai/flux-kontext",
            arguments={
                "image": f,
                "prompt": prompt,
                "strength": 0.6,
                "num_inference_steps": 28,
                "guidance_scale": 4.0,
            },
        )

    image_url = result["images"][0]["url"]
    import requests
    response = requests.get(image_url)
    response.raise_for_status()
    output_path.write_bytes(response.content)

    return str(output_path)
```

### Task 4.2：管理員「生成徽章」指令

**Files:**
- Modify: `travel/admin_commands.py`

- [ ] **Step 1: 加新指令 handler**

```python
def handle_generate_badge(args: str, user_id: str) -> str:
    if not is_admin(user_id):
        return "你不是管理員。"
    import re
    m = re.match(r"#?(\S+)", args.strip())
    if not m:
        return "格式：@bot 生成徽章 #<trip_id>"
    trip_id = m.group(1)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT title, location, trip_type FROM trips WHERE id=?",
            (trip_id,),
        ).fetchone()
    if not row:
        return f"找不到旅行 #{trip_id}"
    from travel.badge_generator import generate_badge
    from travel.db import get_conn
    image_path = generate_badge(row["title"], row["location"] or "", row["trip_type"] or "other")
    badge_id = uuid.uuid4().hex[:12]
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO badges (id, trip_id, rarity, image_path, prompt, master_ref, generated_at, approved_by, approved_at)
               VALUES (?, ?, 'common', ?, ?, 'common_base.png', ?, ?, ?)""",
            (badge_id, trip_id, image_path, row["title"], int(__import__('time').time()), user_id, int(__import__('time').time())),
        )
    return f"✅ 徽章 #{badge_id} 已生成（{image_path}）"


COMMANDS["生成徽章"] = handle_generate_badge
```

### Task 4.3：push 圖片到群組

**Files:**
- Modify: `travel/admin_commands.py`

- [ ] **Step 1: 圖片推到 LINE**

> `handle_generate_badge` 回傳字串後，在 `bot.py` 的指令 dispatcher 判斷：若回應含 `image_path`，改用 Flex Message + ImageMessage 回傳。

修改 `bot.py` 內的指令處理區塊：

```python
        if cmd_result:
            # 若回應含 image_path，用 ImageMessage
            import re
            img_match = re.search(r"\((data/badges/\S+\.png)\)", cmd_result)
            if img_match:
                # 必須是 HTTPS URL，後面 LIFF 部署後改用 ngrok URL
                image_url = f"{os.getenv('PUBLIC_BASE_URL', '')}/badges/{Path(img_match.group(1)).name}"
                self.line_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[
                            ImageMessage(original_content_url=image_url, preview_image_url=image_url),
                            LineTextMessage(text=f"✅ 徽章已生成！"),
                        ],
                    )
                )
            else:
                self.line_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[LineTextMessage(text=cmd_result)],
                    )
                )
            return
```

### Task 4.4：實測

- [ ] **Step 1: `.env` 加 `PUBLIC_BASE_URL=https://<ngrok-url>`**

- [ ] **Step 2: 確認 Flask 掛了 `/badges/` 靜態目錄**

修改 `bot.py` LINE webhook 啟動處（找 `Flask(...)` 那行）：

```python
    app = Flask(__name__)
    app.add_url_rule(
        "/badges/<filename>",
        endpoint="badges",
        view_func=lambda filename: send_from_directory(os.getenv("BADGES_DIR", "data/badges"), filename),
    )
```

- [ ] **Step 3: 跑一次 `建立旅行` + `生成徽章`，確認圖片出現在群組**

---

## Phase 5：LIFF（Vite + Vue 3 + Tailwind）

**目標：** LIFF 頁面展示徽章牆、旅行詳情、統計。

### Task 5.1：LINE Developers 建 LIFF App

- [ ] **Step 1: 到 LINE Developers Console 建 3 個 LIFF App**

| LIFF 名稱 | 用途 | Endpoint URL |
|---|---|---|
| 個人徽章牆 | 首頁 | `https://<ngrok>/liff/` |
| 旅行詳情 | 單趟 | `https://<ngrok>/liff/trip.html` |
| 統計儀表板 | 圖表 | `https://<ngrok>/liff/stats.html` |

Size: `tall`，Scope: `profile` + `openid` + `chat_message.read`

- [ ] **Step 2: 把 LIFF ID 填入 `.env`**

### Task 5.2：建立 LIFF 後端 API

**Files:**
- Create: `travel/routes_liff.py`

- [ ] **Step 1: 建立 Flask Blueprint**

```python
"""LIFF 後端 API。"""
import os
from flask import Blueprint, jsonify, request
from travel.db import get_conn
from travel.permissions import get_role

bp = Blueprint("liff", __name__, url_prefix="/api")


@bp.route("/me", methods=["GET"])
def me():
    """回傳當前使用者基本資料 + role。"""
    user_id = request.args.get("user_id") or request.headers.get("X-Line-User-Id", "")
    role = get_role(None, user_id)
    return jsonify({"user_id": user_id, "role": role})


@bp.route("/me/badges", methods=["GET"])
def my_badges():
    user_id = request.args.get("user_id", "")
    role = get_role(None, user_id)
    with get_conn() as conn:
        if role == "admin":
            rows = conn.execute(
                """SELECT b.*, t.title FROM badges b
                   LEFT JOIN trips t ON b.trip_id = t.id
                   ORDER BY b.generated_at DESC""",
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT b.*, t.title FROM badges b
                   LEFT JOIN trips t ON b.trip_id = t.id
                   LEFT JOIN trip_participants p ON b.trip_id = p.trip_id
                   WHERE p.user_id = ? OR b.approved_by = ?
                   ORDER BY b.generated_at DESC""",
                (user_id, user_id),
            ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/trips", methods=["GET"])
def list_trips():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trips ORDER BY start_date DESC"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/trips/<trip_id>", methods=["GET"])
def trip_detail(trip_id):
    user_id = request.args.get("user_id", "")
    role = get_role(trip_id, user_id)
    if role == "guest":
        return jsonify({"error": "forbidden"}), 403
    with get_conn() as conn:
        trip = conn.execute("SELECT * FROM trips WHERE id=?", (trip_id,)).fetchone()
        participants = conn.execute(
            """SELECT tp.user_id, tp.joined_at, m.user_name
               FROM trip_participants tp
               LEFT JOIN messages m ON tp.user_id = m.user_id
               WHERE tp.trip_id=? LIMIT 1""",
            (trip_id,),
        ).fetchall()
        badges = conn.execute(
            "SELECT * FROM badges WHERE trip_id=?", (trip_id,)
        ).fetchall()
    return jsonify({
        "trip": dict(trip) if trip else None,
        "participants": [dict(r) for r in participants],
        "badges": [dict(r) for r in badges],
        "role": role,
    })


@bp.route("/stats/personal", methods=["GET"])
def personal_stats():
    user_id = request.args.get("user_id", "")
    with get_conn() as conn:
        msgs = conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN type='sticker' THEN 1 ELSE 0 END) AS stickers,
                      SUM(CASE WHEN type='image' THEN 1 ELSE 0 END) AS images
               FROM messages WHERE user_id=?""",
            (user_id,),
        ).fetchone()
        trips = conn.execute(
            """SELECT COUNT(*) AS total FROM trip_participants WHERE user_id=?""",
            (user_id,),
        ).fetchone()
    return jsonify({
        "user_id": user_id,
        "total_messages": msgs["total"] or 0,
        "sticker_count": msgs["stickers"] or 0,
        "image_count": msgs["images"] or 0,
        "total_trips": trips["total"] or 0,
    })


@bp.route("/stats/group", methods=["GET"])
def group_stats():
    """只有管理員可看。"""
    user_id = request.args.get("user_id", "")
    role = get_role(None, user_id)
    if role != "admin":
        return jsonify({"error": "forbidden"}), 403
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT date(timestamp, 'unixepoch') AS date,
                      COUNT(*) AS count
               FROM messages
               GROUP BY date
               ORDER BY date DESC
               LIMIT 30"""
        ).fetchall()
    return jsonify([dict(r) for r in rows])
```

- [ ] **Step 2: 在 Flask app 註冊 Blueprint**

修改 `bot.py` LINE webhook 啟動處（找 `app = Flask(__name__)` 那行附近）：

```python
    from travel.routes_liff import bp as liff_bp
    app.register_blueprint(liff_bp)
```

### Task 5.3：LIFF 前端專案

**Files:**
- Create: `liff/package.json`, `liff/vite.config.js`, `liff/src/*`

- [ ] **Step 1: 初始化專案**

```bash
cd /home/william/projects/Sassy-PTT-Bot/liff
npm create vite@latest . -- --template vue
npm install
npm install -D tailwindcss postcss autoprefixer
npm install chart.js vue-chartjs vue-router @line/liff
npx tailwindcss init -p
```

- [ ] **Step 2: 設定 Tailwind（mobile-first）**

`tailwind.config.js`:

```js
module.exports = {
  content: ["./index.html", "./src/**/*.{vue,js}"],
  theme: { extend: {} },
  plugins: [],
};
```

`src/style.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 3: LIFF init + Vue app（`src/main.js`）**

```js
import liff from "@line/liff";
import { createApp } from "vue";
import App from "./App.vue";
import "./style.css";

const LIFF_ID = import.meta.env.VITE_LIFF_ID;

liff.init({ liffId: LIFF_ID }).then(() => {
  if (!liff.isLoggedIn()) {
    liff.login();
  }
  const app = createApp(App);
  app.config.globalProperties.$liff = liff;
  app.config.globalProperties.$userId = liff.getProfile().userId;
  app.mount("#app");
});
```

- [ ] **Step 4: 三個頁面（Home / TripDetail / Stats）**

> 用 Vue Router。`src/App.vue` 設導覽列 + `<router-view>`。

### Task 5.4：管理員觸發 LIFF 連結

**Files:**
- Modify: `travel/admin_commands.py`

- [ ] **Step 1: 加 `@bot 統計` 與 `@bot 我的徽章` handler**

```python
def handle_open_liff(args: str, user_id: str) -> str:
    """回 Flex Message 含 LIFF 按鈕。"""
    liff_id = os.getenv("LIFF_ID_STATS") if "統計" in args else os.getenv("LIFF_ID_HOME")
    if not liff_id:
        return "LIFF 尚未設定"
    # bot.py 內會把回傳值轉成 Flex Message
    return f"LIFF:{liff_id}"


COMMANDS["統計"] = handle_open_liff
COMMANDS["我的徽章"] = handle_open_liff
```

- [ ] **Step 2: bot.py 的 dispatcher 偵測 `LIFF:` prefix**

```python
        if cmd_result and cmd_result.startswith("LIFF:"):
            liff_id = cmd_result.split(":", 1)[1]
            flex = FlexMessage(
                alt_text="開啟 LIFF",
                contents=FlexContainer.from_json({
                    "type": "bubble",
                    "footer": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [{
                            "type": "button",
                            "action": {"type": "uri", "label": "開啟", "uri": f"line://app/{liff_id}"},
                        }],
                    },
                }),
            )
            self.line_api.reply_message(
                ReplyMessageRequest(reply_token=event.reply_token, messages=[flex])
            )
            return
```

---

## Phase 6：LLM 訊息分析（每月 1 次）

**目標：** 每月 1 號 03:00 批次分析未分析訊息，回填 `is_travel_related` / `topics` / `sentiment` / `locations` / `summary`。

### Task 6.1：批次分析器

**Files:**
- Create: `travel/llm_analyzer.py`

- [ ] **Step 1: 建立分析器**

```python
"""批次 LLM 分析訊息（主題 / 情緒 / 實體 / 摘要）。"""
import json
import os
import time
from openai import AsyncOpenAI
from travel.db import get_conn

PRIMARY_BASE = os.getenv("CLI_PROXY_BASE_URL", "http://localhost:8317/v1")
PRIMARY_KEY = os.getenv("CLI_PROXY_API_KEY", "")
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "gemini-3.6-flash-high")
BATCH_SIZE = 50


def build_prompt(messages: list[dict]) -> str:
    """組 LLM prompt：多則訊息一次分析。"""
    lines = []
    for m in messages:
        ts = time.strftime("%Y-%m-%d", time.localtime(m["timestamp"] / 1000))
        lines.append(f"[{ts}] {m['user_name']}: {m['content'] or '(non-text)'}")
    joined = "\n".join(lines)
    return (
        "分析以下 LINE 群組訊息（多則），每則輸出 JSON。\n"
        "欄位：\n"
        "- id（訊息 id）\n"
        "- is_travel_related（0/1）\n"
        "- topics（陣列，如 travel/food/work/chat）\n"
        "- sentiment（-1 ~ 1）\n"
        "- locations（地點陣列，可空）\n"
        "- summary（一句話摘要，可空）\n\n"
        f"訊息：\n{joined}\n\n"
        "輸出 JSON 陣列："
    )


async def analyze_batch(messages: list[dict]) -> list[dict]:
    client = AsyncOpenAI(base_url=PRIMARY_BASE, api_key=PRIMARY_KEY)
    prompt = build_prompt(messages)
    resp = await client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_completion_tokens=2000,
    )
    content = resp.choices[0].message.content.strip()
    # 移除可能的 ```json 包裹
    if content.startswith("```"):
        content = content.split("```")[1].lstrip("json").strip()
    return json.loads(content)


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
    with get_conn() as conn:
        for r in results:
            conn.execute(
                """UPDATE messages
                   SET is_travel_related=?, topics=?, sentiment=?,
                       locations=?, summary=?, analyzed_at=?
                   WHERE id=?""",
                (
                    r.get("is_travel_related", 0),
                    json.dumps(r.get("topics", [])),
                    r.get("sentiment", 0.0),
                    json.dumps(r.get("locations", [])),
                    r.get("summary", ""),
                    now,
                    r["id"],
                ),
            )
    print(f"[ANALYZER] 完成 {len(results)} 則分析")
```

### Task 6.2：APScheduler 每月排程

**Files:**
- Modify: `telegram_bot/bot.py`（scheduler 區塊）

- [ ] **Step 1: 加 import**

```python
from travel.llm_analyzer import run_monthly_analysis
```

- [ ] **Step 2: 加新 job**

在既有 `add_job` 之後加：

```python
            self._scheduler.add_job(
                run_monthly_analysis,
                trigger='cron',
                day=1,
                hour=3,
                minute=0,
                id='monthly_llm_analysis',
            )
            logger.info("[ANALYZER] 每月 1 號 03:00 訊息分析排程已啟動")
```

### Task 6.3：Backfill 歷史訊息

- [ ] **Step 1: 手動跑一次補跑**

```bash
source venv/bin/activate
python -c "from travel.llm_analyzer import run_monthly_analysis; run_monthly_analysis()"
```

- [ ] **Step 2: 重複執行直到所有訊息都 `analyzed_at IS NOT NULL`**

```bash
while true; do
  python -c "from travel.llm_analyzer import run_monthly_analysis; run_monthly_analysis()"
  REMAINING=$(sqlite3 data/chat.db "SELECT COUNT(*) FROM messages WHERE analyzed_at IS NULL AND type='text'")
  echo "剩餘未分析：$REMAINING"
  [ "$REMAINING" = "0" ] && break
done
```

預期：訊息分批進 Gemini Flash，DB 回填 `topics` / `sentiment` 等。

---

## Phase 7：統計聚合 + 圖表

**目標：** 每日 04:00 跑聚合腳本，更新 `daily_user_stats` / `user_lifetime_stats`；LIFF `stats.html` 顯示 Chart.js 圖表。

### Task 7.1：聚合腳本

**Files:**
- Create: `travel/aggregator.py`

- [ ] **Step 1: 寫聚合**

```python
"""每日統計聚合。"""
import json
import time
from travel.db import get_conn


def aggregate_daily():
    today = time.strftime("%Y-%m-%d", time.localtime())
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
            (today,),
        ).fetchall()
        for r in rows:
            conn.execute(
                """INSERT OR REPLACE INTO daily_user_stats
                   (date, user_id, group_id, text_count, sticker_count,
                    image_count, travel_mention_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (today, r["user_id"], r["group_id"],
                 r["text_count"] or 0, r["sticker_count"] or 0,
                 r["image_count"] or 0, r["travel_mentions"] or 0),
            )


def aggregate_lifetime():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT m.user_id, m.group_id,
                      COUNT(*) AS total,
                      MIN(m.timestamp) AS first_seen,
                      MAX(m.timestamp) AS last_seen,
                      (SELECT COUNT(*) FROM trip_participants tp
                       WHERE tp.user_id = m.user_id) AS total_trips,
                      (SELECT GROUP_CONCAT(DISTINCT json_each.value)
                       FROM messages, json_each(messages.locations)
                       WHERE messages.user_id = m.user_id
                         AND json_each.value IS NOT NULL) AS fav_locs
               FROM messages m
               GROUP BY m.user_id, m.group_id"""
        ).fetchall()
        for r in rows:
            conn.execute(
                """INSERT OR REPLACE INTO user_lifetime_stats
                   (user_id, group_id, total_messages, total_trips,
                    first_seen, last_seen, favorite_locations)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (r["user_id"], r["group_id"], r["total"] or 0,
                 r["total_trips"] or 0, r["first_seen"], r["last_seen"],
                 json.dumps((r["fav_locs"] or "").split(",") if r["fav_locs"] else [])),
            )


def run_daily_aggregation():
    aggregate_daily()
    aggregate_lifetime()
    print("[AGGREGATOR] 每日聚合完成")
```

### Task 7.2：排程整合

**Files:**
- Modify: `telegram_bot/bot.py`

- [ ] **Step 1: 加 import + job**

```python
from travel.aggregator import run_daily_aggregation
```

scheduler 加：

```python
            self._scheduler.add_job(
                run_daily_aggregation,
                trigger='cron',
                hour=4,
                minute=0,
                id='daily_aggregation',
            )
```

### Task 7.3：LIFF 統計頁

**Files:**
- Modify: `liff/src/views/Stats.vue`

- [ ] **Step 1: 接 Chart.js**

```vue
<script setup>
import { ref, onMounted } from "vue";
import { Bar, Pie } from "vue-chartjs";
import { Chart as ChartJS, ArcElement, Tooltip, Legend, BarElement, CategoryScale, LinearScale } from "chart.js";

ChartJS.register(ArcElement, Tooltip, Legend, BarElement, CategoryScale, LinearScale);

const userId = inject("$userId");
const data = ref(null);

onMounted(async () => {
  const r = await fetch(`/api/stats/personal?user_id=${userId}`);
  data.value = await r.json();
});
</script>

<template>
  <div class="p-4">
    <h1 class="text-2xl font-bold mb-4">統計</h1>
    <div v-if="data">
      <p>總訊息：{{ data.total_messages }}</p>
      <p>貼圖：{{ data.sticker_count }}</p>
      <p>圖片：{{ data.image_count }}</p>
      <p>參與旅行：{{ data.total_trips }} 趟</p>
    </div>
  </div>
</template>
```

---

## Phase 8（未來）：徽章稀有度自動判定

> **本計畫範圍外**，之後另開計畫。

預計邏輯：
- `common`：國內、≤ 2 天、≤ 5 人
- `rare`：國內、3+ 天 或 6+ 人
- `epic`：出國 或 特殊節日
- `legendary`：百岳、環島、特殊成就

---

## 備份策略

### Task Backup.1：備份腳本

**Files:**
- Create: `scripts/backup.sh`

- [ ] **Step 1: 寫腳本**

```bash
#!/bin/bash
set -e
DATE=$(date +%Y-%m-%d)
BACKUP_DIR="/path/to/external/backup"
mkdir -p "$BACKUP_DIR/$DATE"

# SQLite 熱備份
sqlite3 /home/william/projects/Sassy-PTT-Bot/data/chat.db \
    ".backup '$BACKUP_DIR/$DATE/chat.db'"

# 徽章圖片
rsync -av --delete \
    /home/william/projects/Sassy-PTT-Bot/data/badges/ \
    "$BACKUP_DIR/$DATE/badges/"

echo "備份完成：$BACKUP_DIR/$DATE"
```

- [ ] **Step 2: crontab 加入每日 02:00 執行**

```bash
chmod +x /home/william/projects/Sassy-PTT-Bot/scripts/backup.sh
crontab -e
# 加：
0 2 * * * /home/william/projects/Sassy-PTT-Bot/scripts/backup.sh
```

### Task Backup.2：Parquet 月匯出

**Files:**
- Create: `scripts/export_parquet.py`

- [ ] **Step 1: 寫匯出**

```python
"""每月把 messages 匯出成 Parquet（壓縮 + DuckDB 可查）。"""
import os
import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "data/chat.db"
ARCHIVE_DIR = "data/archive"
os.makedirs(ARCHIVE_DIR, exist_ok=True)

month = datetime.now().strftime("%Y-%m")
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query(
    "SELECT * FROM messages WHERE analyzed_at IS NOT NULL",
    conn,
)
conn.close()

if not df.empty:
    out_path = f"{ARCHIVE_DIR}/messages-{month}.parquet.gzip"
    df.to_parquet(out_path, compression="gzip")
    print(f"匯出 {len(df)} 則 → {out_path}")
```

- [ ] **Step 2: crontab 每月 1 號 04:30**

```cron
30 4 1 * * cd /home/william/projects/Sassy-PTT-Bot && source venv/bin/activate && python scripts/export_parquet.py
```

---

## 驗證清單（每個 Phase 結束時跑一次）

- [ ] **Phase 1**：`SELECT COUNT(*) FROM messages` 隨時間穩定成長
- [ ] **Phase 2**：`@bot 建立旅行` 與 `@bot 結束旅行` 正常運作
- [ ] **Phase 3**：`data/masters/` 有 4 張 PNG + `metadata.json`
- [ ] **Phase 4**：群組收到生成的徽章圖，檔案在 `data/badges/`
- [ ] **Phase 5**：LIFF 在 LINE 內開啟，徽章牆 / 統計頁正常
- [ ] **Phase 6**：未分析訊息數量歸 0，`topics` / `sentiment` 欄位有值
- [ ] **Phase 7**：`daily_user_stats` / `user_lifetime_stats` 有資料，LIFF 圖表渲染

---

## 開放問題（之後再處理）

1. **聊天記錄容量爆炸怎麼辦？** 目前估算 330MB / 10 年，暫不擔心。
2. **管理員名單動態化？** 目前寫在 `.env`，未來可改 DB。
3. **多語言支援？** 目前只處理中文，之後若加英文需調整 prompt。
4. **圖片 / 影片歷史調用？** 目前只計數，未來若要從 LINE 拉舊圖要改 webhook 即時下載。
5. **Phase 8 徽章稀有度邏輯細節**。
6. **使用者個資刪除請求**（GDPR-like）— 目前不做，未來需要再加。