"""InMemoryMailboxStore — per-team-run mailbox with per-agent streams.

One MemoryObjectStream per (team_run_id, agent). Backpressure via bounded buffer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, AsyncIterator

import anyio

from miniautogen.core.contracts.team_message import MailMessage
from miniautogen.core.events.types import EventType


class InMemoryMailboxStore:
    def __init__(
        self,
        *,
        agents: list[str],
        buffer_size: int = 256,
        event_sink: Any | None = None,
        team_run_id: str | None = None,
    ) -> None:
        self._team_run_id = team_run_id
        self._sink = event_sink
        self._streams: dict[str, Any] = {}
        self._buffer: dict[str, list[MailMessage]] = {agent: [] for agent in agents}
        self._buffer_locks: dict[str, Any] = {agent: anyio.Lock() for agent in agents}
        self._closed = False

        for agent in agents:
            send, recv = anyio.create_memory_object_stream[MailMessage](
                max_buffer_size=buffer_size
            )
            self._streams[agent] = (send, recv)

    async def send(self, message: MailMessage) -> None:
        send_stream = self._streams.get(message.to_agent)
        if send_stream is None:
            raise ValueError(f"Unknown recipient: {message.to_agent}")
        if self._closed:
            raise anyio.ClosedResourceError("Mailbox is closed")
        lock = self._buffer_locks[message.to_agent]
        async with lock:
            self._buffer[message.to_agent].append(message)
        await send_stream[0].send(message)
        await self._emit(EventType.MESSAGE_SENT, message)

    def receive_stream(self, agent: str) -> AsyncIterator[MailMessage]:
        streams = self._streams.get(agent)
        if streams is None:
            raise ValueError(f"Unknown agent: {agent}")

        async def _wrapped() -> AsyncIterator[MailMessage]:
            async for msg in streams[1]:
                lock = self._buffer_locks[agent]
                async with lock:
                    buf = self._buffer[agent]
                    if buf and buf[0].id == msg.id:
                        buf.pop(0)
                await self._emit(EventType.MESSAGE_DELIVERED, msg)
                yield msg

        return _wrapped()

    async def peek(self, agent: str) -> list[MailMessage]:
        lock = self._buffer_locks[agent]
        async with lock:
            return list(self._buffer.get(agent, []))

    async def pending_count(self, agent: str) -> int:
        lock = self._buffer_locks[agent]
        async with lock:
            return len(self._buffer.get(agent, []))

    async def aclose(self) -> None:
        self._closed = True
        for send_stream, recv_stream in self._streams.values():
            try:
                await send_stream.aclose()
            except anyio.ClosedResourceError:
                pass
            try:
                await recv_stream.aclose()
            except anyio.ClosedResourceError:
                pass
        self._buffer.clear()

    async def _emit(
        self, event_type: EventType, message: MailMessage
    ) -> None:
        if self._sink is None:
            return
        from miniautogen.core.contracts.events import ExecutionEvent

        event = ExecutionEvent(
            type=event_type.value,
            timestamp=datetime.now(timezone.utc),
            run_id=self._team_run_id or "",
            correlation_id=message.correlation_id or self._team_run_id or "",
            scope="team_mailbox",
            payload={
                "message_id": message.id,
                "from_agent": message.from_agent,
                "to_agent": message.to_agent,
                "kind": message.kind,
                "team_run_id": self._team_run_id or "",
            },
        )
        await self._sink.publish(event)
