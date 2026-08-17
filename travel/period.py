"""時間區間過濾工具：把 period 字串轉成 epoch-ms 區間與 SQL 片段。

period 格式：
- "all" 或空字串 → 不過濾
- "2026"    → 該年整年
- "2026-08" → 該月整月
- "7d" / "30d" → 從現在往回推 N 天的滾動視窗（週報／月報用）
"""
from datetime import datetime

LOCAL_TZ = datetime.now().astimezone().tzinfo


def parse_period(period: str) -> tuple[int | None, int | None]:
    """回傳 (start_ms, end_ms)。無過濾時回 (None, None)。"""
    if not period or period == "all":
        return (None, None)
    # 滾動視窗："7d" / "30d"：從此刻往回推 N 天（end 為現在）。
    if period.endswith("d") and period[:-1].isdigit():
        days = int(period[:-1])
        now_ms = int(datetime.now().astimezone().timestamp() * 1000)
        return (now_ms - days * 86_400_000, now_ms)
    try:
        parts = period.split("-")
        year = int(parts[0])
        if len(parts) == 1:
            start = datetime(year, 1, 1, tzinfo=LOCAL_TZ)
            end = datetime(year + 1, 1, 1, tzinfo=LOCAL_TZ)
        else:
            month = int(parts[1])
            start = datetime(year, month, 1, tzinfo=LOCAL_TZ)
            end = (datetime(year + 1, 1, 1, tzinfo=LOCAL_TZ)
                   if month == 12 else
                   datetime(year, month + 1, 1, tzinfo=LOCAL_TZ))
    except (ValueError, IndexError):
        return (None, None)
    return (int(start.timestamp() * 1000), int(end.timestamp() * 1000))


def period_filter(period: str, column: str = "timestamp") -> tuple[str, list[int]]:
    """回傳 (sql_fragment, params)，可直接接在 WHERE 之後。

    例：" AND timestamp >= ? AND timestamp < ?"，無過濾時回 ("", [])。
    end 為半開區間（< end），避免跨月/跨年邊界重複。
    """
    start, end = parse_period(period)
    if start is None:
        return ("", [])
    return (f" AND {column} >= ? AND {column} < ?", [start, end])
