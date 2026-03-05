from __future__ import annotations


def test_reexports_available() -> None:
    from docsfy.ai_client import (
        PROVIDERS,
        VALID_AI_PROVIDERS,
        call_ai_cli,
        check_ai_cli_available,
        get_ai_cli_timeout,
        run_parallel_with_limit,
    )

    assert "claude" in PROVIDERS
    assert "gemini" in PROVIDERS
    assert "cursor" in PROVIDERS
    assert VALID_AI_PROVIDERS == frozenset({"claude", "gemini", "cursor"})
    assert callable(call_ai_cli)
    assert callable(check_ai_cli_available)
    assert callable(get_ai_cli_timeout)
    assert callable(run_parallel_with_limit)


def test_provider_config_types() -> None:
    from docsfy.ai_client import PROVIDERS, ProviderConfig

    for name, config in PROVIDERS.items():
        assert isinstance(config, ProviderConfig)
        assert isinstance(config.binary, str)
        assert callable(config.build_cmd)
