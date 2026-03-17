"""Tests for PipelineRunner approval and retry integration."""

import pytest

from miniautogen.core.contracts.enums import RunStatus
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.policies.approval import (
    ApprovalGate,
    ApprovalRequest,
    ApprovalResponse,
    AutoApproveGate,
)
from miniautogen.policies.retry import RetryPolicy


class _DenyGate:
    """Gate that denies all requests."""

    async def request_approval(
        self,
        request: ApprovalRequest,
    ) -> ApprovalResponse:
        return ApprovalResponse(
            request_id=request.request_id,
            decision="denied",
            reason="test denial",
        )


class _NoOpPipeline:
    async def run(self, state: dict) -> dict:
        return {"result": "ok"}


class _FailOncePipeline:
    """Pipeline that fails on first call, succeeds on second."""

    def __init__(self) -> None:
        self._calls = 0

    async def run(self, state: dict) -> dict:
        self._calls += 1
        if self._calls == 1:
            raise RuntimeError("transient failure")
        return {"result": "ok", "calls": self._calls}


@pytest.mark.asyncio
async def test_approval_gate_approved_runs_pipeline() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(
        event_sink=sink,
        approval_gate=AutoApproveGate(),
    )
    result = await runner.run_pipeline(_NoOpPipeline(), {})
    assert result is not None
    # Should have approval_requested and approval_granted events
    types = [e.type for e in sink.events]
    assert "approval_requested" in types
    assert "approval_granted" in types


@pytest.mark.asyncio
async def test_approval_gate_denied_cancels_run() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(
        event_sink=sink,
        approval_gate=_DenyGate(),
    )
    result = await runner.run_pipeline(_NoOpPipeline(), {})
    assert result.status == RunStatus.CANCELLED
    types = [e.type for e in sink.events]
    assert "approval_requested" in types
    assert "approval_denied" in types


@pytest.mark.asyncio
async def test_no_approval_gate_runs_normally() -> None:
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    result = await runner.run_pipeline(_NoOpPipeline(), {})
    types = [e.type for e in sink.events]
    assert "approval_requested" not in types


@pytest.mark.asyncio
async def test_retry_policy_retries_on_failure() -> None:
    sink = InMemoryEventSink()
    pipeline = _FailOncePipeline()
    runner = PipelineRunner(
        event_sink=sink,
        retry_policy=RetryPolicy(max_attempts=2, retry_exceptions=(RuntimeError,)),
    )
    result = await runner.run_pipeline(pipeline, {})
    assert result["result"] == "ok"
    assert result["calls"] == 2


@pytest.mark.asyncio
async def test_retry_policy_exhausted_raises() -> None:
    sink = InMemoryEventSink()
    pipeline = _FailOncePipeline()
    runner = PipelineRunner(
        event_sink=sink,
        retry_policy=RetryPolicy(max_attempts=1, retry_exceptions=(RuntimeError,)),
    )
    with pytest.raises(RuntimeError, match="transient failure"):
        await runner.run_pipeline(pipeline, {})
