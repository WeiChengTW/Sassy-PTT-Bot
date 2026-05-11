import os
import random
import logging
import re
import asyncio
import threading
from pathlib import Path
import chromadb
from chromadb.utils import embedding_functions
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# LINE SDK (optional)
try:
    from flask import Flask, request, abort
    from linebot.v3 import WebhookHandler
    from linebot.v3.messaging import (
        Configuration, ApiClient, MessagingApi,
        ReplyMessageRequest, PushMessageRequest, TextMessage as LineTextMessage,
    )
    from linebot.v3.webhooks import MessageEvent, TextMessageContent
    from linebot.v3.exceptions import InvalidSignatureError
    LINE_SDK_AVAILABLE = True
except ImportError:
    LINE_SDK_AVAILABLE = False

# --- 1. 日誌設定 ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(Path(__file__).resolve().parents[1] / "bot.log", mode='w', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# --- 2. 環境變數載入 ---
try:
    from dotenv import load_dotenv
    project_env = Path(__file__).resolve().parents[1] / ".env"
    hermes_env = Path.home() / "hermes-work" / ".env"
    load_dotenv(project_env)
    load_dotenv(hermes_env, override=False)
except ImportError:
    pass

# --- 3. 配置 ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CGU_API_KEY = os.getenv("CGU_LLM_API_KEY")
CGU_BASE_URL = "https://air.cgu.edu.tw/cgullmapi/v1"
CHROMA_DB_PATH = str(Path(__file__).resolve().parents[1] / "PTT-Crawler-master" / "chroma_db")
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
GENERATION_MODEL_NAME = "gpt-5-mini"

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_WEBHOOK_PORT = int(os.getenv("LINE_WEBHOOK_PORT", "5000"))

TRIGGER_KEYWORDS = [
    # 疑問句
    "為什麼", "怎麼", "怎樣", "如何", "哪裡", "哪個", "什麼", "幾點", "多少",
    # 求推薦／意見
    "推薦", "有沒有", "好嗎", "值得", "覺得", "建議", "選哪",
    # PTT 用語
    "卦", "八卦", "懶人包", "魯蛇", "肥宅", "正妹", "帥哥",
    # 熱門話題
    "股票", "政治", "薪水", "工作", "女友", "男友", "感情", "大學", "考試",
    # 情緒觸發詞
    "笑死", "幹", "靠北", "三小", "啊不就",
]

SYSTEM_PROMPT = (
    "你現在是 PTT 八卦板酸民。你講話極短、極度沒禮貌、愛開噴。\n"
    "你只會輸出推文內容，絕對不准輸出任何解釋、標籤、格式說明或引導文字。\n"
    "看到廢話直接噴，看到魯蛇直接酸。"
)

FIXED_EXAMPLES = (
    "網友說：「推薦好看的電影」\n回應：爛片隨便你愛看哪部都一樣廢\n\n"
    "網友說：「今天天氣好熱」\n回應：廢話夏天不熱要怎樣，台灣人沒救\n\n"
    "網友說：「台大值得念嗎」\n回應：念完還不是回去繼承家業，裝什麼高材生\n\n"
    "網友說：「有沒有推薦的餐廳」\n回應：自己用 Google 不會喔，智障\n\n"
    "網友說：「股票跌了怎麼辦」\n回應：套牢了吧，叫你不要跟風你不聽"
)


def should_trigger(text, always=False):
    """判斷是否應該回應。always=True 代表直接提及（如 @bot 或私訊）。"""
    if always:
        return True
    if any(kw in text for kw in TRIGGER_KEYWORDS):
        return random.random() < 0.7
    return random.random() < 0.1


class SassyBrain:
    def __init__(self):
        logger.info(f"正在喚醒八卦分身 (大腦: {GENERATION_MODEL_NAME})")
        self.emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL_NAME)
        self.chroma = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        self.collection = self.chroma.get_or_create_collection(
            name="ptt_gossip",
            embedding_function=self.emb_fn
        )
        if CGU_API_KEY:
            self.llm = AsyncOpenAI(api_key=CGU_API_KEY, base_url=CGU_BASE_URL)
        else:
            logger.warning("No CGU_LLM_API_KEY found.")
            self.llm = None
        self._llm_sem = threading.Semaphore(2)  # 最多 2 個並行 LLM 請求

        # LINE setup
        self.line_api = None
        self.line_handler = None
        if LINE_SDK_AVAILABLE and LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN:
            self.line_handler = WebhookHandler(LINE_CHANNEL_SECRET)
            line_config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
            self.line_api = MessagingApi(ApiClient(line_config))
            logger.info("LINE Bot 已啟用")
        else:
            logger.info("LINE Bot 未啟用（缺少 LINE_CHANNEL_SECRET 或 LINE_CHANNEL_ACCESS_TOKEN）")

    # ── Telegram handlers ──────────────────────────────────────────────────

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("笑死，又來一個魯蛇。想問什麼快說啦，我很忙。")

    async def handle_telegram_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_text = update.message.text
        if not user_text:
            return

        bot_username = (await context.bot.get_me()).username
        mentioned = f"@{bot_username}" in user_text
        clean_text = re.sub(rf'@{bot_username}\s*', '', user_text).strip()

        if should_trigger(clean_text, always=mentioned):
            response = await self.generate_response(clean_text)
            await update.message.reply_text(response)

    # ── LINE handlers ──────────────────────────────────────────────────────

    def handle_line_event(self, event):
        """同步 LINE 事件處理（Flask 呼叫，用 asyncio.run 橋接非同步）。"""
        if not isinstance(event, MessageEvent):
            return
        if not isinstance(event.message, TextMessageContent):
            return

        user_text = event.message.text
        if not user_text:
            return

        # 私訊（user）永遠回應；群組內 @bot 也永遠回應
        is_direct = event.source.type == "user"
        mention = event.message.mention
        is_mentioned = (
            mention is not None
            and any(getattr(m, 'is_self', False) for m in (mention.mentionees or []))
        )
        # 清除 @提及 文字，避免混入 prompt
        clean_text = user_text
        if mention and mention.mentionees:
            for m in mention.mentionees:
                if hasattr(m, 'text'):
                    clean_text = clean_text.replace(m.text, '').strip()

        if should_trigger(clean_text, always=(is_direct or is_mentioned)):
            # 取得推送目標 ID（reply token 會因 LLM 延遲而過期，改用 push）
            source = event.source
            if source.type == "user":
                target_id = source.user_id
            elif source.type == "group":
                target_id = source.group_id
            else:
                target_id = source.room_id

            def push_async():
                with self._llm_sem:
                    response = asyncio.run(self.generate_response(clean_text))
                self.line_api.push_message(
                    PushMessageRequest(
                        to=target_id,
                        messages=[LineTextMessage(text=response)],
                    )
                )

            threading.Thread(target=push_async, daemon=True).start()

    # ── Core logic ─────────────────────────────────────────────────────────

    def get_relevant_snippets(self, query, n_results=3):
        try:
            results = self.collection.query(query_texts=[query], n_results=n_results)
            return results['documents'][0] if results['documents'] else []
        except Exception as e:
            logger.error(f"檢索失敗: {e}")
            return []

    async def generate_response(self, user_text):
        if not self.llm:
            return "笑死，連 Key 都沒有，你比我還窮。"

        import time
        t0 = time.time()

        snippets = self.get_relevant_snippets(user_text)
        rag_context = "\n".join(snippets) if snippets else ""

        user_prompt = (
            f"以下是 PTT 鄉民的發言風格範例：\n{FIXED_EXAMPLES}\n\n"
            + (f"相關 PTT 語料（參考風格用）：\n{rag_context}\n\n" if rag_context else "")
            + f"網友說：「{user_text}」\nPTT 酸民的回應（一句話，不要解釋）："
        )

        try:
            for attempt in range(3):
                try:
                    resp = await self.llm.chat.completions.create(
                        model=GENERATION_MODEL_NAME,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=1.0,
                        max_completion_tokens=3000,
                    )
                    break
                except Exception as e:
                    if "429" in str(e) and attempt < 2:
                        logger.warning(f"429 rate limit，5s 後重試 (attempt {attempt+1})")
                        await asyncio.sleep(5)
                    else:
                        raise
            elapsed = time.time() - t0
            choice = resp.choices[0]
            raw_text = choice.message.content or ""
            logger.info(f"回應時間: {elapsed:.1f}s")
            logger.info(f"模型原始輸出: {repr(raw_text)} | finish_reason: {choice.finish_reason}")
            return self._sanitize_response(raw_text)
        except Exception as e:
            logger.error(f"生成失敗: {e}")
            return "懶得理你，自己想。"

    def _sanitize_response(self, text):
        if not text:
            return "笑死，懶得理你。"
        clean_text = text.strip()
        clean_text = re.sub(r'^([→推噓]|鄉民推：)\s*', '', clean_text)
        lines = [line.strip() for line in clean_text.split('\n') if line.strip()]
        if not lines:
            return "滾回去洗碗啦。"
        return lines[0]


def run_line_server(brain: SassyBrain):
    """在獨立執行緒中跑 Flask LINE webhook server。"""
    flask_app = Flask(__name__)

    @flask_app.route("/line/callback", methods=['POST'])
    def line_callback():
        signature = request.headers.get('X-Line-Signature', '')
        body = request.get_data(as_text=True)
        try:
            brain.line_handler.handle(body, signature)
        except InvalidSignatureError:
            abort(400)
        return 'OK'

    # 把事件處理綁到 handler
    @brain.line_handler.add(MessageEvent, message=TextMessageContent)
    def on_message(event):
        brain.handle_line_event(event)

    logger.info(f"LINE webhook server 啟動於 port {LINE_WEBHOOK_PORT}")
    flask_app.run(host="0.0.0.0", port=LINE_WEBHOOK_PORT)


def main():
    if not TELEGRAM_TOKEN:
        logger.error("錯誤：請設定 TELEGRAM_TOKEN")
        return

    brain = SassyBrain()

    # 啟動 LINE server（若有設定）
    if brain.line_handler:
        t = threading.Thread(target=run_line_server, args=(brain,), daemon=True)
        t.start()

    # 啟動 Telegram polling
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", brain.start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), brain.handle_telegram_message))
    logger.info(f"Telegram 機器人已啟動 ({GENERATION_MODEL_NAME} 模式)。")
    app.run_polling()


if __name__ == "__main__":
    main()
