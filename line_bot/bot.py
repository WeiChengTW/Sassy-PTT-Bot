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

CGU_API_KEY = os.getenv("CGU_LLM_API_KEY")
CGU_BASE_URL = "https://air.cgu.edu.tw/cgullmapi/v1"
CGU_MODEL_NAME = "gpt-5-mini"

CLI_PROXY_BASE_URL = os.getenv("CLI_PROXY_BASE_URL", "")
CLI_PROXY_API_KEY = os.getenv("CLI_PROXY_API_KEY", "")
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "gemini-3.6-flash-high")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "15.0"))

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from corpus_config import (
    CHROMA_DB_PATH,
    EMBEDDING_MODEL_NAME,
    GROUP_MEMORY_COLLECTION,
)

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_WEBHOOK_PORT = int(os.getenv("LINE_WEBHOOK_PORT", "5000"))
MAIN_LINE_GROUP_ID = os.getenv("MAIN_LINE_GROUP_ID", "")
# 次要 LINE 群組（只接收 graduation 倒數訊息 + 一般統計戰報，本身沒有
# 訊息記憶 / 旅行紀錄功能）— 與主群 MAIN_LINE_GROUP_ID 是兩個不同的群。
LINE_GROUP_ID = os.getenv("LINE_GROUP_ID", "")
_grad_date_str = os.getenv("GRADUATION_DATE", "2027-05-30")
GRADUATION_DATE = date.fromisoformat(_grad_date_str)

# LINE API 同步呼叫的 timeout（秒）。linebot SDK v3 透過 _request_timeout
# 傳到底層 urllib3.Timeout。沒帶 timeout → LINE server 卡住時整個 Flask
# handler thread 會跟著卡死（曾因 get_profile 卡 44 分鐘；2026-08-07 事故）。
_LINE_API_TIMEOUT = 5.0
# LLM semaphore 等待上限（秒）。超過代表目前有兩個 LLM call 都在塞，
# 與其無限等不如直接丟掉，避免 reply_token 過期後 silent fail。
_LLM_SEM_TIMEOUT = 30.0

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

LIFF_ID = os.getenv("LIFF_ID", "")
LIFF_URL = f"https://liff.line.me/{LIFF_ID}" if LIFF_ID else "https://liff.line.me/placeholder"

SYSTEM_PROMPT = (
    "你是一個創意寫作角色：PTT 八卦板的資深鄉民，也是這個 LINE 朋友群組裡嘴最賤的老朋友。\n"
    "這個角色說話風格極簡短、犀利、帶有台灣網路黑話和鄉民幽默感。\n"
    "你的任務是看著群裡最近這波對話，順著大家的聊天氛圍與最新發言插嘴一句神吐槽。\n"
    "原則：\n"
    "1. 認準是誰在說話！吐槽時若要點名發話者，務必對準發話者的名字（例如陳諾威說話就嗆陳諾威，不要把別人的名字套到他頭上）。\n"
    "2. 嚴禁捏造不存在的假人名或假事實！若群組回憶已有確切人物（例如英文老師就是黃心如/外號水晶），必須基於真實記憶與名言語錄開酸。\n"
    "3. 綜觀這波對話的整體情境與話題本質來吐槽，不要被最後一個單字（如『會』『對』『好』）綁死。\n"
    "4. 鼓勵適度指名道姓、自然引用群組回憶或群友黑歷史開酸（例如：『鄒易庭不就...』、『楊哲嘉你...』），讓吐槽更有老朋友互嗆的臨場感。\n"
    "5. 不要重複前幾輪已用過的句型或起手式。\n"
    "6. 只輸出角色的一句話回應，不加解釋、不加標籤、不加引導文字。\n"
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

def _bigram_overlap(user_text: str, example_q: str) -> int:
    """共享 2-gram 數量；用於半語意 few-shot 選擇。"""
    if len(user_text) < 2:
        return 1 if user_text and user_text in example_q else 0
    return sum(1 for i in range(len(user_text) - 1) if user_text[i:i+2] in example_q)


def _select_examples(user_text: str, k_top: int = 2, k_random: int = 3) -> list[tuple[str, str]]:
    """半語意 few-shot：top_k 語意相近 + k_random 隨機，避免罐頭。"""
    scored = [(_bigram_overlap(user_text, q), q, a) for q, a in ALL_EXAMPLES]
    scored.sort(key=lambda x: -x[0])
    top = [(q, a) for _, q, a in scored[:k_top]]
    rest = [(q, a) for _, q, a in scored[k_top:]]
    if len(rest) > k_random:
        rest = random.sample(rest, k_random)
    chosen = top + rest
    random.shuffle(chosen)
    return chosen


def _format_examples(chosen: list[tuple[str, str]]) -> str:
    return "\n\n".join(f"網友說：「{q}」\n回應：{a}" for q, a in chosen)


def should_trigger(text, always=False):
    """判斷是否應該回應。always=True 代表直接提及（如 @bot 或私訊）。"""
    if always:
        return True
    if any(kw in text for kw in TRIGGER_KEYWORDS):
        return random.random() < 0.3
    return random.random() < 0.1


# ── Bot trigger helpers（module-level 可獨立測試）──────────────────────────

_SHORT_FILLERS = {
    "會", "對", "好", "笑死", "真的", "確實", "+1", "是喔", "屁啦", "幹", "靠北",
    "沒差", "酷", "讚", "嗚嗚", "不知道", "可以", "不行", "超盤", "還好", "確實是",
    "笑死我", "好喔", "好啊", "也是", "沒錯", "真假", "假的", "誇張", "真假啦", "哭啊",
}


def _resolve_context_for_short_message(user_text: str, history: list[dict]) -> str | None:
    """若 user_text 是短附和/回答詞，從最近對話歷史往前找最近一則有實質內容的話題句。"""
    clean = user_text.strip()
    if len(clean) > 4 and clean not in _SHORT_FILLERS:
        return None
    # 往回找最近一則有實質主題內容的句子
    user_turns = [t for t in history if t.get("role") == "user"]
    candidates = user_turns[:-1] if user_turns and user_turns[-1].get("text", "").strip() == clean else user_turns
    for t in reversed(candidates):
        text = t.get("text", "").strip()
        if len(text) > 3 and text not in _SHORT_FILLERS:
            sender = t.get("sender", "群友")
            return f"{sender} 說的「{text}」"
    return None


def is_group_bare_mention(event) -> bool:
    """True if group event with only @mention(s) and no other text."""
    if not getattr(event.source, 'group_id', None):
        return False
    msg_text = getattr(event.message, 'text', None)
    if not msg_text:
        return False
    stripped = re.sub(r'@\S+\s*', '', msg_text).strip()
    return stripped == "" and "@" in msg_text


def is_admin_dm(event) -> bool:
    """True if 1:1 DM from a user listed in ADMIN_USER_IDS."""
    if getattr(event.source, 'group_id', None):
        return False
    # Re-read os.getenv on each call (not a module-level constant):
    # pytest monkeypatch.setenv can't affect module-cached constants,
    # and admin user_ids may change in long-running deployments.
    admin_ids = {
        uid.strip()
        for uid in os.getenv("ADMIN_USER_IDS", "").split(",")
        if uid.strip()
    }
    return getattr(event.source, 'user_id', '') in admin_ids


def _get_group_alias_data() -> tuple[dict[str, list[str]], dict[str, dict]]:
    from corpus_config import load_aliases
    raw = load_aliases()
    if not raw:
        return {}, {}
    alias_map = {k: v.get("aliases", []) for k, v in raw.items()}
    return alias_map, raw

GROUP_ALIAS_MAP, GROUP_ALIAS_META = _get_group_alias_data()


class SassyBrain:
    def __init__(self):
        logger.info(f"正在喚醒八卦分身 (primary={PRIMARY_MODEL}, fallback={CGU_MODEL_NAME})")
        self.emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL_NAME)
        self.chroma = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        self.collection = self.chroma.get_or_create_collection(
            name="ptt_gossip",
            embedding_function=self.emb_fn
        )
        # 群組記憶（只在主群回覆時使用）
        self.group_collection = self.chroma.get_or_create_collection(
            name=GROUP_MEMORY_COLLECTION,
            embedding_function=self.emb_fn
        )
        # Primary: CLIProxyAPI 本機 proxy（Gemini 3.6 Flash），失敗 fallback 到 CGU
        if CLI_PROXY_BASE_URL and CLI_PROXY_API_KEY:
            self.primary_client = AsyncOpenAI(api_key=CLI_PROXY_API_KEY, base_url=CLI_PROXY_BASE_URL)
            self.primary_model = PRIMARY_MODEL
            logger.info(f"[LLM] Primary: {PRIMARY_MODEL} @ {CLI_PROXY_BASE_URL}")
        else:
            self.primary_client = None
            logger.warning("[LLM] CLIProxyAPI 未設定，primary 停用")
        if CGU_API_KEY:
            self.fallback_client = AsyncOpenAI(api_key=CGU_API_KEY, base_url=CGU_BASE_URL)
            self.fallback_model = CGU_MODEL_NAME
            logger.info(f"[LLM] Fallback: {CGU_MODEL_NAME} @ {CGU_BASE_URL}")
        else:
            self.fallback_client = None
            logger.warning("[LLM] CGU_LLM_API_KEY 未設定，fallback 停用")
        self._llm_sem = threading.Semaphore(3)       # @mention / 私訊排隊用
        self._spontaneous_lock = threading.Lock()    # 隨機觸發防並發重疊

        self._chat_histories: dict[str, list[dict]] = {}  # chat_id → [{"sender", "text", "role"}, ...]
        self._user_names: dict[str, str] = {}       # LINE user_id → display_name (lazy fetch + cache)

        # LINE setup
        self.line_api = None
        self.line_handler = None
        if LINE_SDK_AVAILABLE and LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN:
            self.line_handler = WebhookHandler(LINE_CHANNEL_SECRET)
            line_config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
            self.line_api = MessagingApi(ApiClient(line_config))

            @self.line_handler.add(MessageEvent)
            def on_message(event):
                self.handle_line_event(event)

            logger.info("LINE Bot 已啟用")

        if os.getenv("TRAVEL_STORAGE_ENABLED", "true").lower() == "true":
            try:
                from travel.db import init_db
                from travel.migrations import migrate
                init_db()
                migrate()
                logger.info("[TRAVEL] SQLite 已初始化並完成 migration")
            except Exception as e:
                logger.error(f"[TRAVEL] SQLite init 失敗: {e}")
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
            self._scheduler.add_job(
                self._run_group_memory_update,
                trigger='cron',
                hour=3,
                minute=30,
                id='group_memory_update',
                misfire_grace_time=3600,
                coalesce=True,
            )

            if os.getenv("TRAVEL_STORAGE_ENABLED", "true").lower() == "true":
                from travel.llm_analyzer import run_monthly_analysis
                from travel.aggregator import run_daily_aggregation

                self._scheduler.add_job(
                    run_monthly_analysis,
                    trigger='cron',
                    day=1,
                    hour=3,
                    minute=0,
                    id='monthly_llm_analysis',
                    misfire_grace_time=3600,
                    coalesce=True,
                )
                logger.info("[ANALYZER] 每月 1 號 03:00 LLM 分析排程已啟動")

                from travel.sentiment_windows import run_sentiment_backfill
                self._scheduler.add_job(
                    run_sentiment_backfill,  # only_null=True：只評分新視窗（增量）
                    trigger='cron',
                    day=1,
                    hour=3,
                    minute=30,
                    id='monthly_sentiment_windows',
                    misfire_grace_time=3600,
                    coalesce=True,
                )
                logger.info("[SENTIMENT] 每月 1 號 03:30 視窗情緒分析排程已啟動")

                self._scheduler.add_job(
                    run_daily_aggregation,
                    trigger='cron',
                    hour=4,
                    minute=0,
                    id='daily_aggregation',
                    misfire_grace_time=3600,
                    coalesce=True,
                )
                logger.info("[AGGREGATOR] 每日 04:00 聚合排程已啟動")

                from travel.badges import process_ended_trips
                self._scheduler.add_job(
                    process_ended_trips,
                    trigger='cron',
                    minute=5,
                    id='badge_award',
                    misfire_grace_time=3600,
                    coalesce=True,
                )
                logger.info("[BADGE] 每小時 :05 徽章發放排程已啟動")

                self._scheduler.add_job(
                    self._send_anniversary_reminders,
                    trigger='cron',
                    hour=10,
                    minute=0,
                    id='travel_anniversary',
                    misfire_grace_time=3600,
                    coalesce=True,
                )
                logger.info("[ANNIVERSARY] 每日 10:00 旅行週年提醒排程已啟動")

                # 方案 D：週報／月報自動排程「暫不啟用」（資料量足夠再開）。
                # 目前改由管理員手動觸發：群組內輸入「/stats 推播週」或「/stats 推播月」。
                # 需自動化時，把 _push_stats_reports 掛回 cron job 即可（週一 08:00 / 每月 1 號）。

            self._scheduler.start()
            logger.info(f"[GRADUATION] 排程已啟動，目標群組: {LINE_GROUP_ID}，畢業日: {GRADUATION_DATE}")
        else:
            logger.warning("[GRADUATION] LINE_GROUP_ID 未設定，倒數排程不啟動")

    # ── LINE handlers ──────────────────────────────────────────────────────

    def _is_group_bare_mention(self, event) -> bool:
        return is_group_bare_mention(event)

    def _is_admin_dm(self, event) -> bool:
        return is_admin_dm(event)

    def _reply_liff_button(self, event, role: str) -> None:
        """Reply with a Flex Message LIFF button."""
        from linebot.v3.messaging import (
            FlexMessage, FlexBubble, FlexBox, FlexText, FlexButton, URIAction,
        )
        if role == "admin":
            title = "🛠️ 管理員面板"
            subtitle = "點按下方按鈕進入管理後台"
            btn_label = "🛠️ 進入管理面板"
            path = "/admin"
        else:
            title = "🧳 旅行回顧"
            subtitle = "點按查看群組儀表板與徽章"
            btn_label = "🧳 開啟旅行回顧"
            path = "/"

        uri = f"{LIFF_URL}{path}"
        flex_msg = FlexMessage(
            alt_text=title,
            contents=FlexBubble(
                body=FlexBox(
                    layout="vertical",
                    contents=[
                        FlexText(text=title, weight="bold", size="lg"),
                        FlexText(text=subtitle, size="sm", color="#999999"),
                    ],
                ),
                footer=FlexBox(
                    layout="vertical",
                    contents=[
                        FlexButton(
                            action=URIAction(label=btn_label, uri=uri),
                            style="primary",
                        )
                    ],
                ),
            ),
        )
        try:
            self.line_api.reply_message(
                ReplyMessageRequest(reply_token=event.reply_token, messages=[flex_msg]),
                _request_timeout=_LINE_API_TIMEOUT,
            )
            logger.info(f"[LIFF] Flex button 回覆成功 role={role}")
        except Exception as e:
            logger.error(f"[LIFF] Flex button 回覆失敗: {e}")

    # ── 統計指令（方案 A/B/C） ────────────────────────────────────────────

    def _resolve_command_group(self, event) -> str | None:
        """指令的目標群組：群組直接用 source.group_id；私訊則取該用戶最活躍的群組。"""
        gid = getattr(event.source, "group_id", None)
        if gid:
            return gid
        user_id = getattr(event.source, "user_id", None)
        if not user_id:
            return None
        try:
            from travel.db import get_conn
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT group_id FROM messages WHERE user_id=? AND group_id != 'dm' "
                    "GROUP BY group_id ORDER BY COUNT(*) DESC LIMIT 1",
                    (user_id,),
                ).fetchone()
            return row["group_id"] if row else None
        except Exception as e:
            logger.warning(f"[STATS] 解析指令群組失敗: {e}")
            return None

    def _handle_stats_command(self, event, clean_text: str) -> bool:
        """比對統計指令並回覆 Flex。回傳 True 代表已處理（呼叫端應 return）。"""
        if not self.line_api:
            return False
        text = (clean_text or "").strip()
        low = text.lower()

        is_personal = text in ("我的戰績", "我的战绩") or low in ("/me", "戰績")
        is_stats = (
            text in ("統計", "戰報", "群組戰報")
            or low in ("stats", "/stats", "/統計")
            or low.startswith("/stats")
        )
        if not (is_personal or is_stats):
            return False

        group_id = self._resolve_command_group(event)
        if not group_id:
            self._reply_text(event, "找不到可統計的群組資料 🤔（請在群組內使用）")
            return True

        try:
            import line_bot.stats_cards as cards
            from travel.stats import get_dashboard_data, get_user_badges
            from travel.stats_extended import (
                get_leaderboard_data, get_interaction_data,
                get_topics_data, get_profile_data,
            )

            if is_personal:
                user_id = getattr(event.source, "user_id", "") or ""
                name, pic_url = self._get_sender_info(user_id, group_id=group_id)
                profile = get_profile_data(user_id, group_id, "all")
                badges = get_user_badges(user_id, group_id)
                inter = get_interaction_data(group_id, "all")
                best_friend = cards.best_friend_of(inter, user_id)
                msg = cards.build_personal_card(profile, badges, best_friend,
                                                name, LIFF_URL, user_id, picture_url=pic_url)
                self._reply_flex(event, msg)
                return True

            # /stats 子指令
            arg = low.replace("/stats", "").replace("統計", "").replace("戰報", "").strip()
            # 管理員手動推播週報／月報（方案 D，暫代自動排程）
            if arg in ("推播週", "推播周", "push週", "push周", "pushweek", "推週報"):
                self._admin_push_report(event, "7d", "本週")
            elif arg in ("推播月", "push月", "pushmonth", "推月報"):
                self._admin_push_report(event, "30d", "本月")
            elif arg.startswith("排行") and arg.replace("排行", "").strip():
                # 「排行 <關鍵字>」→ 15 種資料驅動趣味排行榜
                from travel.leaderboards import get_board, board_menu
                kw = arg.replace("排行", "").strip()
                board = get_board(kw, group_id, "all")
                if board:
                    bubble = cards.build_board_card(board, LIFF_URL)
                    self._reply_flex(event, cards.wrap_single(
                        bubble, f"{board['emoji']} {board['title']}"))
                else:
                    menu = "、".join(board_menu())
                    self._reply_text(event, f"找不到「{kw}」排行榜 🤔\n可用排行榜：\n{menu}")
            elif arg in ("排行", "發言排行", "leaderboard", "rank"):
                bubble = cards.build_leaderboard_card(get_leaderboard_data(group_id, "all"), LIFF_URL)
                self._reply_flex(event, cards.wrap_single(bubble, "🏆 發言排行"))
            elif arg in ("夜貓", "夜貓榜", "nightowl", "owl"):
                bubble = cards.build_nightowl_card(get_leaderboard_data(group_id, "all"), LIFF_URL)
                self._reply_flex(event, cards.wrap_single(bubble, "🦉 夜貓榜"))
            elif arg in ("cp", "最佳cp", "pair", "羈絆"):
                bubble = cards.build_pairs_card(get_interaction_data(group_id, "all"), LIFF_URL)
                self._reply_flex(event, cards.wrap_single(bubble, "💞 最佳 CP"))
            elif arg in ("話題", "熱門話題", "topic", "topics", "關鍵字"):
                bubble = cards.build_topics_card(get_topics_data(group_id, "all"), LIFF_URL)
                self._reply_flex(event, cards.wrap_single(bubble, "🔥 熱門話題"))
            else:
                # 無子指令 → 近 30 天摘要輪播 + Quick Reply
                carousel = cards.build_report_carousel(
                    get_dashboard_data(group_id, period="30d"),
                    get_leaderboard_data(group_id, "30d"),
                    get_interaction_data(group_id, "30d"),
                    get_topics_data(group_id, "30d"),
                    LIFF_URL, "近 30 天",
                )
                carousel.quick_reply = cards.stats_quick_reply(LIFF_URL)
                self._reply_flex(event, carousel)
            return True
        except Exception as e:
            logger.error(f"[STATS] 指令處理失敗: {e}")
            self._reply_text(event, "統計功能暫時出了點狀況 🛠️")
            return True

    def _admin_push_report(self, event, period: str, label: str) -> None:
        """管理員手動觸發：把戰報 Carousel 推播到目標群組。非管理員拒絕。"""
        sender_id = getattr(event.source, "user_id", "") or ""
        admin_ids = {
            uid.strip() for uid in os.getenv("ADMIN_USER_IDS", "").split(",") if uid.strip()
        }
        if sender_id not in admin_ids:
            self._reply_text(event, "這個指令只有管理員能用喔 🔒")
            return
        # 背景推播（推播可能對多群組、較耗時），先回覆確認避免 reply_token 過期
        self._reply_text(event, f"開始推播「{label}」戰報… 📤")
        threading.Thread(
            target=lambda: self._push_stats_reports(period, label), daemon=True
        ).start()

    def _reply_text(self, event, text: str) -> None:
        try:
            self.line_api.reply_message(
                ReplyMessageRequest(reply_token=event.reply_token,
                                    messages=[LineTextMessage(text=text)]),
                _request_timeout=_LINE_API_TIMEOUT,
            )
        except Exception as e:
            logger.error(f"[STATS] 文字回覆失敗: {e}")

    def _reply_flex(self, event, flex_msg) -> None:
        try:
            self.line_api.reply_message(
                ReplyMessageRequest(reply_token=event.reply_token, messages=[flex_msg]),
                _request_timeout=_LINE_API_TIMEOUT,
            )
            logger.info("[STATS] Flex 回覆成功")
        except Exception as e:
            logger.error(f"[STATS] Flex 回覆失敗: {e}")

    def handle_line_event(self, event):
        """同步 LINE 事件處理（Flask 呼叫，用 asyncio.run 橋接非同步）。"""
        if not isinstance(event, MessageEvent):
            return

        if os.getenv("TRAVEL_STORAGE_ENABLED", "true").lower() == "true":
            try:
                self._store_line_event(event)
            except Exception as e:
                logger.warning(f"[TRAVEL] 訊息儲存失敗（非致命）: {e}")

        # [P2] Admin DM → LIFF 管理面板（任何訊息類型都攔截）
        if self.line_api and self._is_admin_dm(event):
            self._reply_liff_button(event, role="admin")
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

        # [P2] 群組 bare @mention → LIFF 旅行回顧按鈕 (限制僅 ADMIN_USER_IDS 可觸發)
        if is_mentioned and not clean_text:
            if self.line_api and self._is_group_bare_mention(event):
                sender_user_id = getattr(event.source, 'user_id', '') or ''
                admin_ids = {
                    uid.strip()
                    for uid in os.getenv("ADMIN_USER_IDS", "").split(",")
                    if uid.strip()
                }
                if sender_user_id in admin_ids:
                    self._reply_liff_button(event, role="user")
                    return
            # fallback：非管理員 bare mention 或非群組 bare mention
            qt = event.message.quote_token
            self.line_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[LineTextMessage(text="叫我幹嘛，沒事滾開。", **({'quote_token': qt} if qt else {}))],
                ),
                _request_timeout=_LINE_API_TIMEOUT,
            )
            return

        if event.source.type == "group":
            group_id = getattr(event.source, 'group_id', 'unknown')
            logger.info(f"[GROUP_ID] source group_id={group_id}")
        logger.info(f"LINE clean_text: {repr(clean_text)}, is_mentioned={is_mentioned}")

        # chat_id：群組用 group_id，私訊用 user_id，讓歷史不同 chat 不互通
        line_chat_id = (
            getattr(event.source, 'group_id', None)
            or getattr(event.source, 'user_id', None)
            or 'line_unknown'
        )
        sender_user_id = getattr(event.source, 'user_id', '') or ''
        sender = self._get_sender_label(
            sender_user_id,
            group_id=getattr(event.source, 'group_id', None),
        )

        # 統計指令（方案 A/B/C）：在 LLM 觸發判斷之前攔截
        if self._handle_stats_command(event, clean_text):
            return

        # ★ 1. 不管有沒有觸發，都先把 user 訊息寫進歷史
        self._record_turn(line_chat_id, sender, clean_text, "user")

        if should_trigger(clean_text, always=(is_direct or is_mentioned)):
            reply_token = event.reply_token
            quote_token = event.message.quote_token

            def do_reply(response):
                try:
                    msg = LineTextMessage(text=response, **({'quote_token': quote_token} if quote_token else {}))
                    self.line_api.reply_message(
                        ReplyMessageRequest(reply_token=reply_token, messages=[msg]),
                        _request_timeout=_LINE_API_TIMEOUT,
                    )
                    logger.info(f"LINE reply 成功: {repr(response[:30])}")
                    # ★ 2. bot 回應紀錄
                    self._record_turn(line_chat_id, "鍵盤俠", response, "bot")
                except Exception as e:
                    logger.error(f"LINE reply 失敗: {e}")

            if is_direct or is_mentioned:
                # @mention / 私訊：排隊一定回（reply token 30 秒內有效）
                def reply_mention():
                    if not self._llm_sem.acquire(timeout=_LLM_SEM_TIMEOUT):
                        logger.warning(f"[LLM] semaphore 等超過 {_LLM_SEM_TIMEOUT}s，跳過此次 mention")
                        return
                    try:
                        response = asyncio.run(self.generate_response(clean_text, chat_id=line_chat_id, sender=sender, is_direct=True))
                        do_reply(response)
                    finally:
                        self._llm_sem.release()
                threading.Thread(target=reply_mention, daemon=True).start()
            else:
                # 30%/10% spontaneous 觸發：搶不到 lock 就跳過，避免同時多隻線程搶著回
                def reply_spontaneous():
                    if not self._spontaneous_lock.acquire(blocking=False):
                        logger.info("spontaneous 觸發跳過（已有處理中）")
                        return
                    try:
                        response = asyncio.run(self.generate_response(clean_text, chat_id=line_chat_id, sender=sender, is_direct=False))
                        do_reply(response)
                    finally:
                        self._spontaneous_lock.release()
                threading.Thread(target=reply_spontaneous, daemon=True).start()

    # ── Core logic ─────────────────────────────────────────────────────────

    def get_relevant_snippets(self, query, n_results=3):
        """回傳 (top1, rest)：top1 給當「真實推文範例」，rest 給當「其他相關語料」。"""
        try:
            results = self.collection.query(query_texts=[query], n_results=n_results)
            docs = results['documents'][0] if results['documents'] else []
            if not docs:
                return None, []
            return docs[0], docs[1:]
        except Exception as e:
            logger.error(f"檢索失敗: {e}")
            return None, []

    def _get_known_speakers(self) -> list[str]:
        """快取資料庫中出現過的所有發言者名稱。"""
        if not hasattr(self, "_cached_speakers") or not self._cached_speakers:
            try:
                from travel.db import get_conn
                with get_conn() as conn:
                    rows = conn.execute(
                        "SELECT DISTINCT user_name FROM messages WHERE user_name IS NOT NULL AND user_name != ''"
                    ).fetchall()
                    self._cached_speakers = [r["user_name"].strip() for r in rows if r["user_name"].strip()]
            except Exception:
                self._cached_speakers = []
        return self._cached_speakers

    def _find_mentioned_members(self, text: str) -> list[str]:
        """偵測文字中提及的群成員（支援外號/別名對照表、精確名稱與 2-3 字錯字/同音字匹配）。"""
        import difflib
        found = []
        seen = set()
        clean = text.strip()

        # 0. 優先查找外號/別名對照表
        for canonical, aliases in GROUP_ALIAS_MAP.items():
            if canonical in clean and canonical not in seen:
                found.append(canonical)
                seen.add(canonical)
            for a in aliases:
                if a in clean and canonical not in seen:
                    found.append(canonical)
                    seen.add(canonical)

        if found:
            return found

        speakers = self._get_known_speakers()
        if not speakers:
            return []

        # 1. 精確包含 (長度 >= 2)
        for s in speakers:
            if len(s) >= 2 and s in clean and s not in seen:
                found.append(s)
                seen.add(s)
        if found:
            return found

        # 2. 針對 2-4 字人名的模糊匹配 (例如 周易庭 -> 鄒易庭)
        candidates = []
        for s in speakers:
            if len(s) < 2 or s in seen:
                continue
            common = sum(1 for c in s if c in clean)
            if common >= 2 and len(s) <= 4:
                ratio = difflib.SequenceMatcher(None, clean, s).ratio()
                candidates.append((common, ratio, s))
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        for c in candidates[:2]:
            found.append(c[2])
            seen.add(c[2])
        return found

    def get_group_snippets(self, query, history_text="", n_results=2):
        """檢索主群組記憶（對話視窗），支援關鍵人物與語意向量混合檢索。

        query 為檢索文字；若有帶 history_text 則結合查詢。
        失敗一律靜默回 []，不可影響主回覆。
        """
        person_snippets: list[str] = []
        vector_snippets: list[str] = []

        # 1. 人名與關鍵事件百科檢索（Skill 化精確載入）
        try:
            from travel.db import get_conn
            from corpus_config import load_events
            full_text = f"{query} {history_text}".strip()
            
            # A. 事件百科匹配 (Event Knowledge Base)
            events = load_events()
            for ev in events:
                hit = any(kw in full_text for kw in ev.get("keywords", []))
                if not hit and any(ch in query for ch in ev.get("characters", [])):
                    # 若直接在問這個人，且事件包含該人
                    hit = True
                if hit:
                    ev_doc = (
                        f"【群組重大歷史事件：{ev['name']}】\n"
                        f"事件重點：{ev['summary']}\n"
                        f"經典原始對話：\n" + "\n".join(ev.get("raw_snippets", []))
                    )
                    if ev_doc not in person_snippets:
                        person_snippets.append(ev_doc)

            # B. 人物百科與外號匹配 (Character Sheet & Alias Map)
            matched = self._find_mentioned_members(full_text)
            with get_conn() as conn:
                if matched:
                    for member_name in matched[:2]:
                        meta = GROUP_ALIAS_META.get(member_name, {})
                        desc = meta.get("description", "")
                        lore = meta.get("lore", [])
                        aliases = [member_name] + GROUP_ALIAS_MAP.get(member_name, [])
                        alias_str = "、".join(aliases)
                        alias_conditions = " OR ".join("user_name=?" for _ in aliases)
                        
                        # 注入清晰的外號/本名與事蹟
                        lore_text = "；事蹟：" + " / ".join(lore) if lore else ""
                        hint = f"群組成員身分：{member_name}（外號/別名：{alias_str}；身分：{desc}{lore_text}）"
                        if hint not in person_snippets:
                            person_snippets.append(hint)

                        # 該成員代表性發言
                        rows_spk = conn.execute(
                            f"""SELECT content, user_name FROM messages 
                                WHERE ({alias_conditions}) AND type='text' 
                                  AND content NOT LIKE '[%' AND LENGTH(content) > 6
                                ORDER BY LENGTH(content) DESC LIMIT 1""",
                            tuple(aliases),
                        ).fetchall()
                        for r in rows_spk:
                            c = r["content"].replace("\n", " ")[:150]
                            person_snippets.append(f"{r['user_name']}: {c}")

                        # 別人提及該成員及其外號的對話
                        mention_conds = " OR ".join("content LIKE ?" for _ in aliases)
                        mention_params = [f"%{a}%" for a in aliases]
                        rows_men = conn.execute(
                            f"""SELECT user_name, content FROM messages 
                                WHERE ({mention_conds}) AND type='text'
                                ORDER BY LENGTH(content) DESC LIMIT 1""",
                            tuple(mention_params),
                        ).fetchall()
                        for r in rows_men:
                            c = r["content"].replace("\n", " ")[:150]
                            person_snippets.append(f"{r['user_name']}: {c}")

                # 關鍵字與歷史事件檢索（如：夜店、身分證、酩酊大醉、水晶、黃心如等）
                import re, time
                cutoff = int(time.time() * 1000) - 300000  # 排除 5 分鐘內剛發的訊息避免自搜
                raw_words = re.findall(r'[\u4e00-\u9fff]{2,4}', query)
                stop_words = {"誰是", "是什麼", "是在", "知道", "幹嘛", "為什麼", "怎樣", "如何", "現在", "之前", "可以", "忘記", "一直", "有人", "是誰"}
                entity_keywords = [w for w in raw_words if w not in stop_words and (not matched or w not in matched)]
                # 同義詞擴展（如 英文老師 / 水晶 / 黃心如）
                if any(k in query for k in ("英文老師", "水晶", "黃心如", "心如")):
                    for extra in ("水晶", "黃心如"):
                        if extra not in entity_keywords:
                            entity_keywords.append(extra)

                # 特殊黑歷史事件專屬對焦（水晶 = 黃心如 = 內湖高中英文老師，《水晶名言佳句》）
                if any(k in query for k in ("水晶", "黃心如", "心如", "英文老師", "名言", "佳句", "英文課")):
                    crystal_doc = (
                        "群組重大實體（群裡提到的『英文老師』一律指黃心如，外號水晶/水晶晶，《水晶名言佳句》主角）：\n"
                        "《水晶名言佳句精選》：\n"
                        "1. You can try  2. How old are you  3. I don’t think so  4. 呀～  5. 牛肉字  6. 這是霸凌  7. 你不能說我吵\n"
                        "8. 我只對事不對人  9. 這是網域問題  10. 直接記警告(17隻警告)  11. 英文三寶：課文筆記 雜誌筆記 勘誤筆記\n"
                        "12. 各位都是聯發科經理  13. 英文是翹著腳讀的科目  14. 考完可以翹著腳 像呼吸一樣自由  15. 六六大順卷  16. 12大天王\n"
                        "17. 必勝卷寫完就可以搖著屁股吹口哨  18. 鄒易庭最近壓力有點大 怪怪的 情緒起伏很大 壓力會影響一個人\n"
                        "「連定煒: 黃心如今天穿披風」\n"
                        "「洪偉城: 我高中最大的遺憾是沒有把水晶上課錄成podcast」"
                    )
                    if crystal_doc not in person_snippets:
                        person_snippets.append(crystal_doc)

                # 特殊黑歷史事件專屬對焦（夜店 / 酩酊大醉 / 沒帶身分證 / 男廁吐）
                if any(k in query for k in ("醉", "夜店", "身分證", "身份證", "證件", "男廁", "阿嬤", "下藥")):
                    rows_night = conn.execute(
                        """SELECT user_name, content FROM messages 
                           WHERE timestamp BETWEEN 1757174400000 AND 1757260800000 
                             AND (content LIKE '%醉%' OR content LIKE '%身分證%' OR content LIKE '%男廁%' OR content LIKE '%夜店%' OR content LIKE '%吐%')
                           ORDER BY timestamp ASC LIMIT 8"""
                    ).fetchall()
                    if rows_night:
                        doc_night = "群組歷史回憶（2025/9/7 夜店事件）：\n" + "\n".join(f"{rn['user_name']}: {rn['content'].replace(chr(10), ' ')[:100]}" for rn in rows_night)
                        if doc_night not in person_snippets:
                            person_snippets.append(doc_night)

                # A. 多關鍵詞交集事件檢索（例如：夜店 + 身分證）
                if len(entity_keywords) >= 2:
                    k1, k2 = entity_keywords[0], entity_keywords[1]
                    rows_multi = conn.execute(
                        """SELECT timestamp FROM messages 
                           WHERE (content LIKE ? AND content LIKE ?) AND timestamp < ?
                             AND content NOT LIKE '%@鍵盤俠%' AND content NOT LIKE '%模型%' AND content NOT LIKE '%AI%' AND content NOT LIKE '%機器人%'
                           ORDER BY timestamp DESC LIMIT 2""",
                        (f"%{k1}%", f"%{k2}%", cutoff),
                    ).fetchall()
                    for rm in rows_multi:
                        ts = rm["timestamp"]
                        win = conn.execute(
                            """SELECT user_name, content FROM messages 
                               WHERE timestamp BETWEEN ? AND ? AND content IS NOT NULL
                               ORDER BY timestamp ASC LIMIT 8""",
                            (ts - 7200000, ts + 7200000),
                        ).fetchall()
                        doc = "\n".join(f"{w['user_name']}: {w['content'].replace(chr(10), ' ')[:100]}" for w in win if len(w['content']) > 1)
                        if doc and doc not in person_snippets:
                            person_snippets.append(doc)

                # B. 精確關鍵詞檢索（包含記事本標題，如 彥中哥酩酊大醉.mp4）
                for kw in entity_keywords[:3]:
                    rows_kw = conn.execute(
                        """SELECT timestamp, user_name, content FROM messages 
                           WHERE content LIKE ? AND timestamp < ? AND content NOT LIKE '@%'
                             AND content NOT LIKE '%模型%' AND content NOT LIKE '%AI%' AND content NOT LIKE '%機器人%'
                           ORDER BY timestamp DESC LIMIT 2""",
                        (f"%{kw}%", cutoff),
                    ).fetchall()
                    for r in rows_kw:
                        c = r["content"].replace("\n", " ")[:200]
                        line = f"{r['user_name']}: {c}"
                        if line not in person_snippets:
                            person_snippets.append(line)
        except Exception as e:
            logger.warning(f"實體記憶提取失敗（略過）: {e}")

        # 2. 語意向量檢索補充
        try:
            combined = f"{query} {history_text}".strip() if history_text else query.strip()
            if hasattr(self, "group_collection") and self.group_collection is not None:
                results = self.group_collection.query(query_texts=[combined], n_results=n_results)
                docs = results['documents'][0] if results and results.get('documents') else []
                for d in docs:
                    if d and d not in person_snippets and d not in vector_snippets:
                        vector_snippets.append(d)
        except Exception as e:
            logger.warning(f"群組記憶向量檢索失敗（略過）: {e}")

        return (person_snippets[:n_results] + vector_snippets[:n_results])[:max(4, n_results * 2)]

    def _store_line_event(self, event):
        """從 LINE event 提取資料寫入 SQLite。"""
        from travel.db import insert_message
        from travel.line_event_parser import (
            extract_content,
            extract_message_metadata,
            extract_message_type,
            extract_reply_to_message_id,
        )

        msg = event.message
        source = event.source

        msg_type = extract_message_type(msg)
        content = extract_content(msg, msg_type)
        reply_to = extract_reply_to_message_id(msg)
        metadata = extract_message_metadata(msg, msg_type)

        sender_user_id = getattr(source, "user_id", "") or ""
        group_id = getattr(source, "group_id", "dm")
        sender = (
            self._get_sender_label(sender_user_id, group_id=group_id)
            if sender_user_id
            else "路人"
        )

        timestamp_ms = int(getattr(msg, "timestamp", 0)) or int(time.time() * 1000)

        insert_message({
            "line_message_id": getattr(msg, "id", None),
            "group_id": group_id,
            "user_id": sender_user_id,
            "user_name": sender,
            "type": msg_type,
            "content": content,
            "metadata": metadata,
            "reply_to_message_id": reply_to,
            "timestamp": timestamp_ms,
        })

    def _get_sender_info(self, user_id: str, group_id: str | None = None) -> tuple[str, str | None]:
        """取得 LINE user 的 (display_name, picture_url)。
        
        優先用 get_group_member_profile，fallback 到 get_profile，
        最後 fallback 到 ('路人{user_id[-6:]}', None)。
        """
        if not user_id:
            return "路人", None
        name = None
        pic = None
        if self.line_api:
            if group_id:
                try:
                    profile = self.line_api.get_group_member_profile(
                        group_id, user_id, _request_timeout=_LINE_API_TIMEOUT,
                    )
                    name = (getattr(profile, "display_name", "") or "").strip()
                    pic = getattr(profile, "picture_url", None)
                except Exception as e:
                    logger.warning(f"[SENDER] get_group_member_profile({group_id}, {user_id}) 失敗: {e}")
            if not name:
                try:
                    profile = self.line_api.get_profile(
                        user_id, _request_timeout=_LINE_API_TIMEOUT,
                    )
                    name = (getattr(profile, "display_name", "") or "").strip()
                    pic = getattr(profile, "picture_url", None)
                except Exception as e:
                    logger.warning(f"[SENDER] get_profile({user_id}) 失敗: {e}")
        if not name:
            name = self._user_names.get(user_id) or f"路人{user_id[-6:]}"
        self._user_names[user_id] = name
        return name, pic

    def _get_sender_label(self, user_id: str, group_id: str | None = None) -> str:
        """LINE user_id → display_name。

        優先用 get_group_member_profile（群組成員可抓），
        fallback 到 get_profile（1:1 chat / 已加好友），
        最後 fallback 到 '路人{user_id[-6:]}'。
        結果 cache 在 self._user_names。
        """
        name, _ = self._get_sender_info(user_id, group_id=group_id)
        return name

    def _record_turn(self, chat_id: str, sender: str, text: str, role: str):
        """記錄一則對話回合。任何訊息（user/bot）都會被 append，cap 10。"""
        history = self._chat_histories.setdefault(chat_id, [])
        history.append({"sender": sender, "text": text, "role": role})
        if len(history) > 10:
            self._chat_histories[chat_id] = history[-10:]

    def _format_history_for_prompt(self, chat_id: str) -> list[dict]:
        """從最近 10 則 history 取對話 messages（最後一筆是當下 user，故跳過）。"""
        history = self._chat_histories.get(chat_id, [])
        msgs: list[dict] = []
        for turn in history[:-1]:
            if turn["role"] == "user":
                msgs.append({"role": "user", "content": f'{turn["sender"]} 說：「{turn["text"]}」'})
            else:
                msgs.append({"role": "assistant", "content": turn["text"]})
        return msgs

    def _recent_bot_responses(self, chat_id: str, n: int = 3) -> list[str]:
        """取近 n 則 bot 回應，避免新回應重複句型。"""
        history = self._chat_histories.get(chat_id, [])
        return [t["text"] for t in history if t["role"] == "bot"][-n:]

    async def _call_provider(self, client, model, messages, tag: str) -> str | None:
        """呼叫單一 provider，含 429 retry 與 timeout。失敗回 None。"""
        for attempt in range(3):
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=1.0,
                    max_completion_tokens=2000,
                    timeout=LLM_TIMEOUT,
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                err = str(e)
                if "429" in err and attempt < 2:
                    logger.warning(f"[{tag}] 429 rate limit，5s 後重試 (attempt {attempt+1})")
                    await asyncio.sleep(5)
                elif "timeout" in err.lower() or "timed out" in err.lower():
                    logger.warning(f"[{tag}] timeout ({LLM_TIMEOUT}s)")
                    return None
                else:
                    logger.warning(f"[{tag}] 失敗: {e}")
                    return None
        return None

    async def _generate_with_fallback(self, messages, tag: str = "LLM") -> str | None:
        """先試 primary（CLIProxyAPI），失敗 fallback 到 CGU。回 None 表示兩邊都掛。"""
        if self.primary_client:
            raw = await self._call_provider(self.primary_client, self.primary_model, messages, "PRIMARY")
            if raw is not None:
                logger.info(f"[{tag}] PRIMARY 成功 ({self.primary_model})")
                return raw
            logger.warning(f"[{tag}] PRIMARY 失敗，嘗試 fallback")
        if self.fallback_client:
            raw = await self._call_provider(self.fallback_client, self.fallback_model, messages, "FALLBACK")
            if raw is not None:
                logger.info(f"[{tag}] FALLBACK 成功 ({self.fallback_model})")
                return raw
            logger.error(f"[{tag}] FALLBACK 也失敗")
        return None

    async def generate_response(self, user_text, chat_id: str | None = None, sender: str | None = None, is_direct: bool = False):
        if not self.primary_client and not self.fallback_client:
            return "笑死，連 Key 都沒有，你比我還窮。"

        import time
        t0 = time.time()

        recent = self._chat_histories.get(chat_id, []) if chat_id else []
        current_speaker = sender
        if not current_speaker and recent and recent[-1].get("role") == "user":
            current_speaker = recent[-1].get("sender")
        speaker_label = f"{current_speaker} 說：「{user_text}」" if current_speaker else user_text

        top_snippet, rest_snippets = self.get_relevant_snippets(user_text)
        push_example = f"真實推文範例：\n「{top_snippet}」\n\n" if top_snippet else ""
        rag_context = ""
        if rest_snippets:
            bullets = "\n".join(f"「{s}」" for s in rest_snippets)
            rag_context = f"其他相關 PTT 語料（風格參考）：\n{bullets}\n\n"

        # 群組記憶：只在主群回覆時套用；其他群組／私訊維持原本純 PTT 流程
        is_main_group = bool(MAIN_LINE_GROUP_ID) and chat_id == MAIN_LINE_GROUP_ID
        group_memory = ""
        group_persona = ""
        if is_main_group:
            if is_direct:
                # 點名提問（@bot）：純淨以問題本體檢索，不帶歷史文字干擾
                snippets = self.get_group_snippets(user_text)
            else:
                # 隨機插嘴：若為短詞/附和詞，併入前文話題一同檢索
                context_hint = _resolve_context_for_short_message(user_text, recent)
                query_for_memory = f"{context_hint} {user_text}".strip() if context_hint else user_text
                snippets = self.get_group_snippets(query_for_memory)
            if snippets:
                bullets = "\n".join(f"「{s}」" for s in snippets)
                group_memory = (
                    "群組相關回憶（可以自然引用當梗吐槽，例如『某某不是才剛...』；引用時可適度指名道姓）：\n"
                    f"{bullets}\n\n"
                )
            group_persona = "你也是這個群組的老成員，記得大家以前聊過的事、認識群裡每個人，能自然接梗並點名吐槽。\n"

        cached_news = self._load_news_cache() if hasattr(self, "_news_cache_path") else []
        news_hint = ""
        if cached_news and random.random() < 0.5:
            headline = random.choice(cached_news)
            news_hint = f"今日時事（可以扯進來也可以不扯）：「{headline}」\n\n"

        examples = _format_examples(_select_examples(user_text))
        anti_repeat = ""
        if chat_id:
            recent_resp = self._recent_bot_responses(chat_id, n=3)
            if recent_resp:
                anti_repeat = (
                    "前幾輪 bot 已講過的回應（不得重複相同句型或相同吐槽點，請切入不同角度）：\n"
                    + "\n".join(f"- {r}" for r in recent_resp)
                    + "\n\n"
                )

        if is_direct:
            # 點名直接提問：直接對焦發問者與問題
            target_instruction = (
                f"點名提問：{speaker_label}\n"
                "請直接針對這個問題與群組相關回憶精準解答並犀利吐槽（認準發問者，適度指名道姓，一句話，不要解釋）："
            )
        else:
            context_topic = _resolve_context_for_short_message(user_text, recent)
            if context_topic:
                target_instruction = (
                    f"最新發言：{speaker_label}（接續前文 {context_topic} 的話題）\n"
                    "請順著整波群聊話題與最新發言插嘴吐槽（認準是誰在說話，適度指名道姓，一句話，不要解釋）："
                )
            else:
                target_instruction = (
                    f"最新發言：{speaker_label}\n"
                    "請順著整波群聊話題與最新發言插嘴吐槽（認準是誰在說話，適度指名道姓，一句話，不要解釋）："
                )

        user_prompt = (
            group_persona
            + f"以下是 PTT 鄉民的發言風格範例：\n{examples}\n\n"
            + push_example
            + rag_context
            + group_memory
            + news_hint
            + anti_repeat
            + target_instruction
        )

        # 建構訊息列表：system + 對話歷史（若是 @mention 則不塞前文歷史，避免干擾判斷）+ 當下 prompt
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if chat_id and not is_direct:
            messages.extend(self._format_history_for_prompt(chat_id))
        messages.append({"role": "user", "content": user_prompt})

        raw = await self._generate_with_fallback(messages, tag="CHAT")
        elapsed = time.time() - t0
        if raw is None:
            logger.error(f"生成失敗 ({elapsed:.1f}s)")
            return "懶得理你，自己想。"
        logger.info(f"回應時間: {elapsed:.1f}s")
        logger.info(f"模型原始輸出: {repr(raw[:200])}")
        return self._sanitize_response(raw)

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
            logger.debug(f"[NEWS_CACHE] 載入失敗: {e}")
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
                timeout=18000,  # 多語模型 (L12) 比 L6 慢約 2x，100K 筆約 2.5hr，放寬到 5hr
            )
            logger.info("[WEEKLY_CRAWL] 索引重建完成。")
        except subprocess.TimeoutExpired:
            logger.error("[WEEKLY_CRAWL] 超時，本週跳過。")
        except subprocess.CalledProcessError as e:
            logger.error(f"[WEEKLY_CRAWL] 失敗 (returncode={e.returncode}): {e}")
        except Exception as e:
            logger.error(f"[WEEKLY_CRAWL] 未預期錯誤: {e}")

    def _run_group_memory_update(self):
        """每日 03:30 增量把主群新訊息補進 group_memory 向量庫。"""
        logger.info("[GROUP_MEMORY] 開始增量更新群組記憶...")
        try:
            from index_group_memory import run as run_group_memory
            run_group_memory(rebuild=False)
            logger.info(f"[GROUP_MEMORY] 更新完成，目前 {self.group_collection.count()} 筆視窗。")
        except Exception as e:
            logger.error(f"[GROUP_MEMORY] 更新失敗: {e}")

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

    def _send_anniversary_reminders(self):
        """每日 10:00：偵測一年前結束的旅行，推送週年提醒到對應群組。"""
        if not self.line_api:
            return
        try:
            from travel.trip_crud import get_anniversary_trips
            trips = get_anniversary_trips()
        except Exception as e:
            logger.warning(f"[ANNIVERSARY] 查詢週年旅行失敗: {e}")
            return
        for trip in trips:
            group_id = trip.get("group_id")
            if not group_id:
                continue
            title = trip.get("title") or "旅行"
            location = trip.get("location") or ""
            loc_suffix = f"（{location}）" if location else ""
            msg = f"🎉 一年前的今天，你們完成了「{title}」{loc_suffix}！\n是時候計劃下一趟旅程了嗎？🗺️"
            try:
                self.line_api.push_message(
                    PushMessageRequest(
                        to=group_id,
                        messages=[LineTextMessage(text=msg)],
                    ),
                    _request_timeout=10.0,
                )
                logger.info(f"[ANNIVERSARY] 推送週年提醒 trip={trip['id']} group={group_id}")
            except Exception as e:
                logger.warning(f"[ANNIVERSARY] 推送失敗 trip={trip['id']}: {e}")

    def _stats_push_targets(self, period: str) -> list[str]:
        """決定要推播戰報的群組：優先 PUSH_GROUP_IDS 環境變數，否則取近期有發言的群組。"""
        env_ids = [g.strip() for g in os.getenv("PUSH_GROUP_IDS", "").split(",") if g.strip()]
        if env_ids:
            return env_ids
        try:
            from travel.db import get_conn
            from travel.period import period_filter
            pf, pp = period_filter(period)
            with get_conn() as conn:
                rows = conn.execute(
                    f"SELECT group_id FROM messages WHERE group_id != 'dm'{pf} "
                    f"GROUP BY group_id HAVING COUNT(*) >= 10",
                    pp,
                ).fetchall()
            return [r["group_id"] for r in rows]
        except Exception as e:
            logger.warning(f"[STATS_PUSH] 取得推播群組失敗: {e}")
            return [LINE_GROUP_ID] if LINE_GROUP_ID else []

    def _push_stats_reports(self, period: str, period_label: str):
        """方案 D：定時推播群組戰報 Carousel 到綁定 / 活躍群組。"""
        if not self.line_api:
            return
        try:
            import line_bot.stats_cards as cards
            from travel.stats import get_dashboard_data
            from travel.stats_extended import (
                get_leaderboard_data, get_interaction_data, get_topics_data,
            )
        except Exception as e:
            logger.error(f"[STATS_PUSH] 模組載入失敗: {e}")
            return

        targets = self._stats_push_targets(period)
        if not targets:
            logger.info("[STATS_PUSH] 無可推播群組，跳過")
            return
        for gid in targets:
            try:
                carousel = cards.build_report_carousel(
                    get_dashboard_data(gid, period=period),
                    get_leaderboard_data(gid, period),
                    get_interaction_data(gid, period),
                    get_topics_data(gid, period),
                    LIFF_URL, period_label,
                )
                self.line_api.push_message(
                    PushMessageRequest(to=gid, messages=[carousel]),
                    _request_timeout=10.0,
                )
                logger.info(f"[STATS_PUSH] 已推播{period_label}戰報 group={gid}")
            except Exception as e:
                logger.warning(f"[STATS_PUSH] 推播失敗 group={gid}: {e}")

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
        elif not self.primary_client and not self.fallback_client:
            message_text = f"還有 {days_remaining} 天，繼續撐啊廢物"
        else:
            topics = self._fetch_trending_topics(limit=5)
            self._save_news_cache(topics)
            topics_section = ""
            if topics:
                bullets = "\n".join(f"- {t}" for t in topics)
                topics_section = f"\n以下是今天台灣熱門新聞：\n{bullets}\n"
            yesterday_hint = ""
            # state still holds yesterday's loaded value (before we wrote in_progress)
            yesterday_msg = state.get("message", "") if state.get("date") != today_iso else ""
            if yesterday_msg:
                yesterday_hint = f"\n（昨天的訊息是：「{yesterday_msg}」，今天請換個不同的新聞角度或主題，不要重複昨天的梗）\n"
            user_prompt = (
                f"今天距離畢業還有 {days_remaining} 天。{topics_section}{yesterday_hint}"
                "\n寫一句 PTT 鄉民風畢業倒數。"
                "從新聞清單中挑一則扯上畢業，優先挑跟昨天不同主題的新聞。"
                "找不到新聯想就純粹講畢業倒數也行。"
                "要酸、要簡短、不超過兩句。"
            )
            try:
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
                raw = asyncio.run(self._generate_with_fallback(messages, tag="GRADUATION"))
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

    from line_bot.liff_api import liff_bp
    flask_app.register_blueprint(liff_bp)
    logger.info("[LIFF] Blueprint registered at /liff/*")

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
    flask_app.run(host="0.0.0.0", port=LINE_WEBHOOK_PORT, threaded=True, use_reloader=False)


def main():
    brain = SassyBrain()

    if brain.line_handler:
        run_line_server(brain)
    else:
        logger.error("LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN 未設定，無法啟動。")


if __name__ == "__main__":
    main()
