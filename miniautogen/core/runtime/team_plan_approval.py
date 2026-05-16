"""PlanApprovalRegistry — cross-teammate rendezvous for plan approval."""

from __future__ import annotations

from typing import Any

import anyio

from miniautogen.core.events.types import EventType


class PlanApprovalRegistry:
    def __init__(
        self,
        event_sink: Any | None = None,
        team_run_id: str | None = None,
    ) -> None:
        self._slots: dict[str, dict[str, Any]] = {}
        self._events: dict[str, anyio.Event] = {}
        self._sink = event_sink
        self._team_run_id = team_run_id

    async def register(
        self, from_agent: str, to_agent: str, timeout: float
    ) -> str:
        import uuid

        corr_id = uuid.uuid4().hex
        self._slots[corr_id] = {
            "decision": None,
            "reason": None,
            "resolved": False,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "timeout": timeout,
        }
        self._events[corr_id] = anyio.Event()
        await self._emit(EventType.PLAN_APPROVAL_REQUESTED, corr_id, from_agent)
        return corr_id

    async def resolve(
        self,
        corr_id: str,
        decision: str,
        reason: str | None = None,
    ) -> None:
        slot = self._slots.get(corr_id)
        if slot is None:
            return
        if slot["resolved"]:
            return
        slot["decision"] = decision
        slot["reason"] = reason
        slot["resolved"] = True

        if decision == "granted":
            await self._emit(EventType.PLAN_APPROVAL_GRANTED, corr_id, slot["from_agent"], reason)
        elif decision == "denied":
            await self._emit(EventType.PLAN_APPROVAL_DENIED, corr_id, slot["from_agent"], reason)
        elif decision == "timeout":
            await self._emit(EventType.PLAN_APPROVAL_TIMED_OUT, corr_id, slot["from_agent"], reason)

        evt = self._events.get(corr_id)
        if evt is not None:
            evt.set()

    async def wait(
        self, corr_id: str
    ) -> tuple[str, str | None]:
        slot = self._slots.get(corr_id)
        if slot is None:
            return ("timeout", "unknown_correlation_id")

        timeout = slot["timeout"]

        try:
            with anyio.move_on_after(timeout) as scope:
                await self._events[corr_id].wait()

            if scope.cancel_called:
                if not slot["resolved"]:
                    await self.resolve(corr_id, "timeout", reason="timeout expired")
                return ("timeout", slot.get("reason"))
        except anyio.get_cancelled_exc_class():
            raise

        if slot["resolved"]:
            return (slot["decision"], slot.get("reason"))
        return ("timeout", slot.get("reason"))

    async def _emit(
        self,
        event_type: EventType,
        corr_id: str,
        agent: str | None = None,
        reason: str | None = None,
    ) -> None:
        if self._sink is None:
            return
        from datetime import datetime, timezone
        from miniautogen.core.contracts.events import ExecutionEvent

        event = ExecutionEvent(
            type=event_type.value,
            timestamp=datetime.now(timezone.utc),
            run_id=self._team_run_id or "",
            correlation_id=corr_id,
            scope="team_plan_approval",
            payload={
                "agent": agent,
                "reason": reason,
                "team_run_id": self._team_run_id or "",
            },
        )
        await self._sink.publish(event)
