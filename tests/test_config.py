from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def test_default_settings() -> None:
    from docsfy.config import Settings

    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
    assert settings.admin_key == ""
    assert settings.ai_provider == "claude"
    assert settings.ai_model == "claude-opus-4-6[1m]"
    assert settings.ai_cli_timeout == 60
    assert settings.log_level == "INFO"
    assert settings.data_dir == "/data"


def test_custom_settings() -> None:
    from docsfy.config import Settings

    env = {
        "ADMIN_KEY": "my-secret-key-long-enough",
        "AI_PROVIDER": "gemini",
        "AI_MODEL": "gemini-2.5-pro",
        "AI_CLI_TIMEOUT": "120",
        "LOG_LEVEL": "DEBUG",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = Settings(_env_file=None)
    assert settings.admin_key == "my-secret-key-long-enough"
    assert settings.ai_provider == "gemini"
    assert settings.ai_model == "gemini-2.5-pro"
    assert settings.ai_cli_timeout == 120
    assert settings.log_level == "DEBUG"


def test_invalid_timeout_rejected() -> None:
    from docsfy.config import Settings

    with patch.dict(os.environ, {"AI_CLI_TIMEOUT": "0"}, clear=True):
        with pytest.raises(Exception):
            Settings(_env_file=None)
