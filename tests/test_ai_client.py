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
    assert provider == "acpx-cursor"
    assert model == "cursor:default[effort=high]"


def test_map_cursor_cli_heuristic() -> None:
    ai_client._model_route_cache.clear()
    provider, model = map_provider_model_for_sidecar("cursor", "cursor:composer-2")
    assert provider == "cli-cursor"
    assert model == "cursor:composer-2"


def test_legacy_cursor_cli_provider_with_cli_model() -> None:
    ai_client._model_route_cache.clear()
    provider, model = map_provider_model_for_sidecar("cursor-cli", "cursor:composer-2")
    assert provider == "cli-cursor"
    assert model == "cursor:composer-2"


def test_cache_overrides_heuristic() -> None:
    ai_client._model_route_cache.clear()
    ai_client._model_route_cache[("cursor", "cursor:composer-2")] = "cli-cursor"
    provider, model = map_provider_model_for_sidecar("cursor", "cursor:composer-2")
    assert provider == "cli-cursor"
    assert model == "cursor:composer-2"


def test_list_models_from_catalog_merges_and_tags_source() -> None:
    ai_client._model_route_cache.clear()
    raw = [
        {
            "id": "cursor:default[]",
            "name": "Default",
            "provider": "acpx-cursor",
        },
        {
            "id": "cursor:composer-2",
            "name": "Composer",
            "provider": "cli-cursor",
        },
        {
            "id": "claude-opus-4-6",
            "name": "Opus",
            "provider": "google-vertex-claude",
        },
    ]
    models = list_models_from_catalog("cursor", raw)
    assert len(models) == 2
    by_id = {m["id"]: m for m in models}
    assert by_id["cursor:default[]"]["source"] == "acpx"
    assert by_id["cursor:default[]"]["provider"] == "cursor"
    assert by_id["cursor:composer-2"]["source"] == "cli"
    assert ai_client._model_route_cache[("cursor", "cursor:composer-2")] == "cli-cursor"


def test_list_models_route_cache_first_source_wins() -> None:
    """Duplicate model ids keep the first sidecar route (ACPX before CLI)."""
    ai_client._model_route_cache.clear()
    raw = [
        {
            "id": "cursor:shared",
            "name": "Shared ACPX",
            "provider": "acpx-cursor",
        },
        {
            "id": "cursor:shared",
            "name": "Shared CLI",
            "provider": "cli-cursor",
        },
    ]
    models = list_models_from_catalog("cursor", raw)
    assert len(models) == 1
    assert models[0]["source"] == "acpx"
    assert ai_client._model_route_cache[("cursor", "cursor:shared")] == "acpx-cursor"


def test_build_friendly_catalog() -> None:
    ai_client._model_route_cache.clear()
    raw = [
        {"id": "m1", "name": "M1", "provider": "google"},
        {"id": "m2", "name": "M2", "provider": "cli-gemini"},
        {"id": "c1", "name": "C1", "provider": "google-vertex-claude"},
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
                    "provider": "acpx-cursor",
                },
                {
                    "id": "cursor:composer-2",
                    "name": "Composer",
                    "provider": "cli-cursor",
                },
            ]

    monkeypatch.setattr(ai_client, "get_sidecar_client", lambda: FakeClient())
    models = await list_models("cursor")
    assert len(models) == 2
    assert {m["source"] for m in models} == {"acpx", "cli"}
