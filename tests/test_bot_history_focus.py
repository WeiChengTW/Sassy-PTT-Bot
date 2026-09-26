"""測試 bot 回應聚焦最新觸發句、歷史僅為背景的 prompt 調整。"""
import asyncio

import pytest


def _bare_brain():
    """建立不跑 __init__ 的 SassyBrain（避免 Chroma/LLM 依賴）。"""
    from line_bot.bot import SassyBrain
    brain = object.__new__(SassyBrain)
    brain._chat_histories = {}
    return brain


# ─── SYSTEM_PROMPT ──────────────────────────────────────────────────────────

def test_system_prompt_instructs_reply_to_latest_only():
    from line_bot.bot import SYSTEM_PROMPT
    assert "插嘴一句神吐槽" in SYSTEM_PROMPT
    assert "綜觀這波對話" in SYSTEM_PROMPT
    assert "指名道姓" in SYSTEM_PROMPT


# ─── _format_history_for_prompt ────────────────────────────────────────────

def test_history_turns_marked_as_past_context():
    brain = _bare_brain()
    brain._chat_histories["C1"] = [
        {"sender": "A", "text": "牛牛牧場", "role": "user"},
        {"sender": "鍵盤俠", "text": "太野了", "role": "bot"},
        {"sender": "B", "text": "最新觸發句", "role": "user"},
    ]
    msgs = brain._format_history_for_prompt("C1")
    assert len(msgs) == 2
    assert "A 說：「牛牛牧場」" in msgs[0]["content"]
    assert "太野了" in msgs[1]["content"]


def test_history_skips_latest_turn():
    brain = _bare_brain()
    brain._chat_histories["C1"] = [
        {"sender": "A", "text": "舊話題", "role": "user"},
        {"sender": "B", "text": "最新觸發句", "role": "user"},
    ]
    msgs = brain._format_history_for_prompt("C1")
    # 最新一則 user 不進歷史（由 user_prompt 帶）
    assert len(msgs) == 1
    assert "舊話題" in msgs[0]["content"]


# ─── generate_response user_prompt ─────────────────────────────────────────

def test_user_prompt_marks_current_message_and_memory_condition(monkeypatch):
    from unittest.mock import patch
    from line_bot.bot import MAIN_LINE_GROUP_ID

    brain = _bare_brain()
    brain._chat_histories["C1"] = [
        {"sender": "A", "text": "誰有班群完整的記憶", "role": "user"},
        {"sender": "B", "text": "陳諾威 我換手機了", "role": "user"},
        {"sender": "C", "text": "絕眼", "role": "user"},
    ]

    captured = {}

    async def fake_generate(messages, tag="CHAT"):
        captured["messages"] = messages
        return "測試回應"

    def fake_snippets(query, n_results=3):
        return None, []

    def fake_group_snippets(query, history_text="", n_results=2):
        captured["group_query"] = query
        return ["以前的牛牛牧場視窗"]

    brain.primary_client = object()
    brain.get_relevant_snippets = fake_snippets
    brain.get_group_snippets = fake_group_snippets
    brain._generate_with_fallback = fake_generate
    brain._recent_bot_responses = lambda chat_id, n=3: []
    brain._load_news_cache = lambda: []

    with patch("line_bot.bot.MAIN_LINE_GROUP_ID", "C1"):
        asyncio.run(brain.generate_response("絕眼", chat_id="C1"))

    user_prompt = captured["messages"][-1]["content"]
    assert "最新發言" in user_prompt
    assert "絕眼" in user_prompt
    # 群組記憶描述允許自然引用
    assert "自然引用當梗吐槽" in user_prompt
    # 短詞會結合前文話題
    assert "接續前文" in user_prompt
    assert "陳諾威 我換手機了" in captured["group_query"]


# ─── get_group_snippets 合併檢索 ───────────────────────────────────────────

def test_get_group_snippets_combines_trigger_and_history():
    """觸發句太短時，用「觸發句 + 最近歷史」合併查詢，提高記憶命中率。"""
    from line_bot.bot import SassyBrain

    captured = {}

    class FakeCollection:
        def query(self, query_texts, n_results, include=None, where=None):
            captured["query_texts"] = query_texts
            captured["n_results"] = n_results
            captured["where"] = where
            return {"documents": [["記憶一", "記憶二"]], "metadatas": [[{"last_ts": None}, {"last_ts": None}]]}

    brain = object.__new__(SassyBrain)
    brain._reranker = False  # 略過 reranker
    brain.group_collection = FakeCollection()
    brain._event_inject_ts = {}
    brain._person_inject_ts = {}
    out = brain.get_group_snippets("屁眼", history_text="誰有班群完整的記憶 陳諾威 我換手機了")
    assert "記憶一" in out
    assert captured["n_results"] >= 5  # 撈足量候選
    assert captured["where"] is None  # 無時間詞不套過濾
    combined = captured["query_texts"][0]
    assert "屁眼" in combined
    assert "班群" in combined


# ─── _label_snippet_time ────────────────────────────────────────────────────

def test_label_snippet_time_old_ts_adds_prefix():
    """距今超過 180 天的時間戳應加 〔YYYY/MM〕 前綴。"""
    from line_bot.bot import SassyBrain
    import time
    old_ts = int((time.time() - 200 * 86400) * 1000)  # 200 天前
    result = SassyBrain._label_snippet_time("洪偉城: 我去補考了", old_ts)
    assert result.startswith("〔")
    assert "洪偉城: 我去補考了" in result


def test_label_snippet_time_recent_ts_no_prefix():
    """距今不超過 180 天的時間戳不應加前綴。"""
    from line_bot.bot import SassyBrain
    import time
    recent_ts = int((time.time() - 10 * 86400) * 1000)  # 10 天前
    result = SassyBrain._label_snippet_time("王弈尹: 我在韓國", recent_ts)
    assert not result.startswith("〔")
    assert result == "王弈尹: 我在韓國"


def test_label_snippet_time_none_ts_no_prefix():
    """ts_ms=None 時直接回傳原文，不加前綴。"""
    from line_bot.bot import SassyBrain
    result = SassyBrain._label_snippet_time("陳諾威: 出包了", None)
    assert result == "陳諾威: 出包了"


# ─── 暱稱隨機化（_nickname_map / _nickname_prompt）────────────────────────

def test_nickname_map_loaded_from_aliases():
    """aliases.json 的本名→暱稱對照應可讀取，且含已知成員。"""
    from line_bot.bot import SassyBrain
    m = SassyBrain._nickname_map()
    assert "陳諾威" in m
    assert "挪威" in m["陳諾威"]


def test_nickname_prompt_includes_random_nickname():
    """有暱稱的成員應產生含隨機暱稱的稱呼指令。"""
    from line_bot.bot import SassyBrain
    p = SassyBrain._nickname_prompt("陳諾威")
    assert "隨機輪用" in p
    assert "挪威" in p
    assert "陳諾威" in p


def test_nickname_prompt_unknown_name_empty():
    """無暱稱記錄的名字應回傳空字串。"""
    from line_bot.bot import SassyBrain
    assert SassyBrain._nickname_prompt("不存在的人xyz") == ""


# ─── 吐槽點多樣化（_detect_used_insults）──────────────────────────────────

def test_detect_used_insults_finds_repeated_keywords():
    """近幾輪回應含「失智」「夜店」時，應被偵測為已用過的吐槽點。"""
    from line_bot.bot import _detect_used_insults
    resp = ["威哥你失智喔，去夜店忘記帶身分證", "你就繼續肥宅啊"]
    used = _detect_used_insults(resp)
    assert "失智" in used
    assert "夜店" in used
    assert "肥" in used
    assert "甲" not in used


def test_detect_used_insults_empty_when_no_match():
    """無命中關鍵字時回傳空清單。"""
    from line_bot.bot import _detect_used_insults
    assert _detect_used_insults(["天氣不錯", "吃飽了嗎"]) == []


def test_detect_used_insults_dedup():
    """同一關鍵字多次出現只記一次。"""
    from line_bot.bot import _detect_used_insults
    assert _detect_used_insults(["失智", "你真失智"]) == ["失智"]


# ─── 時間過濾（_query_time_filter）─────────────────────────────────────────

def test_query_time_filter_recent_term():
    """含「最近」時應限定 last_ts >= 近 30 天。"""
    from line_bot.bot import SassyBrain
    import time
    f = SassyBrain._query_time_filter("最近大家在哪裡")
    assert f is not None
    assert "last_ts" in f and "$gte" in f["last_ts"]
    assert f["last_ts"]["$gte"] > int((time.time() - 31 * 86400) * 1000)


def test_query_time_filter_past_term():
    """含「高中」時應限定 last_ts <= 30 天前。"""
    from line_bot.bot import SassyBrain
    import time
    f = SassyBrain._query_time_filter("洪偉城高中時發生什麼事")
    assert f is not None
    assert "$lte" in f["last_ts"]
    assert f["last_ts"]["$lte"] < int((time.time() - 29 * 86400) * 1000)


def test_query_time_filter_no_term():
    """無時間詞時不套過濾。"""
    from line_bot.bot import SassyBrain
    assert SassyBrain._query_time_filter("牛牛牧場") is None


# ─── rerank 排序 ─────────────────────────────────────────────────────────────

def test_vector_rerank_reorders_candidates():
    """reranker 存在時，應按 cross-encoder 分數重排後取 top n_results。"""
    from line_bot.bot import SassyBrain

    captured = {}

    class FakeCollection:
        def query(self, query_texts, n_results, include=None, where=None):
            captured["n_results"] = n_results
            captured["where"] = where
            return {
                "documents": [["無關的 A", "相關的 B", "無關的 C"]],
                "metadatas": [[{"last_ts": None}, {"last_ts": None}, {"last_ts": None}]],
            }

    class FakeReranker:
        def predict(self, pairs):
            # 依文件內容給分：B 最高、A 次之、C 最低
            return [0.5, 0.9, 0.1]

    brain = object.__new__(SassyBrain)
    brain.group_collection = FakeCollection()
    brain._reranker = FakeReranker()
    brain._event_inject_ts = {}
    brain._person_inject_ts = {}
    brain._user_names = {}
    out = brain.get_group_snippets("qxzyvip-不存在的中文字串", n_results=1)
    assert "相關的 B" in out[0]
    assert "無關的 A" not in out