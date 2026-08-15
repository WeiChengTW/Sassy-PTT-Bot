"""旅行類型權威清單與解析工具。

`trips.trip_type` 欄位型別維持 TEXT，改存 JSON 陣列字串（如 '["beach","food"]'）。
向後相容：舊資料可能是 NULL 或單一字串（"beach"），一律經 parse_trip_types 讀取。

前端 liff/src/constants/tripTypes.ts 持有對應的 value/label/emoji，需手動同步。
"""
import json

# value 權威清單（label/emoji 由前端持有，後端只需驗證 value）
VALID_TYPES: set[str] = {
    "beach", "mountain", "camping", "hotspring", "city",
    "food", "abroad", "theme_park", "culture", "roadtrip", "other",
}


def parse_trip_types(raw) -> list[str]:
    """把 DB 內的 trip_type 原始值解析成 list[str]。

    - falsy（None/空字串）→ []
    - JSON 陣列字串 → 過濾非空、去重保序（僅保留 VALID_TYPES）
    - legacy 單值字串 → [raw]（保留原值，即使不在 VALID_TYPES，避免吃掉舊資料）
    """
    if not raw:
        return []
    text = raw.strip() if isinstance(raw, str) else raw
    if isinstance(text, str) and text.startswith("["):
        try:
            items = json.loads(text)
        except (ValueError, TypeError):
            return []
        seen: set[str] = set()
        result: list[str] = []
        for it in items:
            if it and it in VALID_TYPES and it not in seen:
                seen.add(it)
                result.append(it)
        return result
    # legacy 單值字串
    return [text]


def normalize_trip_types(value) -> str | None:
    """把使用者輸入（list[str] | str | None）正規化成儲存字串。

    過濾至 VALID_TYPES、去重保序。空 → None；否則回 JSON 陣列字串。
    """
    if not value:
        return None
    items = [value] if isinstance(value, str) else list(value)
    seen: set[str] = set()
    result: list[str] = []
    for it in items:
        if it and it in VALID_TYPES and it not in seen:
            seen.add(it)
            result.append(it)
    if not result:
        return None
    return json.dumps(result, ensure_ascii=False)
