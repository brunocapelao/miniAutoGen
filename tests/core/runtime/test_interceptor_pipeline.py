"""Tests for InterceptorPipeline -- composing RuntimeInterceptors."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.interceptor_pipeline import InterceptorPipeline


def _make_context() -> RunContext:
    return RunContext(
        run_id="run-1",
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
    )


class _TagInterceptor:
    """Wraps input/result with a tag."""

    def __init__(self, tag: str) -> None:
        self._tag = tag

    async def before_step(self, input: Any, context: RunContext) -> Any:
        return f"[{self._tag}]{input}"

    async def should_execute(self, context: RunContext) -> bool:
        return True

    async def after_step(self, result: Any, context: RunContext) -> Any:
        return f"{result}[/{self._tag}]"

    async def on_error(self, error: Exception, context: RunContext) -> Any:
        return None


class _BailInterceptor:
    """Always bails."""

    async def before_step(self, input: Any, context: RunContext) -> Any:
        return input

    async def should_execute(self, context: RunContext) -> bool:
        return False

    async def after_step(self, result: Any, context: RunContext) -> Any:
        return result

    async def on_error(self, error: Exception, context: RunContext) -> Any:
        return None


class _ErrorRecoveryInterceptor:
    """Recovers from errors by returning a fallback value."""

    def __init__(self, fallback: Any) -> None:
        self._fallback = fallback

    async def before_step(self, input: Any, context: RunContext) -> Any:
        return input

    async def should_execute(self, context: RunContext) -> bool:
        return True

    async def after_step(self, result: Any, context: RunContext) -> Any:
        return result

    async def on_error(self, error: Exception, context: RunContext) -> Any:
        return self._fallback


# --- Tests ---


@pytest.mark.anyio
async def test_pipeline_before_step_waterfall() -> None:
    sink = InMemoryEventSink()
    pipeline = InterceptorPipeline(
        interceptors=[_TagInterceptor("A"), _TagInterceptor("B")],
        event_sink=sink,
    )
    ctx = _make_context()

    result = await pipeline.run_before_step("hello", ctx)
    # Waterfall: A wraps first, then B wraps
    assert result == "[B][A]hello"

    # Should have emitted INTERCEPTOR_BEFORE_STEP event
    before_events = [
        e for e in sink.events if e.type == EventType.INTERCEPTOR_BEFORE_STEP.value
    ]
    assert len(before_events) >= 1


@pytest.mark.anyio
async def test_pipeline_should_execute_all_true() -> None:
    sink = InMemoryEventSink()
    pipeline = InterceptorPipeline(
        interceptors=[_TagInterceptor("A"), _TagInterceptor("B")],
        event_sink=sink,
    )
    ctx = _make_context()

    result = await pipeline.run_should_execute(ctx)
    assert result is True


@pytest.mark.anyio
async def test_pipeline_should_execute_bail() -> None:
    sink = InMemoryEventSink()
    pipeline = InterceptorPipeline(
        interceptors=[_TagInterceptor("A"), _BailInterceptor()],
        event_sink=sink,
    )
    ctx = _make_context()

    result = await pipeline.run_should_execute(ctx)
    assert result is False

    # Should have emitted INTERCEPTOR_BAIL event
    bail_events = [
        e for e in sink.events if e.type == EventType.INTERCEPTOR_BAIL.value
    ]
    assert len(bail_events) == 1


@pytest.mark.anyio
async def test_pipeline_after_step_series() -> None:
    sink = InMemoryEventSink()
    pipeline = InterceptorPipeline(
        interceptors=[_TagInterceptor("A"), _TagInterceptor("B")],
        event_sink=sink,
    )
    ctx = _make_context()

    result = await pipeline.run_after_step("output", ctx)
    # Series: A processes first, then B
    assert result == "output[/A][/B]"

    # Should have emitted INTERCEPTOR_AFTER_STEP event
    after_events = [
        e for e in sink.events if e.type == EventType.INTERCEPTOR_AFTER_STEP.value
    ]
    assert len(after_events) >= 1


@pytest.mark.anyio
async def test_pipeline_on_error_first_recovery_wins() -> None:
    sink = InMemoryEventSink()
    pipeline = InterceptorPipeline(
        interceptors=[
            _ErrorRecoveryInterceptor("fallback-A"),
            _ErrorRecoveryInterceptor("fallback-B"),
        ],
        event_sink=sink,
    )
    ctx = _make_context()

    result = await pipeline.run_on_error(RuntimeError("boom"), ctx)
    # First interceptor that returns non-None wins
    assert result == "fallback-A"


@pytest.mark.anyio
async def test_pipeline_on_error_all_propagate() -> None:
    sink = InMemoryEventSink()
    pipeline = InterceptorPipeline(
        interceptors=[_TagInterceptor("A"), _TagInterceptor("B")],
        event_sink=sink,
    )
    ctx = _make_context()

    result = await pipeline.run_on_error(RuntimeError("boom"), ctx)
    assert result is None


@pytest.mark.anyio
async def test_empty_pipeline_passthrough() -> None:
    sink = InMemoryEventSink()
    pipeline = InterceptorPipeline(interceptors=[], event_sink=sink)
    ctx = _make_context()

    assert await pipeline.run_before_step("input", ctx) == "input"
    assert await pipeline.run_should_execute(ctx) is True
    assert await pipeline.run_after_step("output", ctx) == "output"
    assert await pipeline.run_on_error(RuntimeError("boom"), ctx) is None
