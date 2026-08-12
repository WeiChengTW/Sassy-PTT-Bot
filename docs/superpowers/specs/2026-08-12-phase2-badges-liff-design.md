# Phase 2 — 徽章 + LIFF + 管理員指令 設計規格

**日期**：2026-08-12
**狀態**：Draft（待 user review）
**對應**：Phase 1 計畫書 `docs/superpowers/plans/2026-08-12-travel-badge-extension.md` 之 Phase 2 章節

## 1. 目標與範圍

### 1.1 目標
讓 Sassy PTT Bot 從「訊息儲存 + 分析」進化為「完整的旅行回顧系統」，讓 LINE 群組成員可以：

1. 管理員透過 LINE 對話建立 / 結束旅行，自動觸發徽章生成
2. 成員透過 LIFF 網頁查看群組活躍度統計（儀表板）
3. 成員透過 LIFF 查看個人 / 群組的徽章收集冊

### 1.2 In Scope（本階段必做）
- **Schema migration**：ALTER TABLE 升級 trips / trip_participants / badges；新增 daily_stats
- **管理員指令**：LINE Flex Message 按鈕（建立旅行 / 加人 / 結束 / 發徽章）
- **權限分級**：admin / participant / guest（用 LIFF SDK + user_id 判定）
- **徽章系統（emoji 版）**：用 emoji + rarity 產生徽章 metadata，先不打圖。架構保留擴充點，之後接 fal.ai 直接換實作
- **稀有度規則**：common/rare/epic/legendary（emoji: 🟢/🔵/🟣/🟡 + 對應 location emoji）
- **Flask LIFF API**：Bluepring 提供 `/liff/dashboard`、`/liff/trips`、`/liff/trips/:id`、`/liff/badges`
- **LIFF 前端**：Vite + Vue 3 + Tailwind，3 個頁面（Dashboard / TripDetail / Badges）
- **APScheduler 整合**：旅行結束後自動發徽章（emoji 版）

### 1.3 Out of Scope（本階段不做，YAGNI）
- 投票系統（votes / vote_records）
- 照片牆（photo_urls 欄位先預留，不實作）
- AI 進階分析（情緒曲線、旅行人格、年度回顧）
- 經典語錄自動提取（memorable_quotes 欄位先預留）
- 多群組管理（假設單一群組，未來另開）
- 圖片 / 影片下載（仍只計數，符合 Phase 1 決策）
- **fal.ai 執行期生圖**（Phase 2.5 之後，badge 架構已預留 `fal_client.py` 介面）
- **ComfyUI 母徽章生成**（emoji 版不需要）

### 1.4 與 Phase 1 的關係
Phase 1 已實作：
- ✅ `messages` 表（含 is_travel_related, topics, sentiment, locations 等 LLM 分析欄位）
- ✅ `trips`、`trip_participants`、`badges` 表（基本結構）
- ✅ `daily_user_stats`、`user_lifetime_stats` 表
- ✅ 訊息儲存 hook（`_store_line_event`）
- ✅ APScheduler（graduation + monthly LLM + daily aggregator）
- ✅ CLI 統計工具（`scripts/show_stats.py`）

Phase 2 **純擴充**，不破壞 Phase 1 既有資料。

---

## 2. 架構

```
LINE Webhook (既有 Flask @ :5000 + ngrok)
    │
    ├── [P2 新] 管理員指令 dispatch
    │   └── Flex Message 按鈕 → 觸發 travel CRUD
    │
    ├── [P2 新] LIFF Blueprint  (/liff/*)
    │   ├── GET  /dashboard?group_id=X
    │   ├── GET  /trips?group_id=X
    │   ├── GET  /trips/:id
    │   └── GET  /badges/:user_id?group_id=X
    │
    └── APScheduler（既有 + 新增）
        └── [P2 新] cron 每小時檢查 ended 旅行 → 觸發徽章發放（emoji 版）

LIFF 前端 (Vite dev server @ :5173 + ngrok)
    ├── Dashboard.vue   群組儀表板（折線圖/熱力圖/排行榜/類型分佈）
    ├── TripDetail.vue  單趟旅行回顧（基本資訊 + 參與者 + 經典語錄佔位）
    └── Badges.vue      個人徽章收集冊（emoji + 稀有度配色）

檔案系統
    （Phase 2 emoji 版無需圖檔，之後接 fal.ai 才會用到 data/badges/）
```

---

## 3. Schema 演進

### 3.1 Migration 機制
- 新檔：`travel/migrations.py`
- 新表：`schema_version (version INTEGER PRIMARY KEY, applied_at INTEGER)`
- `migrate()` 函式：跑所有未套用的 MIGRATIONS（依序、transactional）
- 啟動時自動呼叫（與現有 `init_db()` 並存 — `init_db()` 只確保表存在，schema 變更走 migration）

### 3.2 Migration 清單

```sql
-- Migration 1: trips 擴充
ALTER TABLE trips ADD COLUMN rarity TEXT;
ALTER TABLE trips ADD COLUMN badge_image_url TEXT;
ALTER TABLE trips ADD COLUMN badge_video_url TEXT;
ALTER TABLE trips ADD COLUMN planning_days INTEGER;
ALTER TABLE trips ADD COLUMN total_messages INTEGER DEFAULT 0;
ALTER TABLE trips ADD COLUMN participants_count INTEGER;
ALTER TABLE trips ADD COLUMN budget_total REAL;
ALTER TABLE trips ADD COLUMN key_messages TEXT;        -- JSON
ALTER TABLE trips ADD COLUMN memorable_quotes TEXT;   -- JSON
ALTER TABLE trips ADD COLUMN photo_urls TEXT;         -- JSON
ALTER TABLE trips ADD COLUMN ended_at INTEGER;
ALTER TABLE trips ADD COLUMN updated_at INTEGER DEFAULT (strftime('%s','now'));

-- Migration 2: trip_participants 擴充
ALTER TABLE trip_participants ADD COLUMN role TEXT;
ALTER TABLE trip_participants ADD COLUMN messages_count INTEGER DEFAULT 0;
ALTER TABLE trip_participants ADD COLUMN photos_shared INTEGER DEFAULT 0;

-- Migration 3: badges 改成 user-earning（保留舊欄位相容）
ALTER TABLE badges ADD COLUMN user_id TEXT;
ALTER TABLE badges ADD COLUMN badge_type TEXT;        -- trip / achievement / special
ALTER TABLE badges ADD COLUMN badge_name TEXT;
ALTER TABLE badges ADD COLUMN badge_rarity TEXT;
ALTER TABLE badges ADD COLUMN badge_image_url TEXT;
ALTER TABLE badges ADD COLUMN earned_at INTEGER;
ALTER TABLE badges ADD COLUMN description TEXT;
ALTER TABLE badges ADD COLUMN metadata TEXT;          -- JSON
-- 既有欄位（id, trip_id, rarity, image_path, prompt, master_ref, generated_at, approved_by, approved_at）
-- 保留，新結構以 user_id + badge_type + earned_at 為主鍵邏輯
CREATE UNIQUE INDEX IF NOT EXISTS idx_badges_unique
  ON badges(user_id, trip_id, badge_type)
  WHERE user_id IS NOT NULL;

-- Migration 4: 新增 daily_stats（group 層級，補 Phase 1 缺的 group-level 聚合）
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

-- Migration 5: 加 LIFF 權限用的 group_members 索引（加速 in-group 判定）
CREATE INDEX IF NOT EXISTS idx_messages_user_group
  ON messages(user_id, group_id);
```

### 3.3 Schema 設計決策

| 決策 | 理由 |
|---|---|
| 用 ALTER TABLE 而非重建 | Phase 1 DB 已有資料結構（即使目前 0 筆），migration 模式可重用於未來演進 |
| 預留 `key_messages` / `memorable_quotes` / `photo_urls` 欄位 | Out-of-scope 功能先預留欄位，未來不用再 ALTER |
| `badges` 同時保留舊欄位 + 新欄位 | Phase 1 已存在的 trip-scoped badges 不刪除；新邏輯走 user-scoped 結構 |
| `daily_stats` 與 `daily_user_stats` 並存 | 前者是 group-level（儀表板用），後者是 user-level（個人頁用，Phase 1 已建） |
| `idx_messages_user_group` 複合索引 | 加速「user 是否在 group」判定（每次 LIFF 請求都會跑） |

---

## 4. 管理員指令（LINE Flex Message 按鈕）

### 4.1 觸發方式
- 管理員在 LINE 群組打 `@bot admin` 或 `@bot 管理員`
- Bot 回覆 Flex Message Carousel 包含 4 個按鈕：
  - 🆕 建立旅行
  - 👥 加入參與者
  - 🏁 結束旅行
  - 🏅 發徽章（手動觸發，emoji 版）

### 4.2 指令流程

**建立旅行（Create Trip）**
```
1. Admin tap「建立旅行」
2. Bot 回 Quick Reply：「請直接輸入：建立旅行 <標題> <日期 YYYY-MM-DD>」
3. Admin 回：「建立旅行 墾丁三日遊 2026-09-15」
4. Bot 解析 → 寫入 trips (status='planning')
5. Bot 回 Flex Message 確認卡片（含 trip_id）
```

**加入參與者（Add Participants）**
```
1. Admin tap「加入參與者」
2. Bot 回：「請 tag @參與者 或貼 user_id，可多個，逗號分隔」
3. Admin @小美 @小明
4. Bot 解析 → 寫入 trip_participants (role='participant')
5. Bot 回覆目前參與者列表
```

**結束旅行（End Trip）**
```
1. Admin tap「結束旅行」
2. Bot 回 Quick Reply 列出目前 status='active' 的 trips
3. Admin 選一個 → Bot 更新 trips.status='ended', ended_at=now
4. Bot 回覆確認 + 提示「徽章將於下次排程自動生成」
```

**發徽章（Award Badges，admin 手動觸發）**
```
1. Admin tap「發徽章」
2. Bot 回 Quick Reply 列出 ended trips
3. Admin 選一個 → Bot 觸發 award_badges_for_trip() 為每個參與者寫入 emoji 徽章
4. Bot 回覆發放結果（每個參與者顯示 emoji + 稀有度）
```

### 4.3 檔案結構
```
travel/admin_commands.py
├── AdminCommandDispatcher
│   ├── is_admin(user_id) -> bool
│   ├── handle_admin_keyword(event) -> None
│   ├── send_admin_menu(event) -> None           # Flex Message 主選單
│   ├── handle_create_trip(event, args) -> None
│   ├── handle_add_participants(event, args) -> None
│   ├── handle_end_trip(event, args) -> None
│   └── handle_award_badges(event, args) -> None  # Phase 2 emoji 版
```

### 4.4 安全性
- `is_admin()` 讀 `ADMIN_USER_IDS` env（逗號分隔）
- 非 admin 觸發 → 不回應（靜默忽略，避免被亂觸發）
- Trip CRUD 前檢查 trip 是否屬於該 group（不允許跨群組操作）

---

## 5. 徽章系統（emoji 版）

> **Phase 2 簡化**：不打圖、不呼叫 fal.ai、不存圖檔。徽章 = emoji + metadata。架構預留 `badge_image_url` 欄位，Phase 2.5 之後接 fal.ai 直接換實作即可。

### 5.1 檔案結構
```
travel/badges.py            # 編排流程（emoji 版，介面預留給未來 fal.ai）
（無 data/badges/ 目錄，Phase 2 不存圖）
```

### 5.2 流程（旅行結束自動 / admin 手動）
```
1. 觸發源：APScheduler（hourly）OR admin 手動指令
2. 撈 status='ended' 且尚未發徽章的 trips（用 badges UNIQUE 索引判定）
3. 對每個 trip 的每個 participant：
   a. compute_rarity(trip) → 'common' | 'rare' | 'epic' | 'legendary'
   b. compute_badge_emoji(trip, rarity) → e.g. "🏖️🟣"
   c. compute_badge_name(trip, user_name, rarity) → e.g. "墾丁三日遊・資深冒險家"
   d. 寫入 badges 表（user_id, trip_id, badge_type='trip', badge_name, badge_rarity, badge_image_url=NULL, earned_at）
4. 回傳新發放的徽章清單（admin 指令時貼回 LINE；APScheduler 觸發則 log）
```

### 5.3 Rarity 規則（Phase 2 MVP，之後可調）
| Rarity | Emoji 配色 | 條件 |
|---|---|---|
| common | 🟢 | 旅程 ≤ 2 天 |
| rare | 🔵 | 旅程 3-4 天 |
| epic | 🟣 | 旅程 ≥ 5 天 或 參與者 ≥ 6 人 |
| legendary | 🟡 | 國內跨縣市（如台北→墾丁）OR 出國 |

實作：`compute_rarity(trip) -> Literal['common','rare','epic','legendary']`

### 5.4 Emoji 組合規則
```
常用地點 emoji 對照：
  墾丁/海邊/沙灘 → 🏖️
  山/登山 → 🏔️
  城市/夜市 → 🌃
  溫泉 → ♨️
  露營 → 🏕️
  出國 → ✈️
  其他 → 🗺️

最終 badge_emoji = location_emoji + rarity_circle
  例：墾丁 epic → "🏖️🟣"
      出國 legendary → "✈️🟡"
```

### 5.5 為何先 emoji 而非 PNG
- **不依賴外部 API**：Phase 2 不需要 FAL_KEY、不需要上傳 master、沒有 API 成本
- **流程可驗證**：admin 指令 → 發徽章 → DB 有 row → LIFF 看得到，整條鏈路打通
- **之後換實作零摩擦**：`compute_rarity()` 與 `compute_badge_emoji()` 邏輯在 Phase 2.5 直接重用；只需在 `award_badges_for_trip()` 裡把「寫 emoji + metadata」改成「呼叫 fal.ai + 寫 image_url」

### 5.6 介面預留（Phase 2.5 之後可無痛升級）
```python
# travel/badges.py
def compute_rarity(trip: dict) -> Literal["common","rare","epic","legendary"]:
    """Phase 2.5 邏輯維持不變"""
    ...

def compute_badge_emoji(trip: dict, rarity: str) -> str:
    """Phase 2.5 之後換成 generate_badge_image()"""
    ...

def award_badges_for_trip(trip: dict) -> list[dict]:
    """對 trip 所有 participants 發徽章，回傳新徽章清單。
    
    Phase 2 實作：寫 emoji metadata
    Phase 2.5 之後：在這裡插入 fal_client.generate_badge() 呼叫，寫 image_url
    """
    participants = get_participants(trip["id"])
    new_badges = []
    for p in participants:
        rarity = compute_rarity(trip)
        emoji = compute_badge_emoji(trip, rarity)
        name = compute_badge_name(trip, p["user_name"], rarity)
        badge_id = insert_badge(
            user_id=p["user_id"],
            trip_id=trip["id"],
            badge_type="trip",
            badge_name=name,
            badge_rarity=rarity,
            badge_image_url=None,  # Phase 2.5 改為 fal.ai URL
            description=f"{trip['title']} 完成",
            earned_at=int(time.time()),
        )
        new_badges.append({"badge_id": badge_id, "user_id": p["user_id"], "emoji": emoji, ...})
    return new_badges
```

---

## 6. Flask LIFF API

### 6.1 檔案結構
```
telegram_bot/liff_api.py
├── liff_bp = Blueprint('liff', __name__, url_prefix='/liff')
├── @liff_bp.route('/dashboard')
├── @liff_bp.route('/trips')
├── @liff_bp.route('/trips/<trip_id>')
├── @liff_bp.route('/badges/<user_id>')
└── _require_member(user_id, group_id) -> bool   # 內部 helper
```

### 6.2 Endpoints

| Method | Path | Query | Response | 權限 |
|---|---|---|---|---|
| GET | `/liff/dashboard` | `group_id`, `days=30` | `{ daily_counts[], heatmap[], top_users[], type_distribution[], summary{} }` | participant+ |
| GET | `/liff/trips` | `group_id` | `[{ id, title, start_date, end_date, rarity, badge_image_url }]` | participant+ |
| GET | `/liff/trips/<id>` | — | `{ trip, participants[], stats{}, memorable_quotes[] }` | participant+ |
| GET | `/liff/badges/<user_id>` | `group_id` | `[{ badge_name, badge_rarity, badge_image_url, earned_at }]` | self or admin |

### 6.3 權限檢查
- 從 LIFF SDK 拿到 `user_id`（前端 header `X-LIFF-UserId` 帶上）
- `_require_member(user_id, group_id)`：查 `messages` 表是否有該 user_id + group_id 組合
- Admin 額外檢查 `ADMIN_USER_IDS`
- 不通過 → 回 403 JSON `{ "error": "not_member" }`

### 6.4 範例回應（GET /liff/dashboard）
```json
{
  "summary": {
    "total_messages": 12345,
    "active_days": 234,
    "member_count": 8,
    "active_trips": 3
  },
  "daily_counts": [
    {"date": "2026-07-13", "count": 142},
    ...
  ],
  "heatmap": [
    {"day_of_week": 5, "hour": 22, "count": 87},
    ...
  ],
  "top_users": [
    {"user_id": "Uxxx", "user_name": "小明", "total": 1234, "active_days": 89},
    ...
  ],
  "type_distribution": [
    {"type": "text", "count": 8000},
    {"type": "sticker", "count": 3000},
    {"type": "image", "count": 1345}
  ]
}
```

### 6.5 Flask 整合
- 在 `telegram_bot/bot.py` 既有 Flask app 註冊 blueprint：
  ```python
  from telegram_bot.liff_api import liff_bp
  app.register_blueprint(liff_bp)
  ```
- 既有 app 在 port 5000，LIFF 走 `/liff/*` path，與 LINE webhook (`/line/callback`) 共用 ngrok

---

## 7. LIFF 前端

### 7.1 專案結構
```
liff/                          # 獨立 Vite 專案
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json
├── index.html
├── .env.liff                   # LIFF ID（gitignored）
├── public/
└── src/
    ├── main.ts
    ├── App.vue
    ├── router.ts
    ├── views/
    │   ├── DashboardView.vue
    │   ├── TripListView.vue
    │   ├── TripDetailView.vue
    │   └── BadgesView.vue
    ├── components/
    │   ├── LineChart.vue       # 包 Chart.js
    │   ├── HeatmapChart.vue
    │   └── BarChart.vue
    ├── api/
    │   └── client.ts           # fetch wrapper，自動帶 user_id header
    └── stores/
        └── liff.ts             # Pinia store：liff init state
```

### 7.2 路由（vue-router）
| Path | View | 用途 |
|---|---|---|
| `/` | DashboardView | 群組儀表板 |
| `/trips` | TripListView | 旅行列表 |
| `/trips/:id` | TripDetailView | 單趟旅行回顧 |
| `/badges` | BadgesView | 我的徽章 |

### 7.3 LIFF SDK 整合
- 啟動時 `liff.init({ liffId: import.meta.env.VITE_LIFF_ID })`
- 已登入 → `liff.getProfile()` 拿 userId
- 呼叫後端時帶 `X-LIFF-UserId` header
- 未登入 → 跳轉 `liff.login()`

### 7.4 圖表選擇
- **Chart.js + vue-chartjs**：輕量、官方 Vue 包支援、Chart.js 內建 line / bar / doughnut / matrix（heatmap）
- 不用 Recharts / D3：bundle size 友善、RWD 簡單

### 7.5 RWD
- Tailwind `sm:` / `md:` / `lg:` 斷點
- 行動裝置優先（LINE LIFF 主要在手機開）
- 圖表容器固定寬高 + Chart.js `responsive: true, maintainAspectRatio: false`

### 7.6 開發與部署
- 開發：`cd liff && npm run dev`（Vite @ :5173）
- 本機 ngrok：`ngrok http 5173`（**第二條 ngrok tunnel**，與 Flask 5000 並行）
- 部署（之後）：Vite build → 靜態託管（Vercel / Cloudflare Pages）

---

## 8. APScheduler 整合

### 8.1 新增 jobs
```python
# 每小時檢查 ended trips 觸發徽章發放
self._scheduler.add_job(
    process_ended_trips,
    trigger='cron',
    minute=5,  # 每小時 :05 跑（避免整點撞 LLM 分析）
    id='badge_award',
)
```

### 8.2 process_ended_trips 邏輯
```python
def process_ended_trips():
    """撈 status='ended' 且尚未發徽章的 trips，批次發放。"""
    trips = get_ended_trips_without_badges()
    for trip in trips:
        try:
            award_badges_for_trip(trip)  # travel/badges.py
        except Exception as e:
            logger.error(f"[BADGE] trip {trip['id']} 失敗: {e}")
```

---

## 9. 設定變更

### 9.1 `.env` 新增
```env
# Phase 2 — 管理員
ADMIN_USER_IDS=Uxxxxxxxxxxxxxxxxxxxxxxxxxx,Uyyyyyyyyyyyyyyyyyyyyyyyyyyyyy

# Phase 2 — LIFF
LIFF_ID=your-liff-id-1234

# Phase 2.5 之後才需要（emoji 版不需）
# FAL_KEY=your_fal_api_key
```

### 9.2 `requirements.txt` 新增
```
（Phase 2 emoji 版不加任何依賴；Phase 2.5 再加 fal-client>=0.4.0）
```

### 9.3 `liff/package.json`（新檔）
```json
{
  "dependencies": {
    "vue": "^3.4",
    "vue-router": "^4.3",
    "pinia": "^2.1",
    "@line/liff": "^2.22",
    "chart.js": "^4.4",
    "vue-chartjs": "^5.3"
  },
  "devDependencies": {
    "vite": "^5.2",
    "typescript": "^5.4",
    "tailwindcss": "^3.4",
    "@vitejs/plugin-vue": "^5.0",
    "vue-tsc": "^2.0"
  }
}
```

---

## 10. 檔案清單總覽

### 新檔
```
travel/migrations.py            # ALTER TABLE 執行
travel/badges.py                # 徽章編排（emoji 版，介面預留 fal.ai）
travel/admin_commands.py        # 管理員指令 dispatch
telegram_bot/liff_api.py        # Flask Blueprint
liff/                           # 整個 Vite 專案
tests/test_migrations.py
tests/test_badges.py
tests/test_admin_commands.py
tests/test_liff_api.py
```

### Phase 2.5 之後才新增（emoji 版不需）
```
travel/fal_client.py            # fal.ai 包裝
data/badges/masters/{common,rare,epic,legendary}.png
data/badges/generated/<trip_id>_<user_id>.png
```

### 修改檔
```
travel/db.py                    # 新增 migrate() + run_migrations()
travel/aggregator.py            # 新增 aggregate_daily_stats() (group-level)
telegram_bot/bot.py             # 註冊 liff_bp + admin dispatcher + APScheduler jobs
scripts/show_stats.py           # 新增 dashboard 總覽指令
.env                            # + ADMIN_USER_IDS / LIFF_ID（Phase 2）
.gitignore                      # + liff/node_modules/、.env.liff
```

---

## 11. 測試策略

### 11.1 單元測試（TDD）
- `test_migrations.py`：mock DB，驗證 ALTER 順序、version 紀錄、可重複跑（idempotent）
- `test_badges.py`：驗證 compute_rarity 規則、compute_badge_emoji 規則、award_badges_for_trip 寫 DB 邏輯、idempotent（重跑不重複發）
- `test_admin_commands.py`：mock LINE event，驗證 is_admin、指令解析、Flex Message 結構
- `test_liff_api.py`：用 Flask test client，驗證 4 個 endpoint、權限檢查、JSON 結構

### 11.2 整合測試（手動 E2E）
- **Step A**：啟動 bot → 確認 log 出現 `[MIGRATIONS] schema at version 5`
- **Step B**：admin 在 LINE 打 `@bot admin` → 看到 Flex Message 4 個按鈕
- **Step C**：建立旅行「測試旅行」 → 確認 DB 有 row
- **Step D**：加入 2 個參與者（用 fake user_id） → 確認 trip_participants 有 2 row
- **Step E**：結束旅行 → 確認 status='ended'
- **Step F**：手動 trigger `process_ended_trips()` → 確認 badges 表有 row，emoji metadata 正確（rarity / name / earned_at）
- **Step G**：啟動 Vite dev server → 開 LIFF URL → 確認 dashboard 顯示假資料圖表

### 11.3 不寫的測試
- LIFF 前端 Vue 元件單元測試（手動 E2E 涵蓋）
- Chart.js 視覺測試（眼睛看）

---

## 12. 錯誤處理

| 情境 | 行為 |
|---|---|
| FAL_KEY 未設 | N/A（Phase 2 emoji 版不依賴 fal.ai） |
| fal.ai API 失敗 | N/A（Phase 2.5 才適用；該 participant 跳過、log error、其他繼續、hourly job 重試） |
| Master 圖缺失 | N/A（Phase 2 emoji 版不存圖） |
| Admin 操作跨群組 | 靜默拒絕、回「找不到該旅行」 |
| LIFF 未登入 | 前端導向 `liff.login()` |
| LIFF user_id 不在群組 | 後端回 403、前端顯示「你不是群組成員」 |
| Migration 失敗 | transaction rollback、log error、bot 啟動中止（fail-fast，避免半套 schema） |
| 徽章發放部分失敗 | 成功的寫 DB、失败的 log、hourly job 自動重試（idempotent：用 UNIQUE 索引 + UNIQUE constraint） |
| emoji 規則不認識 location | fallback 到 🗺️ + 對應 rarity circle，不 crash |
| Admin 重複發徽章 | UNIQUE(user_id, trip_id, badge_type) 約束，重跑會跳過已存在的，不會重複發 |

---

## 13. 部署流程

### 13.1 一次性設定
1. 在 LINE Developers 建 LIFF App，記下 LIFF_ID
2. `.env` 加 `ADMIN_USER_IDS` / `LIFF_ID`
3. `cd liff && npm install`

### 13.2 啟動
```bash
# Terminal 1: Flask (LINE webhook + LIFF API)
./run_bot.sh

# Terminal 2: Vite dev server
cd liff && npm run dev

# Terminal 3 & 4: ngrok tunnels
ngrok http 5000   # Flask
ngrok http 5173   # Vite
```

### 13.3 LINE Developers 設定
- Webhook URL：`https://<ngrok-5000>.ngrok-free.app/line/callback`（既有）
- LIFF Endpoint URL：`https://<ngrok-5173>.ngrok-free.app`
- LIFF App 權限：profile + openid（LIFF SDK 預設要求）

### 13.4 Phase 2.5 升級路徑
1. `pip install fal-client`
2. `.env` 加 `FAL_KEY`
3. 把 4 張 master PNG 放 `data/badges/masters/`
4. 在 `travel/badges.py` 把 `award_badges_for_trip()` 內的「寫 emoji」段落改成「呼叫 fal_client.generate_badge() + 寫 image_url」
5. LIFF BadgesView.vue 已有 image 顯示 fallback，自動從 emoji 切到 PNG

---

## 14. 開放問題

1. **傳說級影片**：原計畫提到 `badge_video_url` 但 Phase 2 emoji 版不做影片，Phase 2.5+ 也不急
2. **多群組**：LIFF 設計假設單一群組。多群組時 group_id 從哪來？（從 LIFF URL param？從 launch 參數？）
3. **照片牆先不做**：但 `trips.photo_urls` 預留欄位。之後若要做，admin 指令要加「上傳照片」功能
4. **經典語錄**：手動？自動（LLM 提取高 sentiment 訊息）？Phase 2 留空陣列，UI 顯示「管理員尚未設定」
5. **歷史資料回填**：Phase 1 schema 已升級，但舊 trips / badges 沒有新欄位。處理方式：補 NULL，不主動回填
6. **CLI dashboard 指令**：Phase 2 是否加 `python scripts/show_stats.py dashboard`？建議加，驗證 SQL 正確性
7. **emoji 對照表維護**：location → emoji 對照寫死還是 DB 維護？Phase 2 寫死（dict literal），之後量大再 DB 化

---

## 15. 與 Phase 1 既有功能的相容性檢查

| Phase 1 元件 | Phase 2 影響 | 處理 |
|---|---|---|
| `messages` 表 | 無變動 | — |
| `trips` 表 | ALTER 加欄位 | Migration 1 |
| `trip_participants` 表 | ALTER 加欄位 | Migration 2 |
| `badges` 表 | ALTER 加欄位（保留舊） | Migration 3 |
| `daily_user_stats` 表 | 無變動 | — |
| `user_lifetime_stats` 表 | 無變動 | — |
| `_store_line_event()` hook | 無變動 | — |
| `aggregate_daily()` / `aggregate_lifetime()` | 不影響；Phase 2 加 `aggregate_daily_stats()` | 新函式 |
| `run_monthly_analysis()` | 無變動 | — |
| APScheduler jobs | 加 1 個（badge_generation） | bot.py 新增 |
| `scripts/show_stats.py` | 加 `dashboard` 子指令 | 修改 |
| Flask app port 5000 | 多掛 `/liff/*` blueprint | bot.py 修改 |

**結論**：Phase 2 純擴充，Phase 1 的所有功能在 migration 後照常運作。