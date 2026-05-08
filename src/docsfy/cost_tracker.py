"""Generation-scoped cost accumulator.

Uses ``contextvars.ContextVar`` so that every ``call_ai_cli`` invocation
within a generation run can add its cost without changing function signatures.

Usage in the generation orchestrator (``_run_generation``)::

    acc = CostAccumulator()
    token = set_cost_accumulator(acc)
    try:
        ... # run planner, generate pages, validate, cross-link
    finally:
        reset_cost_accumulator(token)
    total_cost = acc.total_cost_usd  # aggregated cost from all AI calls

The ``add_cost`` helper is called from ``_call_ai_or_raise`` and direct
``call_ai_cli`` call-sites — it's a no-op when no accumulator is active.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field


@dataclass
class CostAccumulator:
    """Asyncio-safe cost accumulator for a single generation run."""

    total_cost_usd: float = field(default=0.0)
    call_count: int = field(default=0)

    def add(self, cost_usd: float | None) -> None:
        """Record an AI CLI call. Always increments call_count; adds to total_cost_usd only for positive values."""
        self.call_count += 1
        if cost_usd is not None and cost_usd > 0:
            self.total_cost_usd += cost_usd


_cost_accumulator_var: contextvars.ContextVar[CostAccumulator | None] = (
    contextvars.ContextVar("cost_accumulator", default=None)
)


def set_cost_accumulator(
    acc: CostAccumulator,
) -> contextvars.Token[CostAccumulator | None]:
    """Set the active cost accumulator for this async context."""
    return _cost_accumulator_var.set(acc)


def reset_cost_accumulator(token: contextvars.Token[CostAccumulator | None]) -> None:
    """Reset the cost accumulator to its previous value."""
    _cost_accumulator_var.reset(token)


def add_cost(cost_usd: float | None) -> None:
    """Add cost to the active accumulator, if any. Safe to call unconditionally."""
    acc = _cost_accumulator_var.get()
    if acc is not None:
        acc.add(cost_usd)
