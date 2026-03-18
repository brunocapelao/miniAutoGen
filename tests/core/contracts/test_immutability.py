"""Immutability invariant tests using DeepDiff.

These tests enforce Architectural Invariant 1 (Immutability) by verifying
that framework models do not mutate their inputs or leak shared references.
"""

from __future__ import annotations

import copy

# ---------------------------------------------------------------------------
# Import the shared helper (available via tests/conftest.py)
# ---------------------------------------------------------------------------
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from deepdiff import DeepDiff

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import RunContext

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from conftest import assert_no_mutation

# ---------------------------------------------------------------------------
# ExecutionEvent immutability tests
# ---------------------------------------------------------------------------


class TestExecutionEventImmutability:
    """Verify ExecutionEvent does not mutate inputs."""

    def test_payload_dict_not_mutated_by_construction(self) -> None:
        """Creating an ExecutionEvent must not mutate the input payload dict."""
        original_payload: dict[str, Any] = {"run_id": "run-123", "data": "value"}
        snapshot = copy.deepcopy(original_payload)

        # Construction triggers infer_run_id_from_payload validator
        _event = ExecutionEvent(type="test", payload=original_payload)

        assert_no_mutation(snapshot, original_payload, "ExecutionEvent payload input")

    def test_event_serialization_round_trip(self) -> None:
        """model_dump_json -> model_validate_json produces zero diff."""
        event = ExecutionEvent(
            type="component_finished",
            run_id="run-1",
            payload={"step": 3, "data": [1, 2, 3]},
        )
        json_str = event.model_dump_json()
        restored = ExecutionEvent.model_validate_json(json_str)

        diff = DeepDiff(
            event.model_dump(mode="python"),
            restored.model_dump(mode="python"),
        )
        assert diff == {}, f"Event round-trip fidelity violation: {diff}"

    @pytest.mark.xfail(
        reason=(
            "Known violation: infer_run_id_from_payload mutates self.run_id in "
            "model_validator(mode='after'). Tracked for refactoring in WS2 (Immutable Core)."
        ),
        strict=True,
    )
    def test_event_run_id_inference_does_not_mutate_self(self) -> None:
        """The model_validator should not mutate self -- it should use model_copy or __init__.

        This test documents the known violation: the validator sets self.run_id
        directly, which is a mutation of the model after construction.
        """
        event = ExecutionEvent(type="test", payload={"run_id": "inferred-123"})
        # The validator mutated self.run_id -- this is the violation.
        # In an ideal world, run_id would be set during __init__, not via mutation.
        # We mark this xfail to document the violation; WS2 will fix it.
        assert event.run_id is None  # This WILL fail because run_id was mutated to "inferred-123"


# ---------------------------------------------------------------------------
# RunContext immutability tests
# ---------------------------------------------------------------------------


class TestRunContextImmutability:
    """Verify RunContext operations produce isolated copies."""

    def _make_context(self, **overrides: Any) -> RunContext:
        defaults: dict[str, Any] = {
            "run_id": "run-1",
            "started_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "correlation_id": "corr-1",
            "execution_state": {"step": 1, "data": [1, 2, 3]},
            "metadata": {"source": "test"},
        }
        defaults.update(overrides)
        return RunContext(**defaults)  # type: ignore[arg-type]

    def test_with_previous_result_does_not_mutate_original(self) -> None:
        """Calling with_previous_result must not change the original context."""
        ctx = self._make_context()
        snapshot = ctx.model_dump(mode="python")

        _child = ctx.with_previous_result({"output": "data"})

        assert_no_mutation(
            snapshot,
            ctx.model_dump(mode="python"),
            "RunContext after with_previous_result",
        )

    @pytest.mark.xfail(
        reason="Pydantic model_copy performs shallow copy of execution_state. "
               "Tracked for fix in WS2 (Immutable Core).",
        strict=True,
    )
    def test_execution_state_isolated_on_copy(self) -> None:
        """execution_state in the child must be a distinct object."""
        ctx = self._make_context()
        child = ctx.with_previous_result({"output": "data"})

        # Identity check: must NOT be the same dict object
        assert child.execution_state is not ctx.execution_state

    def test_metadata_isolated_on_copy(self) -> None:
        """metadata in the child must be a distinct object (it uses spread)."""
        ctx = self._make_context()
        child = ctx.with_previous_result({"output": "data"})

        # Identity check: must NOT be the same dict object
        assert child.metadata is not ctx.metadata

    def test_metadata_changes_do_not_leak_back(self) -> None:
        """Mutating child metadata must not affect parent metadata."""
        ctx = self._make_context()
        child = ctx.with_previous_result({"output": "data"})

        # Mutate the child's metadata
        child.metadata["injected"] = "should_not_leak"

        assert "injected" not in ctx.metadata

    @pytest.mark.xfail(
        reason="Pydantic model_copy performs shallow copy of execution_state. "
               "Tracked for fix in WS2 (Immutable Core).",
        strict=True,
    )
    def test_execution_state_changes_do_not_leak_back(self) -> None:
        """Mutating child execution_state must not affect parent."""
        ctx = self._make_context()
        child = ctx.with_previous_result({"output": "data"})

        # Mutate the child's execution_state
        child.execution_state["injected"] = "should_not_leak"

        assert "injected" not in ctx.execution_state
