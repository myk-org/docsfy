from __future__ import annotations

import json


def test_parse_direct_json() -> None:
    from docsfy.json_parser import parse_json_response

    data = {"project_name": "test", "navigation": []}
    result = parse_json_response(json.dumps(data))
    assert result == data


def test_parse_json_with_surrounding_text() -> None:
    from docsfy.json_parser import parse_json_response

    raw = 'Here is the plan:\n{"project_name": "test", "navigation": []}\nDone!'
    result = parse_json_response(raw)
    assert result is not None
    assert result["project_name"] == "test"


def test_parse_json_from_code_block() -> None:
    from docsfy.json_parser import parse_json_response

    raw = '```json\n{"project_name": "test", "navigation": []}\n```'
    result = parse_json_response(raw)
    assert result is not None
    assert result["project_name"] == "test"


def test_parse_json_nested_braces() -> None:
    from docsfy.json_parser import parse_json_response

    data = {"project_name": "test", "meta": {"key": "value"}, "navigation": []}
    raw = f"Some text before {json.dumps(data)} some text after"
    result = parse_json_response(raw)
    assert result is not None
    assert result["meta"]["key"] == "value"


def test_parse_json_returns_none_for_garbage() -> None:
    from docsfy.json_parser import parse_json_response

    result = parse_json_response("this is not json at all")
    assert result is None


def test_parse_json_empty_string() -> None:
    from docsfy.json_parser import parse_json_response

    result = parse_json_response("")
    assert result is None


def test_parse_json_with_escaped_quotes() -> None:
    from docsfy.json_parser import parse_json_response

    raw = '{"project_name": "test \\"quoted\\" name", "navigation": []}'
    result = parse_json_response(raw)
    assert result is not None
    assert "quoted" in result["project_name"]
