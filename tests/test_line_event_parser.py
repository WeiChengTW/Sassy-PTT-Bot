from unittest.mock import MagicMock

from travel.line_event_parser import (
    extract_content,
    extract_message_type,
    extract_reply_to_message_id,
    extract_sticker_metadata,
    extract_text_metadata,
    extract_video_audio_metadata,
    extract_file_metadata,
    extract_location_metadata,
    extract_image_metadata,
)


def _msg(cls_name: str, **attrs) -> MagicMock:
    msg = MagicMock()
    msg.__class__.__name__ = cls_name
    for k, v in attrs.items():
        setattr(msg, k, v)
    return msg


def test_extract_message_type_text():
    assert extract_message_type(_msg("TextMessageContent")) == "text"


def test_extract_message_type_sticker():
    assert extract_message_type(_msg("StickerMessageContent")) == "sticker"


def test_extract_message_type_image():
    assert extract_message_type(_msg("ImageMessageContent")) == "image"


def test_extract_message_type_video():
    assert extract_message_type(_msg("VideoMessageContent")) == "video"


def test_extract_message_type_audio():
    assert extract_message_type(_msg("AudioMessageContent")) == "audio"


def test_extract_message_type_file():
    assert extract_message_type(_msg("FileMessageContent")) == "file"


def test_extract_message_type_location():
    assert extract_message_type(_msg("LocationMessageContent")) == "location"


def test_extract_message_type_unknown():
    assert extract_message_type(_msg("SomethingElse")) == "unknown"


def test_extract_content_text():
    msg = _msg("TextMessageContent", text="hello")
    assert extract_content(msg, "text") == "hello"


def test_extract_content_sticker_is_none():
    msg = _msg("StickerMessageContent", text=None)
    assert extract_content(msg, "sticker") is None


def test_extract_reply_to_message_id_present():
    msg = _msg("TextMessageContent", quoted_message_id="q-123")
    assert extract_reply_to_message_id(msg) == "q-123"


def test_extract_reply_to_message_id_absent():
    msg = _msg("TextMessageContent", quoted_message_id=None)
    assert extract_reply_to_message_id(msg) is None


def test_extract_text_metadata_emojis():
    e1 = MagicMock(); e1.index = 0; e1.length = 1; e1.product_id = "p1"; e1.emoji_id = "e1"
    e2 = MagicMock(); e2.index = 5; e2.length = 2; e2.product_id = "p2"; e2.emoji_id = "e2"
    msg = _msg(
        "TextMessageContent",
        emojis=[e1, e2],
        mention=MagicMock(mentionees=[]),
    )
    meta = extract_text_metadata(msg)
    assert "emojis" in meta
    assert meta["emojis"] == [
        {"index": 0, "length": 1, "product_id": "p1", "emoji_id": "e1"},
        {"index": 5, "length": 2, "product_id": "p2", "emoji_id": "e2"},
    ]


def test_extract_text_metadata_mention():
    m1 = MagicMock(); m1.index = 0; m1.length = 8; m1.user_id = "U001"; m1.type = "user"
    m2 = MagicMock(); m2.index = 9; m2.length = 8; m2.user_id = "U002"; m2.type = "user"
    msg = _msg(
        "TextMessageContent",
        emojis=None,
        mention=MagicMock(mentionees=[m1, m2]),
    )
    meta = extract_text_metadata(msg)
    assert meta["mention_user_ids"] == ["U001", "U002"]


def test_extract_text_metadata_no_mention():
    msg = _msg("TextMessageContent", emojis=None, mention=None)
    meta = extract_text_metadata(msg)
    assert "mention_user_ids" not in meta


def test_extract_sticker_metadata_full():
    msg = _msg(
        "StickerMessageContent",
        sticker_id="786581052",
        package_id="789",
        sticker_resource_type="STATIC",
        keywords=["hi", "happy"],
        text=None,
        quoted_message_id=None,
    )
    meta = extract_sticker_metadata(msg)
    assert meta["sticker_id"] == "786581052"
    assert meta["package_id"] == "789"
    assert meta["sticker_resource_type"] == "STATIC"
    assert meta["keywords"] == ["hi", "happy"]
    assert "text" not in meta


def test_extract_sticker_metadata_with_text():
    msg = _msg(
        "StickerMessageContent",
        sticker_id="1",
        package_id="2",
        sticker_resource_type="MESSAGE",
        keywords=[],
        text="嗚嗚",
    )
    meta = extract_sticker_metadata(msg)
    assert meta["text"] == "嗚嗚"
    assert meta["sticker_resource_type"] == "MESSAGE"


def test_extract_video_metadata_with_duration():
    msg = _msg("VideoMessageContent", duration=5000)
    meta = extract_video_audio_metadata(msg, "video")
    assert meta["duration_ms"] == 5000


def test_extract_audio_metadata_with_duration():
    msg = _msg("AudioMessageContent", duration=30000)
    meta = extract_video_audio_metadata(msg, "audio")
    assert meta["duration_ms"] == 30000


def test_extract_video_metadata_no_duration():
    msg = _msg("VideoMessageContent", duration=None)
    meta = extract_video_audio_metadata(msg, "video")
    assert "duration_ms" not in meta


def test_extract_file_metadata():
    msg = _msg(
        "FileMessageContent",
        file_name="doc.pdf",
        file_size=12345,
    )
    meta = extract_file_metadata(msg)
    assert meta["file_name"] == "doc.pdf"
    assert meta["file_size"] == 12345


def test_extract_location_metadata_full():
    msg = _msg(
        "LocationMessageContent",
        title="墾丁大街",
        address="屏東縣恆春鎮墾丁路",
        latitude=22.0023,
        longitude=120.7467,
    )
    meta = extract_location_metadata(msg)
    assert meta["title"] == "墾丁大街"
    assert meta["address"] == "屏東縣恆春鎮墾丁路"
    assert meta["latitude"] == 22.0023
    assert meta["longitude"] == 120.7467


def test_extract_location_metadata_no_title():
    msg = _msg(
        "LocationMessageContent",
        title=None,
        address="somewhere",
        latitude=25.0,
        longitude=121.5,
    )
    meta = extract_location_metadata(msg)
    assert "title" not in meta
    assert meta["address"] == "somewhere"


def test_extract_image_metadata_minimal():
    msg = _msg("ImageMessageContent", image_set=None)
    meta = extract_image_metadata(msg)
    assert meta == {}