# 八卦分身 (Sassy PTT Bot)

一個模仿 PTT 八卦版 (Gossiping) 風格的 Telegram 聊天機器人。不提供幫助，只提供毒舌。

## 核心理念

本 Bot 透過 RAG (Retrieval-Augmented Generation) 技術，將真實的 PTT 精華片段注入 LLM Prompt，使其能夠精準捕捉 PTT 鄉民的語氣、用詞與靈魂。

## 技術架構

| 元件 | 技術 |
|------|------|
| LLM | `gpt-5-mini`（OpenAI 相容 API） |
| 向量資料庫 | ChromaDB |
| 嵌入模型 | `sentence-transformers/all-MiniLM-L6-v2` |
| 機器人框架 | `python-telegram-bot`（非同步） |

### 運作流程

**步驟 A：觸發判定**

Bot 不會對每條訊息回應，模擬真實鄉民的「隨緣」特性：

- `@nonsenseTW_bot` 直接提及 → 100% 回應
- 訊息中有人回覆 Bot 的訊息 → 100% 回應
- 包含問句關鍵字（為什麼、怎麼、推薦、有沒有、股票、感情⋯⋯等 30+ 詞）→ 70% 機率回應
- 其他訊息 → 10% 機率隨機發作

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

## 啟動指南

### 環境需求

- Python 3.11+
- 套件：`python-telegram-bot`, `chromadb`, `sentence-transformers`, `openai`, `python-dotenv`

### 環境變數

在專案根目錄建立 `.env`：

```env
TELEGRAM_TOKEN=your_telegram_bot_token
CGU_LLM_API_KEY=your_api_key
```

### 啟動

```bash
source venv/bin/activate
python telegram_bot/bot.py
```

啟動成功會看到：
```
機器人已啟動 (gpt-5-mini 模式)。
```
