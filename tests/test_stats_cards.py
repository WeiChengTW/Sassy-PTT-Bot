"""測試 line_bot/stats_cards.py Flex 卡片產生器（純函式，需 linebot SDK）。"""
import pytest

pytest.importorskip("linebot.v3.messaging")

from line_bot import stats_cards as cards  # noqa: E402

LIFF = "https://liff.line.me/test-id"


def _all_text(node) -> str:
    """遞迴收集 Flex 節點內所有 text。"""
    out = getattr(node, "text", "") or ""
    for child in (getattr(node, "contents", None) or []):
        out += " " + _all_text(child)
    return out

DASH = {
    "summary": {"total_messages": 100, "active_days": 7, "member_count": 5, "active_trips": 1},
    "top_users": [{"user_id": "U1", "user_name": "阿明", "total": 40, "active_days": 6}],
    "type_distribution": [{"type": "text", "count": 80}, {"type": "sticker", "count": 20}],
}
LEAD = {
    "rankings": [
        {"user_id": "U1", "user_name": "阿明", "total": 40, "text_count": 30,
         "sticker_count": 10, "image_count": 0},
        {"user_id": "U2", "user_name": "小華", "total": 25, "text_count": 20,
         "sticker_count": 5, "image_count": 0},
    ],
    "night_owls": [{"user_id": "U2", "user_name": "小華", "night_count": 12}],
    "type_distribution": [],
}
INTER = {
    "best_pairs": [
        {"user1_id": "U1", "user1_name": "阿明", "user2_id": "U2",
         "user2_name": "小華", "count": 8},
    ],
    "network_nodes": [], "network_edges": [],
}
TOPICS = {
    "top_keywords": [{"keyword": "露營", "count": 9}, {"keyword": "美食", "count": 7}],
    "highlight_quotes": [{"user_name": "阿明", "content": "這趟真的太扯了啦",
                          "summary": "", "sentiment": 0.9, "tone": "戲劇", "timestamp": 0}],
    "hot_locations": [], "top_topics": [],
}
PROFILE = {
    "summary": {"total": 40, "active_days": 6, "avg_per_day": 6.6},
    "time_slots": {"night": 8, "morning": 5, "daytime": 20, "evening": 7},
    "personality": [{"tag": "夜貓子", "reason": ""}, {"tag": "貼圖狂魔", "reason": ""}],
    "top_topics": [], "avg_sentiment": 0.3,
}
BADGES = [{"badge_name": "露營王", "badge_rarity": "epic", "badge_emoji": "🏕️"}]


def test_leaderboard_card_has_ranking():
    b = cards.build_leaderboard_card(LEAD, LIFF)
    assert b.header.contents[0].text.startswith("🏆")
    # body 有兩位排行者
    assert len(b.body.contents) == 2


def test_leaderboard_card_empty_graceful():
    b = cards.build_leaderboard_card({"rankings": []}, LIFF)
    assert b.body.contents  # 有 fallback 文字


def test_nightowl_and_pairs_and_topics_build():
    assert cards.build_nightowl_card(LEAD, LIFF).header.contents[0].text.startswith("🦉")
    assert cards.build_pairs_card(INTER, LIFF).header.contents[0].text.startswith("🤝")
    tcard = cards.build_topics_card(TOPICS, LIFF)
    # 關鍵字與金句都在 body
    joined = _all_text(tcard.body)
    assert "露營" in joined and "太扯" in joined


def test_report_carousel_has_three_bubbles():
    msg = cards.build_report_carousel(DASH, LEAD, INTER, TOPICS, LIFF, "本週")
    assert msg.alt_text.startswith("[本週群組戰報]")
    assert len(msg.contents.contents) == 3


def test_personal_card_includes_name_and_best_friend():
    bf = cards.best_friend_of(INTER, "U1")
    assert bf == "小華"
    msg = cards.build_personal_card(PROFILE, BADGES, bf, "阿明", LIFF, "U1")
    assert "阿明" in msg.alt_text
    assert "小華" in _all_text(msg.contents.body)  # 最佳拍檔


def test_quick_reply_has_five_items():
    qr = cards.stats_quick_reply(LIFF)
    assert len(qr.items) == 5
