"""CLI 工具：查看 SQLite 統計。

用法：
    python scripts/show_stats.py overview
    python scripts/show_stats.py user <user_id>
    python scripts/show_stats.py top-users
    python scripts/show_stats.py topics
    python scripts/show_stats.py travel
    python scripts/show_stats.py dashboard
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from travel.db import get_conn


def overview():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT type, COUNT(*) AS count
            FROM messages
            GROUP BY type
            ORDER BY count DESC
        """).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        analyzed = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE analyzed_at IS NOT NULL"
        ).fetchone()[0]
        travel = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE is_travel_related=1"
        ).fetchone()[0]
    print(f"總訊息：{total}")
    print(f"已分析：{analyzed}")
    print(f"旅行相關：{travel}")
    print("---")
    for r in rows:
        print(f"  {r['type']}: {r['count']}")


def user_stats(user_id: str):
    with get_conn() as conn:
        msgs = conn.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN type='sticker' THEN 1 ELSE 0 END) AS stickers,
                   SUM(CASE WHEN type='image' THEN 1 ELSE 0 END) AS images,
                   SUM(CASE WHEN type='video' THEN 1 ELSE 0 END) AS videos,
                   SUM(CASE WHEN is_travel_related=1 THEN 1 ELSE 0 END) AS travel
            FROM messages WHERE user_id=?
        """, (user_id,)).fetchone()
        lifetime = conn.execute(
            "SELECT * FROM user_lifetime_stats WHERE user_id=?",
            (user_id,),
        ).fetchone()
        last_5 = conn.execute("""
            SELECT timestamp, type, content
            FROM messages WHERE user_id=?
            ORDER BY timestamp DESC LIMIT 5
        """, (user_id,)).fetchall()
    print(f"使用者 {user_id}")
    print(f"  總訊息: {msgs['total'] or 0}")
    print(f"  貼圖: {msgs['stickers'] or 0}")
    print(f"  圖片: {msgs['images'] or 0}")
    print(f"  影片: {msgs['videos'] or 0}")
    print(f"  旅行相關: {msgs['travel'] or 0}")
    if lifetime:
        locs = json.loads(lifetime["favorite_locations"] or "[]")
        print(f"  常用地點: {', '.join(locs) if locs else '(無)'}")
    print("--- 最近 5 則 ---")
    for m in last_5:
        ts = m['timestamp']
        c = (m['content'] or '')[:40]
        print(f"  [{ts}] {m['type']}: {c}")


def top_users():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT user_name, COUNT(*) AS total
            FROM messages
            WHERE user_name IS NOT NULL
            GROUP BY user_name
            ORDER BY total DESC
            LIMIT 10
        """).fetchall()
    print("Top 10 話癆：")
    for i, r in enumerate(rows, 1):
        print(f"  {i:2d}. {r['user_name']}: {r['total']}")


def topic_distribution():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT topics FROM messages
            WHERE topics IS NOT NULL AND topics != '[]'
        """).fetchall()
    counter: dict[str, int] = {}
    for r in rows:
        try:
            topics = json.loads(r["topics"])
        except (json.JSONDecodeError, TypeError):
            continue
        for t in topics:
            counter[t] = counter.get(t, 0) + 1
    print("主題分佈（僅已分析訊息）：")
    if not counter:
        print("  (尚無已分析訊息)")
        return
    for topic, count in sorted(counter.items(), key=lambda x: -x[1]):
        print(f"  {topic}: {count}")


def travel_related():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT user_name, COUNT(*) AS count
            FROM messages
            WHERE is_travel_related=1 AND user_name IS NOT NULL
            GROUP BY user_name
            ORDER BY count DESC
        """).fetchall()
    print("旅行相關訊息排行：")
    if not rows:
        print("  (尚無旅行相關訊息)")
        return
    for i, r in enumerate(rows, 1):
        print(f"  {i:2d}. {r['user_name']}: {r['count']}")


def dashboard():
    with get_conn() as conn:
        # group-level daily_stats
        recent = conn.execute("""
            SELECT date, group_id, text_count, sticker_count, image_count,
                   active_users, travel_mentions
            FROM daily_stats
            ORDER BY date DESC LIMIT 14
        """).fetchall()
        groups = conn.execute(
            "SELECT DISTINCT group_id FROM messages"
        ).fetchall()
        trips = conn.execute(
            "SELECT status, COUNT(*) AS n FROM trips GROUP BY status"
        ).fetchall()
        badge_count = conn.execute(
            "SELECT COUNT(*) FROM badges WHERE user_id IS NOT NULL"
        ).fetchone()[0]
    print("=== Dashboard ===")
    print(f"群組數: {len(groups)}")
    for t in trips:
        print(f"  旅行 ({t['status']}): {t['n']}")
    print(f"已發徽章: {badge_count}")
    print("--- 近 14 天 daily_stats ---")
    for r in recent:
        print(f"  {r['date']} [{r['group_id'][:8]}] text={r['text_count']} active={r['active_users']}")


COMMANDS = {
    "overview": overview,
    "user": user_stats,
    "top-users": top_users,
    "topics": topic_distribution,
    "travel": travel_related,
    "dashboard": dashboard,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print("\n可用指令:", ", ".join(COMMANDS.keys()))
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "user":
        if len(sys.argv) < 3:
            print("用法: python scripts/show_stats.py user <user_id>")
            sys.exit(1)
        COMMANDS[cmd](sys.argv[2])
    else:
        COMMANDS[cmd]()


if __name__ == "__main__":
    main()