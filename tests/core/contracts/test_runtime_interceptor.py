"""Tests for RuntimeInterceptor protocol."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.runtime_interceptor import RuntimeInterceptor


def _make_context() -> RunContext:
    return RunContext(
        run_id="run-1",
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
    )


# --- Fake implementations ---


class _FakeInterceptor:
    """Satisfies RuntimeInterceptor structurally."""

    async def before_step(
        self,
        input: Any,
        context: RunContext,
    ) -> Any:
        return input

    async def should_execute(self, context: RunContext) -> bool:
        return True

    async def after_step(
        self,
        result: Any,
        context: RunContext,
    ) -> Any:
        return result

    async def on_error(
        self,
        error: Exception,
        context: RunContext,
    ) -> Any:
        return None


class _BrokenInterceptorMissingShouldExecute:
    """Missing should_execute -- does NOT satisfy RuntimeInterceptor."""

    async def before_step(self, input: Any, context: RunContext) -> Any:
        return input

    async def after_step(self, result: Any, context: RunContext) -> Any:
        return result

    async def on_error(self, error: Exception, context: RunContext) -> Any:
        return None


class _TransformingInterceptor:
    """Transforms input by prepending a tag."""

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
    """Always bails -- should_execute returns False."""

    async def before_step(self, input: Any, context: RunContext) -> Any:
        return input

    async def should_execute(self, context: RunContext) -> bool:
        return False

    async def after_step(self, result: Any, context: RunContext) -> Any:
        return result

    async def on_error(self, error: Exception, context: RunContext) -> Any:
        return None


# --- Tests ---


def test_runtime_interceptor_is_runtime_checkable() -> None:
    interceptor = _FakeInterceptor()
    assert isinstance(interceptor, RuntimeInterceptor)


def test_broken_interceptor_not_satisfied() -> None:
    interceptor = _BrokenInterceptorMissingShouldExecute()
    assert not isinstance(interceptor, RuntimeInterceptor)


def test_transforming_interceptor_satisfies_protocol() -> None:
    interceptor = _TransformingInterceptor("tag")
    assert isinstance(interceptor, RuntimeInterceptor)


def test_bail_interceptor_satisfies_protocol() -> None:
    interceptor = _BailInterceptor()
    assert isinstance(interceptor, RuntimeInterceptor)
