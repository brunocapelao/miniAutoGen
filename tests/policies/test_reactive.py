"""Tests for reactive policies that respond to events via EventBus."""

from __future__ import annotations

import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.event_bus import EventBus
from miniautogen.policies.budget import BudgetExceededError, BudgetPolicy
from miniautogen.policies.reactive import ReactiveBudgetTracker

pytestmark = pytest.mark.anyio


class TestReactiveBudgetTracker:
    """ReactiveBudgetTracker tracks cost from COMPONENT_FINISHED events."""

    async def test_tracks_cost_from_event_payload(self) -> None:
        """Extracts cost from event payload and records it."""
        tracker = ReactiveBudgetTracker(
            policy=BudgetPolicy(max_cost=10.0),
        )

        event = ExecutionEvent(
            type="component_finished",
            scope="test",
            payload={"cost": 3.5},
        )
        await tracker.on_event(event)

        assert tracker.spent == 3.5

    async def test_raises_budget_exceeded_on_overflow(self) -> None:
        """Raises BudgetExceededError when cumulative cost exceeds budget."""
        tracker = ReactiveBudgetTracker(
            policy=BudgetPolicy(max_cost=5.0),
        )

        event1 = ExecutionEvent(
            type="component_finished",
            scope="test",
            payload={"cost": 3.0},
        )
        await tracker.on_event(event1)

        event2 = ExecutionEvent(
            type="component_finished",
            scope="test",
            payload={"cost": 3.0},
        )
        with pytest.raises(BudgetExceededError):
            await tracker.on_event(event2)

    async def test_ignores_events_without_cost(self) -> None:
        """Events without a 'cost' key in payload are silently ignored."""
        tracker = ReactiveBudgetTracker(
            policy=BudgetPolicy(max_cost=10.0),
        )

        event = ExecutionEvent(
            type="component_finished",
            scope="test",
            payload={"result": "ok"},
        )
        await tracker.on_event(event)

        assert tracker.spent == 0.0

    async def test_subscribed_events_property(self) -> None:
        """subscribed_events returns the set of event types this policy cares about."""
        tracker = ReactiveBudgetTracker(
            policy=BudgetPolicy(max_cost=10.0),
        )

        assert "component_finished" in tracker.subscribed_events

    async def test_integration_with_event_bus(self) -> None:
        """ReactiveBudgetTracker works when wired to EventBus."""
        bus = EventBus()
        tracker = ReactiveBudgetTracker(
            policy=BudgetPolicy(max_cost=10.0),
        )

        # Wire up: subscribe to the events the tracker cares about
        for event_type in tracker.subscribed_events:
            bus.subscribe(event_type, tracker.on_event)

        # Publish events through the bus
        await bus.publish(ExecutionEvent(
            type="component_finished",
            scope="test",
            payload={"cost": 4.0},
        ))
        await bus.publish(ExecutionEvent(
            type="component_finished",
            scope="test",
            payload={"cost": 2.0},
        ))

        assert tracker.spent == 6.0

        # Exceeding budget via bus: EventBus catches handler exceptions
        # (fire-and-forget), so publish does NOT raise.
        # The cost is still recorded up to the exceeded point.
        await bus.publish(ExecutionEvent(
            type="component_finished",
            scope="test",
            payload={"cost": 5.0},
        ))

        # Budget was exceeded at 11.0 (6.0 + 5.0 > 10.0), but bus swallowed the error
        assert tracker.spent == 11.0

    async def test_unlimited_budget_does_not_raise(self) -> None:
        """With no max_cost, budget is unlimited."""
        tracker = ReactiveBudgetTracker(
            policy=BudgetPolicy(max_cost=None),
        )

        event = ExecutionEvent(
            type="component_finished",
            scope="test",
            payload={"cost": 1000.0},
        )
        await tracker.on_event(event)

        assert tracker.spent == 1000.0
