"""Tests for EventBus with async subscriptions."""

from __future__ import annotations

import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.event_bus import EventBus

pytestmark = pytest.mark.anyio


async def test_subscribe_and_publish_type_specific() -> None:
    """Subscriber receives events matching its subscribed type."""
    bus = EventBus()
    received: list[ExecutionEvent] = []

    async def handler(event: ExecutionEvent) -> None:
        received.append(event)

    bus.subscribe("component_finished", handler)

    await bus.publish(ExecutionEvent(type="component_finished", scope="test"))
    await bus.publish(ExecutionEvent(type="run_started", scope="test"))

    assert len(received) == 1
    assert received[0].type == "component_finished"


async def test_global_subscriber_receives_all_events() -> None:
    """Global subscriber (event_type=None) receives every event."""
    bus = EventBus()
    received: list[ExecutionEvent] = []

    async def handler(event: ExecutionEvent) -> None:
        received.append(event)

    bus.subscribe(None, handler)

    await bus.publish(ExecutionEvent(type="component_finished", scope="test"))
    await bus.publish(ExecutionEvent(type="run_started", scope="test"))

    assert len(received) == 2


async def test_multiple_subscribers_for_same_type() -> None:
    """Multiple handlers for the same event type all get called."""
    bus = EventBus()
    results_a: list[str] = []
    results_b: list[str] = []

    async def handler_a(event: ExecutionEvent) -> None:
        results_a.append("a")

    async def handler_b(event: ExecutionEvent) -> None:
        results_b.append("b")

    bus.subscribe("run_started", handler_a)
    bus.subscribe("run_started", handler_b)

    await bus.publish(ExecutionEvent(type="run_started", scope="test"))

    assert results_a == ["a"]
    assert results_b == ["b"]


async def test_handler_exception_does_not_break_other_handlers() -> None:
    """If one handler raises, other handlers still execute (fire-and-forget)."""
    bus = EventBus()
    received: list[str] = []

    async def failing_handler(event: ExecutionEvent) -> None:
        raise RuntimeError("handler exploded")

    async def good_handler(event: ExecutionEvent) -> None:
        received.append("ok")

    bus.subscribe("run_started", failing_handler)
    bus.subscribe("run_started", good_handler)

    # Should not raise
    await bus.publish(ExecutionEvent(type="run_started", scope="test"))

    assert received == ["ok"]


async def test_unsubscribe_type_specific() -> None:
    """After unsubscribing, handler no longer receives events."""
    bus = EventBus()
    received: list[ExecutionEvent] = []

    async def handler(event: ExecutionEvent) -> None:
        received.append(event)

    bus.subscribe("run_started", handler)
    bus.unsubscribe("run_started", handler)

    await bus.publish(ExecutionEvent(type="run_started", scope="test"))

    assert len(received) == 0


async def test_unsubscribe_global() -> None:
    """Unsubscribing a global handler works correctly."""
    bus = EventBus()
    received: list[ExecutionEvent] = []

    async def handler(event: ExecutionEvent) -> None:
        received.append(event)

    bus.subscribe(None, handler)
    bus.unsubscribe(None, handler)

    await bus.publish(ExecutionEvent(type="run_started", scope="test"))

    assert len(received) == 0


async def test_publish_with_no_subscribers_is_noop() -> None:
    """Publishing with no subscribers should not raise."""
    bus = EventBus()
    # Should not raise
    await bus.publish(ExecutionEvent(type="run_started", scope="test"))


async def test_global_handler_exception_isolates_from_type_handler() -> None:
    """A failing global handler doesn't prevent type-specific handlers from running."""
    bus = EventBus()
    received: list[str] = []

    async def failing_global(event: ExecutionEvent) -> None:
        raise ValueError("global boom")

    async def good_typed(event: ExecutionEvent) -> None:
        received.append("typed_ok")

    bus.subscribe(None, failing_global)
    bus.subscribe("run_started", good_typed)

    await bus.publish(ExecutionEvent(type="run_started", scope="test"))

    assert received == ["typed_ok"]


async def test_event_bus_satisfies_event_sink_protocol() -> None:
    """EventBus can be used wherever EventSink is expected."""

    bus = EventBus()
    # Structural subtyping: EventBus has async publish(ExecutionEvent) -> None
    assert hasattr(bus, "publish")
    # Can call publish without error
    await bus.publish(ExecutionEvent(type="test", scope="test"))
