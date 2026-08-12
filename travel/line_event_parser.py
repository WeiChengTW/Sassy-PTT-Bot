"""LINE event 欄位抽取（pure functions，方便 TDD）。

從 linebot SDK 的 MessageEvent 物件抽取所有可用 metadata，
統一放進 metadata JSON 欄位，保留 LINE 原始欄位供未來擴展。
"""

_KNOWN_TYPES = {
    "TextMessageContent": "text",
    "StickerMessageContent": "sticker",
    "ImageMessageContent": "image",
    "VideoMessageContent": "video",
    "AudioMessageContent": "audio",
    "FileMessageContent": "file",
    "LocationMessageContent": "location",
}


def extract_message_type(msg) -> str:
    """從 message 物件 class name 抽出訊息類型。"""
    cls_name = type(msg).__name__
    return _KNOWN_TYPES.get(cls_name, "unknown")


def extract_content(msg, msg_type: str) -> str | None:
    """提取文字內容。Text 才會有值；其他類型固定 None。"""
    if msg_type == "text":
        return getattr(msg, "text", None)
    return None


def extract_reply_to_message_id(msg) -> str | None:
    """提取回覆訊息 ID（quoted_message_id）。"""
    return getattr(msg, "quoted_message_id", None)


def extract_text_metadata(msg) -> dict:
    """Text 訊息的 metadata：emojis + 提及的 user_ids。"""
    meta: dict = {}
    emojis = getattr(msg, "emojis", None) or []
    if emojis:
        meta["emojis"] = [
            {
                "index": getattr(e, "index", None),
                "length": getattr(e, "length", None),
                "product_id": getattr(e, "product_id", None),
                "emoji_id": getattr(e, "emoji_id", None),
            }
            for e in emojis
        ]
    mention = getattr(msg, "mention", None)
    if mention:
        mentionees = getattr(mention, "mentionees", None) or []
        user_ids = [
            getattr(m, "user_id", None)
            for m in mentionees
            if getattr(m, "user_id", None)
        ]
        if user_ids:
            meta["mention_user_ids"] = user_ids
    return meta


def extract_sticker_metadata(msg) -> dict:
    """Sticker 訊息的 metadata：id + package + resource_type + keywords + text。"""
    meta: dict = {}
    sticker_id = getattr(msg, "sticker_id", None)
    if sticker_id is not None:
        meta["sticker_id"] = sticker_id
    package_id = getattr(msg, "package_id", None)
    if package_id is not None:
        meta["package_id"] = package_id
    resource_type = getattr(msg, "sticker_resource_type", None)
    if resource_type:
        meta["sticker_resource_type"] = resource_type
    keywords = getattr(msg, "keywords", None) or []
    if keywords:
        meta["keywords"] = list(keywords)
    text = getattr(msg, "text", None)
    if text:
        meta["text"] = text
    return meta


def extract_video_audio_metadata(msg, msg_type: str) -> dict:
    """Video / Audio 的 metadata：duration_ms。"""
    meta: dict = {}
    duration = getattr(msg, "duration", None)
    if duration is not None:
        meta["duration_ms"] = int(duration)
    return meta


def extract_file_metadata(msg) -> dict:
    """File 的 metadata：file_name + file_size。"""
    meta: dict = {}
    name = getattr(msg, "file_name", None)
    if name:
        meta["file_name"] = name
    size = getattr(msg, "file_size", None)
    if size is not None:
        meta["file_size"] = int(size)
    return meta


def extract_location_metadata(msg) -> dict:
    """Location 的 metadata：title + address + latitude + longitude。"""
    meta: dict = {}
    title = getattr(msg, "title", None)
    if title:
        meta["title"] = title
    address = getattr(msg, "address", None)
    if address:
        meta["address"] = address
    lat = getattr(msg, "latitude", None)
    if lat is not None:
        meta["latitude"] = float(lat)
    lng = getattr(msg, "longitude", None)
    if lng is not None:
        meta["longitude"] = float(lng)
    return meta


def extract_image_metadata(msg) -> dict:
    """Image 的 metadata：保留空 dict（Phase 1 決定圖只計數，不拉 image_set URLs）。"""
    return {}


_EXTRACTORS = {
    "text": extract_text_metadata,
    "sticker": extract_sticker_metadata,
    "video": lambda m: extract_video_audio_metadata(m, "video"),
    "audio": lambda m: extract_video_audio_metadata(m, "audio"),
    "file": extract_file_metadata,
    "location": extract_location_metadata,
    "image": extract_image_metadata,
}


def extract_message_metadata(msg, msg_type: str) -> dict:
    """依訊息類型抽出對應 metadata。"""
    extractor = _EXTRACTORS.get(msg_type)
    return extractor(msg) if extractor else {}