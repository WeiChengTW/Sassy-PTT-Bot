import os
import random
import logging
import re
from pathlib import Path
import chromadb
from chromadb.utils import embedding_functions
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

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

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("笑死，又來一個魯蛇。想問什麼快說啦，我很忙。")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_text = update.message.text
        if not user_text:
            return

        should_respond = False
        bot_username = (await context.bot.get_me()).username

        if f"@{bot_username}" in user_text:
            should_respond = True
        elif any(kw in user_text for kw in [
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
        ]):
            if random.random() < 0.7:
                should_respond = True
        elif random.random() < 0.1:
            should_respond = True

        if should_respond:
            clean_user_text = re.sub(rf'@{bot_username}\s*', '', user_text).strip()
            response = await self.generate_response(clean_user_text)
            await update.message.reply_text(response)

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

        snippets = self.get_relevant_snippets(user_text)
        rag_context = "\n".join(snippets) if snippets else ""

        user_prompt = (
            f"以下是 PTT 鄉民的發言風格範例：\n{FIXED_EXAMPLES}\n\n"
            + (f"相關 PTT 語料（參考風格用）：\n{rag_context}\n\n" if rag_context else "")
            + f"網友說：「{user_text}」\nPTT 酸民的回應（一句話，不要解釋）："
        )

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
            choice = resp.choices[0]
            raw_text = choice.message.content or ""
            logger.info(f"模型原始輸出: {repr(raw_text)} | finish_reason: {choice.finish_reason}")
            return self._sanitize_response(raw_text)
        except Exception as e:
            logger.error(f"生成失敗: {e}")
            return "笑死，這也要問，滾好嗎。"

    def _sanitize_response(self, text):
        if not text:
            return "笑死，懶得理你。"

        clean_text = text.strip()
        clean_text = re.sub(r'^([→推噓]|鄉民推：)\s*', '', clean_text)

        lines = [line.strip() for line in clean_text.split('\n') if line.strip()]
        if not lines:
            return "滾回去洗碗啦。"

        return lines[0]

def main():
    if not TELEGRAM_TOKEN:
        logger.error("錯誤：請設定 TELEGRAM_TOKEN")
        return
    bot_logic = SassyBrain()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", bot_logic.start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), bot_logic.handle_message))
    logger.info(f"機器人已啟動 ({GENERATION_MODEL_NAME} 模式)。")
    app.run_polling()

if __name__ == "__main__":
    main()
