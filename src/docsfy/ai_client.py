from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from simple_logger.logger import get_logger

logger = get_logger(name=__name__)


@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable[[str, str, Path | None], list[str]]
    uses_own_cwd: bool = False


def _build_claude_cmd(binary: str, model: str, _cwd: Path | None) -> list[str]:
    return [binary, "--model", model, "--dangerously-skip-permissions", "-p"]


def _build_gemini_cmd(binary: str, model: str, _cwd: Path | None) -> list[str]:
    return [binary, "--model", model, "--yolo"]


def _build_cursor_cmd(binary: str, model: str, cwd: Path | None) -> list[str]:
    cmd = [binary, "--force", "--model", model, "--print"]
    if cwd:
        cmd.extend(["--workspace", str(cwd)])
    return cmd


PROVIDER_CONFIG: dict[str, ProviderConfig] = {
    "claude": ProviderConfig(binary="claude", build_cmd=_build_claude_cmd),
    "gemini": ProviderConfig(binary="gemini", build_cmd=_build_gemini_cmd),
    "cursor": ProviderConfig(binary="agent", uses_own_cwd=True, build_cmd=_build_cursor_cmd),
}
VALID_AI_PROVIDERS = set(PROVIDER_CONFIG.keys())


def _get_ai_cli_timeout() -> int:
    raw = os.getenv("AI_CLI_TIMEOUT", "60")
    try:
        value = int(raw)
        if value <= 0:
            raise ValueError
        return value
    except (ValueError, TypeError):
        logger.warning(f"Invalid AI_CLI_TIMEOUT={raw}; defaulting to 60")
        return 60


AI_CLI_TIMEOUT = _get_ai_cli_timeout()


async def call_ai_cli(
    prompt: str, cwd: Path | None = None, ai_provider: str = "", ai_model: str = "", ai_cli_timeout: int | None = None,
) -> tuple[bool, str]:
    config = PROVIDER_CONFIG.get(ai_provider)
    if not config:
        return (False, f"Unknown AI provider: '{ai_provider}'. Valid: {', '.join(sorted(VALID_AI_PROVIDERS))}")
    if not ai_model:
        return (False, "No AI model configured. Set AI_MODEL environment variable.")
    provider_info = f"{ai_provider.upper()} ({ai_model})"
    cmd = config.build_cmd(config.binary, ai_model, cwd)
    subprocess_cwd = None if config.uses_own_cwd else cwd
    effective_timeout = ai_cli_timeout or AI_CLI_TIMEOUT
    timeout = effective_timeout * 60
    logger.info(f"Calling {provider_info} CLI")
    try:
        result = await asyncio.to_thread(
            subprocess.run, cmd, cwd=subprocess_cwd, capture_output=True, text=True, timeout=timeout, input=prompt,
        )
    except subprocess.TimeoutExpired:
        return (False, f"{provider_info} CLI error: timed out after {effective_timeout} minutes")
    except FileNotFoundError:
        return (False, f"{provider_info} CLI error: '{config.binary}' not found in PATH")
    if result.returncode != 0:
        error_detail = result.stderr or result.stdout or "unknown error (no output)"
        return False, f"{provider_info} CLI error: {error_detail}"
    logger.debug(f"{provider_info} CLI response length: {len(result.stdout)} chars")
    return True, result.stdout


async def check_ai_cli_available(ai_provider: str, ai_model: str) -> tuple[bool, str]:
    config = PROVIDER_CONFIG.get(ai_provider)
    if not config:
        return (False, f"Unknown AI provider: '{ai_provider}'")
    if not ai_model:
        return (False, "No AI model configured")
    provider_info = f"{ai_provider.upper()} ({ai_model})"
    sanity_cmd = config.build_cmd(config.binary, ai_model, None)
    try:
        sanity_result = await asyncio.to_thread(
            subprocess.run, sanity_cmd, cwd=None, capture_output=True, text=True, timeout=60, input="Hi",
        )
        if sanity_result.returncode != 0:
            error_detail = sanity_result.stderr or sanity_result.stdout or "unknown"
            return False, f"{provider_info} sanity check failed: {error_detail}"
    except subprocess.TimeoutExpired:
        return False, f"{provider_info} sanity check timed out"
    except FileNotFoundError:
        return False, f"{provider_info}: '{config.binary}' not found in PATH"
    return True, ""
