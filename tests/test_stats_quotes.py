"""測試 travel/stats_extended.py 精選語錄選取純函式（內容過濾／時間去重／正負平衡）。"""
import pytest
from travel.stats_extended import (
    _QUOTE_WINDOW_MS,
    _is_quote_worthy,
    _dedup_quote_rows,
    _balance_quotes,
)


def _row(content, sentiment, timestamp, user_name="A"):
    return {"user_name": user_name, "content": content,
            "summary": "", "sentiment": sentiment, "timestamp": timestamp}


# ─── 內容過濾 ───────────────────────────────────────────────────────────────

def test_worthy_rejects_none_and_blank():
    assert not _is_quote_worthy(None)
    assert not _is_quote_worthy("")
    assert not _is_quote_worthy("   ")


def test_worthy_rejects_short_ack():
    for text in ("真的", "確實", "好喔", "笑死", "哈哈", "嗯嗯"):
        assert not _is_quote_worthy(text), f"應過濾短附和: {text}"


def test_worthy_rejects_pure_url():
    for text in ("https://youtu.be/abc123", "http://example.com", "https://www.ptt.cc/bbs/index.html"):
        assert not _is_quote_worthy(text), f"應過濾純網址: {text}"


def test_worthy_rejects_placeholder():
    for text in ("[照片]", "[貼圖]", "[語音]", "[影片]"):
        assert not _is_quote_worthy(text), f"應過濾佔位符: {text}"


def test_worthy_rejects_noise_quotes():
    for text in ("哈哈哈哈", "呵呵呵呵", "好喔好喔"):
        assert not _is_quote_worthy(text), f"應過濾無意義笑聲/附和: {text}"


def test_worthy_accepts_real_sentence():
    assert _is_quote_worthy("這趟真的太扯了啦")
    assert _is_quote_worthy("今天天氣爛到爆炸")
    assert _is_quote_worthy("居然連這種地方都能吃到超好吃的小籠包")


# ─── 時間視窗去重 ───────────────────────────────────────────────────────────

def test_dedup_same_window_keeps_longest():
    base = 1735693200000
    rows = [
        _row("短句", 0.9, base),
        _row("這個太扯了吧", 0.9, base + 1000),
        _row("真的假的", 0.9, base + 2000),
        _row("一個完整到不行的完整句子內容", 0.9, base + 3000),
    ]
    out = _dedup_quote_rows(rows)
    assert len(out) == 1
    assert out[0]["content"] == "一個完整到不行的完整句子內容"


def test_dedup_keeps_separate_windows():
    base = 1735693200000
    rows = [
        _row("第一段對話的最長句子", 0.9, base),
        _row("第二段對話的句子", 0.9, base + _QUOTE_WINDOW_MS + 1000),
    ]
    out = _dedup_quote_rows(rows)
    assert len(out) == 2


def test_dedup_picks_longest_in_each_cluster():
    base = 1735693200000
    rows = [
        # 視窗 A：三則，最長是「A 完整句子內容比較長」
        _row("A 短", 0.8, base),
        _row("A 完整句子內容比較長", 0.8, base + 1000),
        _row("A 中", 0.8, base + 2000),
        # 視窗 B（與視窗 A 最後一則間隔 >10 分鐘）
        _row("B 完整句子內容比較長長", 0.8, base + _QUOTE_WINDOW_MS + 3000),
        _row("B 短", 0.8, base + _QUOTE_WINDOW_MS + 4000),
    ]
    out = _dedup_quote_rows(rows)
    assert [r["content"] for r in out] == ["A 完整句子內容比較長", "B 完整句子內容比較長長"]


# ─── 正負平衡 ───────────────────────────────────────────────────────────────

def test_balance_even_pos_neg():
    base = 1735693200000
    rows = (
        [_row(f"正{i}", 0.9 - i * 0.1, base + i * 1000) for i in range(5)]
        + [_row(f"負{i}", -0.9 + i * 0.1, base + (10 + i) * 1000) for i in range(5)]
    )
    out = _balance_quotes(rows, 10)
    pos = [r for r in out if r["sentiment"] >= 0]
    neg = [r for r in out if r["sentiment"] < 0]
    assert len(out) == 10
    assert len(pos) == 5
    assert len(neg) == 5


def test_balance_fills_short_side_from_long_side():
    base = 1735693200000
    rows = (
        [_row(f"正{i}", 0.9 - i * 0.05, base + i * 1000) for i in range(8)]
        + [_row("負0", -0.8, base + 9000 * 1000)]
    )
    out = _balance_quotes(rows, 10)
    assert len(out) == 9
    assert sum(1 for r in out if r["sentiment"] < 0) == 1
    assert sum(1 for r in out if r["sentiment"] >= 0) == 8


def test_balance_fewer_rows_than_limit():
    rows = [_row("只有一則", 0.7, 1735693200000)]
    out = _balance_quotes(rows, 10)
    assert len(out) == 1


def test_balance_orders_by_abs_sentiment():
    base = 1735693200000
    rows = [
        _row("弱正", 0.3, base + 1000),
        _row("強負", -0.95, base),
        _row("強正", 0.9, base + 2000),
    ]
    out = _balance_quotes(rows, 2)
    # 各側取極端者：強正 (0.9) 與 強負 (-0.95)
    assert {r["content"] for r in out} == {"強正", "強負"}