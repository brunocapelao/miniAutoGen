"""Policy chain for composing multiple policy checks.

Policies are evaluated in order. A 'deny' from any policy
short-circuits the chain. A 'retry' is recorded and the chain
continues. If all policies return 'proceed', the final decision
is 'proceed'.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

PolicyDecision = Literal["proceed", "deny", "retry"]


class PolicyContext(BaseModel):
    """Context passed to policy evaluation."""

    action: str
    run_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class PolicyResult(BaseModel):
    """Result of a policy evaluation."""

    decision: PolicyDecision
    reason: str | None = None


@runtime_checkable
class PolicyEvaluator(Protocol):
    """Protocol for policies that can evaluate an action."""

    async def evaluate(
        self, context: PolicyContext,
    ) -> PolicyResult: ...


class PolicyChain:
    """Evaluates a sequence of policies in order.

    Short-circuits on 'deny'. Records 'retry' and continues.
    Returns 'proceed' only if all policies agree.
    """

    def __init__(self, evaluators: list[PolicyEvaluator]) -> None:
        self._evaluators = list(evaluators)

    async def evaluate(
        self, context: PolicyContext,
    ) -> PolicyResult:
        has_retry = False
        for evaluator in self._evaluators:
            result = await evaluator.evaluate(context)
            if result.decision == "deny":
                return result
            if result.decision == "retry":
                has_retry = True
        if has_retry:
            return PolicyResult(
                decision="retry", reason="retry requested by policy",
            )
        return PolicyResult(decision="proceed")
