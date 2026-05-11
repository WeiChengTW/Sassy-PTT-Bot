# 八卦分身 (Sassy PTT Bot)

一個模仿 PTT 八卦版 (Gossiping) 風格的聊天機器人，同時支援 **Telegram** 和 **LINE**。不提供幫助，只提供毒舌。

## 核心理念

本 Bot 透過 RAG (Retrieval-Augmented Generation) 技術，將真實的 PTT 精華片段注入 LLM Prompt，使其能夠精準捕捉 PTT 鄉民的語氣、用詞與靈魂。

## 技術架構

| 元件 | 技術 |
|------|------|
| LLM | `gpt-5-mini`（OpenAI 相容 API） |
| 向量資料庫 | ChromaDB |
| 嵌入模型 | `sentence-transformers/all-MiniLM-L6-v2` |
| Telegram 框架 | `python-telegram-bot`（非同步） |
| LINE 框架 | `line-bot-sdk` v3 + Flask webhook |

### 運作流程

**步驟 A：觸發判定**

Bot 不會對每條訊息回應，模擬真實鄉民的「隨緣」特性：

**Telegram**
- `@bot` 直接提及 → 100% 回應
- 包含問句關鍵字（為什麼、怎麼、推薦、有沒有、股票、感情⋯⋯等 30+ 詞）→ 70% 機率回應
- 其他訊息 → 10% 機率隨機發作

**LINE**
- 私訊（1:1）→ 100% 回應
- 群組內含關鍵字 → 70% 機率回應
- 群組其他訊息 → 10% 機率隨機發作

**步驟 B：語料檢索 (RAG)**

- 用戶輸入轉為向量，在 ChromaDB（約 8.8 萬條 PTT 語料）中語義搜索最相關的 3 條。

**步驟 C：毒舌生成**

- 固定 few-shot 示範 + RAG 檢索語料注入 Prompt。
- System prompt 設定為 PTT 八卦板酸民人設：極短、極度沒禮貌、愛開噴。
- 輸出經後處理，移除 PTT 標記符號，只取第一行。

## 專案結構

```
nlp_final_project/
├── telegram_bot/
│   └── bot.py           # 機器人主程式
├── indexer.py           # 將 PTT 語料建立 ChromaDB 索引
├── corpus.py            # 語料處理邏輯
├── PTT-Crawler-master/
│   └── chroma_db/       # 向量資料庫（不含於 repo）
└── requirements.txt
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

---

## 啟動指南

### 環境需求

- Python 3.11+
- 套件：`python-telegram-bot`, `chromadb`, `sentence-transformers`, `openai`, `python-dotenv`, `line-bot-sdk`, `flask`

```bash
pip install python-telegram-bot chromadb sentence-transformers openai python-dotenv line-bot-sdk flask
```

### 環境變數

在專案根目錄建立 `.env`：

```env
# Telegram（必填）
TELEGRAM_TOKEN=your_telegram_bot_token

# LLM API（必填）
CGU_LLM_API_KEY=your_api_key

# LINE（選填，不填則只啟動 Telegram）
LINE_CHANNEL_SECRET=your_line_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_WEBHOOK_PORT=5000
```

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
Telegram 機器人已啟動 (gpt-5-mini 模式)。
LINE webhook server 啟動於 port 5000   # 若有設定 LINE 環境變數
```
