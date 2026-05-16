"""Tests for TimeoutPolicy — Spec 013."""

from __future__ import annotations

import anyio
import pytest

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.policies.timeout_policy import TimeoutPolicy

pytestmark = pytest.mark.anyio


class TestTimeoutPolicy:
    async def test_timeout_emits_event_and_continues(self) -> None:
        """Timeout emits agent_turn_timed_out and suppresses exception."""
        events: list[ExecutionEvent] = []

        async def emit(event_type: str, **payload: object) -> None:
            events.append(ExecutionEvent(type=event_type, payload=payload))

        policy = TimeoutPolicy(
            agent_timeouts={"agent_a": 0.1},
            round_timeouts={},
            flow_timeout=None,
            engine_timeout=120.0,
            on_timeout_action="continue",
        )

        async def turn_slow() -> None:
            await anyio.sleep(2.0)

        async with policy.scope_for_turn(
            agent_id="agent_a",
            round_name="contribute",
            emit=emit,
        ) as resolved:
            with anyio.move_on_after(2.0):
                await turn_slow()

        assert len(events) >= 1
        timed_out = [e for e in events if e.type == "agent_turn_timed_out"]
        assert len(timed_out) == 1
        assert timed_out[0].get_payload("agent_id") == "agent_a"
        assert timed_out[0].get_payload("source") == "agent"

    async def test_abort_action_propagates_timeout_error(self) -> None:
        """on_timeout_action='abort' re-raises TimeoutError."""
        events: list[ExecutionEvent] = []

        async def emit(event_type: str, **payload: object) -> None:
            events.append(ExecutionEvent(type=event_type, payload=payload))

        policy = TimeoutPolicy(
            agent_timeouts={"agent_a": 0.1},
            round_timeouts={},
            flow_timeout=None,
            engine_timeout=120.0,
            on_timeout_action="abort",
        )

        with pytest.raises(TimeoutError):
            async with policy.scope_for_turn(
                agent_id="agent_a",
                round_name="contribute",
                emit=emit,
            ):
                await anyio.sleep(2.0)

        assert len(events) >= 1
        timed_out = [e for e in events if e.type == "agent_turn_timed_out"]
        assert len(timed_out) == 1

    async def test_outer_fail_after_cancels_before_agent_timeout(self) -> None:
        """Outer flow-level fail_after cancels before the policy's agent
        timeout fires — simulates runner-level nesting (flow < agent)."""
        events: list[str] = []

        async def emit(event_type: str, **payload: object) -> None:
            events.append(event_type)

        policy = TimeoutPolicy(
            agent_timeouts={"agent_a": 10.0},
            round_timeouts={},
            flow_timeout=10.0,
            engine_timeout=120.0,
            on_timeout_action="continue",
        )

        with pytest.raises(TimeoutError):
            with anyio.fail_after(0.05):
                async with policy.scope_for_turn(
                    agent_id="agent_a",
                    round_name="contribute",
                    emit=emit,
                ):
                    await anyio.sleep(5.0)

        assert "agent_turn_timed_out" not in events

    async def test_emits_payload_with_source_agent(self) -> None:
        """Event payload includes source='agent' when agent timeout fires."""
        events: list[ExecutionEvent] = []

        async def emit(event_type: str, **payload: object) -> None:
            events.append(ExecutionEvent(type=event_type, payload=payload))

        policy = TimeoutPolicy(
            agent_timeouts={"agent_a": 0.1},
            round_timeouts={},
            flow_timeout=None,
            engine_timeout=120.0,
            on_timeout_action="continue",
        )

        async with policy.scope_for_turn(
            agent_id="agent_a",
            round_name="contribute",
            emit=emit,
        ):
            await anyio.sleep(1.0)

        timed_out = [e for e in events if e.type == "agent_turn_timed_out"]
        assert len(timed_out) == 1
        payload = timed_out[0]
        assert payload.get_payload("source") == "agent"
        assert payload.get_payload("agent_id") == "agent_a"
        assert payload.get_payload("round_name") == "contribute"
        assert payload.get_payload("applied_timeout") == 0.1
