"""G8 偵查器：偵測「ji + ba」同音詞（雞巴/紀吧/幾把…）。"""
import pytest

from line_bot.bot import is_g8


@pytest.mark.parametrize("text", [
    "除了洪偉城都雞吧",        # 句尾
    "最主要的是年紀吧",        # 紀吧
    "幾把人啊",               # 句首
    "你這個機八人",            # 句中
    "雞 巴",                  # 中間夾空白
    "雞，吧",                 # 中間夾標點
    "雞...吧",
    "年紀～吧！",
    "今天G8了",
    "g8",
    "JB啦",
])
def test_g8_triggers(text):
    assert is_g8(text) is True


@pytest.mark.parametrize("text", [
    "等下啊我們什麼生肖",
    "記得吧",                 # ji 與 ba 不相鄰
    "計畫一下",
    "給吧",
    "雞a吧",                  # 中間夾英數字不算
    "AG8X",                   # 英數混在單字中
    "",
])
def test_g8_not_triggers(text):
    assert is_g8(text) is False
