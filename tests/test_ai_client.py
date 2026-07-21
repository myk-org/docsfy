from __future__ import annotations

import pytest

from docsfy import ai_client
from docsfy.ai_client import (
    AIResult,
    build_friendly_catalog,
    call_ai_once,
    check_sidecar_available,
    list_models,
    list_models_from_catalog,
    map_provider_model_for_sidecar,
    normalize_provider,
    refresh_models,
    run_parallel_with_limit,
)
from docsfy.models import (
    SIDECAR_ACPX_CURSOR,
    SIDECAR_CLI_CURSOR,
    SIDECAR_CLI_GEMINI,
    SIDECAR_GOOGLE_GEMINI,
    SIDECAR_VERTEX_CLAUDE,
)


def test_reexports_available() -> None:
    assert callable(call_ai_once)
    assert callable(check_sidecar_available)
    assert callable(list_models)
    assert callable(refresh_models)
    assert callable(run_parallel_with_limit)
    assert "success" in AIResult.__dataclass_fields__
    assert "text" in AIResult.__dataclass_fields__


def test_normalize_provider_legacy_aliases() -> None:
    assert normalize_provider("cursor-cli") == "cursor"
    assert normalize_provider("Claude") == "claude"
    assert normalize_provider("gemini-cli") == "gemini"


def test_map_cursor_acpx_heuristic() -> None:
    ai_client._model_route_cache.clear()
    provider, model = map_provider_model_for_sidecar(
        "cursor", "cursor:default[effort=high]"
    )
    assert provider == SIDECAR_ACPX_CURSOR
    assert model == "cursor:default[effort=high]"


def test_map_cursor_cache_miss_defaults_to_acpx() -> None:
    """Free-typed cursor:* must not assume CLI when catalog has no route."""
    ai_client._model_route_cache.clear()
    provider, model = map_provider_model_for_sidecar("cursor", "cursor:composer-2")
    assert provider == SIDECAR_ACPX_CURSOR
    assert model == "cursor:composer-2"


def test_legacy_cursor_cli_provider_with_cli_model() -> None:
    ai_client._model_route_cache.clear()
    # Without catalog cache, legacy alias still defaults to ACPX (safe fallback).
    provider, model = map_provider_model_for_sidecar("cursor-cli", "cursor:composer-2")
    assert provider == SIDECAR_ACPX_CURSOR
    assert model == "cursor:composer-2"


def test_cache_overrides_heuristic() -> None:
    ai_client._model_route_cache.clear()
    ai_client._model_route_cache[("cursor", "cursor:composer-2")] = SIDECAR_CLI_CURSOR
    provider, model = map_provider_model_for_sidecar("cursor", "cursor:composer-2")
    assert provider == SIDECAR_CLI_CURSOR
    assert model == "cursor:composer-2"


def test_map_cursor_prefixless_uses_cache() -> None:
    """Free-typed cursor ids without cursor: still hit the catalog route cache."""
    ai_client._model_route_cache.clear()
    ai_client._model_route_cache[("cursor", "cursor:composer-2")] = SIDECAR_CLI_CURSOR
    provider, model = map_provider_model_for_sidecar("cursor", "composer-2")
    assert provider == SIDECAR_CLI_CURSOR
    assert model == "cursor:composer-2"


def test_list_models_from_catalog_merges_and_tags_source() -> None:
    ai_client._model_route_cache.clear()
    raw = [
        {
            "id": "cursor:default[]",
            "name": "Default",
            "provider": SIDECAR_ACPX_CURSOR,
        },
        {
            "id": "cursor:composer-2",
            "name": "Composer",
            "provider": SIDECAR_CLI_CURSOR,
        },
        {
            "id": "claude-opus-4-6",
            "name": "Opus",
            "provider": SIDECAR_VERTEX_CLAUDE,
        },
    ]
    models = list_models_from_catalog("cursor", raw)
    assert len(models) == 2
    by_id = {m["id"]: m for m in models}
    assert by_id["cursor:default[]"]["source"] == "acpx"
    assert by_id["cursor:default[]"]["provider"] == "cursor"
    assert by_id["cursor:composer-2"]["source"] == "cli"
    assert (
        ai_client._model_route_cache[("cursor", "cursor:composer-2")]
        == SIDECAR_CLI_CURSOR
    )


def test_list_models_route_cache_first_source_wins() -> None:
    """Duplicate model ids keep the first sidecar route (ACPX before CLI)."""
    ai_client._model_route_cache.clear()
    raw = [
        {
            "id": "cursor:shared",
            "name": "Shared ACPX",
            "provider": SIDECAR_ACPX_CURSOR,
        },
        {
            "id": "cursor:shared",
            "name": "Shared CLI",
            "provider": SIDECAR_CLI_CURSOR,
        },
    ]
    models = list_models_from_catalog("cursor", raw)
    assert len(models) == 1
    assert models[0]["source"] == "acpx"
    assert (
        ai_client._model_route_cache[("cursor", "cursor:shared")] == SIDECAR_ACPX_CURSOR
    )


def test_build_friendly_catalog() -> None:
    ai_client._model_route_cache.clear()
    raw = [
        {"id": "m1", "name": "M1", "provider": SIDECAR_GOOGLE_GEMINI},
        {"id": "m2", "name": "M2", "provider": SIDECAR_CLI_GEMINI},
        {"id": "c1", "name": "C1", "provider": SIDECAR_VERTEX_CLAUDE},
    ]
    catalog = build_friendly_catalog(raw)
    assert set(catalog.keys()) == {"claude", "gemini", "cursor"}
    assert len(catalog["gemini"]) == 2
    assert {m["source"] for m in catalog["gemini"]} == {"api", "cli"}
    assert catalog["claude"][0]["source"] == "api"
    assert catalog["cursor"] == []


@pytest.mark.asyncio
async def test_list_models_uses_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ai_client._model_route_cache.clear()

    class FakeClient:
        async def get_models(self) -> list[dict]:
            return [
                {
                    "id": "cursor:default[]",
                    "name": "Default",
                    "provider": SIDECAR_ACPX_CURSOR,
                },
                {
                    "id": "cursor:composer-2",
                    "name": "Composer",
                    "provider": SIDECAR_CLI_CURSOR,
                },
            ]

    monkeypatch.setattr(ai_client, "get_sidecar_client", lambda: FakeClient())
    models = await list_models("cursor")
    assert len(models) == 2
    assert {m["source"] for m in models} == {"acpx", "cli"}


@pytest.mark.asyncio
async def test_refresh_models_clears_stale_route_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ai_client._model_route_cache.clear()
    ai_client._model_route_cache[("cursor", "cursor:stale")] = SIDECAR_CLI_CURSOR

    class FakeClient:
        async def refresh_models(self) -> list[dict]:
            return [
                {
                    "id": "cursor:default[]",
                    "name": "Default",
                    "provider": SIDECAR_ACPX_CURSOR,
                },
            ]

    monkeypatch.setattr(ai_client, "get_sidecar_client", lambda: FakeClient())
    raw = await refresh_models()
    assert len(raw) == 1
    assert ("cursor", "cursor:stale") not in ai_client._model_route_cache
    assert (
        ai_client._model_route_cache[("cursor", "cursor:default[]")]
        == SIDECAR_ACPX_CURSOR
    )


def test_cursor_status_from_model_count_ok() -> None:
    status = ai_client.cursor_status_from_model_count(5)
    assert status["ok"] is True
    assert status["model_count"] == 5


def test_cursor_status_from_model_count_empty() -> None:
    status = ai_client.cursor_status_from_model_count(0)
    assert status["ok"] is False
    assert status["reason"] == "unavailable"


def test_cursor_status_for_client_redacts_for_non_admin() -> None:
    raw = {
        "ok": False,
        "reason": "auth_expired",
        "hint": "login expired",
        "has_api_key": False,
        "model_count": 0,
    }
    out = ai_client.cursor_status_for_client(raw, is_admin=False)
    assert "has_api_key" not in out
    assert out["reason"] == "unavailable"
    assert "administrator" in (out["hint"] or "").lower()


@pytest.mark.asyncio
async def test_prewarm_skips_repeat_catalog_fetch_for_unknown_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ai_client._model_route_cache.clear()
    ai_client._warmed_providers.clear()
    calls = {"n": 0}

    async def fake_list(provider: str = "") -> list[dict]:
        calls["n"] += 1
        return []

    monkeypatch.setattr(ai_client, "list_models", fake_list)
    await ai_client._prewarm_model_routes("cursor", "cursor:free-typed")
    await ai_client._prewarm_model_routes("cursor", "cursor:free-typed")
    await ai_client._prewarm_model_routes("cursor", "cursor:another-unknown")
    assert calls["n"] == 1
    assert "cursor" in ai_client._warmed_providers


def test_normalize_provider_empty() -> None:
    assert normalize_provider("") == ""
    assert normalize_provider("cursor-cli") == "cursor"


@pytest.mark.asyncio
async def test_probe_cursor_auth_ok_when_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ai_client.clear_cursor_auth_cache()

    async def fake_list(provider: str = "") -> list[dict]:
        return [{"id": "cursor:x", "name": "X", "provider": "cursor", "source": "cli"}]

    monkeypatch.setattr(ai_client, "list_models", fake_list)
    status = await ai_client.probe_cursor_auth()
    assert status["ok"] is True
    assert status["model_count"] == 1


@pytest.mark.asyncio
async def test_probe_cursor_auth_agent_missing_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ai_client.clear_cursor_auth_cache()
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)

    async def empty_list(provider: str = "") -> list[dict]:
        return []

    async def boom(*_a: object, **_k: object) -> None:
        raise FileNotFoundError("agent")

    monkeypatch.setattr(ai_client, "list_models", empty_list)
    monkeypatch.setattr(ai_client.asyncio, "create_subprocess_exec", boom)
    status = await ai_client.probe_cursor_auth(force=True, model_count=0)
    assert status["ok"] is False
    assert status["reason"] == "agent_missing"
    assert "PATH" in (status["hint"] or "")


@pytest.mark.asyncio
async def test_probe_cursor_auth_no_models_keeps_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ai_client.clear_cursor_auth_cache()
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)

    class FakeProc:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"Logged in as user", b""

    async def fake_exec(*_a: object, **_k: object) -> FakeProc:
        return FakeProc()

    monkeypatch.setattr(ai_client.asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(
        ai_client.asyncio, "wait_for", lambda awaitable, timeout: awaitable
    )
    status = await ai_client.probe_cursor_auth(force=True, model_count=0)
    assert status["reason"] == "no_models"
    assert (
        "ACPX_AGENTS" in (status["hint"] or "")
        or "discovered" in (status["hint"] or "").lower()
    )
