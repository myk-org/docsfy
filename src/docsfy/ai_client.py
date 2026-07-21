"""AI client adapter — friendly providers with ACPX/CLI/API catalog routing."""

from __future__ import annotations

from typing import Any

from pi_sidecar_client import AIResult
from pi_sidecar_client import call_ai_once as _call_ai_once
from pi_sidecar_client import (
    check_sidecar_available,
    get_sidecar_client,
    run_parallel_with_limit,
)
from simple_logger.logger import get_logger

from docsfy.models import VALID_PROVIDERS

logger = get_logger(name=__name__)

# Accepted on input; normalized to canonical VALID_PROVIDERS names.
_LEGACY_PROVIDER_ALIASES: dict[str, str] = {
    "cursor-cli": "cursor",
    "claude-cli": "claude",
    "gemini-cli": "gemini",
}

# Friendly → default sidecar (ACPX / Vertex / Google API)
_DEFAULT_SIDECAR: dict[str, str] = {
    "cursor": "acpx-cursor",
    "claude": "google-vertex-claude",
    "gemini": "google",
}

# Friendly → CLI sidecar (only populated when CLI_AGENTS enables the agent)
_CLI_SIDECAR: dict[str, str] = {
    "cursor": "cli-cursor",
    "claude": "cli-claude",
    "gemini": "cli-gemini",
}

# (friendly_provider, model_id) → sidecar provider id (filled by catalog build)
_model_route_cache: dict[tuple[str, str], str] = {}


def normalize_provider(provider: str) -> str:
    """Normalize provider name (lowercase + legacy *-cli aliases → canonical)."""
    p = (provider or "").lower().strip()
    return _LEGACY_PROVIDER_ALIASES.get(p, p)


def _source_for_sidecar(sidecar_provider: str) -> str:
    if sidecar_provider.startswith("cli-"):
        return "cli"
    if sidecar_provider.startswith("acpx-"):
        return "acpx"
    return "api"


def _resolve_sidecar_for_model(friendly: str, model: str) -> str:
    """Pick ACPX/API vs CLI sidecar for a friendly provider + model id."""
    cached = _model_route_cache.get((friendly, model))
    if cached:
        return cached

    # Cursor id shapes: ACPX uses bracket params; CLI uses plain cursor:… ids.
    if friendly == "cursor":
        if "[" in model:
            return _DEFAULT_SIDECAR["cursor"]
        if model.startswith("cursor:"):
            return _CLI_SIDECAR["cursor"]
        return _DEFAULT_SIDECAR["cursor"]

    return _DEFAULT_SIDECAR.get(friendly, friendly)


def _map_model_for_sidecar(sidecar_provider: str, model: str) -> str:
    """Ensure cursor models keep the cursor: prefix expected by ACPX/CLI."""
    if (
        sidecar_provider in ("acpx-cursor", "cli-cursor")
        and model
        and not model.startswith("cursor:")
    ):
        return f"cursor:{model}"
    return model


def map_provider_model_for_sidecar(provider: str, model: str) -> tuple[str, str]:
    """Map friendly provider/model to sidecar ids for session create / AI calls."""
    friendly = normalize_provider(provider)
    model = (model or "").strip()
    sidecar_provider = _resolve_sidecar_for_model(friendly, model)
    return sidecar_provider, _map_model_for_sidecar(sidecar_provider, model)


def list_models_from_catalog(
    friendly: str, all_models: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Filter a sidecar catalog into one friendly provider's models.

    Updates ``_model_route_cache`` for each ``(friendly, model_id)``.
    Deduplicates by model id (first source wins: default/ACPX/API before CLI).
    """
    friendly = normalize_provider(friendly)
    if friendly not in VALID_PROVIDERS:
        return []

    sidecar_order = [_DEFAULT_SIDECAR[friendly]]
    cli_id = _CLI_SIDECAR.get(friendly)
    if cli_id:
        sidecar_order.append(cli_id)

    result: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for sidecar_id in sidecar_order:
        source = _source_for_sidecar(sidecar_id)
        for m in all_models:
            if m.get("provider") != sidecar_id:
                continue
            mid = m.get("id") or ""
            if not mid:
                continue
            if mid in seen_ids:
                continue
            seen_ids.add(mid)
            _model_route_cache[(friendly, mid)] = sidecar_id
            result.append(
                {
                    "id": mid,
                    "name": m.get("name") or mid,
                    "provider": friendly,
                    "source": source,
                }
            )
    return result


def build_friendly_catalog(
    all_models: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Build per-friendly-provider catalogs from one sidecar ``get_models()`` result."""
    return {p: list_models_from_catalog(p, all_models) for p in VALID_PROVIDERS}


async def list_models(provider: str = "") -> list[dict[str, Any]]:
    """List models for a friendly provider, merging ACPX/API + CLI sources.

    Each entry includes ``source``: ``acpx`` | ``cli`` | ``api``.
    With empty ``provider``, returns the merged catalog for all friendly providers
    flattened (same order as ``VALID_PROVIDERS``).
    """
    client = get_sidecar_client()
    all_models = await client.get_models()

    if not provider:
        flat: list[dict[str, Any]] = []
        for p in VALID_PROVIDERS:
            flat.extend(list_models_from_catalog(p, all_models))
        return flat

    friendly = normalize_provider(provider)
    if friendly not in VALID_PROVIDERS:
        return []
    return list_models_from_catalog(friendly, all_models)


async def refresh_models() -> list[dict[str, Any]]:
    """Trigger model re-discovery on the sidecar and rebuild the route cache."""
    client = get_sidecar_client()
    raw = await client.refresh_models()
    # Rebuild cache from the refreshed catalog (keep old routes until success).
    build_friendly_catalog(raw)
    return raw


async def _prewarm_model_routes(friendly: str, model: str = "") -> None:
    """Best-effort catalog fetch to populate ``_model_route_cache``.

    When ``model`` is set, skip only if that exact ``(friendly, model)`` route
    is already cached. Failures are non-fatal: heuristic defaults still apply.
    """
    if not friendly:
        return
    model = (model or "").strip()
    if model:
        if (friendly, model) in _model_route_cache:
            return
    elif any(fp == friendly for fp, _ in _model_route_cache):
        return
    try:
        await list_models(friendly)
    except Exception:
        logger.debug(
            "Model catalog prewarm failed for provider=%s; using heuristic routes",
            friendly,
            exc_info=True,
        )


async def call_ai_once(
    *args: Any, ai_provider: str = "", ai_model: str = "", **kwargs: Any
) -> AIResult:
    """call_ai_once with friendly→sidecar provider/model routing."""
    friendly = normalize_provider(ai_provider)
    await _prewarm_model_routes(friendly, ai_model)
    sidecar_provider, sidecar_model = map_provider_model_for_sidecar(
        ai_provider, ai_model
    )
    return await _call_ai_once(
        *args, ai_provider=sidecar_provider, ai_model=sidecar_model, **kwargs
    )


__all__ = [
    "AIResult",
    "build_friendly_catalog",
    "call_ai_once",
    "check_sidecar_available",
    "get_sidecar_client",
    "list_models",
    "list_models_from_catalog",
    "map_provider_model_for_sidecar",
    "normalize_provider",
    "refresh_models",
    "run_parallel_with_limit",
]
