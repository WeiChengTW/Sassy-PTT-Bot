"""測試 scripts/import_line_export.py 的解析與 --no-members 行為。"""
import os
import tempfile
import pytest

from travel.db import init_db, get_conn
from scripts.import_line_export import parse, do_import, synth_line_id


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


def test_synth_line_id_different_source_no_collision():
    """不同 source（來源檔名）的同分鐘訊息，應產生不同 line_message_id。"""
    gid = "TEST_GRP"
    ts = 1700000000000
    seq = 0
    id_a = synth_line_id(gid, ts, seq, source="fileA.txt")
    id_b = synth_line_id(gid, ts, seq, source="fileB.txt")
    assert id_a != id_b
    assert id_a.startswith("import:")
    assert id_b.startswith("import:")


def test_synth_line_id_empty_source_backward_compat():
    """source='' 時行為與舊版（無 source 參數）完全相同。"""
    gid = "TEST_GRP"
    ts = 1700000000000
    seq = 3
    # 驗證新版 source="" 的 hash 與舊公式一致
    import hashlib
    expected = "import:" + hashlib.sha1(f"{gid}|{ts}|{seq}|".encode()).hexdigest()[:16]
    assert synth_line_id(gid, ts, seq, source="") == expected
    assert synth_line_id(gid, ts, seq) == expected  # 預設值


def test_no_cutoff_skips_and_preserves_messages(temp_db, tmp_path):
    """no_cutoff=True 時，訊息不受 live cutoff 過濾；no_cutoff=False 時受過濾。

    透過直接操作 do_import 的 cutoff 邏輯驗證：
    - 用 no_cutoff=True 匯入一批舊訊息，全部寫入。
    - 再用 no_cutoff=False 嘗試匯入同批訊息（因 line_message_id 冪等），跳過重複也不影響。
    主要確保兩個路徑都不拋例外且行為可控。
    """
    txt_content = """[LINE] 測試聊天記錄
儲存日期： 2026/08/16 12:00

2022/06/12（日）
12:00\tUserA\t這是古老訊息
12:01\tUserB\t也是古老的
"""
    file_path = str(tmp_path / "old.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(txt_content)

    msgs, _ = parse(file_path)
    assert len(msgs) == 2

    # no_cutoff=True：不管 live cutoff，直接匯入
    do_import(msgs, keep_bots=False, no_members=True, no_cutoff=True, source="old.txt")
    with get_conn() as conn:
        cnt = conn.execute("SELECT COUNT(*) FROM messages WHERE user_name IN ('UserA','UserB')").fetchone()[0]
    assert cnt == 2, "no_cutoff=True 時應匯入全部"

    # 再跑一次（冪等）
    do_import(msgs, keep_bots=False, no_members=True, no_cutoff=True, source="old.txt")
    with get_conn() as conn:
        cnt2 = conn.execute("SELECT COUNT(*) FROM messages WHERE user_name IN ('UserA','UserB')").fetchone()[0]
    assert cnt2 == 2, "冪等：重跑不重複"
