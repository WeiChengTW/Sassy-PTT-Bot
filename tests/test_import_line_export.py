"""測試 scripts/import_line_export.py 的解析與 --no-members 行為。"""
import os
import tempfile
import pytest

from travel.db import init_db, get_conn
from scripts.import_line_export import parse, do_import


@pytest.fixture
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DB_PATH", path)
    monkeypatch.setenv("MAIN_LINE_GROUP_ID", "TEST_MAIN_GRP")
    init_db()
    yield path
    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


def test_parse_12h_and_24h_formats(tmp_path):
    txt_content = """[LINE] 測試聊天記錄
儲存日期： 2026/08/16 12:00

2023/05/12（五）
14:30\tAlice\t下午文字24h
下午03:15\tBob\t下午文字12h
上午11:20\tCarol\t上午文字12h
08:05\tDave\t早晨文字24h
"""
    file_path = str(tmp_path / "chat_test.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(txt_content)

    msgs, system = parse(file_path)
    assert len(msgs) == 4
    assert len(system) == 0
    assert [m["user_name"] for m in msgs] == ["Alice", "Bob", "Carol", "Dave"]


def test_import_with_no_members_uses_imported_prefix_and_skips_members(temp_db, tmp_path):
    txt_content = """[LINE] 測試聊天記錄
儲存日期： 2026/08/16 12:00

2023/05/12（五）
14:30\tStrangerA\t哈囉
14:31\tStrangerB\t你好
"""
    file_path = str(tmp_path / "chat_test.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(txt_content)

    msgs, system = parse(file_path)
    do_import(msgs, keep_bots=False, no_members=True)

    with get_conn() as conn:
        # messages 應該有寫入
        msg_rows = conn.execute("SELECT user_id, user_name, content FROM messages").fetchall()
        assert len(msg_rows) == 2
        for r in msg_rows:
            assert r["user_id"].startswith("imported:")

        # members 表不應該有寫入
        member_rows = conn.execute("SELECT * FROM members").fetchall()
        assert len(member_rows) == 0
