"""群組語料相關共用常數（import_line_export / index_group_memory / bot 共用）。"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

# 已知的機器人 / 非真人發言者：建群組記憶與匯入時都要略過。
KNOWN_BOTS = {"卡米狗", "鍵盤俠", "nonsense", "弈塵 8"}

# 向量庫共用設定：ptt_gossip 與 group_memory 必須用同一個 embedding 模型，
# 因為查詢時用同一段 query text 去打兩個 collection。
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
CHROMA_DB_PATH = str(Path(__file__).resolve().parent / "PTT-Crawler-master" / "chroma_db")

# 主群組 ID：群組記憶只屬於這個群。從 MAIN_LINE_GROUP_ID env 讀，沒設定會在
# import 時直接 raise，避免不小心打到別的群 / 把陌生訊息寫進向量庫。
def _resolve_main_group_id() -> str:
    gid = os.getenv("MAIN_LINE_GROUP_ID", "").strip()
    if not gid:
        raise RuntimeError(
            "MAIN_LINE_GROUP_ID 未設定。請在 .env 填入主群 LINE 群組 ID（從 LINE Developers "
            "Console 或 bot log 的 webhook event 取）。"
        )
    return gid

MAIN_GROUP_ID = _resolve_main_group_id()

# 群組記憶向量庫設定
GROUP_MEMORY_COLLECTION = "group_memory"
GROUP_WINDOW_MAX_MSGS = 8      # 每個對話視窗最多幾則訊息
GROUP_WINDOW_GAP_SEC = 600     # 訊息間隔超過此秒數（10 分鐘）就切新視窗
GROUP_MIN_WINDOW_CHARS = 12    # 視窗內容太短就丟棄（純「好」「哈哈」）

ALIASES_FILE_PATH = Path(__file__).resolve().parent / "data" / "aliases.json"
EVENTS_FILE_PATH = Path(__file__).resolve().parent / "data" / "events.json"


def load_aliases() -> dict[str, dict]:
    """載入群組成員外號與別名設定檔。"""
    import json
    if not ALIASES_FILE_PATH.exists():
        return {}
    try:
        return json.loads(ALIASES_FILE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_events() -> list[dict]:
    """載入群組重大事件百科（含關鍵字、參與者與原始對話 raw_snippets）。"""
    import json
    if not EVENTS_FILE_PATH.exists():
        return []
    try:
        return json.loads(EVENTS_FILE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
