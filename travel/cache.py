"""輕量 API 回應快取（stale-while-revalidate）。

用於排行榜 / 儀表板等重運算：每次讀取都對 messages 全表掃描多輪，隨資料量成長變慢。
策略：
  - 命中且新鮮（< TTL）→ 直接回傳。
  - 命中但過期 → 立刻回傳舊值，同時背景重算（同 key 只跑一個重算執行緒）。
  - 未命中（冷啟）→ 同步計算一次，寫入後回傳。

快取存於 SQLite api_cache 表，跨程序重啟仍在；payload 為 JSON 字串。
"""
import json
import threading
import time

from travel.db import get_conn

DEFAULT_TTL = 600  # 10 分鐘

_refreshing: set[str] = set()
_lock = threading.Lock()


def _read(key: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT payload, computed_at FROM api_cache WHERE cache_key=?", (key,)
        ).fetchone()
    if not row:
        return None
    return json.loads(row["payload"]), row["computed_at"]


def _write(key: str, value) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO api_cache (cache_key, payload, computed_at)
               VALUES (?, ?, ?)
               ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload,
                                                    computed_at=excluded.computed_at""",
            (key, json.dumps(value, ensure_ascii=False), int(time.time())),
        )


def _refresh_async(key: str, compute) -> None:
    with _lock:
        if key in _refreshing:
            return  # 已有重算中，避免重覆
        _refreshing.add(key)

    def run():
        try:
            _write(key, compute())
        except Exception:
            pass  # best-effort；下次讀取再重試
        finally:
            with _lock:
                _refreshing.discard(key)

    threading.Thread(target=run, daemon=True).start()


def cached(kind: str, group_id: str, period: str, compute, ttl: int = DEFAULT_TTL):
    """回傳 compute() 的結果，套 stale-while-revalidate 快取。

    kind: 邏輯名稱（如 'leaderboards' / 'dashboard'）。compute: 無參數、回傳可 JSON 序列化物件。
    """
    key = f"{kind}:{group_id}:{period}"
    hit = _read(key)
    if hit is not None:
        payload, computed_at = hit
        if time.time() - computed_at >= ttl:
            _refresh_async(key, compute)  # 過期：背景重算，先回舊值
        return payload
    # 冷啟：同步算一次
    value = compute()
    _write(key, value)
    return value


def invalidate(group_id: str | None = None) -> None:
    """清除快取。給定 group_id 只清該群，否則全清。"""
    with get_conn() as conn:
        if group_id:
            conn.execute("DELETE FROM api_cache WHERE cache_key LIKE ?", (f"%:{group_id}:%",))
        else:
            conn.execute("DELETE FROM api_cache")
