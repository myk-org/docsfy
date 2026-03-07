from __future__ import annotations

import json
import re
from typing import Any

from simple_logger.logger import get_logger

logger = get_logger(name=__name__)


def parse_json_response(raw_text: str) -> dict[str, Any] | None:
    result = _parse_json_payload(
        raw_text,
        opening_char="{",
        inline_extractor=_extract_json_by_braces,
        code_block_extractor=_extract_json_from_code_blocks,
        label="JSON",
    )
    if isinstance(result, dict):
        return result
    return None


def parse_json_array_response(raw_text: str) -> list[Any] | None:
    """Parse AI response as a JSON array while preserving item types."""
    result = _parse_json_payload(
        raw_text,
        opening_char="[",
        inline_extractor=_extract_json_array_by_brackets,
        code_block_extractor=_extract_json_array_from_code_blocks,
        label="JSON array",
    )
    if isinstance(result, list):
        return result
    return None


def _parse_json_payload(
    raw_text: str,
    *,
    opening_char: str,
    inline_extractor: Any,
    code_block_extractor: Any,
    label: str,
) -> Any | None:
    text = raw_text.strip()
    if not text:
        return None
    if text.startswith(opening_char):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass
    result = inline_extractor(text)
    if result is not None:
        return result
    result = code_block_extractor(text)
    if result is not None:
        return result
    logger.warning(f"Failed to parse AI response as {label}")
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


def _extract_json_array_by_brackets(text: str) -> list[Any] | None:
    first_bracket = text.find("[")
    if first_bracket == -1:
        return None
    last_bracket = text.rfind("]")
    if last_bracket == -1 or last_bracket <= first_bracket:
        return None
    json_str = text[first_bracket : last_bracket + 1]
    try:
        result = json.loads(json_str)
        if isinstance(result, list):
            return result
    except (json.JSONDecodeError, ValueError):
        pass
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


def _extract_json_array_from_code_blocks(text: str) -> list[Any] | None:
    blocks = re.findall(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    for block_content in blocks:
        block_content = block_content.strip()
        if not block_content or "[" not in block_content:
            continue
        try:
            result = json.loads(block_content)
            if isinstance(result, list):
                return result
        except (json.JSONDecodeError, ValueError):
            pass
        result = _extract_json_array_by_brackets(block_content)
        if result is not None:
            return result
    return None
