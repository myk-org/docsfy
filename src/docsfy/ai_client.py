"""AI client adapter — friendly providers with ACPX/CLI/API catalog routing."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from pi_sidecar_client import (
    AIResult,
    check_sidecar_available,
    get_sidecar_client,
    run_parallel_with_limit,
)
from pi_sidecar_client import call_ai_once as _call_ai_once
from simple_logger.logger import get_logger

from docsfy.models import (
    CLI_SIDECAR_BY_PROVIDER,
    DEFAULT_SIDECAR_BY_PROVIDER,
    SIDECAR_ACPX_CURSOR,
    SIDECAR_CLI_CURSOR,
    VALID_PROVIDERS,
)

logger = get_logger(name=__name__)

# Accepted on input; normalized to canonical VALID_PROVIDERS names.
_LEGACY_PROVIDER_ALIASES: dict[str, str] = {
    "cursor-cli": "cursor",
    "claude-cli": "claude",
    "gemini-cli": "gemini",
}

# Re-export maps under the historical private names used in this module.
_DEFAULT_SIDECAR = DEFAULT_SIDECAR_BY_PROVIDER
_CLI_SIDECAR = CLI_SIDECAR_BY_PROVIDER

# (friendly_provider, model_id) → sidecar provider id (filled by catalog build)
_model_route_cache: dict[tuple[str, str], str] = {}

# Cached cursor auth probe: (monotonic_ts, status_dict)
_cursor_auth_cache: tuple[float, dict[str, Any]] | None = None
_CURSOR_AUTH_CACHE_TTL_SEC = 60.0
_CURSOR_AGENT_STATUS_TIMEOUT_SEC = 20.0
# Providers whose catalog has been fetched at least once this process lifetime
# (cleared on refresh_models). Prevents repeated get_models for unknown model ids.
_warmed_providers: set[str] = set()
_CURSOR_BROWSER_LOGIN_EXPIRED_HINT = (
    "Cursor browser login (`agent login`) expired or is missing. "
    "Set CURSOR_API_KEY on the server (does not expire; always works when set), "
    "or re-run `agent login` on the host and restart the sidecar. "
    "Browser login cannot be auto-refreshed."
)
_CURSOR_KEY_SET_BUT_UNAVAILABLE_HINT = (
    "CURSOR_API_KEY is set (that key does not expire) but Cursor models are "
    "unavailable. Check the key is visible to the sidecar process, restart "
    "the sidecar, and verify network to Cursor APIs."
)
_CURSOR_AGENT_MISSING_HINT = (
    "Cursor `agent` binary was not found on PATH. Install Cursor CLI / agent "
    "in the container image (or mount it) and ensure PATH includes it, then "
    "restart the sidecar."
)
_CURSOR_NO_MODELS_HINT = (
    "No Cursor models were discovered. Check ACPX_AGENTS / CLI_AGENTS, "
    "sidecar extension paths (SIDECAR_ACPX_EXTENSION_PATH / "
    "SIDECAR_CLI_PROVIDER_EXTENSION_PATH), then refresh models."
)
_CURSOR_UNAVAILABLE_HINT = (
    "Cursor is unavailable. Check sidecar logs, network, and agent/CLI health, "
    "then retry model refresh."
)


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
    """Pick ACPX/API vs CLI sidecar for a friendly provider + model id.

    Catalog-driven routes win. On cache miss, default to ACPX/API — never
    assume CLI is available (free-typed / stale model ids).
    """
    cached = _model_route_cache.get((friendly, model))
    if cached:
        return cached

    # Bracketed cursor ids are ACPX-shaped; otherwise prefer default ACPX/API.
    if friendly == "cursor" and "[" in model:
        return _DEFAULT_SIDECAR["cursor"]

    return _DEFAULT_SIDECAR.get(friendly, friendly)


def _map_model_for_sidecar(sidecar_provider: str, model: str) -> str:
    """Ensure cursor models keep the cursor: prefix expected by ACPX/CLI."""
    if (
        sidecar_provider in (SIDECAR_ACPX_CURSOR, SIDECAR_CLI_CURSOR)
        and model
        and not model.startswith("cursor:")
    ):
        return f"cursor:{model}"
    return model


def _canonical_model_for_routing(friendly: str, model: str) -> str:
    """Normalize free-typed cursor ids before route-cache lookup.

    Catalog keys use ``cursor:<id>``; Combobox free-text may omit the prefix.
    """
    if friendly == "cursor" and model and not model.startswith("cursor:"):
        return f"cursor:{model}"
    return model


def map_provider_model_for_sidecar(provider: str, model: str) -> tuple[str, str]:
    """Map friendly provider/model to sidecar ids for session create / AI calls."""
    friendly = normalize_provider(provider)
    model = (model or "").strip()
    route_model = _canonical_model_for_routing(friendly, model)
    sidecar_provider = _resolve_sidecar_for_model(friendly, route_model)
    return sidecar_provider, _map_model_for_sidecar(sidecar_provider, route_model)


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
    # Drop stale routes, then rebuild from the refreshed catalog.
    _model_route_cache.clear()
    _warmed_providers.clear()
    build_friendly_catalog(raw)
    clear_cursor_auth_cache()
    return raw


def _parse_agent_status_text(text: str) -> str | None:
    """Return auth reason from `agent status` output, or None if looks OK."""
    lower = text.lower()
    if any(
        s in lower
        for s in (
            "authentication required",
            "not authenticated",
            "not logged in",
            "please run 'agent login'",
            'please run "agent login"',
            "agent login' first",
        )
    ):
        return "auth_expired"
    if "logged in" in lower or "authenticated" in lower:
        return None
    return "unavailable"


async def probe_cursor_auth(
    *, force: bool = False, model_count: int | None = None
) -> dict[str, Any]:
    """Probe Cursor CLI/ACPX auth health for admin UI.

    Browser ``agent login`` expires and cannot be auto-refreshed.
    ``CURSOR_API_KEY`` does **not** expire — when set in the server/sidecar
    env it keeps working.

    Returns dict: ok, reason, hint, has_api_key, model_count.
    """
    global _cursor_auth_cache
    now = time.monotonic()
    if (
        not force
        and model_count is None
        and _cursor_auth_cache is not None
        and (now - _cursor_auth_cache[0]) < _CURSOR_AUTH_CACHE_TTL_SEC
    ):
        return dict(_cursor_auth_cache[1])

    if (
        not force
        and model_count is not None
        and _cursor_auth_cache is not None
        and (now - _cursor_auth_cache[0]) < _CURSOR_AUTH_CACHE_TTL_SEC
        and _cursor_auth_cache[1].get("model_count") == model_count
    ):
        return dict(_cursor_auth_cache[1])

    has_api_key = bool(os.environ.get("CURSOR_API_KEY", "").strip())
    if model_count is None:
        models = await list_models("cursor")
        model_count = len(models)
    if model_count > 0:
        status: dict[str, Any] = {
            "ok": True,
            "reason": None,
            "hint": None,
            "has_api_key": has_api_key,
            "model_count": model_count,
        }
        _cursor_auth_cache = (now, status)
        return dict(status)

    reason = "no_models"
    try:
        proc = await asyncio.create_subprocess_exec(
            "agent",
            "status",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ.copy(),
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=_CURSOR_AGENT_STATUS_TIMEOUT_SEC
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            reason = "unavailable"
            logger.warning("Cursor auth probe: agent status timed out")
        else:
            text_out = (stdout or b"").decode(errors="replace") + (
                stderr or b""
            ).decode(errors="replace")
            parsed = _parse_agent_status_text(text_out)
            if parsed:
                reason = parsed
            elif proc.returncode not in (0, None):
                reason = "unavailable"
            logger.info(
                "Cursor auth probe: models=0 reason=%s returncode=%s has_api_key=%s",
                reason,
                proc.returncode,
                has_api_key,
            )
    except FileNotFoundError:
        reason = "agent_missing"
        logger.warning("Cursor auth probe: agent binary not found on PATH")
    except Exception:
        reason = "unavailable"
        logger.warning("Cursor auth probe failed", exc_info=True)

    # Only remap auth_expired when an API key is set but still unused.
    if reason == "auth_expired" and has_api_key:
        reason = "api_key_not_applied"

    if reason == "agent_missing":
        hint = _CURSOR_AGENT_MISSING_HINT
    elif reason == "no_models":
        hint = _CURSOR_NO_MODELS_HINT
    elif reason == "api_key_not_applied":
        hint = _CURSOR_KEY_SET_BUT_UNAVAILABLE_HINT
    elif reason == "auth_expired":
        hint = _CURSOR_BROWSER_LOGIN_EXPIRED_HINT
    elif has_api_key:
        hint = _CURSOR_KEY_SET_BUT_UNAVAILABLE_HINT
    else:
        hint = _CURSOR_UNAVAILABLE_HINT

    status = {
        "ok": False,
        "reason": reason,
        "hint": hint,
        "has_api_key": has_api_key,
        "model_count": model_count,
    }
    _cursor_auth_cache = (now, status)
    return dict(status)


def clear_cursor_auth_cache() -> None:
    """Clear cached cursor auth probe (e.g. after model refresh)."""
    global _cursor_auth_cache
    _cursor_auth_cache = None


def cursor_status_for_client(
    status: dict[str, Any], *, is_admin: bool
) -> dict[str, Any]:
    """Return Cursor provider_status safe for the caller's role."""
    out = dict(status)
    if is_admin:
        return out
    out.pop("has_api_key", None)
    if out.get("reason") in ("auth_expired", "api_key_not_applied"):
        out["reason"] = "unavailable"
    if not out.get("ok"):
        out["hint"] = "Cursor is unavailable. Contact an administrator."
    return out


def cursor_status_from_model_count(model_count: int) -> dict[str, Any]:
    """Coarse Cursor status for non-admins (no subprocess / credential probe)."""
    if model_count > 0:
        return {"ok": True, "reason": None, "hint": None, "model_count": model_count}
    return {
        "ok": False,
        "reason": "unavailable",
        "hint": "Cursor is unavailable. Contact an administrator.",
        "model_count": model_count,
    }


async def _prewarm_model_routes(friendly: str, model: str = "") -> None:
    """Best-effort catalog fetch to populate ``_model_route_cache``.

    After a successful catalog fetch for ``friendly``, further calls skip
    re-fetching even for unknown/free-typed model ids (heuristic routes apply).
    Failures are non-fatal.
    """
    if not friendly:
        return
    model = (model or "").strip()
    if friendly in _warmed_providers:
        return
    if model and (friendly, model) in _model_route_cache:
        return
    if not model and any(fp == friendly for fp, _ in _model_route_cache):
        _warmed_providers.add(friendly)
        return
    try:
        await list_models(friendly)
        _warmed_providers.add(friendly)
        # Cache a heuristic route for unknown free-typed models so routing is
        # stable without further catalog hits.
        if model and (friendly, model) not in _model_route_cache:
            _model_route_cache[(friendly, model)] = _resolve_sidecar_for_model(
                friendly, model
            )
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
    "clear_cursor_auth_cache",
    "cursor_status_for_client",
    "cursor_status_from_model_count",
    "get_sidecar_client",
    "list_models",
    "list_models_from_catalog",
    "map_provider_model_for_sidecar",
    "normalize_provider",
    "probe_cursor_auth",
    "refresh_models",
    "run_parallel_with_limit",
]
