"""Tests for checkpoint recovery wiring into run_from_config().

Verifies two gaps are closed:
1. _build_coordination_from_config passes CheckpointManager to WorkflowRuntime
   when PipelineRunner has a checkpoint_store.
2. run_from_config accepts resume_run_id to reuse a previous run's checkpoints.
"""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from miniautogen.core.runtime.pipeline_runner import (
    PipelineRunner,
    _build_coordination_from_config,
)
from miniautogen.stores.in_memory_checkpoint_store import InMemoryCheckpointStore


def _make_flow_config(mode: str = "workflow", participants: list[str] | None = None):
    """Create a minimal FlowConfig-like object for testing."""
    from miniautogen.cli.config import FlowConfig

    return FlowConfig(
        name="test-flow",
        mode=mode,
        participants=participants or ["agent-a"],
    )


class TestWorkflowRuntimeReceivesCheckpointManager:
    """When PipelineRunner has checkpoint_store, WorkflowRuntime must get a CheckpointManager."""

    def test_checkpoint_manager_passed_when_store_exists(self) -> None:
        runner = PipelineRunner(checkpoint_store=InMemoryCheckpointStore())
        flow_config = _make_flow_config()
        agent_registry: dict[str, Any] = {"agent-a": object()}

        captured_kwargs: dict[str, Any] = {}
        original_init = __import__(
            "miniautogen.core.runtime.workflow_runtime",
            fromlist=["WorkflowRuntime"],
        ).WorkflowRuntime.__init__

        def spy_init(self_wrt, **kwargs):
            captured_kwargs.update(kwargs)
            original_init(self_wrt, **kwargs)

        with patch(
            "miniautogen.core.runtime.workflow_runtime.WorkflowRuntime.__init__",
            spy_init,
        ):
            _build_coordination_from_config(
                flow_config=flow_config,
                runner=runner,
                agent_registry=agent_registry,
            )

        assert "checkpoint_manager" in captured_kwargs, (
            "WorkflowRuntime should receive checkpoint_manager kwarg"
        )
        assert captured_kwargs["checkpoint_manager"] is not None, (
            "WorkflowRuntime should receive a CheckpointManager when runner has checkpoint_store"
        )

    def test_no_checkpoint_manager_when_no_store(self) -> None:
        runner = PipelineRunner()  # no checkpoint_store
        flow_config = _make_flow_config()
        agent_registry: dict[str, Any] = {"agent-a": object()}

        captured_kwargs: dict[str, Any] = {}
        original_init = __import__(
            "miniautogen.core.runtime.workflow_runtime",
            fromlist=["WorkflowRuntime"],
        ).WorkflowRuntime.__init__

        def spy_init(self_wrt, **kwargs):
            captured_kwargs.update(kwargs)
            original_init(self_wrt, **kwargs)

        with patch(
            "miniautogen.core.runtime.workflow_runtime.WorkflowRuntime.__init__",
            spy_init,
        ):
            _build_coordination_from_config(
                flow_config=flow_config,
                runner=runner,
                agent_registry=agent_registry,
            )

        assert captured_kwargs.get("checkpoint_manager") is None, (
            "WorkflowRuntime should NOT receive a CheckpointManager when runner lacks checkpoint_store"
        )


class TestRunFromConfigAcceptsResumeRunId:
    """run_from_config must accept resume_run_id parameter."""

    def test_resume_run_id_in_signature(self) -> None:
        sig = inspect.signature(PipelineRunner.run_from_config)
        assert "resume_run_id" in sig.parameters, (
            "run_from_config should accept resume_run_id parameter"
        )

    def test_resume_run_id_default_is_none(self) -> None:
        sig = inspect.signature(PipelineRunner.run_from_config)
        param = sig.parameters["resume_run_id"]
        assert param.default is None, (
            "resume_run_id should default to None"
        )
