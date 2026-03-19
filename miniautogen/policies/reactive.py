"""Reactive policies that respond to events asynchronously via EventBus.

ReactivePolicy is a Protocol for policies that subscribe to specific event
types and react via on_event. ReactiveBudgetTracker is a concrete implementation
that tracks cost from COMPONENT_FINISHED events.
"""

from __future__ import annotations

from typing import Protocol

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.policies.budget import BudgetPolicy, BudgetTracker


class ReactivePolicy(Protocol):
    """Policy that reacts to events asynchronously.

    Designed to be wired to an EventBus: the bus calls on_event
    for matching event types.
    """

    @property
    def subscribed_events(self) -> set[str]:
        """Event types this policy cares about."""
        ...

    async def on_event(self, event: ExecutionEvent) -> None:
        """React to an event. Called by EventBus."""
        ...


class ReactiveBudgetTracker:
    """Budget tracker that reacts to COMPONENT_FINISHED events.

    Extracts cost from event payload and tracks against budget.
    Raises BudgetExceededError when exceeded.
    """

    def __init__(self, policy: BudgetPolicy) -> None:
        self._tracker = BudgetTracker(policy=policy)

    @property
    def subscribed_events(self) -> set[str]:
        """Event types this policy cares about."""
        return {"component_finished"}

    @property
    def spent(self) -> float:
        """Total cost recorded so far."""
        return self._tracker.spent

    @property
    def remaining(self) -> float | None:
        """Remaining budget, or None if unlimited."""
        return self._tracker.remaining

    async def on_event(self, event: ExecutionEvent) -> None:
        """Extract cost from event payload and record it.

        If the event payload contains a 'cost' key, the value is
        recorded against the budget. Events without 'cost' are ignored.

        Raises:
            BudgetExceededError: When cumulative cost exceeds the budget.
        """
        cost = event.get_payload("cost")
        if cost is not None:
            self._tracker.record(float(cost))
