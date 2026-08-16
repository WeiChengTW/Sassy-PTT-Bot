"""測試 scripts/import_memories.py 的冪等去重邏輯。

核心：以 (group_id, start_date) 去重，不含 title——因為 title 可能被使用者在
LIFF 改名，若把 title 納入去重，重跑 import 會在「同一天」重複插入空記錄。
"""
import os
import tempfile
import pytest

from travel.db import init_db, get_conn
from travel.migrations import migrate


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


def _midnight(y, m, d):
    from datetime import datetime
    return int(datetime(y, m, d).timestamp())


def _import(conn, group_id, title, rarity, start, end=None):
    from scripts.import_memories import _insert_if_new
    return _insert_if_new(conn, group_id, title, rarity, start, end)


def test_insert_then_idempotent_reimport(temp_db):
    with get_conn() as conn:
        start = _midnight(2023, 5, 25)
        assert _import(conn, "G1", "鬆餅", "legendary", start) is True
        # 同 title 同 start 重跑 → skip
        assert _import(conn, "G1", "鬆餅", "legendary", start) is False
    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
        assert n == 1


def test_same_day_different_title_skipped(temp_db):
    """改名情境：同一天已有改名後的旅行（title 不同）→ 不再插入。"""
    with get_conn() as conn:
        start = _midnight(2023, 5, 25)
        # 先有使用者改過名的「無限再生鬆餅」（模擬已存在）
        assert _import(conn, "G1", "無限再生鬆餅", "legendary", start) is True
        # memories.json 還是舊 title「鬆餅」→ 應 skip，不產生重複
        assert _import(conn, "G1", "鬆餅", "legendary", start) is False
    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
        assert n == 1


def test_different_day_inserts_both(temp_db):
    with get_conn() as conn:
        s1 = _midnight(2023, 5, 25)
        s2 = _midnight(2023, 5, 26)
        assert _import(conn, "G1", "鬆餅", "legendary", s1) is True
        assert _import(conn, "G1", "火鍋", "legendary", s2) is True
    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
        assert n == 2


def test_different_group_same_day_both_inserted(temp_db):
    with get_conn() as conn:
        start = _midnight(2023, 5, 25)
        assert _import(conn, "G1", "鬆餅", "legendary", start) is True
        assert _import(conn, "G2", "鬆餅", "legendary", start) is True
    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
        assert n == 2