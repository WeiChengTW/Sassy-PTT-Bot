"""群組語料相關共用常數（import_line_export / index_group_memory / bot 共用）。"""
import os
from pathlib import Path

# 已知的機器人 / 非真人發言者：建群組記憶與匯入時都要略過。
KNOWN_BOTS = {"卡米狗", "鍵盤俠", "nonsense", "弈塵 8"}

# 向量庫共用設定：ptt_gossip 與 group_memory 必須用同一個 embedding 模型，
# 因為查詢時用同一段 query text 去打兩個 collection。
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
CHROMA_DB_PATH = str(Path(__file__).resolve().parent / "PTT-Crawler-master" / "chroma_db")

# 主群組 ID：群組記憶只屬於這個群。優先讀 LINE_GROUP_ID，否則用匯出檔對應的固定值。
MAIN_GROUP_ID = os.getenv("LINE_GROUP_ID", "") or "Cba567481e809e13952a49947ad6afea2"

# 群組記憶向量庫設定
GROUP_MEMORY_COLLECTION = "group_memory"
GROUP_WINDOW_MAX_MSGS = 8      # 每個對話視窗最多幾則訊息
GROUP_WINDOW_GAP_SEC = 600     # 訊息間隔超過此秒數（10 分鐘）就切新視窗
GROUP_MIN_WINDOW_CHARS = 12    # 視窗內容太短就丟棄（純「好」「哈哈」）
