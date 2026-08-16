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
        def query(self, query_texts, n_results):
            captured["query_texts"] = query_texts
            captured["n_results"] = n_results
            return {"documents": [["記憶一", "記憶二"]]}

    brain = object.__new__(SassyBrain)
    brain.group_collection = FakeCollection()
    out = brain.get_group_snippets("屁眼", history_text="誰有班群完整的記憶 陳諾威 我換手機了")
    assert "記憶一" in out
    assert captured["n_results"] == 2
    combined = captured["query_texts"][0]
    assert "屁眼" in combined
    assert "班群" in combined