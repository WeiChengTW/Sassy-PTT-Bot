"""測試 travel/period.py，含新增的滾動視窗 7d/30d。"""
import time

from travel.period import parse_period, period_filter


def test_all_and_empty_no_filter():
    assert parse_period("all") == (None, None)
    assert parse_period("") == (None, None)
    assert period_filter("all") == ("", [])


def test_year_and_month():
    ys, ye = parse_period("2026")
    assert ys is not None and ye > ys
    ms, me = parse_period("2026-08")
    assert ms is not None and me > ms
    # 月區間比整年短
    assert (me - ms) < (ye - ys)


def test_rolling_window_7d():
    start, end = parse_period("7d")
    now_ms = int(time.time() * 1000)
    assert end is not None and start is not None
    # end 約等於現在（容許幾秒誤差）
    assert abs(end - now_ms) < 5000
    # 視窗約為 7 天
    assert abs((end - start) - 7 * 86_400_000) < 5000


def test_rolling_window_30d_filter_fragment():
    frag, params = period_filter("30d")
    assert frag == " AND timestamp >= ? AND timestamp < ?"
    assert len(params) == 2 and params[1] > params[0]


def test_invalid_period_falls_back_to_no_filter():
    assert parse_period("garbage") == (None, None)
