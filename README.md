# 八卦分身 (Sassy PTT Bot)

一個模仿 PTT 八卦版 (Gossiping) 風格的 **LINE** 群組機器人。介面有 LINE 對話 + LIFF 旅行回顧前端 + 旅遊擴充模組 + 群組分析儀表板。不提供幫助，只提供毒舌。

## 核心理念

- 透過 RAG（Retrieval-Augmented Generation）將真實 PTT 推文與群組歷史對話記憶注入 LLM Prompt
- 半語意 few-shot + 對話脈絡感知 + 群組人物別名與事件百科，產出像熟人互嗆、神回覆的短句
- LINE 群組行為模擬真實鄉民「隨緣」特性（不一定每則都回，但被點名精準開酸）
- 附帶旅遊 / 徽章 / 群組分析作為「附加價值」，讓群組回頭看得到累積

## 技術架構

| 元件 | 技術 |
|------|------|
| LLM（Primary） | `gemini-3.6-flash-high` via CLIProxyAPI `http://localhost:8317/v1` |
| LLM（Fallback） | `gpt-5-mini` via CGU API（Primary 掛掉時自動切換） |
| LLM 共通 | 15s 單次 timeout + 429 retry 3 次 |
| 向量資料庫 | ChromaDB（含 PTT 語料與群組對話記憶 `group_memory` 雙 collection） |
| 嵌入模型 | `sentence-transformers/all-MiniLM-L6-v2` |
| LINE 框架 | `line-bot-sdk` v3 + Flask webhook |
| 排程 | APScheduler（每日倒數 / 聚合 / 徽章 + 每週爬蟲 + 每月 LLM 分析） |
| 後端 | Python 3.11+ |
| 前端 | Vite + Vue 3 + TypeScript + Tailwind + Pinia + Vue Router |
| 前端圖表 | Chart.js + vue-chartjs（柱狀 / 圓餅 / 折線）+ D3 v7（力導向網絡圖） |
| 分析儲存 | SQLite（WAL 模式）：訊息、trip、participant、badge、daily / lifetime stats、members |

### 運作流程（對話引擎）

**步驟 A：觸發判定**

Bot 不會對每則訊息回應，模擬真實鄉民的「隨緣」：

| 場景 | 觸發率 |
|------|--------|
| LINE 私訊（1:1） | 100% |
| 群組內 `@bot` 直接提及 | 100%（精準對焦問題，不被前文雜訊干擾） |
| 群組內 bare `@bot`（無其他文字） | 回 LIFF 旅行回顧按鈕 |
| 群組內 Admin DM | 回 LIFF 管理員後台按鈕 |
| 群組內含關鍵字（為什麼、怎麼、推薦、股票、感情⋯⋯等 30+ 詞） | 30% 機率 |
| 群組其他訊息 | 10% 機率隨機發作（短詞附和自動回溯上文主旨插嘴） |

**步驟 B：語料與記憶雙軌檢索 (RAG & Group Memory)**

- **PTT 語料檢索**：用戶輸入轉向量，在 ChromaDB 約 8.8 萬條 PTT 語料中語義搜索
  - **Top 1** 標為「真實推文範例」
  - **Top 2-3** 標為「其他相關語料」，作為風格參考
- **群組記憶與實體檢索**：
  - **人物與外號對照**：載入 `data/aliases.json`，精確識別發言者與被提及者本名/綽號與代表作
  - **重大歷史事件百科**：載入 `data/events.json` 與 SQLite 對話紀錄，檢索經典黑歷史與名言佳句
  - **向量記憶檢索**：在 `group_memory` 向量庫中檢索相關對話視窗

**步驟 C：毒舌生成**

- **半語意 few-shot**：對 15 個 example Q&A 算 2-gram overlap，取 top 2 語意相近 + 3 個隨機，混搭後塞 prompt
- **短句回溯對齊**：若群友發「會」「真的」「笑死」等短附和詞觸發，自動往前鎖定最近有實質內容的話題
- **對話 window**：群聊保留最近對話歷史，訊息前綴 sender display_name（例如 `Alice 說：「三小」`）
- **Anti-repeat**：當下 prompt 附帶「前幾輪 bot 已用過的回應」，強迫模型切換不同切入點與句型
- **System prompt**：PTT 鄉民 + 群內毒舌老友雙重人設，指名道姓精準開酸，杜絕捏造假人名與罐頭話
- **LINE 引用回覆**：回應時自動帶 `quote_token` 引用觸發的那則訊息

**步驟 D：LLM 雙 Provider**

- 先試 **PRIMARY**（CLIProxyAPI / `gemini-3.6-flash-high`），timeout 15s
- 失敗（timeout / 連線錯誤 / 全部 429 重試耗盡）→ 自動切到 **FALLBACK**（CGU / `gpt-5-mini`）
- 兩邊都掛 → 回「懶得理你，自己想。」
- 觸發 semaphore：`@mention` 走 2-slot semaphore（避免 reply_token 過期），自發觸發走 `non-blocking lock`（搶不到就跳過）

**步驟 E：自動排程**

| 排程 | 動作 |
|------|------|
| 每日 09:00 | 推播畢業倒數 + 當日 PTT 熱門時事（快取至 `data/news_cache.json`） |
| 每日 09:05 | watchdog 補推（如果前一天沒推到） |
| 每日 04:00 | 聚合前一日的 `daily_user_stats` / `user_lifetime_stats` / group-level `daily_stats` |
| 每小時 :05 | 批次發放已結束旅行的 user-scoped 徽章 |
| 每月 1 號 03:00 | 對已收集訊息跑 LLM 主題 / 情緒 / 旅行偵測，回寫 `messages` 表 |
| 每週日 03:00 | 自動爬取最新 PTT 八卦板文章並重建 ChromaDB 索引 |

## 模組總覽

### 1. LINE 對話引擎 — `line_bot/`

LINE webhook 主程式，包含 webhook handler、LLM 雙 provider、ChromaDB 查詢、對話歷史、sender 標記。Flask 同時掛載 LIFF API blueprint（後述）。

**啟動**：
```bash
./run_bot.sh                    # 等同：./venv/bin/python line_bot/bot.py
```

### 2. LIFF 旅行回顧前端 — `liff/`

Vue 3 + Vite 的 LINE 前端框架應用，提供群組儀表板、旅行清單 / 詳情、徽章牆、管理員後台（建立 / 結束旅行、發放徽章），以及 Phase 3 分析頁面（排行榜、互動關係、話題、個人檔案）。所有頁面透過 Vite proxy 把 `/liff/*` 轉發到 bot 的 Flask port 5000。

**啟動**：
```bash
cd liff
npm install                     # 首次
npm run dev                     # 開發：http://localhost:5174
npm run build                   # 生產：vue-tsc + vite build → dist/
```

**路由總覽**：
- `/` — DashboardView（總訊息 / 成員數 / 旅行中 / 活躍天數 / Top 話癆 / 訊息類型）
- `/trips`、`/trips/:id` — TripListView / TripDetailView
- `/badges` — BadgesView（個人徽章牆）
- `/leaderboard` — 活躍度排行 + 夜貓子排行 + 類型圓餅圖（Chart.js）
- `/interactions` — 最佳拍檔 + D3 力導向互動網絡圖
- `/topics` — 熱門話題 + 情緒曲線
- `/profile` — 個人總訊息 / 活躍天數 / 時段分佈 / 24h 柱狀圖 / 常聊話題
- `/admin/*` — 管理員後台（需 `ADMIN_USER_IDS` 通過）

### 3. 旅遊擴充 — `travel/`

後端分析 / 旅遊邏輯模組，啟動時若 `TRAVEL_STORAGE_ENABLED=true` 會自動 `init_db()` + 跑 migrations。每次 LINE 訊息都會 `_store_line_event` 寫入 SQLite（`messages` 表），再由排程聚合到 `daily_user_stats` / `user_lifetime_stats` / `daily_stats`。

包含：
- `trip_crud.py` — Trip CRUD（建立 / 結束 / 參與者）
- `badges.py` — 依地點 + 旅行天數 + 參與人數計算稀有度（common / rare / epic / legendary），自動發 emoji 徽章
- `aggregator.py` — 每日 / 終身統計聚合
- `llm_analyzer.py` — 每月 LLM 主題 / 情緒 / 旅行偵測
- `stats.py` / `stats_extended.py` — Dashboard / Leaderboard / Interactions / Topics / Profile 查詢

**API endpoints**（`/liff/*`）：
- 一般：`/me`、`/dashboard`、`/trips`、`/trips/:id`、`/badges/:user_id`
- 分析：`/leaderboard`、`/interactions`、`/topics`、`/profile/:user_id`
- 管理員：`/admin/trips`、`/admin/trips/:id/participants`、`/admin/trips/:id/end`、`/admin/trips/:id/award-badges`

**啟動**：跟著 `line_bot/bot.py` 一起啟動，不需獨立指令。

### 4. 分析 CLI — `scripts/show_stats.py`

不想開 LIFF 時，從 terminal 直接看 SQLite 統計。

```bash
python scripts/show_stats.py overview          # 總訊息 / 已分析 / 旅行相關 / 類型分佈
python scripts/show_stats.py user <user_id>    # 單一使用者統計
python scripts/show_stats.py top-users          # Top 10 話癆
python scripts/show_stats.py topics             # 主題分佈
python scripts/show_stats.py travel             # 旅行相關訊息排行
python scripts/show_stats.py dashboard          # 群組 dashboard 摘要
```

## 專案結構

```
Sassy-PTT-Bot/
├── line_bot/
│   ├── bot.py                  # LINE webhook 主程式 + APScheduler
│   └── liff_api.py             # Flask Blueprint：/liff/* API endpoints
├── liff/                       # LIFF 前端（Vue 3 + Vite + Tailwind）
│   ├── src/
│   │   ├── views/              # Dashboard / TripList / TripDetail / Badges /
│   │   │                       # Leaderboard / Interactions / Topics / Profile / Admin
│   │   ├── api/client.ts       # API client wrapper
│   │   ├── stores/, router.ts, App.vue, main.ts
│   ├── package.json            # v5 d3 / chart.js 4 / vue-chartjs 5
│   └── vite.config.ts          # dev port 5174, proxy /liff → :5000
├── travel/                     # 旅遊擴充 + 群組分析
│   ├── db.py                   # SQLite schema + get_conn() (WAL)
│   ├── trip_crud.py            # Trip CRUD
│   ├── badges.py               # 稀有度計算 + 自動發徽章
│   ├── aggregator.py           # 每日 / 終身 / group-level 聚合
│   ├── llm_analyzer.py         # 每月 LLM 主題分析
│   ├── line_event_parser.py    # LINE event → SQLite row
│   ├── stats.py                # Dashboard / Trip / User badge 查詢
│   ├── stats_extended.py       # Phase 3 分析查詢
│   └── migrations.py
├── corpus_config.py            # 語料與群組記憶設定、別名與重大事件載入
├── indexer.py                  # PTT 語料 → ChromaDB 索引
├── index_group_memory.py       # 群組歷史對話視窗 → ChromaDB 索引 (group_memory)
├── scripts/
│   ├── import_line_export.py   # LINE 匯出文字紀錄匯入資料庫
│   └── show_stats.py           # CLI 統計工具
├── data/                       # 自動產生（git ignored）
│   ├── chat.db                 # SQLite
│   ├── aliases.json            # 群組成員別名/外號對照表（可選）
│   ├── events.json             # 群組歷史重大事件百科（可選）
│   ├── news_cache.json         # 每日新聞快取
│   └── graduation_state.json   # 倒數推送狀態
├── PTT-Crawler-master/         # PTT 爬蟲（submodule）
│   ├── data_Gossiping_2025/    # 原始 JSON 語料（不入 repo）
│   └── chroma_db/              # 向量資料庫（不入 repo）
├── docs/superpowers/
│   ├── specs/                  # 設計規格
│   └── plans/                  # 實作計畫
├── tests/                      # pytest
├── requirements.txt
├── run_bot.sh                  # 啟動 bot 的 launcher
├── ngrok.yml                   # 兩個 tunnel：bot :5000 + liff :5174
├── .env                        # 環境變數（不入 repo）
└── bot.log                     # 滾動日誌（5MB × 7 份）
```

## 從零開始準備語料

本專案的向量資料庫（`chroma_db/`）和原始語料（GB 等級）不包含於 repo，需自行建立。

### 步驟 1：爬取 PTT 八卦板文章

使用 `PTT-Crawler-master/` 內的爬蟲抓取文章，輸出為 JSON 格式：
```json
[
  {
    "Content": "文章內文",
    "Responses": [{ "Content": "推文內容" }]
  }
]
```

將所有 JSON 檔放入 `PTT-Crawler-master/data_Gossiping_2025/`。

### 步驟 2：建立向量索引
```bash
source venv/bin/activate
python indexer.py
```

執行完成會在 `PTT-Crawler-master/chroma_db/` 建立向量資料庫，預設最多索引 100,000 筆（可在 `indexer.py` 的 `MAX_DOCUMENTS` 調整）。啟動後每週日 03:00 會自動增量爬取並重建索引。

> 語料越多、涵蓋話題越廣，RAG 檢索效果越好。建議至少準備 **5 萬筆以上**的推文。

---

## 啟動指南

### 環境需求

- Python 3.11+
- Node.js 18+（LIFF 前端開發）
- CLIProxyAPI（選填，推薦，本機 proxy 跑 Gemini）— 參考對應 repo 安裝步驟

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

```bash
cd liff && npm install && cd ..
```

### 環境變數

在專案根目錄建立 `.env`：

```env
# LINE（必填）
LINE_CHANNEL_SECRET=your_line_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_WEBHOOK_PORT=5000

# 主群：所有功能（訊息記憶 / 旅行紀錄 / 統計 / LIFF）都在這個群
MAIN_LINE_GROUP_ID=your_main_line_group_id
# 次要群組：只接收 graduation 倒數 + 一般統計戰報，本身無訊息記憶
LINE_GROUP_ID=your_secondary_line_group_id

# LLM — Primary（推薦，CLIProxyAPI 本機 proxy）
CLI_PROXY_BASE_URL=http://localhost:8317/v1
CLI_PROXY_API_KEY=your_cliproxy_api_key
PRIMARY_MODEL=gemini-3.6-flash-high

# LLM — Fallback（CGU 學術 API，Primary 掛掉時切換）
CGU_LLM_API_KEY=your_cgu_api_key

# 單次 LLM 請求 timeout（秒，預設 15）
LLM_TIMEOUT=15.0

# LIFF
LIFF_ID=your-liff-id

# 旅遊擴充
TRAVEL_STORAGE_ENABLED=true
DB_PATH=data/chat.db

# 管理員（LINE user_id，逗號分隔；可從 LINE Bot 私訊收訊息時的 source.user_id 取得）
ADMIN_USER_IDS=user_id_1,user_id_2

# 畢業倒數（選填）
GRADUATION_DATE=2027-05-22
```

### 啟動

#### Bot
```bash
./run_bot.sh
```

啟動成功會看到：
```
[LLM] Primary: gemini-3.6-flash-high @ http://localhost:8317/v1
[LLM] Fallback: gpt-5-mini @ https://air.cgu.edu.tw/cgullmapi/v1
LINE Bot 已啟用
[TRAVEL] SQLite 已初始化並完成 migration
[GRADUATION] 排程已啟動，目標群組: ...
LINE webhook server 啟動於 port 5000
```

#### LIFF 前端（開發）
```bash
cd liff
npm run dev
```
開 `http://localhost:5174/`，Vite 會把 `/liff/*` 轉發到 bot 的 :5000。

### 對外 HTTPS（LINE webhook + LIFF）

LINE Bot 跟 LIFF 都需要公開的 HTTPS 端點。本機開發用 `ngrok.yml`（已配置兩個 tunnel）：
```bash
ngrok start --all              # 啟動 nlp_final_project (5000) + sassy_liff (5174)
```

把 ngrok 給的網址填入：
- LINE Developers Console → Webhook URL：`https://<bot-tunnel>.ngrok-free.app/line/callback`
- LINE LIFF Endpoint URL：`https://<liff-tunnel>.ngrok-free.app`

> 若只用雲端部署（不用 ngrok），替換成正式 HTTPS 網域即可。

日誌寫入 `bot.log`（RotatingFileHandler，5MB × 7 份，重啟不清除）。

## 開發規格

設計決策記錄在 `docs/superpowers/specs/` 下，commit 進 repo 供 reviewer 參考：
- 對話感知設計（2026-08-07）
- 畢業倒數機制（2026-05-30）
- Phase 2 徽章 + LIFF 設計（2026-08-12）

實作計畫：
- `plans/2026-05-30-daily-graduation-countdown.md`
- `plans/2026-08-12-phase2-badges-liff.md`
- `plans/2026-08-12-phase3-analytics-dashboard.md`
- `plans/2026-08-12-travel-badge-extension.md`
