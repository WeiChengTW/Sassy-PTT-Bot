"""聊天摘要：觸發詞判斷與「這一輪」切段。"""
from line_bot.chat_summary import (
    ROUND_GAP_MS, format_transcript, is_summary_request, select_round, too_short_reply,
)

MIN = 60 * 1000


def _msgs(timestamps):
    return [{"user_name": "A", "content": str(i), "type": "text", "timestamp": t}
            for i, t in enumerate(timestamps)]


def test_is_summary_request():
    assert is_summary_request("現在是怎樣")
    assert is_summary_request(" 現在是怎樣？？ ")
    assert is_summary_request("現在是怎樣!")
    assert not is_summary_request("剛剛在吵什麼")
    assert not is_summary_request("摘要")
    assert not is_summary_request("所以現在是怎樣啦")


def test_round_stops_at_gap():
    old = [i * MIN for i in range(20)]
    new_start = old[-1] + ROUND_GAP_MS + MIN
    new = [new_start + i * MIN for i in range(15)]
    assert select_round(_msgs(old + new)) == _msgs(old + new)[20:]


def test_short_round_is_not_extended():
    old = [i * MIN for i in range(20)]
    new_start = old[-1] + ROUND_GAP_MS + MIN
    new = [new_start + i * MIN for i in range(5)]
    # 當前這輪只有 5 則 → 不往前補，由呼叫端決定嗆回去
    assert len(select_round(_msgs(old + new))) == 5


def test_asker_after_long_silence_gets_previous_round():
    # 發問那則不在 msgs 裡：最後一輪就是上一輪
    prev = [i * MIN for i in range(12)]
    assert select_round(_msgs(prev)) == _msgs(prev)


def test_no_cap_within_same_round():
    many = [i * 20 * MIN for i in range(1000)]           # 每 20 分鐘一則，跨 13 天都沒斷
    assert len(select_round(_msgs(many))) == 1000


def test_too_short_reply_mentions_count():
    assert "7" in too_short_reply(7)


def test_empty():
    assert select_round([]) == []


def test_format_transcript_marks_non_text():
    msgs = [
        {"user_name": "A", "content": "嗨", "type": "text", "timestamp": 0},
        {"user_name": "B", "content": "", "type": "sticker", "timestamp": MIN},
    ]
    lines = format_transcript(msgs).splitlines()
    assert lines[0].endswith("A: 嗨")
    assert lines[1].endswith("B: [貼圖]")
