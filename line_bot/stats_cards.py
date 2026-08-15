"""統計 Flex 卡片產生器（方案 A–D 共用）。

把 travel.stats / travel.stats_extended 的查詢結果轉成 LINE Messaging API 的
Flex Message / Carousel 與 Quick Reply。純函式、無副作用，方便單元測試。

這裡在模組頂層 import linebot SDK——僅由 bot.py 在 line_api 可用時才 lazy import
本模組，故不影響「無 SDK 也能跑」的設計。
"""
from linebot.v3.messaging import (
    FlexMessage, FlexBubble, FlexBox, FlexText, FlexButton, FlexSeparator,
    URIAction, MessageAction, QuickReply, QuickReplyItem, TextMessage,
)

# ── 主題色（與 liff/src/constants/rarity.ts 藍/金風格一致） ──
BLUE = "#2563eb"
GOLD = "#f59e0b"
ROSE = "#f43f5e"
ORANGE = "#f97316"  # 最佳拍檔（兄弟感暖橘）
PURPLE = "#a855f7"
GREY = "#94a3b8"


def best_friend_of(inter: dict, user_id: str) -> str | None:
    """從 best_pairs 找出與該 user 互動最密切的對象名字（已按 count 排序）。"""
    for p in (inter.get("best_pairs") or []):
        if p.get("user1_id") == user_id:
            return p.get("user2_name")
        if p.get("user2_id") == user_id:
            return p.get("user1_name")
    return None


# ── 低階組裝 helpers ────────────────────────────────────────────────

def _liff_button(label: str, uri: str, color: str = BLUE) -> FlexButton:
    return FlexButton(action=URIAction(label=label, uri=uri), style="primary",
                      color=color, height="sm")


def _rank_row(idx: int, name: str, value: str, color: str) -> FlexBox:
    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, f"{idx}.")
    return FlexBox(layout="baseline", spacing="sm", contents=[
        FlexText(text=medal, size="sm", flex=0, color=color, weight="bold"),
        FlexText(text=name, size="sm", flex=1, wrap=False, color="#333333"),
        FlexText(text=value, size="sm", flex=0, align="end", color="#888888"),
    ])


def _bubble(title: str, accent: str, body: list, button: FlexButton | None) -> FlexBubble:
    return FlexBubble(
        header=FlexBox(layout="vertical", backgroundColor=accent, paddingAll="14px",
                       contents=[FlexText(text=title, weight="bold", size="md",
                                          color="#ffffff", wrap=True)]),
        body=FlexBox(layout="vertical", spacing="sm", paddingAll="16px", contents=body),
        footer=(FlexBox(layout="vertical", paddingAll="12px", contents=[button])
                if button else None),
    )


def _empty_body(msg: str) -> list:
    return [FlexText(text=msg, size="sm", color="#999999", wrap=True)]


# ── 各維度單卡（方案 B 的 quick-reply 點擊回覆） ──────────────────────

def build_leaderboard_card(lead: dict, liff_url: str) -> FlexBubble:
    rankings = (lead.get("rankings") or [])[:5]
    body = _empty_body("這段期間還沒有人發言 🙊")
    if rankings:
        body = []
        for i, r in enumerate(rankings, 1):
            body.append(_rank_row(i, r.get("user_name") or "路人",
                                  f"{r.get('total', 0)} 則", GOLD))
    return _bubble("🏆 發言排行", GOLD, body,
                   _liff_button("📊 開啟完整排行", f"{liff_url}/leaderboard", GOLD))


def build_nightowl_card(lead: dict, liff_url: str) -> FlexBubble:
    owls = (lead.get("night_owls") or [])[:5]
    body = _empty_body("最近沒有人熬夜 🌙")
    if owls:
        body = [FlexText(text="凌晨 00:00–04:00 發言排行", size="xs", color="#999999")]
        for i, r in enumerate(owls, 1):
            body.append(_rank_row(i, r.get("user_name") or "路人",
                                  f"{r.get('night_count', 0)} 則", PURPLE))
    return _bubble("🦉 夜貓榜", PURPLE, body,
                   _liff_button("📊 開啟儀表板", f"{liff_url}/leaderboard", PURPLE))


def build_pairs_card(inter: dict, liff_url: str) -> FlexBubble:
    pairs = (inter.get("best_pairs") or [])[:5]
    body = _empty_body("還沒有麻吉互相 tag 💔")
    if pairs:
        body = []
        for i, p in enumerate(pairs, 1):
            names = f"{p.get('user1_name') or '路人'} 🤝 {p.get('user2_name') or '路人'}"
            body.append(_rank_row(i, names, f"{p.get('count', 0)} 次", ORANGE))
    return _bubble("🤝 最佳拍檔", ORANGE, body,
                   _liff_button("🕸️ 查看互動網絡", f"{liff_url}/interactions", ORANGE))


def build_topics_card(topics: dict, liff_url: str) -> FlexBubble:
    keywords = (topics.get("top_keywords") or [])[:8]
    quotes = topics.get("highlight_quotes") or []
    body: list = []
    if keywords:
        body.append(FlexText(text="🔥 熱門關鍵字", size="sm", weight="bold", color="#333333"))
        body.append(FlexText(text="、".join(k.get("keyword", "") for k in keywords),
                             size="sm", color="#555555", wrap=True))
    if quotes:
        q = quotes[0]
        if body:
            body.append(FlexSeparator(margin="md"))
        body.append(FlexText(text="💬 本期最戲劇金句", size="sm", weight="bold",
                             color="#333333", margin="md"))
        body.append(FlexText(text=f"「{(q.get('content') or '').strip()[:60]}」",
                             size="sm", color="#555555", wrap=True))
        body.append(FlexText(text=f"— {q.get('user_name') or '匿名'}", size="xs",
                             color="#999999", align="end"))
    if not body:
        body = _empty_body("還沒有足夠的話題資料 📭")
    return _bubble("🔥 熱門話題與金句", BLUE, body,
                   _liff_button("📊 開啟話題分析", f"{liff_url}/topics", BLUE))


# ── 方案 A / D：週報 / 月報 Carousel（多頁輪播） ─────────────────────

def build_report_carousel(dash: dict, lead: dict, inter: dict, topics: dict,
                          liff_url: str, period_label: str) -> FlexMessage:
    """三頁輪播：風雲榜 / 互動CP / 情緒話題。"""
    # 卡片 1：風雲榜（發話冠軍 + 夜貓王 + 貼圖大師）
    top_users = dash.get("top_users") or []
    owls = lead.get("night_owls") or []
    rankings = lead.get("rankings") or []
    sticker_master = max(rankings, key=lambda r: r.get("sticker_count", 0), default=None)

    b1_body: list = []
    if top_users:
        b1_body.append(_rank_row(1, top_users[0].get("user_name") or "路人",
                                 f"{top_users[0].get('total', 0)} 則", GOLD))
    if owls:
        b1_body.append(FlexBox(layout="baseline", spacing="sm", contents=[
            FlexText(text="🦉", size="sm", flex=0),
            FlexText(text=owls[0].get("user_name") or "路人", size="sm", flex=1),
            FlexText(text=f"{owls[0].get('night_count', 0)} 則", size="sm", flex=0,
                     align="end", color="#888888"),
        ]))
    if sticker_master and sticker_master.get("sticker_count", 0) > 0:
        b1_body.append(FlexBox(layout="baseline", spacing="sm", contents=[
            FlexText(text="🎨", size="sm", flex=0),
            FlexText(text=sticker_master.get("user_name") or "路人", size="sm", flex=1),
            FlexText(text=f"{sticker_master.get('sticker_count', 0)} 貼圖", size="sm",
                     flex=0, align="end", color="#888888"),
        ]))
    if not b1_body:
        b1_body = _empty_body("這段期間群組很安靜 😴")
    bubble1 = _bubble(f"🏆 {period_label}風雲榜", GOLD, b1_body,
                      _liff_button("📊 查看詳細儀表板", f"{liff_url}/", GOLD))

    # 卡片 2：互動 CP
    bubble2 = build_pairs_card(inter, liff_url)
    bubble2.header.contents[0].text = f"🤝 {period_label}最佳拍檔"

    # 卡片 3：情緒與熱門話題
    bubble3 = build_topics_card(topics, liff_url)
    bubble3.header.contents[0].text = f"🔥 {period_label}話題與金句"

    from linebot.v3.messaging import FlexCarousel
    return FlexMessage(
        alt_text=f"[{period_label}群組戰報] 風雲榜・最佳拍檔・熱門話題",
        contents=FlexCarousel(contents=[bubble1, bubble2, bubble3]),
    )


# ── 方案 C：個人戰績卡 ──────────────────────────────────────────────

def build_personal_card(profile: dict, badges: list, best_friend: str | None,
                        user_name: str, liff_url: str, user_id: str = "") -> FlexMessage:
    summary = profile.get("summary") or {}
    slots = profile.get("time_slots") or {}
    tags = [p.get("tag") for p in (profile.get("personality") or []) if p.get("tag")]
    total = summary.get("total", 0)
    night = slots.get("night", 0)
    night_pct = round(night / total * 100) if total else 0

    body: list = [
        FlexBox(layout="baseline", spacing="sm", contents=[
            FlexText(text="💬 發話量", size="sm", color="#888888", flex=0),
            FlexText(text=f"{total} 則", size="sm", align="end", flex=1, color="#333333"),
        ]),
        FlexBox(layout="baseline", spacing="sm", contents=[
            FlexText(text="📅 活躍天數", size="sm", color="#888888", flex=0),
            FlexText(text=f"{summary.get('active_days', 0)} 天", size="sm", align="end",
                     flex=1, color="#333333"),
        ]),
        FlexBox(layout="baseline", spacing="sm", contents=[
            FlexText(text="🦉 夜貓指數", size="sm", color="#888888", flex=0),
            FlexText(text=f"{night_pct}%", size="sm", align="end", flex=1, color="#333333"),
        ]),
    ]
    if best_friend:
        body.append(FlexBox(layout="baseline", spacing="sm", contents=[
            FlexText(text="🤝 最佳拍檔", size="sm", color="#888888", flex=0),
            FlexText(text=best_friend, size="sm", align="end", flex=1, color="#333333"),
        ]))
    if tags:
        body.append(FlexSeparator(margin="md"))
        body.append(FlexText(text="🏷️ " + "　".join(tags[:4]), size="sm",
                             color=BLUE, wrap=True, margin="md"))
    if badges:
        emojis = "".join(b.get("badge_emoji", "🏅") for b in badges[:8])
        body.append(FlexText(text=f"🎖️ 徽章 {len(badges)}　{emojis}", size="sm",
                             color=GOLD, wrap=True))

    bubble = FlexBubble(
        header=FlexBox(layout="vertical", backgroundColor=BLUE, paddingAll="16px",
                       contents=[
                           FlexText(text="個人戰績卡", size="xs", color="#ffffffcc"),
                           FlexText(text=f"🎖️ {user_name}", size="lg", weight="bold",
                                    color="#ffffff", wrap=True, margin="sm"),
                       ]),
        body=FlexBox(layout="vertical", spacing="sm", paddingAll="16px", contents=body),
        footer=FlexBox(layout="vertical", paddingAll="12px", contents=[
            _liff_button("📊 開啟個人檔案",
                         f"{liff_url}/profile" + (f"/{user_id}" if user_id else ""), BLUE),
        ]),
    )
    return FlexMessage(alt_text=f"[個人戰績] {user_name}", contents=bubble)


# ── Quick Reply（方案 B 的互動選單） ───────────────────────────────

def stats_quick_reply(liff_url: str) -> QuickReply:
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="🏆 發言排行", text="/stats 排行")),
        QuickReplyItem(action=MessageAction(label="🦉 夜貓榜", text="/stats 夜貓")),
        QuickReplyItem(action=MessageAction(label="🤝 最佳拍檔", text="/stats cp")),
        QuickReplyItem(action=MessageAction(label="🔥 熱門話題", text="/stats 話題")),
        QuickReplyItem(action=URIAction(label="📊 開啟 LIFF", uri=f"{liff_url}/")),
    ])


def wrap_single(bubble: FlexBubble, alt_text: str, quick_reply: QuickReply | None = None) -> FlexMessage:
    return FlexMessage(alt_text=alt_text, contents=bubble, quick_reply=quick_reply)
