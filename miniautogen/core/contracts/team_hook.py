"""TeamHook protocol — lifecycle hooks for team coordination (Spec 017).

These hooks fire at the TeamRuntime level, not AgentRuntime.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from miniautogen.core.contracts.team_message import MailMessage, PlanApprovalRequest


@runtime_checkable
class TeamHook(Protocol):
    async def on_message_received(
        self, message: MailMessage, context: Any = None
    ) -> None: ...

    async def on_teammate_idle(
        self, teammate: str, context: Any = None
    ) -> None: ...

    async def on_plan_approval_requested(
        self, request: PlanApprovalRequest, context: Any = None
    ) -> None: ...

    async def on_plan_approval_decided(
        self,
        correlation_id: str,
        decision: Literal["granted", "denied", "timeout"],
        reason: str | None,
        context: Any = None,
    ) -> None: ...
