"""CoordinatorCapability protocol for agents that orchestrate sub-Flows.

Recovers the v0 pattern (ChatAdmin extends Agent) with type safety.
An agent with this capability can instantiate sub-Flows within a
parent Flow, selecting participants dynamically.

This composes with the existing CompositeRuntime: a CoordinatorCapability
agent creates a CompositionStep sequence and delegates execution.

See docs/pt/architecture/07-agent-anatomy.md section 6.3.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from miniautogen.core.contracts.agent_spec import AgentSpec
from miniautogen.core.contracts.coordination import CoordinationPlan
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.run_result import RunResult


@runtime_checkable
class CoordinatorCapability(Protocol):
    """Agent capability for orchestrating sub-Flows.

    An agent with this capability can:
    - Instantiate a sub-Flow within the parent Flow
    - Select participants dynamically
    - Pass context from parent to sub-Flow
    - Receive the result and continue in the parent Flow
    """

    async def coordinate(
        self,
        plan: CoordinationPlan,
        participants: list[AgentSpec],
        context: RunContext,
    ) -> RunResult:
        """Execute a sub-Flow with the given plan and participants.

        Args:
            plan: The coordination plan for the sub-Flow.
            participants: Agent specs for participating agents.
            context: The current RunContext from the parent Flow.

        Returns:
            RunResult from the sub-Flow execution.
        """
        ...
