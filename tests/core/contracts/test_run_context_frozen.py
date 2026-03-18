"""Tests for frozen RunContext with FrozenState and tuple metadata."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.run_context import FrozenState, RunContext


def _make_ctx(**overrides: object) -> RunContext:
    defaults: dict[str, object] = {
        "run_id": "run-1",
        "started_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "correlation_id": "corr-1",
    }
    defaults.update(overrides)
    return RunContext(**defaults)  # type: ignore[arg-type]


class TestRunContextFrozen:
    def test_attribute_assignment_raises(self) -> None:
        ctx = _make_ctx()
        with pytest.raises(ValidationError):
            ctx.input_payload = "mutated"  # type: ignore[misc]

    def test_run_id_assignment_raises(self) -> None:
        ctx = _make_ctx()
        with pytest.raises(ValidationError):
            ctx.run_id = "changed"  # type: ignore[misc]


class TestRunContextState:
    def test_default_state_is_empty(self) -> None:
        ctx = _make_ctx()
        assert ctx.state.to_dict() == {}

    def test_construction_with_frozen_state(self) -> None:
        ctx = _make_ctx(state=FrozenState(step=1, agent="writer"))
        assert ctx.state.get("step") == 1
        assert ctx.state.get("agent") == "writer"

    def test_with_state_returns_new_context(self) -> None:
        ctx = _make_ctx(state=FrozenState(step=1))
        ctx2 = ctx.with_state(step=2)
        assert ctx2.state.get("step") == 2
        assert ctx.state.get("step") == 1  # original unchanged

    def test_with_state_preserves_other_fields(self) -> None:
        ctx = _make_ctx(input_payload="hello", state=FrozenState(a=1))
        ctx2 = ctx.with_state(b=2)
        assert ctx2.run_id == ctx.run_id
        assert ctx2.input_payload == "hello"
        assert ctx2.state.get("a") == 1
        assert ctx2.state.get("b") == 2


class TestRunContextMetadata:
    def test_default_metadata_is_empty_tuple(self) -> None:
        ctx = _make_ctx()
        assert ctx.metadata == ()

    def test_construction_with_metadata_tuple(self) -> None:
        ctx = _make_ctx(metadata=(("source", "cli"),))
        assert ctx.get_metadata("source") == "cli"

    def test_get_metadata_missing_returns_default(self) -> None:
        ctx = _make_ctx()
        assert ctx.get_metadata("missing") is None
        assert ctx.get_metadata("missing", "fallback") == "fallback"

    def test_evolve_metadata(self) -> None:
        ctx = _make_ctx(metadata=(("source", "cli"),))
        ctx2 = ctx.evolve_metadata(retry_count=3)
        assert ctx2.get_metadata("source") == "cli"
        assert ctx2.get_metadata("retry_count") == 3
        # Original unchanged
        assert ctx.get_metadata("retry_count") is None

    def test_with_previous_result(self) -> None:
        ctx = _make_ctx()
        ctx2 = ctx.with_previous_result({"output": "data"})
        assert ctx2.input_payload == {"output": "data"}
        assert ctx2.get_metadata("previous_result") == {"output": "data"}
        assert ctx2.run_id == ctx.run_id


class TestRunContextSerialization:
    def test_round_trip(self) -> None:
        ctx = _make_ctx(
            state=FrozenState(group_chat="chat"),
            metadata=(("source", "cli"),),
            input_payload={"text": "hello"},
        )
        dumped = ctx.model_dump()
        restored = RunContext.model_validate(dumped)
        assert restored.state.get("group_chat") == "chat"
        assert restored.get_metadata("source") == "cli"
        assert restored.input_payload == {"text": "hello"}
        assert restored.run_id == ctx.run_id

    def test_state_serializes_as_dict(self) -> None:
        ctx = _make_ctx(state=FrozenState(a=1))
        dumped = ctx.model_dump()
        assert isinstance(dumped["state"], dict)
        assert dumped["state"] == {"a": 1}


class TestRunContextConcurrencySafety:
    def test_concurrent_with_state_isolated(self) -> None:
        """Two branches from the same context do not see each other's state."""
        base = _make_ctx(state=FrozenState(counter=0))
        branch_a = base.with_state(counter=1, branch="a")
        branch_b = base.with_state(counter=2, branch="b")

        assert branch_a.state.get("counter") == 1
        assert branch_a.state.get("branch") == "a"
        assert branch_b.state.get("counter") == 2
        assert branch_b.state.get("branch") == "b"
        assert base.state.get("counter") == 0
        assert base.state.get("branch") is None
