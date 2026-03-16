from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from miniautogen.core.contracts.agentic_loop import ConversationPolicy

if TYPE_CHECKING:
    from miniautogen.core.contracts.coordination import AgenticLoopPlan
    from miniautogen.core.contracts.run_context import RunContext
    from miniautogen.core.contracts.run_result import RunResult
    from miniautogen.core.runtime.agentic_loop_runtime import AgenticLoopRuntime


@dataclass
class AgenticLoopComponent:
    policy: ConversationPolicy
    runtime: AgenticLoopRuntime | None = field(default=None)

    async def execute(
        self,
        agents: list[Any],
        context: RunContext,
        plan: AgenticLoopPlan,
    ) -> RunResult:
        """Delegate execution to the runtime if available.

        Raises ``RuntimeError`` when no runtime has been configured.
        """
        if self.runtime is None:
            raise RuntimeError(
                "AgenticLoopComponent.execute requires a runtime, but none was set."
            )
        return await self.runtime.run(agents, context, plan)
