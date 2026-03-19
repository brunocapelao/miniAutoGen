"""Tests for CoordinatorCapability protocol."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from miniautogen.core.contracts.agent_spec import AgentSpec
from miniautogen.core.contracts.coordination import CoordinationPlan
from miniautogen.core.contracts.coordinator_capability import CoordinatorCapability
from miniautogen.core.contracts.enums import RunStatus
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult


def _make_context() -> RunContext:
    return RunContext(
        run_id="run-1",
        started_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
    )


# --- Fake implementations ---


class _FakeCoordinator:
    """Satisfies CoordinatorCapability structurally."""

    async def coordinate(
        self,
        plan: CoordinationPlan,
        participants: list[AgentSpec],
        context: RunContext,
    ) -> RunResult:
        return RunResult(
            run_id=context.run_id,
            status=RunStatus.FINISHED,
            output="coordinated",
        )


class _BrokenCoordinator:
    """Missing coordinate -- does NOT satisfy CoordinatorCapability."""

    pass


class _CoordinatorWithWrongSignature:
    """Has coordinate but wrong signature -- still structurally matches
    because Protocol only checks method existence, not signatures."""

    async def coordinate(self, x: int) -> str:
        return "wrong"


# --- Tests ---


def test_coordinator_capability_is_runtime_checkable() -> None:
    coordinator = _FakeCoordinator()
    assert isinstance(coordinator, CoordinatorCapability)


def test_broken_coordinator_not_satisfied() -> None:
    coordinator = _BrokenCoordinator()
    assert not isinstance(coordinator, CoordinatorCapability)


@pytest.mark.anyio
async def test_fake_coordinator_returns_run_result() -> None:
    coordinator = _FakeCoordinator()
    ctx = _make_context()
    plan = CoordinationPlan()
    spec = AgentSpec(id="agent-1", name="Agent 1")
    result = await coordinator.coordinate(plan, [spec], ctx)

    assert result.status == RunStatus.FINISHED
    assert result.output == "coordinated"
    assert result.run_id == "run-1"
