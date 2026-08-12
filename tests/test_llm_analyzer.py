import pytest

from travel.llm_analyzer import build_prompt, parse_llm_response


def test_build_prompt_includes_all_messages():
    messages = [
        {"id": 1, "user_name": "Alice", "content": "周末去墾丁", "timestamp": 1700000000000},
        {"id": 2, "user_name": "Bob", "content": "+1", "timestamp": 1700000001000},
    ]
    prompt = build_prompt(messages)
    assert "Alice" in prompt
    assert "Bob" in prompt
    assert "周末去墾丁" in prompt


def test_build_prompt_handles_none_content():
    messages = [{"id": 1, "user_name": "Alice", "content": None, "timestamp": 1700000000000}]
    prompt = build_prompt(messages)
    assert "Alice" in prompt


def test_parse_llm_response_strips_json_block():
    raw = '```json\n[{"id": 1, "is_travel_related": 1}]\n```'
    result = parse_llm_response(raw)
    assert result == [{"id": 1, "is_travel_related": 1}]


def test_parse_llm_response_handles_plain_json():
    raw = '[{"id": 1, "topics": ["travel"]}]'
    result = parse_llm_response(raw)
    assert result == [{"id": 1, "topics": ["travel"]}]


def test_parse_llm_response_raises_on_invalid():
    with pytest.raises(ValueError):
        parse_llm_response("not json at all")


def test_parse_llm_response_raises_on_non_array():
    raw = '{"id": 1}'
    with pytest.raises(ValueError):
        parse_llm_response(raw)