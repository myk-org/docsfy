from __future__ import annotations

import json
import re
from typing import Any

from simple_logger.logger import get_logger

logger = get_logger(name=__name__)


def parse_json_response(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass
    result = _extract_json_by_braces(text)
    if result is not None:
        return result
    result = _extract_json_from_code_blocks(text)
    if result is not None:
        return result
    logger.warning("Failed to parse AI response as JSON")
    return None


def _extract_json_by_braces(text: str) -> dict[str, Any] | None:
    first_brace = text.find("{")
    if first_brace == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    end_pos = -1
    for i in range(first_brace, len(text)):
        char = text[i]
        if escape_next:
            escape_next = False
            continue
        if char == "\\":
            if in_string:
                escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end_pos = i
                break
    if end_pos == -1:
        return None
    json_str = text[first_brace : end_pos + 1]
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_json_from_code_blocks(text: str) -> dict[str, Any] | None:
    blocks = re.findall(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    for block_content in blocks:
        block_content = block_content.strip()
        if not block_content or "{" not in block_content:
            continue
        try:
            return json.loads(block_content)
        except (json.JSONDecodeError, ValueError):
            pass
        result = _extract_json_by_braces(block_content)
        if result is not None:
            return result
    return None
