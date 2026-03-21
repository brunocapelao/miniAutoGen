"""Test that reactive policies receive events from the runtime event flow."""

import anyio
import pytest

from miniautogen.core.events.event_bus import EventBus
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.types import EventType
from miniautogen.policies.budget import BudgetPolicy
from miniautogen.policies.reactive import ReactiveBudgetTracker


@pytest.mark.anyio
async def test_reactive_budget_tracker_receives_events():
    """ReactiveBudgetTracker should react when events are published to EventBus."""
    policy = BudgetPolicy(max_cost=100.0)
    tracker = ReactiveBudgetTracker(policy=policy)
    bus = EventBus()
    for event_type in tracker.subscribed_events:
        bus.subscribe(event_type, tracker.on_event)

    from datetime import datetime, timezone
    event = ExecutionEvent(
        type=EventType.COMPONENT_FINISHED.value,
        timestamp=datetime.now(timezone.utc),
        run_id="test-run",
        correlation_id="test-corr",
        scope="test",
        payload={"cost": 25.0},
    )
    await bus.publish(event)
    assert tracker.spent == 25.0


@pytest.mark.anyio
async def test_pipeline_runner_has_event_bus():
    """PipelineRunner should expose an EventBus for reactive policy subscription."""
    from miniautogen.core.runtime.pipeline_runner import PipelineRunner
    runner = PipelineRunner()
    assert hasattr(runner, 'event_bus')
    assert isinstance(runner.event_bus, EventBus)


@pytest.mark.anyio
async def test_events_reach_bus_subscribers():
    """Events published to runner.event_sink should reach EventBus subscribers."""
    from miniautogen.core.runtime.pipeline_runner import PipelineRunner
    runner = PipelineRunner()
    received = []

    async def handler(event):
        received.append(event)

    runner.event_bus.subscribe(EventType.RUN_STARTED.value, handler)

    from datetime import datetime, timezone
    event = ExecutionEvent(
        type=EventType.RUN_STARTED.value,
        timestamp=datetime.now(timezone.utc),
        run_id="test-run",
        correlation_id="test-corr",
        scope="test",
    )
    await runner.event_sink.publish(event)
    assert len(received) == 1


@pytest.mark.anyio
async def test_events_reach_bus_when_custom_sink_provided():
    """When user provides an event_sink, EventBus should still receive events."""
    from miniautogen.core.runtime.pipeline_runner import PipelineRunner
    from miniautogen.core.events.event_sink import InMemoryEventSink

    user_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=user_sink)
    received = []

    async def handler(event):
        received.append(event)

    runner.event_bus.subscribe(EventType.RUN_STARTED.value, handler)

    from datetime import datetime, timezone
    event = ExecutionEvent(
        type=EventType.RUN_STARTED.value,
        timestamp=datetime.now(timezone.utc),
        run_id="test-run",
        correlation_id="test-corr",
        scope="test",
    )
    await runner.event_sink.publish(event)
    assert len(received) == 1, "EventBus should receive events even with custom sink"
    assert len(user_sink.events) == 1, "User sink should also receive events"
