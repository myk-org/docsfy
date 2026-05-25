"""AI client adapter — re-exports from pi-sidecar-client."""

from pi_sidecar_client import (
    AIResult,
    call_ai_once,
    check_sidecar_available,
    list_models,
    run_parallel_with_limit,
)

__all__ = [
    "AIResult",
    "call_ai_once",
    "check_sidecar_available",
    "list_models",
    "run_parallel_with_limit",
]
