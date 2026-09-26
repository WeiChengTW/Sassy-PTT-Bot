"""自動取綽號：區間選擇、FIFO 替換、LLM 輸出解析。"""
from line_bot.auto_nickname import (
    MAX_AUTO_ALIASES, choose_window, parse_nickname_response, push_auto_alias,
)


def test_choose_window():
    assert choose_window(30, 100) == 7
    assert choose_window(29, 30) == 30
    assert choose_window(5, 29) is None


def _alias(name):
    return {"name": name, "reason": "r", "created": "2026-09-27", "window_days": 7}


def test_push_replaces_oldest_when_full():
    entry = {"aliases": ["偉城"]}
    for n in ("甲", "乙", "丙", "丁"):
        assert push_auto_alias(entry, _alias(n))
    assert [a["name"] for a in entry["auto_aliases"]] == ["乙", "丙", "丁"]
    assert len(entry["auto_aliases"]) == MAX_AUTO_ALIASES
    assert entry["aliases"] == ["偉城"]          # 手寫外號不動


def test_push_skips_duplicates():
    entry = {"aliases": ["偉城"], "auto_aliases": [_alias("甲")]}
    assert not push_auto_alias(entry, _alias("偉城"))
    assert not push_auto_alias(entry, _alias("甲"))
    assert len(entry["auto_aliases"]) == 1


def test_parse_response():
    raw = '好的！\n```json\n{"name": "深夜哲學家", "reason": "凌晨三點還在發文"}\n```'
    assert parse_nickname_response(raw) == {"name": "深夜哲學家", "reason": "凌晨三點還在發文"}


def test_parse_rejects_bad_output():
    assert parse_nickname_response(None) is None
    assert parse_nickname_response("沒有 JSON") is None
    assert parse_nickname_response('{"name": "", "reason": "x"}') is None
    assert parse_nickname_response('{"name": "這個稱號實在是太長了超過十個字", "reason": "x"}') is None
    assert parse_nickname_response('{"name": "短", "reason": ""}') is None
