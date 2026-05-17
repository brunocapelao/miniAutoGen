"""Shared tool injection utilities for team coordination mode.

Extracted from TeamRuntime to allow the CLI team command to inject
team tools into agent runtimes without instantiating a full TeamRuntime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from miniautogen.core.contracts.coordination import (
        PlanApprovalConfig,
        TeamPlan,
    )
    from miniautogen.core.events.event_sink import EventSink


def inject_task_tools(agent: Any, store: Any, agent_name: str) -> None:
    """Compose team task tools into an agent's tool registry."""
    from miniautogen.core.runtime.composite_tool_registry import (
        CompositeToolRegistry,
    )
    from miniautogen.core.runtime.team_task_tools import build_team_task_tools
    from miniautogen.core.runtime.tool_registry import InMemoryToolRegistry

    team_registry = InMemoryToolRegistry()
    for definition, handler in build_team_task_tools(store, agent_name):
        team_registry.register(definition, handler)

    existing = getattr(agent, "tool_registry", None)
    if existing is not None:
        if isinstance(existing, CompositeToolRegistry):
            existing._registries = list(existing._registries) + [team_registry]
        else:
            agent.tool_registry = CompositeToolRegistry([existing, team_registry])
    else:
        agent.tool_registry = team_registry


def inject_mailbox_tools(
    agent: Any,
    agent_name: str,
    is_lead: bool,
    mailbox: Any,
    approvals: Any,
    event_sink: EventSink,
    team_run_id: str,
    plan: TeamPlan,
) -> None:
    """Compose team mailbox and plan-approval tools into an agent's registry."""
    from miniautogen.core.runtime.approval_gated_tool_registry import (
        ApprovalGatedToolRegistry,
    )
    from miniautogen.core.runtime.builtin_team_tools import (
        _make_request_plan_approval_handler,
        build_team_tools,
    )
    from miniautogen.core.runtime.composite_tool_registry import (
        CompositeToolRegistry,
    )
    from miniautogen.core.runtime.tool_registry import InMemoryToolRegistry

    team_registry = InMemoryToolRegistry()
    for definition, handler in build_team_tools(
        agent_id=agent_name,
        is_lead=is_lead,
        mailbox=mailbox,
        approvals=approvals,
        event_sink=event_sink,
        team_run_id=team_run_id,
        lead_agent=plan.lead_agent,
    ):
        team_registry.register(definition, handler)

    plan_approval_cfg: PlanApprovalConfig | None = None
    try:
        raw = plan.plan_approval
        if isinstance(raw, PlanApprovalConfig):
            plan_approval_cfg = raw
        elif isinstance(raw, dict):
            plan_approval_cfg = PlanApprovalConfig(**raw)
    except Exception:
        pass

    if plan_approval_cfg is not None and plan_approval_cfg.required_for and not is_lead:
        approval_handler = _make_request_plan_approval_handler(
            mailbox, approvals, agent_name, plan.lead_agent,
            event_sink, team_run_id,
        )

        async def _approval_wrapper(plan_summary: str | dict) -> str:
            result = await approval_handler(
                {"plan": plan_summary, "timeout_seconds": 60.0}
            )
            if result.success:
                return result.output.get("decision", "denied")
            return "denied"

        wrapped = ApprovalGatedToolRegistry(
            inner=team_registry,
            approval_tool=_approval_wrapper,
            required_for=set(plan_approval_cfg.required_for),
            agent_id=agent_name,
            event_sink=event_sink,
        )
        team_registry = wrapped

    existing = getattr(agent, "tool_registry", None)
    if existing is not None:
        if isinstance(existing, CompositeToolRegistry):
            existing._registries = list(existing._registries) + [team_registry]
        else:
            agent.tool_registry = CompositeToolRegistry([existing, team_registry])
    else:
        agent.tool_registry = team_registry
