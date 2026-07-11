"""AI client adapter — re-exports from pi-sidecar-client."""

from typing import Any

from pi_sidecar_client import (
    AIResult,
    call_ai_once,
    check_sidecar_available,
    get_sidecar_client,
    list_models,
    run_parallel_with_limit,
)


async def refresh_models() -> list[dict[str, Any]]:
    """Trigger model re-discovery on the sidecar and return updated list."""
    client = get_sidecar_client()
    return await client.refresh_models()


__all__ = [
    "AIResult",
    "call_ai_once",
    "check_sidecar_available",
    "list_models",
    "refresh_models",
    "run_parallel_with_limit",
]
