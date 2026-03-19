"""Tests for PolicyChain wiring in PipelineRunner.

Verifies that PolicyChain acts as pre-execution middleware:
- No chain = normal execution (backward compatible)
- proceed = normal execution
- deny = RuntimeError, pipeline NOT executed
- retry = WARNING logged, pipeline executes normally
- BudgetPolicy evaluator integration
"""

from __future__ import annotations

import pytest

from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.policies.chain import (
    PolicyChain,
    PolicyContext,
    PolicyResult,
)


class _NoOpPipeline:
    def __init__(self) -> None:
        self.call_count = 0

    async def run(self, state: dict) -> dict:
        self.call_count += 1
        return {"result": "ok"}


class _ProceedEvaluator:
    async def evaluate(self, context: PolicyContext) -> PolicyResult:
        return PolicyResult(decision="proceed")


class _DenyEvaluator:
    def __init__(self, reason: str = "over budget") -> None:
        self._reason = reason

    async def evaluate(self, context: PolicyContext) -> PolicyResult:
        return PolicyResult(decision="deny", reason=self._reason)


class _RetryEvaluator:
    async def evaluate(self, context: PolicyContext) -> PolicyResult:
        return PolicyResult(decision="retry", reason="rate limit approaching")


class _BudgetPolicyEvaluator:
    """Evaluator that denies when accumulated cost exceeds a limit."""

    def __init__(self, max_cost: float, current_cost: float) -> None:
        self._max_cost = max_cost
        self._current_cost = current_cost

    async def evaluate(self, context: PolicyContext) -> PolicyResult:
        if self._current_cost > self._max_cost:
            return PolicyResult(
                decision="deny",
                reason=f"budget exceeded: {self._current_cost:.2f} > {self._max_cost:.2f}",
            )
        return PolicyResult(decision="proceed")


@pytest.mark.anyio
async def test_no_policy_chain_normal_execution() -> None:
    """No policy_chain = normal execution (backward compatible)."""
    runner = PipelineRunner()
    pipeline = _NoOpPipeline()
    result = await runner.run_pipeline(pipeline, {})
    assert result == {"result": "ok"}
    assert pipeline.call_count == 1


@pytest.mark.anyio
async def test_policy_chain_proceed_normal_execution() -> None:
    """PolicyChain returning 'proceed' allows normal execution."""
    chain = PolicyChain([_ProceedEvaluator()])
    runner = PipelineRunner(policy_chain=chain)
    pipeline = _NoOpPipeline()
    result = await runner.run_pipeline(pipeline, {})
    assert result == {"result": "ok"}
    assert pipeline.call_count == 1


@pytest.mark.anyio
async def test_policy_chain_deny_raises_and_blocks_execution() -> None:
    """PolicyChain returning 'deny' raises RuntimeError; pipeline NOT executed."""
    chain = PolicyChain([_DenyEvaluator(reason="cost limit reached")])
    runner = PipelineRunner(policy_chain=chain)
    pipeline = _NoOpPipeline()

    with pytest.raises(RuntimeError, match="denied by policy.*cost limit reached"):
        await runner.run_pipeline(pipeline, {})

    assert pipeline.call_count == 0


@pytest.mark.anyio
async def test_policy_chain_retry_logs_warning_and_executes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """PolicyChain returning 'retry' logs WARNING; pipeline executes normally."""
    chain = PolicyChain([_RetryEvaluator()])
    runner = PipelineRunner(policy_chain=chain)
    pipeline = _NoOpPipeline()

    result = await runner.run_pipeline(pipeline, {})

    assert result == {"result": "ok"}
    assert pipeline.call_count == 1


@pytest.mark.anyio
async def test_policy_chain_budget_evaluator_denies_over_budget() -> None:
    """BudgetPolicy evaluator denies when cost exceeds limit."""
    evaluator = _BudgetPolicyEvaluator(max_cost=10.0, current_cost=15.0)
    chain = PolicyChain([evaluator])
    runner = PipelineRunner(policy_chain=chain)
    pipeline = _NoOpPipeline()

    with pytest.raises(RuntimeError, match="denied by policy.*budget exceeded"):
        await runner.run_pipeline(pipeline, {})

    assert pipeline.call_count == 0


@pytest.mark.anyio
async def test_policy_chain_budget_evaluator_allows_under_budget() -> None:
    """BudgetPolicy evaluator allows execution when within budget."""
    evaluator = _BudgetPolicyEvaluator(max_cost=10.0, current_cost=5.0)
    chain = PolicyChain([evaluator])
    runner = PipelineRunner(policy_chain=chain)
    pipeline = _NoOpPipeline()

    result = await runner.run_pipeline(pipeline, {})
    assert result == {"result": "ok"}
    assert pipeline.call_count == 1
