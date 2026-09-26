"""群組問答：指令解析、LLM JSON 解析、關鍵字視窗搜尋。"""
from datetime import datetime

from line_bot import group_qa
from line_bot.group_qa import (
    empty_question_reply, parse_intent, parse_qa_command, search_windows, today_label,
)


def test_parse_qa_command():
    assert parse_qa_command("？9/28 幾點") == "9/28 幾點"
    assert parse_qa_command("? 幾點集合") == "幾點集合"
    assert parse_qa_command(" ？？ 幾點") == "幾點"
    assert parse_qa_command("？") == ""
    assert parse_qa_command("你好") is None
    assert parse_qa_command("現在是怎樣？") is None


def test_empty_question_reply():
    assert empty_question_reply()


def test_today_label():
    assert today_label(datetime(2026, 9, 26)) == "2026/09/26（週六）"


def test_parse_intent_json_in_code_fence():
    raw = '```json\n{"question": "9/28 幾點集合", "keywords": ["9/28", "28號", "9/28", " ", "約"]}\n```'
    assert parse_intent(raw, "原問題") == {"question": "9/28 幾點集合", "keywords": ["9/28", "28號"]}


def test_parse_intent_falls_back_on_bad_output():
    out = parse_intent("看不懂", "9/28 烤肉幾點集合")
    assert out["question"] == "9/28 烤肉幾點集合"
    assert "9/28" in out["keywords"]


def _msgs(contents):
    return [{"user_name": "A", "content": c, "type": "text", "timestamp": i}
            for i, c in enumerate(contents)]


def test_search_windows_takes_context_around_hit(monkeypatch):
    monkeypatch.setattr(group_qa, "RADIUS", 2)
    msgs = _msgs(["a", "b", "c", "約個13、14 在山下", "d", "e", "f", "g"])
    [w] = search_windows(msgs, ["山下"])
    assert [m["content"] for m in w] == ["b", "c", "約個13、14 在山下", "d", "e"]


def test_search_windows_merges_overlaps_and_ranks(monkeypatch):
    monkeypatch.setattr(group_qa, "RADIUS", 1)
    monkeypatch.setattr(group_qa, "MAX_WINDOWS", 1)
    contents = ["x"] * 20
    contents[2] = "幾點"                 # 只命中 1 個關鍵字
    contents[10] = "28號烤肉"            # 命中 2 個
    contents[11] = "幾點集合"            # 與上面重疊 → 合併
    [w] = search_windows(_msgs(contents), ["28號", "烤肉", "幾點"])
    assert [m["content"] for m in w] == ["x", "28號烤肉", "幾點集合", "x"]


def test_search_windows_no_hit():
    assert search_windows(_msgs(["a", "b"]), ["烤肉"]) == []


def test_format_trip_facts():
    from line_bot.group_qa import format_trip_facts
    day = 86400
    okinawa = int(datetime(2026, 8, 28, 12).timestamp())
    text = format_trip_facts([
        {"title": "沖繩哇操局", "location": "沖繩", "start_date": okinawa,
         "end_date": okinawa + 6 * day, "status": "ended"},
        {"title": "返校", "location": None, "start_date": okinawa, "end_date": None, "status": "planning"},
        {"title": "沒日期", "location": "x", "start_date": None, "end_date": None, "status": "ended"},
    ])
    assert text.splitlines() == [
        "沖繩哇操局｜沖繩｜2026/08/28～2026/09/03｜已結束",
        "返校｜—｜2026/08/28｜規劃中",
    ]


def test_expand_date_keywords():
    from line_bot.group_qa import expand_date_keywords
    now = datetime(2026, 9, 26)
    kws = expand_date_keywords(["烤肉"], "9/28 幾點集合", now)
    for k in ("烤肉", "9/28", "28號", "9月28", "禮拜一", "週一", "星期一"):
        assert k in kws
    # 跨年：9 月問 1/3 → 算明年（2027/1/3 是週日）
    assert "禮拜天" in expand_date_keywords([], "1/3 要幹嘛", now)
    assert expand_date_keywords(["烤肉"], "什麼時候烤肉", now) == ["烤肉"]


def test_search_windows_reserves_recent_slots(monkeypatch):
    monkeypatch.setattr(group_qa, "RADIUS", 0)
    monkeypatch.setattr(group_qa, "MAX_WINDOWS", 2)
    monkeypatch.setattr(group_qa, "RECENT_WINDOWS", 1)
    msgs = [
        {"user_name": "A", "content": "28號幾點", "type": "text", "timestamp": 1},    # 舊，命中 2 個
        {"user_name": "A", "content": "x", "type": "text", "timestamp": 2},
        {"user_name": "A", "content": "28號幾點", "type": "text", "timestamp": 3},    # 舊，命中 2 個
        {"user_name": "A", "content": "x", "type": "text", "timestamp": 4},
        {"user_name": "A", "content": "禮拜一集合", "type": "text", "timestamp": 100}, # 新，只命中 1 個
    ]
    kws = ["28號", "幾點", "禮拜一"]
    # 沒有保留名額：兩段舊的勝出
    assert [w[0]["timestamp"] for w in search_windows(msgs, kws)] == [1, 3]
    # 保留 1 段給新的
    assert [w[0]["timestamp"] for w in search_windows(msgs, kws, recent_since_ms=50)] == [3, 100]
