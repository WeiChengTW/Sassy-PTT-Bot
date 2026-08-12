"""測試 bot.py 新增的觸發判定純函式。"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class FakeSource:
    type: str
    user_id: str
    group_id: Optional[str] = None


@dataclass
class FakeMsg:
    text: Optional[str] = ""
    type: str = "text"


@dataclass
class FakeEvent:
    source: FakeSource
    message: FakeMsg
    reply_token: str = "tok001"


def test_bare_mention_group_only_at(monkeypatch):
    from line_bot.bot import is_group_bare_mention
    event = FakeEvent(
        source=FakeSource(type="group", user_id="U1", group_id="C1"),
        message=FakeMsg(text="@Sassy"),
    )
    assert is_group_bare_mention(event) is True


def test_bare_mention_with_text_is_false(monkeypatch):
    from line_bot.bot import is_group_bare_mention
    event = FakeEvent(
        source=FakeSource(type="group", user_id="U1", group_id="C1"),
        message=FakeMsg(text="@Sassy 你好"),
    )
    assert is_group_bare_mention(event) is False


def test_bare_mention_dm_is_false(monkeypatch):
    from line_bot.bot import is_group_bare_mention
    event = FakeEvent(
        source=FakeSource(type="user", user_id="U1"),
        message=FakeMsg(text="@Sassy"),
    )
    assert is_group_bare_mention(event) is False


def test_bare_mention_non_text_is_false(monkeypatch):
    from line_bot.bot import is_group_bare_mention
    event = FakeEvent(
        source=FakeSource(type="group", user_id="U1", group_id="C1"),
        message=FakeMsg(text=None),
    )
    assert is_group_bare_mention(event) is False


def test_admin_dm_true_for_admin_in_dm(monkeypatch):
    monkeypatch.setenv("ADMIN_USER_IDS", "U_ADMIN,U_ADMIN2")
    from line_bot.bot import is_admin_dm
    event = FakeEvent(
        source=FakeSource(type="user", user_id="U_ADMIN"),
        message=FakeMsg(text="任何訊息"),
    )
    assert is_admin_dm(event) is True


def test_admin_dm_false_for_admin_in_group(monkeypatch):
    monkeypatch.setenv("ADMIN_USER_IDS", "U_ADMIN")
    from line_bot.bot import is_admin_dm
    event = FakeEvent(
        source=FakeSource(type="group", user_id="U_ADMIN", group_id="C1"),
        message=FakeMsg(text="在群組裡"),
    )
    assert is_admin_dm(event) is False


def test_admin_dm_false_for_non_admin_in_dm(monkeypatch):
    monkeypatch.setenv("ADMIN_USER_IDS", "U_ADMIN")
    from line_bot.bot import is_admin_dm
    event = FakeEvent(
        source=FakeSource(type="user", user_id="U_RANDO"),
        message=FakeMsg(text="私訊"),
    )
    assert is_admin_dm(event) is False