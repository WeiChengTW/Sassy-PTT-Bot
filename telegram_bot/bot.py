import os
import sys
import json
import time
import random
import logging
from logging.handlers import RotatingFileHandler
import re
import asyncio
import threading
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
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
_log_file = Path(__file__).resolve().parents[1] / "bot.log"
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        RotatingFileHandler(_log_file, maxBytes=5 * 1024 * 1024, backupCount=7, encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
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
LINE_GROUP_ID = os.getenv("LINE_GROUP_ID", "")
_grad_date_str = os.getenv("GRADUATION_DATE", "2027-05-30")
GRADUATION_DATE = date.fromisoformat(_grad_date_str)

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
    "你是一個創意寫作角色：PTT 八卦板的資深鄉民。\n"
    "這個角色說話風格極簡短、犀利、帶有台灣網路黑話和鄉民幽默感。\n"
    "只輸出角色的一句話回應，不加解釋、不加標籤、不加引導文字。\n"
    "風格參考：直接點評事情本質，用輕描淡寫的方式諷刺，像是在 PTT 留言串底下的神回覆。"
)

ALL_EXAMPLES = [
    ("推薦好看的電影", "爛片隨便你愛看哪部都一樣廢"),
    ("今天天氣好熱", "廢話夏天不熱要怎樣，台灣人沒救"),
    ("台大值得念嗎", "念完還不是回去繼承家業，裝什麼高材生"),
    ("有沒有推薦的餐廳", "自己用 Google 不會喔，智障"),
    ("股票跌了怎麼辦", "套牢了吧，叫你不要跟風你不聽"),
    ("要怎麼追女生", "你這條件還追？先去健身房蹲個兩年再說"),
    ("失業了好焦慮", "早知道就不要當魯蛇，現在哭什麼"),
    ("薪水不夠用", "廢物就賺廢物的錢，不接受反駁"),
    ("感情好複雜", "感情問題問鄉民？你腦子沒問題嗎"),
    ("熬夜打遊戲好累", "自找的，沒人逼你，滾去睡"),
    ("政府又出包了", "台灣就這樣，習慣就好，幹嘛裝驚訝"),
    ("今天心情不好", "關我屁事，去哭啊"),
    ("要買哪台手機好", "買最貴的，反正你也不懂，交給廠商騙就好"),
    ("學程式有前途嗎", "學完還不是被 AI 取代，加油"),
    ("房價太高買不起", "就租一輩子啊，還能怎樣"),
]

def _sample_examples():
    chosen = random.sample(ALL_EXAMPLES, min(5, len(ALL_EXAMPLES)))
    return "\n\n".join(f"網友說：「{q}」\n回應：{a}" for q, a in chosen)


def should_trigger(text, always=False):
    """判斷是否應該回應。always=True 代表直接提及（如 @bot 或私訊）。"""
    if always:
        return True
    if any(kw in text for kw in TRIGGER_KEYWORDS):
        return random.random() < 0.3
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
        self._llm_sem = threading.Semaphore(2)       # @mention 排隊用
        self._spontaneous_lock = threading.Lock()    # 70%/10% 觸發：同時只能一個，否則跳過
        self._bot_username: str | None = None        # 啟動後第一次訊息時 lazy fetch 並快取
        self._chat_histories: dict[str, list[tuple[str, str]]] = {}  # chat_id → [(user, bot), ...]

        # LINE setup
        self.line_api = None
        self.line_handler = None
        if LINE_SDK_AVAILABLE and LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN:
            self.line_handler = WebhookHandler(LINE_CHANNEL_SECRET)
            line_config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
            self.line_api = MessagingApi(ApiClient(line_config))

            @self.line_handler.add(MessageEvent, message=TextMessageContent)
            def on_message(event):
                self.handle_line_event(event)

            logger.info("LINE Bot 已啟用")
        else:
            logger.info("LINE Bot 未啟用（缺少 LINE_CHANNEL_SECRET 或 LINE_CHANNEL_ACCESS_TOKEN）")

        # 每日倒數畢業排程
        if LINE_GROUP_ID:
            self._graduation_state_path = (
                Path(__file__).resolve().parents[1] / "data" / "graduation_state.json"
            )
            self._news_cache_path = (
                Path(__file__).resolve().parents[1] / "data" / "news_cache.json"
            )
            self._scheduler = BackgroundScheduler(daemon=True)
            self._scheduler.add_job(
                self.send_daily_graduation_message,
                trigger='cron',
                hour=9,
                minute=0,
                id='graduation_countdown',
                misfire_grace_time=600,
                coalesce=True,
            )
            self._scheduler.add_job(
                self._watchdog_graduation_push,
                trigger='cron',
                hour=9,
                minute=5,
                id='graduation_watchdog',
                misfire_grace_time=3600,
                coalesce=True,
            )
            self._scheduler.add_job(
                self._run_weekly_crawl_and_index,
                trigger='cron',
                day_of_week='sun',
                hour=3,
                minute=0,
                id='weekly_ptt_update',
                misfire_grace_time=3600,
                coalesce=True,
            )
            self._scheduler.start()
            logger.info(f"[GRADUATION] 排程已啟動，目標群組: {LINE_GROUP_ID}，畢業日: {GRADUATION_DATE}")
        else:
            logger.warning("[GRADUATION] LINE_GROUP_ID 未設定，倒數排程不啟動")

    # ── Telegram handlers ──────────────────────────────────────────────────

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("笑死，又來一個魯蛇。想問什麼快說啦，我很忙。")

    async def handle_telegram_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_text = update.message.text
        if not user_text:
            return

        if not self._bot_username:
            self._bot_username = (await context.bot.get_me()).username
        bot_username = self._bot_username
        mentioned = f"@{bot_username}" in user_text
        clean_text = re.sub(rf'@{bot_username}\s*', '', user_text).strip()

        if mentioned and not clean_text:
            await update.message.reply_text("叫我幹嘛，沒事滾開。")
            return

        if should_trigger(clean_text, always=mentioned):
            chat_id = str(update.effective_chat.id)
            response = await self.generate_response(clean_text, chat_id=chat_id)
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
        # 只清除 bot 自己的 @mention，其他人的保留
        clean_text = user_text
        if mention and mention.mentionees:
            for m in sorted(mention.mentionees, key=lambda x: x.index, reverse=True):
                if getattr(m, 'is_self', False):
                    clean_text = clean_text[:m.index] + clean_text[m.index + m.length:]
            clean_text = clean_text.strip()

        # 純 @mention 沒有附文字，直接嗆回不過 LLM
        if is_mentioned and not clean_text:
            qt = event.message.quote_token
            self.line_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[LineTextMessage(text="叫我幹嘛，沒事滾開。", **({'quote_token': qt} if qt else {}))],
                )
            )
            return

        if event.source.type == "group":
            group_id = getattr(event.source, 'group_id', 'unknown')
            logger.info(f"[GROUP_ID] source group_id={group_id}")
        logger.info(f"LINE clean_text: {repr(clean_text)}, is_mentioned={is_mentioned}")
        if should_trigger(clean_text, always=(is_direct or is_mentioned)):
            reply_token = event.reply_token
            quote_token = event.message.quote_token
            # chat_id：群組用 group_id，私訊用 user_id，讓歷史不同 chat 不互通
            line_chat_id = (
                getattr(event.source, 'group_id', None)
                or getattr(event.source, 'user_id', None)
                or 'line_unknown'
            )

            def do_reply(response):
                try:
                    msg = LineTextMessage(text=response, **({'quote_token': quote_token} if quote_token else {}))
                    self.line_api.reply_message(
                        ReplyMessageRequest(reply_token=reply_token, messages=[msg])
                    )
                    logger.info(f"LINE reply 成功: {repr(response[:30])}")
                except Exception as e:
                    logger.error(f"LINE reply 失敗: {e}")

            if is_direct or is_mentioned:
                # @mention / 私訊：排隊一定回（reply token 30 秒內有效）
                def reply_mention():
                    with self._llm_sem:
                        response = asyncio.run(self.generate_response(clean_text, chat_id=line_chat_id))
                    do_reply(response)
                threading.Thread(target=reply_mention, daemon=True).start()
            else:
                # 30%/10% 觸發：搶不到 lock 就跳過
                def reply_spontaneous():
                    if not self._spontaneous_lock.acquire(blocking=False):
                        logger.info("spontaneous 觸發跳過（已有處理中）")
                        return
                    try:
                        response = asyncio.run(self.generate_response(clean_text, chat_id=line_chat_id))
                        do_reply(response)
                    finally:
                        self._spontaneous_lock.release()
                threading.Thread(target=reply_spontaneous, daemon=True).start()

    # ── Core logic ─────────────────────────────────────────────────────────

    def get_relevant_snippets(self, query, n_results=3):
        try:
            results = self.collection.query(query_texts=[query], n_results=n_results * 2)
            docs = results['documents'][0] if results['documents'] else []
            if len(docs) > n_results:
                docs = random.sample(docs, n_results)
            return docs
        except Exception as e:
            logger.error(f"檢索失敗: {e}")
            return []

    async def generate_response(self, user_text, chat_id: str | None = None):
        if not self.llm:
            return "笑死，連 Key 都沒有，你比我還窮。"

        import time
        t0 = time.time()

        snippets = self.get_relevant_snippets(user_text)
        rag_context = "\n".join(snippets) if snippets else ""

        cached_news = self._load_news_cache() if hasattr(self, "_news_cache_path") else []
        news_hint = ""
        if cached_news and random.random() < 0.5:
            headline = random.choice(cached_news)
            news_hint = f"今日時事（可以扯進來也可以不扯）：「{headline}」\n\n"

        user_prompt = (
            f"以下是 PTT 鄉民的發言風格範例：\n{_sample_examples()}\n\n"
            + (f"相關 PTT 語料（參考風格用）：\n{rag_context}\n\n" if rag_context else "")
            + news_hint
            + f"網友說：「{user_text}」\nPTT 酸民的回應（一句話，不要解釋）："
        )

        # 建構訊息列表，注入最近 3 輪對話歷史
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if chat_id:
            for hist_user, hist_bot in self._chat_histories.get(chat_id, [])[-3:]:
                messages.append({"role": "user", "content": hist_user})
                messages.append({"role": "assistant", "content": hist_bot})
        messages.append({"role": "user", "content": user_prompt})

        try:
            for attempt in range(3):
                try:
                    resp = await self.llm.chat.completions.create(
                        model=GENERATION_MODEL_NAME,
                        messages=messages,
                        temperature=1.0,
                        max_tokens=80,
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
            result = self._sanitize_response(raw_text)
            # 儲存到對話歷史（最多保留 5 輪）
            if chat_id:
                history = self._chat_histories.setdefault(chat_id, [])
                history.append((user_text, result))
                if len(history) > 5:
                    self._chat_histories[chat_id] = history[-5:]
            return result
        except Exception as e:
            logger.error(f"生成失敗: {e}")
            return "懶得理你，自己想。"

    REFUSAL_PATTERNS = re.compile(
        r'抱歉|我不能|無法協助|不適合|不應該|I cannot|I can\'t|I\'m sorry|sorry', re.IGNORECASE
    )
    REFUSAL_REPLIES = [
        "懶得理你，自己想。",
        "問這幹嘛，沒意義。",
        "笑死，這也要問。",
        "廢話少說。",
        "自己查啦，魯蛇。",
    ]

    def _sanitize_response(self, text):
        if not text:
            return "笑死，懶得理你。"
        clean_text = text.strip()
        clean_text = re.sub(r'^([→推噓]|鄉民推：)\s*', '', clean_text)
        lines = [line.strip() for line in clean_text.split('\n') if line.strip()]
        if not lines:
            return "滾回去洗碗啦。"
        first = lines[0]
        if self.REFUSAL_PATTERNS.search(first):
            return random.choice(self.REFUSAL_REPLIES)
        return first

    def _load_graduation_state(self) -> dict:
        try:
            return json.loads(self._graduation_state_path.read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_graduation_state(self, state: dict):
        self._graduation_state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._graduation_state_path.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self._graduation_state_path)

    def _save_news_cache(self, topics: list[str]) -> None:
        try:
            path = self._news_cache_path
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"date": date.today().isoformat(), "topics": topics}
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
            logger.info(f"[NEWS_CACHE] 已儲存 {len(topics)} 則新聞快取")
        except Exception as e:
            logger.warning(f"[NEWS_CACHE] 儲存失敗: {e}")

    def _load_news_cache(self) -> list[str]:
        try:
            data = json.loads(self._news_cache_path.read_text(encoding="utf-8"))
            if data.get("date") != date.today().isoformat():
                return []
            return data.get("topics", [])
        except Exception as e:
            logger.warning(f"[NEWS_CACHE] 載入失敗: {e}")
            return []

    def _fetch_trending_topics(self, limit: int = 5, timeout: float = 5.0) -> list[str]:
        """抓台灣 Google News 焦點新聞標題，作為倒數時事素材。失敗回 []。

        來源：Google News RSS (zh-TW/TW)，免費、免 key、台灣本地化。
        """
        try:
            url = "https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            req = urllib.request.Request(url, headers={"User-Agent": "SassyBot/1.0 (+graduation-countdown)"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            root = ET.fromstring(data)
            channel = root.find("channel")
            if channel is None:
                return []
            titles: list[str] = []
            for item in channel.findall("item"):
                t = item.find("title")
                if t is None or not t.text:
                    continue
                # Google News 標題常是 "標題 | 來源"，取 | 前當主標
                title = t.text.split("|")[0].strip()
                if title and title not in titles:
                    titles.append(title)
                if len(titles) >= limit:
                    break
            logger.info(f"[GRADUATION] 抓到 {len(titles)} 則時事: {titles[:3]}...")
            return titles
        except Exception as e:
            logger.warning(f"[GRADUATION] 抓時事失敗 (fallback 空): {e}")
            return []

    def _run_weekly_crawl_and_index(self):
        """每週日凌晨 3:00 自動爬取近 8 天 PTT 新文章並重建向量索引。"""
        project_root = Path(__file__).resolve().parents[1]
        crawler_dir = project_root / "PTT-Crawler-master"
        indexer_script = project_root / "indexer.py"
        target_date = (date.today() - timedelta(days=8)).isoformat()

        logger.info(f"[WEEKLY_CRAWL] 開始爬取 PTT（target_date={target_date}）...")
        try:
            crawl_code = (
                f"import sys; sys.path.insert(0, r'{crawler_dir}'); "
                f"from Crawler import PttCrawler; "
                f"PttCrawler().crawl_by_date(board='Gossiping', target_date='{target_date}')"
            )
            subprocess.run(
                [sys.executable, "-c", crawl_code],
                cwd=str(crawler_dir),
                check=True,
                timeout=3600,
            )
            logger.info("[WEEKLY_CRAWL] 爬蟲完成，開始重建向量索引...")
            subprocess.run(
                [sys.executable, str(indexer_script)],
                cwd=str(project_root),
                check=True,
                timeout=7200,
            )
            logger.info("[WEEKLY_CRAWL] 索引重建完成。")
        except subprocess.TimeoutExpired:
            logger.error("[WEEKLY_CRAWL] 超時，本週跳過。")
        except subprocess.CalledProcessError as e:
            logger.error(f"[WEEKLY_CRAWL] 失敗 (returncode={e.returncode}): {e}")
        except Exception as e:
            logger.error(f"[WEEKLY_CRAWL] 未預期錯誤: {e}")

    def _push_line_with_retry(self, message_text: str) -> bool:
        # _request_timeout=10.0：原本無 timeout，曾卡 16 分鐘才被 server 斷線
        for attempt in range(2):
            try:
                self.line_api.push_message(
                    PushMessageRequest(
                        to=LINE_GROUP_ID,
                        messages=[LineTextMessage(text=message_text)],
                    ),
                    _request_timeout=10.0,
                )
                if attempt == 1:
                    logger.info(f"[GRADUATION] 第二次重試推送成功: {repr(message_text)}")
                return True
            except Exception as e:
                logger.warning(f"[GRADUATION] 推送失敗 (attempt {attempt+1}/2): {e}")
                if attempt == 0:
                    time.sleep(2)
        return False

    def _watchdog_graduation_push(self):
        """09:05 補推 watchdog：若今日 state 不是 success/in_progress，重跑整個流程。"""
        _IN_PROGRESS_STALE_SECONDS = 480  # 主 job 正常 < 30s，給 8min buffer
        today = date.today().isoformat()
        state = self._load_graduation_state()
        status = state.get("status") if state.get("date") == today else None

        if status == "success":
            logger.info("[GRADUATION][WATCHDOG] 今日已成功推送，no-op")
            return

        if status == "in_progress":
            ts_str = state.get("ts", "")
            try:
                ts = datetime.fromisoformat(ts_str)
                age = (datetime.now() - ts).total_seconds()
            except (ValueError, TypeError):
                age = 999999
            if age < _IN_PROGRESS_STALE_SECONDS:
                logger.info(f"[GRADUATION][WATCHDOG] 主 job in_progress 中（{age:.0f}s），跳過")
                return
            logger.warning(f"[GRADUATION][WATCHDOG] in_progress 卡死（{age:.0f}s > {_IN_PROGRESS_STALE_SECONDS}s），接管補推")
        else:
            logger.warning(f"[GRADUATION][WATCHDOG] 今日狀態={status or 'missing'}，補推")

        self.send_daily_graduation_message()

    def send_daily_graduation_message(self):
        """每天 09:00 推送鄉民風倒數畢業訊息到 LINE 群組。"""
        if not self.line_api or not LINE_GROUP_ID:
            logger.warning("[GRADUATION] LINE API 未初始化或 LINE_GROUP_ID 未設定，跳過推送")
            return

        today_iso = date.today().isoformat()
        state = self._load_graduation_state()
        if state.get("date") == today_iso and state.get("status") == "success":
            logger.info(f"[GRADUATION] 今日 ({today_iso}) 已成功推送，跳過")
            return

        # Mark in_progress 鎖，防止 watchdog 與主 job 並發推送
        self._save_graduation_state({
            "date": today_iso,
            "status": "in_progress",
            "ts": datetime.now().isoformat(timespec='seconds'),
        })

        today = date.today()
        days_remaining = (GRADUATION_DATE - today).days

        if days_remaining <= 0:
            message_text = "已畢業了幹，還在這邊傳訊息"
            logger.info("[GRADUATION] 已畢業，推送固定訊息")
        elif not self.llm:
            message_text = f"還有 {days_remaining} 天，繼續撐啊廢物"
        else:
            topics = self._fetch_trending_topics(limit=5)
            self._save_news_cache(topics)
            topics_section = ""
            if topics:
                bullets = "\n".join(f"- {t}" for t in topics)
                topics_section = f"\n以下是今天台灣熱門新聞：\n{bullets}\n"
            user_prompt = (
                f"今天距離畢業還有 {days_remaining} 天。{topics_section}"
                "\n寫一句 PTT 鄉民風畢業倒數。"
                "可以挑一則新聞扯上畢業（颱風/比賽/時事/政治隨你挑），"
                "找不到聯想就純粹講畢業倒數也行。"
                "要酸、要簡短、不超過兩句。"
            )
            try:
                async def _call_llm():
                    for attempt in range(3):
                        try:
                            resp = await self.llm.chat.completions.create(
                                model=GENERATION_MODEL_NAME,
                                messages=[
                                    {"role": "system", "content": SYSTEM_PROMPT},
                                    {"role": "user", "content": user_prompt},
                                ],
                                temperature=1.0,
                            )
                            return resp.choices[0].message.content or ""
                        except Exception as e:
                            if "429" in str(e) and attempt < 2:
                                logger.warning(f"[GRADUATION] 429 rate limit，5s 後重試 (attempt {attempt+1})")
                                await asyncio.sleep(5)
                            else:
                                raise

                raw = asyncio.run(_call_llm())
                if not raw or not raw.strip():
                    raise ValueError("LLM 回傳空字串")
                message_text = self._sanitize_response(raw)
                logger.info(f"[GRADUATION] LLM 生成: {repr(message_text)}")
            except Exception as e:
                logger.error(f"[GRADUATION] LLM 失敗，使用 fallback: {e}")
                message_text = f"還有 {days_remaining} 天，繼續撐啊廢物"

        success = self._push_line_with_retry(message_text)
        new_state = {
            "date": today_iso,
            "message": message_text,
            "status": "success" if success else "failed",
            "ts": datetime.now().isoformat(timespec='seconds'),
        }
        self._save_graduation_state(new_state)
        if success:
            logger.info(f"[GRADUATION] 推送成功: {repr(message_text)}")
        else:
            logger.error(f"[GRADUATION] 推送失敗 (含 retry)，state 已記錄，等 09:05 watchdog 補推")


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

    logger.info(f"LINE webhook server 啟動於 port {LINE_WEBHOOK_PORT}")
    flask_app.run(host="0.0.0.0", port=LINE_WEBHOOK_PORT, threaded=True)


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
