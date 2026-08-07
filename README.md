# 八卦分身 (Sassy PTT Bot)

一個模仿 PTT 八卦版 (Gossiping) 風格的聊天機器人，同時支援 **Telegram** 和 **LINE**。不提供幫助，只提供毒舌。

## 核心理念

本 Bot 透過 RAG (Retrieval-Augmented Generation) 技術，將真實的 PTT 精華片段注入 LLM Prompt，並透過半語意 few-shot + 對話脈絡感知，產出像鄉民留言串底下神回覆的短句。

## 技術架構

| 元件 | 技術 |
|------|------|
| LLM（Primary） | `gemini-3.6-flash-high` via CLIProxyAPI `http://localhost:8317/v1` |
| LLM（Fallback） | `gpt-5-mini` via CGU API（Primary 掛掉時自動切換） |
| 共通 | 15s 單次 timeout + 429 retry 3 次 |
| 向量資料庫 | ChromaDB |
| 嵌入模型 | `sentence-transformers/all-MiniLM-L6-v2` |
| Telegram 框架 | `python-telegram-bot`（非同步） |
| LINE 框架 | `line-bot-sdk` v3 + Flask webhook |
| 排程 | APScheduler（每日倒數、每週爬蟲） |

### 運作流程

**步驟 A：觸發判定**

Bot 不會對每條訊息回應，模擬真實鄉民的「隨緣」特性：

**Telegram**
- `@bot` 直接提及 → 100% 回應
- 包含問句關鍵字（為什麼、怎麼、推薦、有沒有、股票、感情⋯⋯等 30+ 詞）→ 30% 機率回應
- 其他訊息 → 10% 機率隨機發作

**LINE**
- 私訊（1:1）→ 100% 回應
- 群組內 `@bot` 直接提及 → 100% 回應
- 群組內含關鍵字 → 30% 機率回應
- 群組其他訊息 → 10% 機率隨機發作

**步驟 B：語料檢索 (RAG)**

- 用戶輸入轉為向量，在 ChromaDB（約 8.8 萬條 PTT 語料）中語義搜索最相關的 3 條
- **Top 1** 標為「真實推文範例」（給 LLM 看一段真的 PTT 推文怎麼寫）
- **Top 2-3** 標為「其他相關語料」，作為風格參考

**步驟 C：毒舌生成**

- **半語意 few-shot**：對 15 個 example Q&A 算 2-gram overlap，取 top 2 語意相近 + 3 個隨機，混搭後塞 prompt
- **對話 window**：每個群組/私訊保留最近 10 則訊息（user 訊息前置 sender 名稱，例如 `Alice 說：「三小」`，bot 回應原樣）
- **Anti-repeat**：當下 prompt 內附「前幾輪 bot 已用過的句型（不得重複）」列表，強迫模型換花樣
- **System prompt**：設定 PTT 鄉民人設 + 強制規定「回應必須呼應/引用 user 訊息的具體字詞，不可產生通用罐頭回應」
- **Sender 標記**：LINE 群組 lazy fetch `display_name` 並 cache，私訊/Telegram 用 username
- 輸出經後處理，移除 PTT 標記符號，只取第一行；若 LLM 觸發安全過濾，自動替換為人設台詞
- **LINE**：回應時自動引用（quote reply）觸發的那則訊息，群組中一眼看出 bot 在回哪句話

**步驟 D：LLM 雙 Provider**

- 先試 **PRIMARY**（CLIProxyAPI / `gemini-3.6-flash-high`），timeout 15s
- 失敗（timeout / 連線錯誤 / 全部 429 重試耗盡）→ 自動切到 **FALLBACK**（CGU / `gpt-5-mini`）
- 兩邊都掛 → 回「懶得理你，自己想。」

**步驟 E：自動排程**

- **每日 09:00**：推播畢業倒數天數 + 當日 PTT 熱門時事（快取至 `data/news_cache.json`，供當日嘴砲使用）
- **每日 09:05**：watchdog 補推（如果前一天沒推到或狀態 stuck）
- **每週日 03:00**：自動爬取最新 PTT 八卦板文章並重建 ChromaDB 索引，語料持續更新

## 專案結構

```
Sassy-PTT-Bot/
├── telegram_bot/
│   └── bot.py           # 機器人主程式（單檔）
├── indexer.py           # 將 PTT 語料建立 ChromaDB 索引
├── docs/superpowers/specs/  # 設計規格
├── data/
│   ├── news_cache.json       # 每日新聞快取（自動產生）
│   └── graduation_state.json # 倒數推送狀態（自動產生）
├── PTT-Crawler-master/
│   ├── Crawler.py       # PTT 爬蟲
│   └── chroma_db/       # 向量資料庫（不含於 repo）
├── requirements.txt
└── bot.log              # 滾動日誌（5MB × 7 份）
```

## 從零開始準備語料

本專案的向量資料庫（`chroma_db/`）和原始語料（7.4GB）均不包含於 repo，需自行建立。

### 步驟 1：爬取 PTT 八卦板文章

使用 `PTT-Crawler-master/` 內的爬蟲抓取文章，輸出為 JSON 格式。
每個 JSON 檔的結構應為：

```json
[
  {
    "Content": "文章內文",
    "Responses": [
      { "Content": "推文內容" }
    ]
  }
]
```

將所有 JSON 檔放入：

```
PTT-Crawler-master/data_Gossiping_2025/
```

### 步驟 2：建立向量索引

```bash
source venv/bin/activate
python indexer.py
```

執行完成後會在 `PTT-Crawler-master/chroma_db/` 建立向量資料庫。
預設最多索引 100,000 筆語料（可在 `indexer.py` 的 `MAX_DOCUMENTS` 調整）。

> 語料越多、涵蓋話題越廣，RAG 檢索效果越好。建議至少準備 **5 萬筆以上**的推文。
> 啟動後每週日 03:00 會自動增量爬取並重建索引。

---

## 啟動指南

### 環境需求

- Python 3.11+
- CLIProxyAPI（選填，推薦，本機 proxy 跑 Gemini） — 可參考對應 repo 的安裝步驟

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 環境變數

在專案根目錄建立 `.env`：

```env
# Telegram（必填）
TELEGRAM_TOKEN=your_telegram_bot_token

# LLM — Primary（推薦，CLIProxyAPI 本機 proxy）
CLI_PROXY_BASE_URL=http://localhost:8317/v1
CLI_PROXY_API_KEY=your_cliproxy_api_key
PRIMARY_MODEL=gemini-3.6-flash-high

# LLM — Fallback（CGU 學術 API，Primary 掛掉時切換）
CGU_LLM_API_KEY=your_cgu_api_key

# 單次 LLM 請求 timeout（秒，預設 15）
LLM_TIMEOUT=15.0

# LINE（選填，不填則只啟動 Telegram）
LINE_CHANNEL_SECRET=your_line_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_WEBHOOK_PORT=5000
LINE_GROUP_ID=your_line_group_id

# 畢業倒數（選填）
GRADUATION_DATE=2027-05-22
```

> 也支援 `GOOGLE_API_KEY`（gemini api）等其他 key，但需要先改 `bot.py` 對應的 client 設定。

> LINE Bot 需要公開的 HTTPS 端點才能接收 webhook。本機開發可用 [ngrok](https://ngrok.com/)：
> ```bash
> ngrok http 5000
> ```
> 將 ngrok 產生的 URL + `/line/callback` 填入 LINE Developers Console 的 Webhook URL。

### 啟動

```bash
source venv/bin/activate
python telegram_bot/bot.py
```

啟動成功會看到：
```
[LLM] Primary: gemini-3.6-flash-high @ http://localhost:8317/v1
[LLM] Fallback: gpt-5-mini @ https://air.cgu.edu.tw/cgullmapi/v1
LINE Bot 已啟用
Telegram 機器人已啟動 (primary=gemini-3.6-flash-high, fallback=gpt-5-mini)。
LINE webhook server 啟動於 port 5000
```

日誌寫入 `bot.log`（RotatingFileHandler，5MB × 7 份，重啟不清除）。

## 開發規格

所有設計決策記錄在 `docs/superpowers/specs/` 下，commit 進 repo 供 reviewer 參考。

