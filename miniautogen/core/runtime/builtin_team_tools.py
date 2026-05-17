"""Built-in team mailbox tools for teammates.

Factories inject per-team-run state (mailbox, approvals, agent_id, is_lead).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import anyio

from miniautogen.core.contracts.team_message import MailMessage
from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.contracts.tool_registry import ToolDefinition
from miniautogen.core.events.types import EventType
from miniautogen.core.runtime.tool_registry import ToolHandler

TOOL_SEND_MESSAGE = "send_message"
TOOL_INBOX_READ = "inbox_read"
TOOL_INBOX_POP = "inbox_pop"
TOOL_REQUEST_PLAN_APPROVAL = "request_plan_approval"
TOOL_APPROVE_PLAN = "approve_plan"
TOOL_REJECT_PLAN = "reject_plan"


def _send_message_def() -> ToolDefinition:
    return ToolDefinition(
        name=TOOL_SEND_MESSAGE,
        description="Send a message to a teammate's inbox.",
        parameters={
            "type": "object",
            "properties": {
                "to_teammate": {
                    "type": "string",
                    "description": "Name of the recipient teammate",
                },
                "content": {
                    "type": "string",
                    "description": "Message content",
                },
                "kind": {
                    "type": "string",
                    "description": "Message kind: chat (default)",
                    "enum": ["chat"],
                },
                "correlation_id": {
                    "type": "string",
                    "description": "Optional correlation ID for tracking",
                },
            },
            "required": ["to_teammate", "content"],
        },
    )


def _make_send_message_handler(
    mailbox: Any,
    agent_id: str,
    event_sink: Any,
    team_run_id: str,
) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        to_teammate = params.get("to_teammate", "")
        content = params.get("content", "")
        kind = params.get("kind", "chat")
        corr_id = params.get("correlation_id")

        if not to_teammate:
            return ToolResult(success=False, error="to_teammate is required")
        if not content:
            return ToolResult(success=False, error="content is required")

        msg_id = uuid.uuid4().hex
        message = MailMessage(
            id=msg_id,
            from_agent=agent_id,
            to_agent=to_teammate,
            content=content,
            kind=kind,
            correlation_id=corr_id,
        )
        await mailbox.send(message)
        return ToolResult(success=True, output={"message_id": msg_id})

    return handler


def _inbox_read_def() -> ToolDefinition:
    return ToolDefinition(
        name=TOOL_INBOX_READ,
        description="Read messages from your inbox without consuming them.",
        parameters={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of messages to read (default 10)",
                },
            },
        },
    )


def _make_inbox_read_handler(
    mailbox: Any,
    agent_id: str,
) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        limit = params.get("limit", 10)
        messages = await mailbox.peek(agent_id)
        truncated = messages[:limit]
        return ToolResult(
            success=True,
            output={
                "messages": [
                    {
                        "id": m.id,
                        "from": m.from_agent,
                        "content": m.content,
                        "kind": m.kind,
                        "correlation_id": m.correlation_id,
                    }
                    for m in truncated
                ],
                "total_pending": len(messages),
            },
        )

    return handler


def _inbox_pop_def() -> ToolDefinition:
    return ToolDefinition(
        name=TOOL_INBOX_POP,
        description="Read and consume messages from your inbox.",
        parameters={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of messages to pop (default 10)",
                },
            },
        },
    )


def _make_inbox_pop_handler(
    mailbox: Any,
    agent_id: str,
    event_sink: Any,
    team_run_id: str,
) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        limit = params.get("limit", 10)
        messages: list[MailMessage] = []

        try:
            async with anyio.move_on_after(0):
                stream = mailbox.receive_stream(agent_id)
                async for msg in stream:
                    messages.append(msg)
                    if len(messages) >= limit:
                        break
        except Exception:
            pass

        if event_sink:
            from miniautogen.core.contracts.events import ExecutionEvent

            event = ExecutionEvent(
                type=EventType.INBOX_DRAINED.value,
                timestamp=datetime.now(timezone.utc),
                run_id=team_run_id,
                correlation_id=team_run_id,
                scope="builtin_team_tools",
                payload={
                    "agent": agent_id,
                    "count": len(messages),
                    "team_run_id": team_run_id,
                },
            )
            await event_sink.publish(event)

        return ToolResult(
            success=True,
            output={
                "messages": [
                    {
                        "id": m.id,
                        "from": m.from_agent,
                        "content": m.content,
                        "kind": m.kind,
                        "correlation_id": m.correlation_id,
                    }
                    for m in messages
                ],
                "consumed": len(messages),
            },
        )

    return handler


def _request_plan_approval_def() -> ToolDefinition:
    return ToolDefinition(
        name=TOOL_REQUEST_PLAN_APPROVAL,
        description="Request approval from the lead before executing a sensitive plan.",
        parameters={
            "type": "object",
            "properties": {
                "plan": {
                    "type": "string",
                    "description": "Description of the plan to be approved",
                },
                "to_lead": {
                    "type": "boolean",
                    "description": "Send to lead (default true)",
                },
                "timeout_seconds": {
                    "type": "number",
                    "description": "Timeout in seconds (default 300)",
                },
            },
            "required": ["plan"],
        },
    )


def _make_request_plan_approval_handler(
    mailbox: Any,
    approvals: Any,
    agent_id: str,
    lead_agent: str,
    event_sink: Any,
    team_run_id: str,
) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        plan = params.get("plan", "")
        timeout = params.get("timeout_seconds", 300.0)

        if not plan:
            return ToolResult(success=False, error="plan is required")

        corr_id = await approvals.register(agent_id, lead_agent, timeout)

        plan_content = json.dumps(plan) if isinstance(plan, dict) else plan
        await mailbox.send(MailMessage(
            id=uuid.uuid4().hex,
            from_agent=agent_id,
            to_agent=lead_agent,
            content=plan_content,
            kind="plan_approval_request",
            correlation_id=corr_id,
        ))

        try:
            decision, reason = await approvals.wait(corr_id)
        except anyio.get_cancelled_exc_class():
            raise

        if decision == "granted":
            return ToolResult(
                success=True,
                output={"decision": "granted", "reason": reason},
            )
        elif decision == "timeout":
            return ToolResult(
                success=False,
                error=f"Plan approval timed out after {timeout}s",
                output={"decision": "timeout", "reason": reason},
            )
        else:
            return ToolResult(
                success=False,
                error=f"Plan approval denied: {reason}" if reason else "Plan approval denied",
                output={"decision": "denied", "reason": reason},
            )

    return handler


def _approve_plan_def() -> ToolDefinition:
    return ToolDefinition(
        name=TOOL_APPROVE_PLAN,
        description="Approve a plan approval request from a teammate (lead only).",
        parameters={
            "type": "object",
            "properties": {
                "correlation_id": {
                    "type": "string",
                    "description": "Correlation ID from the approval request",
                },
                "comment": {
                    "type": "string",
                    "description": "Optional approval comment",
                },
            },
            "required": ["correlation_id"],
        },
    )


def _make_approve_plan_handler(
    mailbox: Any,
    approvals: Any,
    agent_id: str,
    is_lead: bool,
    event_sink: Any,
    team_run_id: str,
) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        if not is_lead:
            return ToolResult(
                success=False,
                error="Only the team lead can approve plans",
            )

        corr_id = params.get("correlation_id", "")
        comment = params.get("comment")

        if not corr_id:
            return ToolResult(success=False, error="correlation_id is required")

        await approvals.resolve(corr_id, "granted", reason=comment)
        return ToolResult(
            success=True,
            output={"decision": "granted", "correlation_id": corr_id, "comment": comment},
        )

    return handler


def _reject_plan_def() -> ToolDefinition:
    return ToolDefinition(
        name=TOOL_REJECT_PLAN,
        description="Reject a plan approval request from a teammate (lead only).",
        parameters={
            "type": "object",
            "properties": {
                "correlation_id": {
                    "type": "string",
                    "description": "Correlation ID from the approval request",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for rejection",
                },
            },
            "required": ["correlation_id", "reason"],
        },
    )


def _make_reject_plan_handler(
    mailbox: Any,
    approvals: Any,
    agent_id: str,
    is_lead: bool,
    event_sink: Any,
    team_run_id: str,
) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        if not is_lead:
            return ToolResult(
                success=False,
                error="Only the team lead can reject plans",
            )

        corr_id = params.get("correlation_id", "")
        reason = params.get("reason", "")

        if not corr_id:
            return ToolResult(success=False, error="correlation_id is required")
        if not reason:
            return ToolResult(success=False, error="reason is required")

        await approvals.resolve(corr_id, "denied", reason=reason)
        return ToolResult(
            success=True,
            output={"decision": "denied", "correlation_id": corr_id, "reason": reason},
        )

    return handler


def build_team_tools(
    *,
    agent_id: str,
    is_lead: bool,
    mailbox: Any,
    approvals: Any,
    event_sink: Any,
    team_run_id: str,
    lead_agent: str,
) -> list[tuple[ToolDefinition, ToolHandler]]:
    tools: list[tuple[ToolDefinition, ToolHandler]] = [
        (
            _send_message_def(),
            _make_send_message_handler(mailbox, agent_id, event_sink, team_run_id),
        ),
        (
            _inbox_read_def(),
            _make_inbox_read_handler(mailbox, agent_id),
        ),
        (
            _inbox_pop_def(),
            _make_inbox_pop_handler(mailbox, agent_id, event_sink, team_run_id),
        ),
    ]

    if not is_lead:
        tools.append((
            _request_plan_approval_def(),
            _make_request_plan_approval_handler(
                mailbox, approvals, agent_id, lead_agent, event_sink, team_run_id
            ),
        ))

    if is_lead:
        tools.append((
            _approve_plan_def(),
            _make_approve_plan_handler(
                mailbox, approvals, agent_id, is_lead, event_sink, team_run_id
            ),
        ))
        tools.append((
            _reject_plan_def(),
            _make_reject_plan_handler(
                mailbox, approvals, agent_id, is_lead, event_sink, team_run_id
            ),
        ))

    return tools
