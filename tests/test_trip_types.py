"""旅行類型：後端 VALID_TYPES 與前端 tripTypes.ts 必須同步。"""
import re
from pathlib import Path

from travel.trip_types import VALID_TYPES, normalize_trip_types


def test_frontend_and_backend_types_in_sync():
    ts = (Path(__file__).resolve().parents[1] / "liff/src/constants/tripTypes.ts").read_text(encoding="utf-8")
    assert set(re.findall(r"value: '([a-z_]+)'", ts)) == VALID_TYPES


def test_new_types_accepted():
    assert normalize_trip_types(["school", "meme"]) == '["school", "meme"]'
