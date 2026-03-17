"""Tests for PolicyChain."""

import pytest

from miniautogen.policies.chain import (
    PolicyChain,
    PolicyContext,
    PolicyEvaluator,
    PolicyResult,
)


class _AlwaysProceed:
    async def evaluate(self, ctx: PolicyContext) -> PolicyResult:
        return PolicyResult(decision="proceed")


class _AlwaysDeny:
    async def evaluate(self, ctx: PolicyContext) -> PolicyResult:
        return PolicyResult(decision="deny", reason="blocked")


class _AlwaysRetry:
    async def evaluate(self, ctx: PolicyContext) -> PolicyResult:
        return PolicyResult(decision="retry", reason="transient")


def test_policy_evaluator_protocol() -> None:
    assert isinstance(_AlwaysProceed(), PolicyEvaluator)


@pytest.mark.anyio
async def test_chain_all_proceed() -> None:
    chain = PolicyChain([_AlwaysProceed(), _AlwaysProceed()])
    ctx = PolicyContext(action="test")
    result = await chain.evaluate(ctx)
    assert result.decision == "proceed"


@pytest.mark.anyio
async def test_chain_deny_short_circuits() -> None:
    chain = PolicyChain([_AlwaysDeny(), _AlwaysProceed()])
    ctx = PolicyContext(action="test")
    result = await chain.evaluate(ctx)
    assert result.decision == "deny"


@pytest.mark.anyio
async def test_chain_retry_continues() -> None:
    chain = PolicyChain([_AlwaysRetry(), _AlwaysProceed()])
    ctx = PolicyContext(action="test")
    result = await chain.evaluate(ctx)
    assert result.decision == "retry"


@pytest.mark.anyio
async def test_chain_deny_beats_retry() -> None:
    chain = PolicyChain([_AlwaysRetry(), _AlwaysDeny()])
    ctx = PolicyContext(action="test")
    result = await chain.evaluate(ctx)
    assert result.decision == "deny"


@pytest.mark.anyio
async def test_chain_empty_proceeds() -> None:
    chain = PolicyChain([])
    ctx = PolicyContext(action="test")
    result = await chain.evaluate(ctx)
    assert result.decision == "proceed"
