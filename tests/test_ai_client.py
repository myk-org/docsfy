from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


def test_provider_config_registry() -> None:
    from docsfy.ai_client import PROVIDER_CONFIG, VALID_AI_PROVIDERS

    assert "claude" in PROVIDER_CONFIG
    assert "gemini" in PROVIDER_CONFIG
    assert "cursor" in PROVIDER_CONFIG
    assert VALID_AI_PROVIDERS == {"claude", "gemini", "cursor"}


def test_build_claude_cmd() -> None:
    from docsfy.ai_client import PROVIDER_CONFIG

    config = PROVIDER_CONFIG["claude"]
    cmd = config.build_cmd(config.binary, "claude-opus-4-6", None)
    assert cmd == [
        "claude",
        "--model",
        "claude-opus-4-6",
        "--dangerously-skip-permissions",
        "-p",
    ]
    assert config.uses_own_cwd is False


def test_build_gemini_cmd() -> None:
    from docsfy.ai_client import PROVIDER_CONFIG

    config = PROVIDER_CONFIG["gemini"]
    cmd = config.build_cmd(config.binary, "gemini-2.5-pro", None)
    assert cmd == ["gemini", "--model", "gemini-2.5-pro", "--yolo"]
    assert config.uses_own_cwd is False


def test_build_cursor_cmd() -> None:
    from docsfy.ai_client import PROVIDER_CONFIG

    config = PROVIDER_CONFIG["cursor"]
    cmd = config.build_cmd(config.binary, "claude-sonnet", Path("/tmp/repo"))
    assert cmd == [
        "agent",
        "--force",
        "--model",
        "claude-sonnet",
        "--print",
        "--workspace",
        "/tmp/repo",
    ]
    assert config.uses_own_cwd is True


def test_build_cursor_cmd_no_cwd() -> None:
    from docsfy.ai_client import PROVIDER_CONFIG

    config = PROVIDER_CONFIG["cursor"]
    cmd = config.build_cmd(config.binary, "claude-sonnet", None)
    assert "--workspace" not in cmd


async def test_call_ai_cli_unknown_provider() -> None:
    from docsfy.ai_client import call_ai_cli

    success, msg = await call_ai_cli("hello", ai_provider="unknown", ai_model="test")
    assert success is False
    assert "Unknown AI provider" in msg


async def test_call_ai_cli_no_model() -> None:
    from docsfy.ai_client import call_ai_cli

    success, msg = await call_ai_cli("hello", ai_provider="claude", ai_model="")
    assert success is False
    assert "No AI model" in msg


async def test_call_ai_cli_success() -> None:
    from docsfy.ai_client import call_ai_cli

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "AI response here"
    mock_result.stderr = ""

    with patch("docsfy.ai_client.asyncio.to_thread", return_value=mock_result):
        success, output = await call_ai_cli(
            "test prompt", ai_provider="claude", ai_model="opus"
        )
    assert success is True
    assert output == "AI response here"


async def test_call_ai_cli_nonzero_exit() -> None:
    from docsfy.ai_client import call_ai_cli

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "some error"

    with patch("docsfy.ai_client.asyncio.to_thread", return_value=mock_result):
        success, output = await call_ai_cli(
            "test", ai_provider="claude", ai_model="opus"
        )
    assert success is False
    assert "some error" in output


async def test_call_ai_cli_timeout() -> None:
    import subprocess
    from docsfy.ai_client import call_ai_cli

    with patch(
        "docsfy.ai_client.asyncio.to_thread",
        side_effect=subprocess.TimeoutExpired("cmd", 60),
    ):
        success, output = await call_ai_cli(
            "test", ai_provider="claude", ai_model="opus", ai_cli_timeout=1
        )
    assert success is False
    assert "timed out" in output


async def test_call_ai_cli_binary_not_found() -> None:
    from docsfy.ai_client import call_ai_cli

    with patch("docsfy.ai_client.asyncio.to_thread", side_effect=FileNotFoundError()):
        success, output = await call_ai_cli(
            "test", ai_provider="claude", ai_model="opus"
        )
    assert success is False
    assert "not found" in output


async def test_check_ai_cli_available_success() -> None:
    from docsfy.ai_client import check_ai_cli_available

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Hello!"
    mock_result.stderr = ""

    with patch("docsfy.ai_client.asyncio.to_thread", return_value=mock_result):
        success, msg = await check_ai_cli_available("claude", "opus")
    assert success is True


async def test_check_ai_cli_available_failure() -> None:
    from docsfy.ai_client import check_ai_cli_available

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "auth error"

    with patch("docsfy.ai_client.asyncio.to_thread", return_value=mock_result):
        success, msg = await check_ai_cli_available("claude", "opus")
    assert success is False
    assert "sanity check failed" in msg
