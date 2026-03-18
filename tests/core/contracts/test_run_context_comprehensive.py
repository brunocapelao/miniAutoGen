"""Comprehensive tests for RunContext."""

from datetime import datetime

from miniautogen.core.contracts.run_context import FrozenState, RunContext


def _make_context(**overrides: object) -> RunContext:
    defaults: dict[str, object] = {
        "run_id": "run-1",
        "started_at": datetime(2026, 1, 1),
        "correlation_id": "corr-1",
    }
    defaults.update(overrides)
    return RunContext(**defaults)  # type: ignore[arg-type]


def test_run_context_creation() -> None:
    ctx = _make_context()
    assert ctx.run_id == "run-1"


def test_run_context_with_previous_result() -> None:
    ctx = _make_context()
    new_ctx = ctx.with_previous_result({"output": "data"})
    assert new_ctx.run_id == ctx.run_id
    assert new_ctx.input_payload == {"output": "data"}
    assert new_ctx.get_metadata("previous_result") == {"output": "data"}


def test_run_context_state() -> None:
    ctx = _make_context(state=FrozenState(step=1))
    assert ctx.state.get("step") == 1


def test_run_context_serialization() -> None:
    ctx = _make_context()
    data = ctx.model_dump()
    restored = RunContext.model_validate(data)
    assert restored.run_id == ctx.run_id
