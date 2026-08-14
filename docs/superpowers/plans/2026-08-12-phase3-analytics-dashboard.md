# Phase 3 — Analytics Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在現有 LIFF 基礎上新增四個分析頁面：成員排行榜、互動關係圖、話題分析、個人檔案，並補齊 DashboardView 的 Chart.js 圖表渲染。

**Architecture:** 全部新功能只加 query functions（`travel/stats_extended.py`）＋ API endpoints（`line_bot/liff_api.py`）＋ Vue views，不動 DB schema。社交網絡力導向圖用 D3 v7（`liff/` 裡安裝），其餘圖表沿用已有的 Chart.js + vue-chartjs。

**Tech Stack:** 延用 Phase 2 全部 stack；新增 `d3@^7` 在 `liff/`。

## Global Constraints

- `travel/` 層不 import Flask；所有查詢邏輯寫在 `travel/stats_extended.py`
- DB_PATH 從 env 讀；測試用 `monkeypatch.setenv("DB_PATH", tmp_path)` 隔離
- LIFF user_id 從 `X-LIFF-UserId` header 取；group_id 從 `X-LIFF-GroupId` header 取
- `reply_to_message_id` / `line_message_id` 已在 `messages` 表，best-pairs 直接 JOIN
- topics 欄位是 JSON 字串（`'["旅行","美食"]'`），Python 端解析
- sentiment 欄位 REAL，NULL 表示未分析；skip NULL rows 不列入平均
- Chart.js 已安裝（`chart.js@^4` + `vue-chartjs@^5`），直接 import
- D3 只在 `InteractionView.vue` 裡用；不全域 register
- pytest 在專案根目錄：`python -m pytest tests/ -v`
- liff 開發：`cd liff && npm run dev`

## File Map

```
新建：
  travel/stats_extended.py          4 個分析查詢函式
  tests/test_stats_extended.py
  liff/src/views/LeaderboardView.vue
  liff/src/views/TopicsView.vue
  liff/src/views/ProfileView.vue
  liff/src/views/InteractionView.vue

修改：
  line_bot/liff_api.py              新增 4 個 GET endpoint
  liff/src/api/client.ts            新增 4 個 api method
  liff/src/router.ts                新增 4 條路由
  liff/src/App.vue                  nav 加 4 個連結
  liff/package.json                 加 d3
```

---

## Task 1: Backend 分析查詢（TDD）

**Files:**
- Create: `travel/stats_extended.py`
- Create: `tests/test_stats_extended.py`

**Interfaces — Produces:**
- `get_leaderboard_data(group_id: str) -> dict`
- `get_interaction_data(group_id: str) -> dict`
- `get_topics_data(group_id: str) -> dict`
- `get_profile_data(user_id: str, group_id: str) -> dict`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_stats_extended.py
"""測試 travel/stats_extended.py 分析查詢。"""
import json
import os
import tempfile
import time
import pytest
from travel.db import init_db, get_conn


@pytest.fixture
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DB_PATH", path)
    init_db()
    yield path
    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


def _insert_msg(conn, *, msg_id, group_id="g1", user_id, user_name,
                msg_type="text", timestamp, reply_to=None,
                topics=None, sentiment=None):
    conn.execute(
        """INSERT INTO messages
           (line_message_id, group_id, user_id, user_name, type,
            timestamp, reply_to_message_id, topics, sentiment)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (msg_id, group_id, user_id, user_name, msg_type,
         timestamp, reply_to,
         json.dumps(topics) if topics else None, sentiment),
    )


# ─── leaderboard ─────────────────────────────────────────────────────────────

def test_leaderboard_rankings_order(temp_db):
    from travel.stats_extended import get_leaderboard_data
    now = int(time.time() * 1000)
    with get_conn() as conn:
        for i in range(3):
            _insert_msg(conn, msg_id=f"m{i}", user_id="uA", user_name="Alice", timestamp=now - i * 1000)
        _insert_msg(conn, msg_id="m3", user_id="uB", user_name="Bob", timestamp=now)
    data = get_leaderboard_data("g1")
    assert data["rankings"][0]["user_id"] == "uA"
    assert data["rankings"][0]["total"] == 3
    assert data["rankings"][1]["user_id"] == "uB"


def test_leaderboard_night_owl(temp_db):
    from travel.stats_extended import get_leaderboard_data
    # 凌晨 2 點 UTC = 2025-01-01 02:00:00 → timestamp in ms
    night_ts = 1735693200000  # 2025-01-01 02:00 UTC
    day_ts   = 1735722000000  # 2025-01-01 10:00 UTC
    with get_conn() as conn:
        _insert_msg(conn, msg_id="n1", user_id="uA", user_name="Alice", timestamp=night_ts)
        _insert_msg(conn, msg_id="n2", user_id="uA", user_name="Alice", timestamp=night_ts + 60000)
        _insert_msg(conn, msg_id="n3", user_id="uB", user_name="Bob",   timestamp=day_ts)
    data = get_leaderboard_data("g1")
    owls = data["night_owls"]
    assert owls[0]["user_id"] == "uA"
    assert owls[0]["night_count"] == 2


def test_leaderboard_type_distribution(temp_db):
    from travel.stats_extended import get_leaderboard_data
    now = int(time.time() * 1000)
    with get_conn() as conn:
        _insert_msg(conn, msg_id="t1", user_id="uA", user_name="A", msg_type="text",    timestamp=now)
        _insert_msg(conn, msg_id="t2", user_id="uA", user_name="A", msg_type="sticker", timestamp=now + 1)
        _insert_msg(conn, msg_id="t3", user_id="uA", user_name="A", msg_type="sticker", timestamp=now + 2)
    data = get_leaderboard_data("g1")
    dist = {d["type"]: d["count"] for d in data["type_distribution"]}
    assert dist["sticker"] == 2
    assert dist["text"] == 1


# ─── interactions ─────────────────────────────────────────────────────────────

def test_interaction_best_pairs(temp_db):
    from travel.stats_extended import get_interaction_data
    now = int(time.time() * 1000)
    with get_conn() as conn:
        _insert_msg(conn, msg_id="base1", user_id="uB", user_name="Bob",   timestamp=now)
        _insert_msg(conn, msg_id="rep1",  user_id="uA", user_name="Alice", timestamp=now + 1, reply_to="base1")
        _insert_msg(conn, msg_id="base2", user_id="uB", user_name="Bob",   timestamp=now + 2)
        _insert_msg(conn, msg_id="rep2",  user_id="uA", user_name="Alice", timestamp=now + 3, reply_to="base2")
    data = get_interaction_data("g1")
    pairs = data["best_pairs"]
    assert len(pairs) >= 1
    assert pairs[0]["count"] == 2
    ids = {pairs[0]["user1_id"], pairs[0]["user2_id"]}
    assert ids == {"uA", "uB"}


def test_interaction_network_nodes_and_edges(temp_db):
    from travel.stats_extended import get_interaction_data
    now = int(time.time() * 1000)
    with get_conn() as conn:
        _insert_msg(conn, msg_id="b1", user_id="uA", user_name="Alice", timestamp=now)
        _insert_msg(conn, msg_id="r1", user_id="uB", user_name="Bob",   timestamp=now + 1, reply_to="b1")
    data = get_interaction_data("g1")
    node_ids = {n["id"] for n in data["network_nodes"]}
    assert "uA" in node_ids and "uB" in node_ids
    assert len(data["network_edges"]) >= 1


# ─── topics ──────────────────────────────────────────────────────────────────

def test_topics_top_topics(temp_db):
    from travel.stats_extended import get_topics_data
    now = int(time.time() * 1000)
    with get_conn() as conn:
        _insert_msg(conn, msg_id="tp1", user_id="uA", user_name="A",
                    timestamp=now, topics=["旅行", "美食"])
        _insert_msg(conn, msg_id="tp2", user_id="uA", user_name="A",
                    timestamp=now + 1, topics=["旅行"])
    data = get_topics_data("g1")
    top = {t["topic"]: t["count"] for t in data["top_topics"]}
    assert top["旅行"] == 2
    assert top["美食"] == 1


def test_topics_daily_sentiment(temp_db):
    from travel.stats_extended import get_topics_data
    ts = 1735693200000  # 2025-01-01
    with get_conn() as conn:
        _insert_msg(conn, msg_id="s1", user_id="uA", user_name="A",
                    timestamp=ts, sentiment=0.8)
        _insert_msg(conn, msg_id="s2", user_id="uA", user_name="A",
                    timestamp=ts + 1000, sentiment=0.4)
    data = get_topics_data("g1")
    assert len(data["daily_sentiment"]) == 1
    assert abs(data["daily_sentiment"][0]["avg_sentiment"] - 0.6) < 0.01


# ─── profile ─────────────────────────────────────────────────────────────────

def test_profile_summary(temp_db):
    from travel.stats_extended import get_profile_data
    now = int(time.time() * 1000)
    with get_conn() as conn:
        for i in range(5):
            _insert_msg(conn, msg_id=f"p{i}", user_id="uA", user_name="A",
                        timestamp=now + i * 1000)
    data = get_profile_data("uA", "g1")
    assert data["summary"]["total"] == 5


def test_profile_time_slots(temp_db):
    from travel.stats_extended import get_profile_data
    # 凌晨 2 點 (hour=2)，白天 10 點 (hour=10)
    night_ts = 1735693200000  # 02:00 UTC
    day_ts   = 1735722000000  # 10:00 UTC
    with get_conn() as conn:
        _insert_msg(conn, msg_id="ps1", user_id="uA", user_name="A", timestamp=night_ts)
        _insert_msg(conn, msg_id="ps2", user_id="uA", user_name="A", timestamp=day_ts)
    data = get_profile_data("uA", "g1")
    slots = data["time_slots"]
    assert slots["night"] == 1    # 0-4
    assert slots["daytime"] == 1  # 9-17


def test_profile_top_topics(temp_db):
    from travel.stats_extended import get_profile_data
    now = int(time.time() * 1000)
    with get_conn() as conn:
        _insert_msg(conn, msg_id="pt1", user_id="uA", user_name="A",
                    timestamp=now, topics=["旅行"])
        _insert_msg(conn, msg_id="pt2", user_id="uA", user_name="A",
                    timestamp=now + 1, topics=["旅行", "美食"])
    data = get_profile_data("uA", "g1")
    topics = {t["topic"]: t["count"] for t in data["top_topics"]}
    assert topics["旅行"] == 2
```

- [ ] **Step 2: 跑測試確認 FAIL**

```bash
python -m pytest tests/test_stats_extended.py -v
```

預期：`ModuleNotFoundError: No module named 'travel.stats_extended'`

- [ ] **Step 3: 實作 `travel/stats_extended.py`**

```python
# travel/stats_extended.py
"""Phase 3 分析查詢：排行榜、互動關係、話題分析、個人檔案。"""
import json
from travel.db import get_conn


def get_leaderboard_data(group_id: str) -> dict:
    with get_conn() as conn:
        rankings = conn.execute(
            """SELECT user_id, user_name,
                      COUNT(*) AS total,
                      SUM(CASE WHEN type='text'    THEN 1 ELSE 0 END) AS text_count,
                      SUM(CASE WHEN type='sticker' THEN 1 ELSE 0 END) AS sticker_count,
                      SUM(CASE WHEN type='image'   THEN 1 ELSE 0 END) AS image_count
               FROM messages WHERE group_id=?
               GROUP BY user_id ORDER BY total DESC LIMIT 20""",
            (group_id,),
        ).fetchall()

        night_owls = conn.execute(
            """SELECT user_id, user_name, COUNT(*) AS night_count
               FROM messages
               WHERE group_id=?
                 AND CAST(strftime('%H', timestamp/1000, 'unixepoch') AS INTEGER) BETWEEN 0 AND 4
               GROUP BY user_id ORDER BY night_count DESC LIMIT 10""",
            (group_id,),
        ).fetchall()

        type_dist = conn.execute(
            """SELECT type, COUNT(*) AS count FROM messages
               WHERE group_id=? GROUP BY type ORDER BY count DESC""",
            (group_id,),
        ).fetchall()

    return {
        "rankings": [dict(r) for r in rankings],
        "night_owls": [dict(r) for r in night_owls],
        "type_distribution": [dict(r) for r in type_dist],
    }


def get_interaction_data(group_id: str) -> dict:
    with get_conn() as conn:
        # Best pairs via reply JOIN — sort by count DESC, deduplicate (A,B)==(B,A)
        raw_pairs = conn.execute(
            """SELECT a.user_id AS user1_id, a.user_name AS user1_name,
                      b.user_id AS user2_id, b.user_name AS user2_name,
                      COUNT(*) AS count
               FROM messages a
               JOIN messages b ON a.reply_to_message_id = b.line_message_id
               WHERE a.group_id=? AND b.group_id=?
               GROUP BY a.user_id, b.user_id
               ORDER BY count DESC LIMIT 40""",
            (group_id, group_id),
        ).fetchall()

        # Merge (A→B) and (B→A) pairs
        pair_map: dict[tuple, dict] = {}
        for r in raw_pairs:
            key = tuple(sorted([r["user1_id"], r["user2_id"]]))
            if key not in pair_map:
                pair_map[key] = {
                    "user1_id": r["user1_id"], "user1_name": r["user1_name"],
                    "user2_id": r["user2_id"], "user2_name": r["user2_name"],
                    "count": r["count"],
                }
            else:
                pair_map[key]["count"] += r["count"]
        best_pairs = sorted(pair_map.values(), key=lambda x: -x["count"])[:10]

        # Network nodes
        nodes_rows = conn.execute(
            """SELECT user_id AS id, user_name AS name, COUNT(*) AS message_count
               FROM messages WHERE group_id=?
               GROUP BY user_id""",
            (group_id,),
        ).fetchall()

    return {
        "best_pairs": best_pairs,
        "network_nodes": [dict(r) for r in nodes_rows],
        "network_edges": [
            {"source": p["user1_id"], "target": p["user2_id"], "weight": p["count"]}
            for p in best_pairs
        ],
    }


def get_topics_data(group_id: str) -> dict:
    with get_conn() as conn:
        topic_rows = conn.execute(
            """SELECT topics FROM messages
               WHERE group_id=? AND topics IS NOT NULL AND topics != '[]'""",
            (group_id,),
        ).fetchall()

        sentiment_rows = conn.execute(
            """SELECT date(timestamp/1000,'unixepoch') AS date,
                      AVG(sentiment) AS avg_sentiment
               FROM messages
               WHERE group_id=? AND sentiment IS NOT NULL
               GROUP BY date ORDER BY date ASC""",
            (group_id,),
        ).fetchall()

        weekly_rows = conn.execute(
            """SELECT strftime('%Y-W%W', timestamp/1000,'unixepoch') AS week, topics
               FROM messages
               WHERE group_id=? AND topics IS NOT NULL AND topics != '[]'
               ORDER BY week""",
            (group_id,),
        ).fetchall()

    # Aggregate topic counts
    topic_counter: dict[str, int] = {}
    for r in topic_rows:
        try:
            for t in json.loads(r["topics"]):
                topic_counter[t] = topic_counter.get(t, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    top_topics = sorted(
        [{"topic": k, "count": v} for k, v in topic_counter.items()],
        key=lambda x: -x["count"],
    )[:20]

    # Weekly trend aggregation
    weekly: dict[str, dict[str, int]] = {}
    for r in weekly_rows:
        week = r["week"]
        if week not in weekly:
            weekly[week] = {}
        try:
            for t in json.loads(r["topics"]):
                weekly[week][t] = weekly[week].get(t, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    weekly_trend = [{"week": w, "topics": counts} for w, counts in sorted(weekly.items())]

    return {
        "top_topics": top_topics,
        "weekly_trend": weekly_trend,
        "daily_sentiment": [dict(r) for r in sentiment_rows],
    }


def get_profile_data(user_id: str, group_id: str) -> dict:
    with get_conn() as conn:
        summary_row = conn.execute(
            """SELECT COUNT(*) AS total,
                      COUNT(DISTINCT date(timestamp/1000,'unixepoch')) AS active_days,
                      MIN(timestamp) AS first_seen,
                      MAX(timestamp) AS last_seen
               FROM messages WHERE user_id=? AND group_id=?""",
            (user_id, group_id),
        ).fetchone()

        type_rows = conn.execute(
            """SELECT type, COUNT(*) AS count FROM messages
               WHERE user_id=? AND group_id=? GROUP BY type ORDER BY count DESC""",
            (user_id, group_id),
        ).fetchall()

        hourly_rows = conn.execute(
            """SELECT CAST(strftime('%H', timestamp/1000,'unixepoch') AS INTEGER) AS hour,
                      COUNT(*) AS count
               FROM messages WHERE user_id=? AND group_id=?
               GROUP BY hour ORDER BY hour""",
            (user_id, group_id),
        ).fetchall()

        topic_rows = conn.execute(
            """SELECT topics FROM messages
               WHERE user_id=? AND group_id=?
                 AND topics IS NOT NULL AND topics != '[]'""",
            (user_id, group_id),
        ).fetchall()

        sentiment_row = conn.execute(
            """SELECT AVG(sentiment) AS avg_sentiment FROM messages
               WHERE user_id=? AND group_id=? AND sentiment IS NOT NULL""",
            (user_id, group_id),
        ).fetchone()

    # Time slots
    hour_map: dict[int, int] = {r["hour"]: r["count"] for r in hourly_rows}
    time_slots = {
        "night":   sum(hour_map.get(h, 0) for h in range(0, 5)),    # 0-4
        "morning": sum(hour_map.get(h, 0) for h in range(5, 9)),    # 5-8
        "daytime": sum(hour_map.get(h, 0) for h in range(9, 18)),   # 9-17
        "evening": sum(hour_map.get(h, 0) for h in range(18, 24)),  # 18-23
    }

    # Per-user topic counts
    topic_counter: dict[str, int] = {}
    for r in topic_rows:
        try:
            for t in json.loads(r["topics"]):
                topic_counter[t] = topic_counter.get(t, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    top_topics = sorted(
        [{"topic": k, "count": v} for k, v in topic_counter.items()],
        key=lambda x: -x["count"],
    )[:10]

    total = summary_row["total"] or 0
    active_days = summary_row["active_days"] or 1
    avg_sentiment = sentiment_row["avg_sentiment"]

    return {
        "summary": {
            "total": total,
            "active_days": active_days,
            "avg_per_day": round(total / active_days, 1) if active_days else 0,
            "first_seen": summary_row["first_seen"],
            "last_seen": summary_row["last_seen"],
        },
        "type_breakdown": [dict(r) for r in type_rows],
        "hourly_distribution": [{"hour": h, "count": hour_map.get(h, 0)} for h in range(24)],
        "time_slots": time_slots,
        "top_topics": top_topics,
        "avg_sentiment": round(avg_sentiment, 3) if avg_sentiment is not None else None,
    }
```

- [ ] **Step 4: 跑測試確認全 PASS**

```bash
python -m pytest tests/test_stats_extended.py -v
```

預期：全 PASS（11 個測試）

- [ ] **Step 5: Commit**

```bash
git add travel/stats_extended.py tests/test_stats_extended.py
git commit -m "feat(stats): add extended analytics queries — leaderboard, interactions, topics, profile"
```

---

## Task 2: API Endpoints + client.ts（TDD）

**Files:**
- Modify: `line_bot/liff_api.py`
- Modify: `liff/src/api/client.ts`
- Modify: `tests/test_liff_api.py`（新增 4 個測試）

**Interfaces — Consumes:**
- `get_leaderboard_data(group_id)` from `travel.stats_extended`
- `get_interaction_data(group_id)` from `travel.stats_extended`
- `get_topics_data(group_id)` from `travel.stats_extended`
- `get_profile_data(user_id, group_id)` from `travel.stats_extended`

**Interfaces — Produces:**
- `GET /liff/leaderboard` → `{"rankings": [...], "night_owls": [...], "type_distribution": [...]}`
- `GET /liff/interactions` → `{"best_pairs": [...], "network_nodes": [...], "network_edges": [...]}`
- `GET /liff/topics` → `{"top_topics": [...], "weekly_trend": [...], "daily_sentiment": [...]}`
- `GET /liff/profile` → `{"summary": {...}, "type_breakdown": [...], "time_slots": {...}, ...}`
- 新增 `api.leaderboard()`, `api.interactions()`, `api.topics()`, `api.profile()` in `client.ts`

- [ ] **Step 1: 在 `tests/test_liff_api.py` 新增測試（在現有測試檔末尾追加）**

找到現有測試檔的 `temp_db` fixture，然後在檔案末尾新增：

```python
# 追加到 tests/test_liff_api.py 末尾

def test_leaderboard_endpoint_member(client, temp_db, monkeypatch):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (line_message_id, group_id, user_id, user_name, type, timestamp) VALUES (?,?,?,?,?,?)",
            ("ml1", "gTest", "uMember", "Member", "text", 1000000),
        )
    res = client.get("/liff/leaderboard",
                     headers={"X-LIFF-UserId": "uMember", "X-LIFF-GroupId": "gTest"})
    assert res.status_code == 200
    data = res.get_json()
    assert "rankings" in data
    assert "night_owls" in data


def test_leaderboard_endpoint_forbidden(client, temp_db):
    res = client.get("/liff/leaderboard",
                     headers={"X-LIFF-UserId": "stranger", "X-LIFF-GroupId": "gTest"})
    assert res.status_code == 403


def test_interactions_endpoint(client, temp_db):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (line_message_id, group_id, user_id, user_name, type, timestamp) VALUES (?,?,?,?,?,?)",
            ("mi1", "gTest", "uMember", "Member", "text", 1000000),
        )
    res = client.get("/liff/interactions",
                     headers={"X-LIFF-UserId": "uMember", "X-LIFF-GroupId": "gTest"})
    assert res.status_code == 200
    data = res.get_json()
    assert "best_pairs" in data and "network_nodes" in data


def test_topics_endpoint(client, temp_db):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (line_message_id, group_id, user_id, user_name, type, timestamp) VALUES (?,?,?,?,?,?)",
            ("mt1", "gTest", "uMember", "Member", "text", 1000000),
        )
    res = client.get("/liff/topics",
                     headers={"X-LIFF-UserId": "uMember", "X-LIFF-GroupId": "gTest"})
    assert res.status_code == 200
    data = res.get_json()
    assert "top_topics" in data and "daily_sentiment" in data


def test_profile_endpoint_self(client, temp_db):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (line_message_id, group_id, user_id, user_name, type, timestamp) VALUES (?,?,?,?,?,?)",
            ("mp1", "gTest", "uMember", "Member", "text", 1000000),
        )
    res = client.get("/liff/profile/uMember",
                     headers={"X-LIFF-UserId": "uMember", "X-LIFF-GroupId": "gTest"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["summary"]["total"] == 1


def test_profile_endpoint_not_self_forbidden(client, temp_db):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (line_message_id, group_id, user_id, user_name, type, timestamp) VALUES (?,?,?,?,?,?)",
            ("mp2", "gTest", "uMember", "Member", "text", 1000001),
        )
    res = client.get("/liff/profile/uMember",
                     headers={"X-LIFF-UserId": "stranger", "X-LIFF-GroupId": "gTest"})
    assert res.status_code == 403
```

- [ ] **Step 2: 跑測試確認 FAIL**

```bash
python -m pytest tests/test_liff_api.py -k "leaderboard or interactions or topics or profile" -v
```

預期：FAIL（endpoints 不存在）

- [ ] **Step 3: 在 `line_bot/liff_api.py` 新增 4 個 endpoint**

在現有 `liff_api.py` 末尾（`admin_award_badges` 之後）追加：

```python
# ── Phase 3 分析 endpoints ───────────────────────────────────────────────────

from travel.stats_extended import (
    get_leaderboard_data, get_interaction_data,
    get_topics_data, get_profile_data,
)


@liff_bp.route("/leaderboard")
def leaderboard():
    user_id = _get_liff_user_id()
    group_id = _get_liff_group_id()
    err = _require_member(user_id, group_id)
    if err:
        return err
    return jsonify(get_leaderboard_data(group_id))


@liff_bp.route("/interactions")
def interactions():
    user_id = _get_liff_user_id()
    group_id = _get_liff_group_id()
    err = _require_member(user_id, group_id)
    if err:
        return err
    return jsonify(get_interaction_data(group_id))


@liff_bp.route("/topics")
def topics():
    user_id = _get_liff_user_id()
    group_id = _get_liff_group_id()
    err = _require_member(user_id, group_id)
    if err:
        return err
    return jsonify(get_topics_data(group_id))


@liff_bp.route("/profile/<target_user_id>")
def profile(target_user_id: str):
    requester = _get_liff_user_id()
    group_id = _get_liff_group_id()
    if not _is_admin(requester) and requester != target_user_id:
        return _forbid("not_self_or_admin")
    return jsonify(get_profile_data(target_user_id, group_id))
```

- [ ] **Step 4: 跑測試確認全 PASS**

```bash
python -m pytest tests/test_liff_api.py -v
```

- [ ] **Step 5: 更新 `liff/src/api/client.ts`**

在現有 `api` 物件末尾追加 4 個 method：

```typescript
// 追加到 api = { ... } 物件末尾（adminAwardBadges 後面加逗號再加）
leaderboard: () => req<any>('/leaderboard'),
interactions: () => req<any>('/interactions'),
topics: () => req<any>('/topics'),
profile: (userId: string) => req<any>(`/profile/${userId}`),
```

- [ ] **Step 6: Commit**

```bash
git add line_bot/liff_api.py tests/test_liff_api.py liff/src/api/client.ts
git commit -m "feat(api): add leaderboard, interactions, topics, profile endpoints"
```

---

## Task 3: LeaderboardView + TopicsView + Router + Nav

**Files:**
- Create: `liff/src/views/LeaderboardView.vue`
- Create: `liff/src/views/TopicsView.vue`
- Modify: `liff/src/router.ts`
- Modify: `liff/src/App.vue`

**Interfaces — Consumes:**
- `api.leaderboard()` → `{ rankings, night_owls, type_distribution }`
- `api.topics()` → `{ top_topics, weekly_trend, daily_sentiment }`

- [ ] **Step 1: 安裝 D3（後面 Task 5 會用）**

```bash
cd liff && npm install d3@^7 && cd ..
```

- [ ] **Step 2: 更新 `liff/src/router.ts`**

在現有 routes 陣列裡，`/403` 之前加入：

```typescript
{ path: '/leaderboard', component: () => import('@/views/LeaderboardView.vue'), meta: { requiresParticipant: true } },
{ path: '/interactions', component: () => import('@/views/InteractionView.vue'), meta: { requiresParticipant: true } },
{ path: '/topics', component: () => import('@/views/TopicsView.vue'), meta: { requiresParticipant: true } },
{ path: '/profile', component: () => import('@/views/ProfileView.vue'), meta: { requiresParticipant: true } },
```

- [ ] **Step 3: 更新 `liff/src/App.vue`** — 將原本水平 nav 改為含 Phase 3 頁面的底部 tab bar

```vue
<template>
  <div class="min-h-screen bg-gray-50 pb-16">
    <main class="p-4">
      <router-view />
    </main>

    <nav v-if="auth.initialized"
         class="fixed bottom-0 inset-x-0 bg-white border-t flex justify-around text-xs py-1 z-50">
      <router-link to="/" class="flex flex-col items-center gap-0.5 px-2 py-1"
                   active-class="text-blue-600">
        <span class="text-lg">📊</span><span>儀表板</span>
      </router-link>
      <router-link to="/leaderboard" class="flex flex-col items-center gap-0.5 px-2 py-1"
                   active-class="text-blue-600">
        <span class="text-lg">🏆</span><span>排行榜</span>
      </router-link>
      <router-link to="/interactions" class="flex flex-col items-center gap-0.5 px-2 py-1"
                   active-class="text-blue-600">
        <span class="text-lg">🤝</span><span>互動</span>
      </router-link>
      <router-link to="/topics" class="flex flex-col items-center gap-0.5 px-2 py-1"
                   active-class="text-blue-600">
        <span class="text-lg">🏷️</span><span>話題</span>
      </router-link>
      <router-link to="/profile" class="flex flex-col items-center gap-0.5 px-2 py-1"
                   active-class="text-blue-600">
        <span class="text-lg">👤</span><span>個人</span>
      </router-link>
      <router-link to="/trips" class="flex flex-col items-center gap-0.5 px-2 py-1"
                   active-class="text-blue-600">
        <span class="text-lg">🧳</span><span>旅行</span>
      </router-link>
      <router-link v-if="auth.role === 'admin'" to="/admin"
                   class="flex flex-col items-center gap-0.5 px-2 py-1"
                   active-class="text-red-500">
        <span class="text-lg">🛠️</span><span>管理</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
</script>
```

- [ ] **Step 4: 建立 `liff/src/views/LeaderboardView.vue`**

```vue
<template>
  <div>
    <h1 class="text-xl font-bold mb-4">🏆 排行榜</h1>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="data">
      <!-- 訊息量排行 -->
      <h2 class="font-semibold mb-2 mt-4">📣 活躍度排行</h2>
      <div class="bg-white rounded-xl shadow divide-y mb-6">
        <div v-for="(u, i) in data.rankings" :key="u.user_id"
             class="flex items-center px-4 py-2 gap-3">
          <span class="text-gray-400 text-sm w-6">
            {{ i === 0 ? '👑' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1 }}
          </span>
          <span class="flex-1 text-sm">{{ u.user_name || u.user_id }}</span>
          <span class="text-sm font-medium">{{ u.total }} 則</span>
        </div>
      </div>

      <!-- 訊息類型圓餅圖 -->
      <h2 class="font-semibold mb-2">📊 訊息類型分佈</h2>
      <div class="bg-white rounded-xl shadow p-4 mb-6">
        <Pie :data="pieChartData" :options="pieOptions" style="max-height:200px" />
      </div>

      <!-- 夜貓子排行 -->
      <h2 class="font-semibold mb-2">🌙 夜貓子排行 (0–4 點)</h2>
      <div class="bg-white rounded-xl shadow divide-y">
        <div v-for="(u, i) in data.night_owls" :key="u.user_id"
             class="flex items-center px-4 py-2 gap-3">
          <span class="text-gray-400 text-sm w-5">{{ i + 1 }}</span>
          <span class="flex-1 text-sm">{{ u.user_name || u.user_id }}</span>
          <span class="text-sm font-medium">{{ u.night_count }} 則</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Pie } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import { api } from '@/api/client'

ChartJS.register(ArcElement, Tooltip, Legend)

const data = ref<any>(null)
const loading = ref(true)

const TYPE_COLORS: Record<string, string> = {
  text: '#60a5fa', sticker: '#f472b6', image: '#34d399',
  video: '#fb923c', audio: '#a78bfa', file: '#94a3b8',
}

const pieChartData = computed(() => {
  if (!data.value) return { labels: [], datasets: [] }
  const dist = data.value.type_distribution
  return {
    labels: dist.map((d: any) => d.type),
    datasets: [{
      data: dist.map((d: any) => d.count),
      backgroundColor: dist.map((d: any) => TYPE_COLORS[d.type] || '#94a3b8'),
    }],
  }
})

const pieOptions = { responsive: true, plugins: { legend: { position: 'bottom' as const } } }

onMounted(async () => {
  try { data.value = await api.leaderboard() }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
```

- [ ] **Step 5: 建立 `liff/src/views/TopicsView.vue`**

```vue
<template>
  <div>
    <h1 class="text-xl font-bold mb-4">🏷️ 話題分析</h1>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="data">
      <!-- 熱門話題 -->
      <h2 class="font-semibold mb-2">🔥 熱門話題 Top 10</h2>
      <div class="bg-white rounded-xl shadow p-4 mb-6">
        <Bar :data="topicBarData" :options="barOptions" style="max-height:220px" />
      </div>

      <!-- 情緒曲線 -->
      <h2 class="font-semibold mb-2">😊 群組情緒曲線</h2>
      <div class="bg-white rounded-xl shadow p-4 mb-6">
        <Line :data="sentimentLineData" :options="lineOptions" style="max-height:180px" />
      </div>

      <!-- 話題列表 -->
      <h2 class="font-semibold mb-2">📋 話題總覽</h2>
      <div class="bg-white rounded-xl shadow divide-y">
        <div v-for="t in data.top_topics" :key="t.topic"
             class="flex items-center px-4 py-2">
          <span class="flex-1 text-sm">{{ t.topic }}</span>
          <span class="text-sm font-medium text-gray-500">{{ t.count }} 次</span>
        </div>
        <div v-if="!data.top_topics.length" class="px-4 py-3 text-sm text-gray-400">
          尚無已分析話題
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Bar, Line } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale,
  BarElement, PointElement, LineElement, Title, Tooltip, Legend, Filler,
} from 'chart.js'
import { api } from '@/api/client'

ChartJS.register(CategoryScale, LinearScale, BarElement, PointElement, LineElement, Title, Tooltip, Legend, Filler)

const data = ref<any>(null)
const loading = ref(true)

const topicBarData = computed(() => {
  if (!data.value) return { labels: [], datasets: [] }
  const top10 = data.value.top_topics.slice(0, 10)
  return {
    labels: top10.map((t: any) => t.topic),
    datasets: [{ label: '提及次數', data: top10.map((t: any) => t.count), backgroundColor: '#60a5fa' }],
  }
})

const barOptions = {
  responsive: true,
  indexAxis: 'y' as const,
  plugins: { legend: { display: false } },
}

const sentimentLineData = computed(() => {
  if (!data.value) return { labels: [], datasets: [] }
  const rows = data.value.daily_sentiment.slice(-30)
  return {
    labels: rows.map((r: any) => r.date),
    datasets: [{
      label: '情緒值',
      data: rows.map((r: any) => r.avg_sentiment),
      borderColor: '#34d399',
      backgroundColor: 'rgba(52,211,153,0.1)',
      fill: true,
      tension: 0.4,
    }],
  }
})

const lineOptions = {
  responsive: true,
  plugins: { legend: { display: false } },
  scales: { y: { min: -1, max: 1 } },
}

onMounted(async () => {
  try { data.value = await api.topics() }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
```

- [ ] **Step 6: 在 Vite dev server 驗證兩個頁面正常顯示**

```bash
# 確認 Vite 跑在 :5174
ss -tlnp | grep 5174
# 瀏覽器開 http://localhost:5174/leaderboard 和 /topics
```

確認：頁面載入不爆錯，圖表 placeholder 出現（資料為空時顯示「尚無...」是正常的）

- [ ] **Step 7: Commit**

```bash
git add liff/src/views/LeaderboardView.vue liff/src/views/TopicsView.vue \
        liff/src/router.ts liff/src/App.vue liff/package.json liff/package-lock.json
git commit -m "feat(liff): add LeaderboardView, TopicsView, bottom tab nav"
```

---

## Task 4: ProfileView

**Files:**
- Create: `liff/src/views/ProfileView.vue`

**Interfaces — Consumes:**
- `api.profile(userId)` → `{ summary, type_breakdown, hourly_distribution, time_slots, top_topics, avg_sentiment }`
- `useAuthStore()` → `auth.userId` (自動帶入當前使用者)

- [ ] **Step 1: 建立 `liff/src/views/ProfileView.vue`**

```vue
<template>
  <div>
    <h1 class="text-xl font-bold mb-4">👤 個人檔案</h1>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="data">
      <!-- Summary cards -->
      <div class="grid grid-cols-2 gap-3 mb-6">
        <div class="bg-white rounded-xl p-4 shadow text-center">
          <p class="text-2xl font-bold">{{ data.summary.total }}</p>
          <p class="text-xs text-gray-500">總訊息數</p>
        </div>
        <div class="bg-white rounded-xl p-4 shadow text-center">
          <p class="text-2xl font-bold">{{ data.summary.active_days }}</p>
          <p class="text-xs text-gray-500">活躍天數</p>
        </div>
        <div class="bg-white rounded-xl p-4 shadow text-center">
          <p class="text-2xl font-bold">{{ data.summary.avg_per_day }}</p>
          <p class="text-xs text-gray-500">平均每日</p>
        </div>
        <div class="bg-white rounded-xl p-4 shadow text-center">
          <p class="text-2xl font-bold">
            {{ data.avg_sentiment != null ? (data.avg_sentiment >= 0 ? '+' : '') + data.avg_sentiment.toFixed(2) : 'N/A' }}
          </p>
          <p class="text-xs text-gray-500">平均情緒</p>
        </div>
      </div>

      <!-- 訊息類型 -->
      <h2 class="font-semibold mb-2">📊 訊息類型</h2>
      <div class="bg-white rounded-xl shadow p-4 mb-6">
        <Bar :data="typeBarData" :options="barOptions" style="max-height:180px" />
      </div>

      <!-- 時段分佈 -->
      <h2 class="font-semibold mb-2">🕐 活躍時段</h2>
      <div class="bg-white rounded-xl shadow p-4 mb-6">
        <div class="grid grid-cols-4 gap-2 text-center text-sm">
          <div v-for="slot in slotList" :key="slot.key"
               class="bg-gray-50 rounded-lg p-2">
            <p class="text-lg">{{ slot.emoji }}</p>
            <p class="font-semibold">{{ data.time_slots[slot.key] }}</p>
            <p class="text-xs text-gray-500">{{ slot.label }}</p>
          </div>
        </div>
      </div>

      <!-- 24h 分佈 -->
      <h2 class="font-semibold mb-2">📈 24 小時分佈</h2>
      <div class="bg-white rounded-xl shadow p-4 mb-6">
        <Bar :data="hourlyBarData" :options="hourlyOptions" style="max-height:160px" />
      </div>

      <!-- 話題 -->
      <h2 class="font-semibold mb-2">🏷️ 常聊話題</h2>
      <div class="bg-white rounded-xl shadow divide-y">
        <div v-for="t in data.top_topics" :key="t.topic"
             class="flex items-center px-4 py-2">
          <span class="flex-1 text-sm">{{ t.topic }}</span>
          <span class="text-sm text-gray-500">{{ t.count }} 次</span>
        </div>
        <div v-if="!data.top_topics.length" class="px-4 py-3 text-sm text-gray-400">
          尚無話題資料
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Bar } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from 'chart.js'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

const auth = useAuthStore()
const data = ref<any>(null)
const loading = ref(true)

const slotList = [
  { key: 'night',   emoji: '🌙', label: '深夜 (0-4)' },
  { key: 'morning', emoji: '🌅', label: '早晨 (5-8)' },
  { key: 'daytime', emoji: '☀️', label: '白天 (9-17)' },
  { key: 'evening', emoji: '🌆', label: '晚上 (18-23)' },
]

const TYPE_COLORS: Record<string, string> = {
  text: '#60a5fa', sticker: '#f472b6', image: '#34d399',
  video: '#fb923c', audio: '#a78bfa', file: '#94a3b8',
}

const typeBarData = computed(() => {
  if (!data.value) return { labels: [], datasets: [] }
  const breakdown = data.value.type_breakdown
  return {
    labels: breakdown.map((d: any) => d.type),
    datasets: [{
      label: '訊息數',
      data: breakdown.map((d: any) => d.count),
      backgroundColor: breakdown.map((d: any) => TYPE_COLORS[d.type] || '#94a3b8'),
    }],
  }
})

const barOptions = { responsive: true, plugins: { legend: { display: false } } }

const hourlyBarData = computed(() => {
  if (!data.value) return { labels: [], datasets: [] }
  const h = data.value.hourly_distribution
  return {
    labels: h.map((d: any) => `${d.hour}時`),
    datasets: [{
      data: h.map((d: any) => d.count),
      backgroundColor: h.map((d: any) => {
        const hr = d.hour
        if (hr < 5)  return '#818cf8'  // 深夜紫
        if (hr < 9)  return '#fb923c'  // 早晨橙
        if (hr < 18) return '#60a5fa'  // 白天藍
        return '#f472b6'               // 夜晚粉
      }),
    }],
  }
})

const hourlyOptions = { responsive: true, plugins: { legend: { display: false } } }

onMounted(async () => {
  try { data.value = await api.profile(auth.userId) }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>
```

- [ ] **Step 2: 在瀏覽器確認 `/profile` 頁面**

開 `http://localhost:5174/profile`，確認 summary cards 顯示、圖表出現、時段 4 格 grid 正常。

- [ ] **Step 3: Commit**

```bash
git add liff/src/views/ProfileView.vue
git commit -m "feat(liff): add ProfileView with type breakdown, time slots, 24h bar chart"
```

---

## Task 5: InteractionView + D3 力導向圖

**Files:**
- Create: `liff/src/views/InteractionView.vue`

**Interfaces — Consumes:**
- `api.interactions()` → `{ best_pairs, network_nodes, network_edges }`

- [ ] **Step 1: 建立 `liff/src/views/InteractionView.vue`**

```vue
<template>
  <div>
    <h1 class="text-xl font-bold mb-4">🤝 互動關係</h1>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="data">
      <!-- 最佳拍檔 -->
      <h2 class="font-semibold mb-2">💬 最佳拍檔（依回覆次數）</h2>
      <div class="bg-white rounded-xl shadow divide-y mb-6">
        <div v-if="!data.best_pairs.length" class="px-4 py-3 text-sm text-gray-400">
          尚無回覆互動資料
        </div>
        <div v-for="(pair, i) in data.best_pairs" :key="i"
             class="flex items-center px-4 py-3 gap-2">
          <span class="text-gray-400 text-sm w-5">{{ i + 1 }}</span>
          <span class="flex-1 text-sm font-medium">
            {{ pair.user1_name || pair.user1_id }}
            <span class="text-gray-400 mx-1">↔</span>
            {{ pair.user2_name || pair.user2_id }}
          </span>
          <span class="text-sm text-gray-500">{{ pair.count }} 次</span>
        </div>
      </div>

      <!-- 社交網絡圖 -->
      <h2 class="font-semibold mb-2">🕸️ 互動網絡</h2>
      <div class="bg-white rounded-xl shadow p-2 mb-6">
        <svg ref="svgRef" :width="svgW" :height="svgH" class="w-full" />
        <p v-if="!data.network_edges.length" class="text-center text-sm text-gray-400 py-4">
          尚無互動資料
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { api } from '@/api/client'

const data = ref<any>(null)
const loading = ref(true)
const svgRef = ref<SVGSVGElement | null>(null)
const svgW = 340
const svgH = 280

async function drawGraph() {
  if (!svgRef.value || !data.value?.network_edges.length) return
  // Dynamic import D3 so it's code-split
  const d3 = await import('d3')

  const nodes: any[] = data.value.network_nodes.map((n: any) => ({ ...n }))
  const links: any[] = data.value.network_edges.map((e: any) => ({
    source: e.source, target: e.target, weight: e.weight,
  }))

  const svg = d3.select(svgRef.value)
  svg.selectAll('*').remove()

  const maxMsg = Math.max(...nodes.map((n: any) => n.message_count), 1)
  const rScale = d3.scaleSqrt().domain([0, maxMsg]).range([6, 20])
  const maxW = Math.max(...links.map((l: any) => l.weight), 1)
  const strokeScale = d3.scaleLinear().domain([0, maxW]).range([1, 5])

  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id((d: any) => d.id).distance(80))
    .force('charge', d3.forceManyBody().strength(-120))
    .force('center', d3.forceCenter(svgW / 2, svgH / 2))
    .force('collision', d3.forceCollide().radius((d: any) => rScale(d.message_count) + 4))

  const link = svg.append('g')
    .selectAll('line')
    .data(links)
    .join('line')
    .attr('stroke', '#cbd5e1')
    .attr('stroke-width', (d: any) => strokeScale(d.weight))

  const node = svg.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .call(d3.drag<any, any>()
      .on('start', (event, d) => {
        if (!event.active) sim.alphaTarget(0.3).restart()
        d.fx = d.x; d.fy = d.y
      })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
      .on('end', (event, d) => {
        if (!event.active) sim.alphaTarget(0)
        d.fx = null; d.fy = null
      }))

  node.append('circle')
    .attr('r', (d: any) => rScale(d.message_count))
    .attr('fill', '#60a5fa')
    .attr('stroke', '#fff')
    .attr('stroke-width', 2)

  node.append('text')
    .text((d: any) => (d.name || d.id).slice(0, 4))
    .attr('text-anchor', 'middle')
    .attr('dy', '0.35em')
    .attr('font-size', 9)
    .attr('fill', '#fff')
    .attr('pointer-events', 'none')

  sim.on('tick', () => {
    link
      .attr('x1', (d: any) => d.source.x)
      .attr('y1', (d: any) => d.source.y)
      .attr('x2', (d: any) => d.target.x)
      .attr('y2', (d: any) => d.target.y)
    node.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
  })
}

onMounted(async () => {
  try { data.value = await api.interactions() }
  catch (e) { console.error(e) }
  finally {
    loading.value = false
    await nextTick()
    drawGraph()
  }
})
</script>
```

- [ ] **Step 2: 在瀏覽器確認 `/interactions`**

開 `http://localhost:5174/interactions`，確認：
- 最佳拍檔列表出現（無資料時顯示提示文字）
- SVG 區域出現（有回覆資料時，節點與連線會在幾秒內穩定下來）
- 節點可以拖曳

- [ ] **Step 3: Commit**

```bash
git add liff/src/views/InteractionView.vue
git commit -m "feat(liff): add InteractionView with D3 force-directed network graph"
```

---

## Self-Review Checklist

**Spec coverage（對照用戶提供的設計稿）：**

| 設計稿功能 | 對應 Task | 實作 |
|-----------|----------|------|
| 群組總覽折線圖、熱力圖 | — | ⚠️ 已在 Phase 2 `DashboardView` 有 heatmap data，但未加 Chart.js 渲染 → 留給用戶選擇是否補上 |
| 成員排行榜 | Task 3 LeaderboardView | ✅ |
| 類型分佈圓餅圖 | Task 3 LeaderboardView | ✅ |
| 夜貓子排行 | Task 3 LeaderboardView | ✅ |
| 最佳拍檔 | Task 5 InteractionView | ✅ |
| 社交網絡圖 | Task 5 InteractionView | ✅ D3 force-directed |
| 熱門話題 | Task 3 TopicsView | ✅ |
| 情緒曲線 | Task 3 TopicsView | ✅ |
| 個人總訊息/活躍天數 | Task 4 ProfileView | ✅ |
| 個人類型分佈 | Task 4 ProfileView | ✅ |
| 個人時段分佈 | Task 4 ProfileView | ✅ |
| 個人話題 | Task 4 ProfileView | ✅ |
| 個人情緒 | Task 4 ProfileView | ✅ |
| 最長對話串 | — | ❌ 未實作（需 window-based consecutive 分析，留 optional） |

**注意：**
- DashboardView 的折線圖和熱力圖 data 已有，只差前端 Chart.js 渲染 → 可以在 Task 3 之後單獨補
- 「最長對話串」需要 rolling window 計算，實作複雜度較高，本計畫標為 optional

**Placeholder scan：** 無 TBD / TODO 字樣。

**Type consistency：** `api.profile(userId)` → endpoint `/profile/<target_user_id>` → `get_profile_data(user_id, group_id)` — 全部一致。
