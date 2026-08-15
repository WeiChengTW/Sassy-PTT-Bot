"""測試 travel/leaderboards.py 資料驅動排行榜。"""
import os
import tempfile
import time
import pytest
from travel.db import init_db, get_conn
from travel.migrations import migrate

DAY = 86_400_000
BASE = 1_735_693_200_000  # 2025-01-01 02:00 UTC


@pytest.fixture
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DB_PATH", path)
    init_db()
    migrate()
    yield path
    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


def _msg(conn, *, mid, uid, name, ts, mtype="text", content="hi",
         reply_to=None, sentiment=None, group="g1"):
    conn.execute(
        """INSERT INTO messages
           (line_message_id, group_id, user_id, user_name, type, content,
            timestamp, reply_to_message_id, sentiment)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (mid, group, uid, name, mtype, content, ts, reply_to, sentiment),
    )


def _bulk(conn, uid, name, n, *, start=BASE, step=1000, **kw):
    for i in range(n):
        _msg(conn, mid=f"{uid}-{i}-{kw.get('mtype','t')}", uid=uid, name=name,
             ts=start + i * step, **kw)


# ─── 全體結構 ─────────────────────────────────────────────────────────────

def test_all_boards_shape(temp_db):
    from travel.leaderboards import get_all_boards, BOARDS
    with get_conn() as conn:
        _bulk(conn, "uA", "Alice", 15, sentiment=0.8)
        _bulk(conn, "uB", "Bob", 12, sentiment=-0.2)
    data = get_all_boards("g1")
    assert len(data["boards"]) == len(BOARDS)
    ids = {b["id"] for b in data["boards"]}
    assert {"sentiment", "streak", "contribution", "all_rounder", "reply_speed"} <= ids
    for b in data["boards"]:
        assert set(b) >= {"id", "title", "emoji", "variant", "accent", "sparse", "rows", "highlight"}
        for r in b["rows"]:
            assert {"user_id", "name", "value", "value_str"} <= set(r)


def test_period_all_and_month_do_not_crash(temp_db):
    from travel.leaderboards import get_all_boards
    with get_conn() as conn:
        _bulk(conn, "uA", "Alice", 15, sentiment=0.5)
    from travel.leaderboards import BOARDS
    for period in ("all", "2025-01", "2099-12"):
        data = get_all_boards("g1", period)
        assert len(data["boards"]) == len(BOARDS)


# ─── 個別排行榜 ───────────────────────────────────────────────────────────

def test_sentiment_order_and_highlight(temp_db):
    from travel.leaderboards import get_board
    with get_conn() as conn:
        _bulk(conn, "uA", "Alice", 12, sentiment=0.9)
        _bulk(conn, "uB", "Bob", 12, sentiment=0.1)
        _msg(conn, mid="peak", uid="uA", name="Alice", ts=BASE, sentiment=0.99, content="最棒")
    b = get_board("正能量", "g1")
    assert b["rows"][0]["user_id"] == "uA"
    assert b["rows"][0]["value"] > b["rows"][1]["value"]
    assert b["highlight"] and b["highlight"]["name"] == "Alice"


def test_sentiment_threshold_excludes_small_samples(temp_db):
    from travel.leaderboards import get_board
    with get_conn() as conn:
        _bulk(conn, "uA", "Alice", 12, sentiment=0.5)
        _bulk(conn, "uB", "Bob", 3, sentiment=0.9)  # <10 → 排除
    b = get_board("sentiment", "g1")
    assert {r["user_id"] for r in b["rows"]} == {"uA"}


def test_streak_days(temp_db):
    from travel.leaderboards import get_board
    with get_conn() as conn:
        for d in range(5):  # 連續 5 天
            _msg(conn, mid=f"s{d}", uid="uA", name="Alice", ts=BASE + d * DAY)
    b = get_board("連擊", "g1")
    assert b["rows"][0]["value"] == 5


def test_msg_length_highlight(temp_db):
    from travel.leaderboards import get_board
    with get_conn() as conn:
        _bulk(conn, "uA", "Alice", 12, content="short")
        _msg(conn, mid="long", uid="uA", name="Alice", ts=BASE, content="x" * 500)
    b = get_board("長文", "g1")
    assert b["rows"][0]["user_id"] == "uA"
    assert b["highlight"]["value_str"] == "500 字"


def test_sticker_ratio(temp_db):
    from travel.leaderboards import get_board
    with get_conn() as conn:
        _bulk(conn, "uA", "Alice", 5, mtype="sticker")
        _bulk(conn, "uA", "Alice", 5, mtype="text")  # 5/10 = 50%
    b = get_board("貼圖", "g1")
    assert b["rows"][0]["value"] == 50.0


def test_reply_speed_sparse_and_threshold(temp_db):
    from travel.leaderboards import get_board
    with get_conn() as conn:
        for i in range(3):  # B 發 3 則，A 各回覆一次（3 次 → 達門檻）
            _msg(conn, mid=f"base{i}", uid="uB", name="Bob", ts=BASE + i * 10000)
            _msg(conn, mid=f"rep{i}", uid="uA", name="Alice",
                 ts=BASE + i * 10000 + 120000, reply_to=f"base{i}")  # 2 分鐘後
    b = get_board("reply_speed", "g1")
    assert b["sparse"] is True
    assert b["rows"] and b["rows"][0]["user_id"] == "uA"
    assert abs(b["rows"][0]["value"] - 2.0) < 0.1  # 平均 2 分鐘


def test_contribution_score_bounded(temp_db):
    from travel.leaderboards import get_board
    with get_conn() as conn:
        _bulk(conn, "uA", "Alice", 20, sentiment=0.8)
        _bulk(conn, "uB", "Bob", 15, sentiment=-0.5)
    b = get_board("contribution", "g1")
    assert b["variant"] == "score"
    for r in b["rows"]:
        assert 0 <= r["value"] <= 100
        assert "breakdown" in r


def test_all_rounder_radar_axes(temp_db):
    from travel.leaderboards import get_board
    with get_conn() as conn:
        _bulk(conn, "uA", "Alice", 15, sentiment=0.5)
    b = get_board("all_rounder", "g1")
    assert b["variant"] == "radar"
    axes = b["rows"][0]["axes"]
    assert set(axes) == {"活躍", "回應", "情緒", "話題", "創意", "旅行"}
    assert all(0 <= v <= 100 for v in axes.values())


# ─── 查找 helpers ─────────────────────────────────────────────────────────

def test_find_board_and_menu(temp_db):
    from travel.leaderboards import find_board, get_board, board_menu, BOARDS
    assert find_board("正能量").id == "sentiment"
    assert find_board("streak").id == "streak"
    assert find_board("不存在xyz") is None
    assert get_board("不存在xyz", "g1") is None
    assert len(board_menu()) == len(BOARDS)
