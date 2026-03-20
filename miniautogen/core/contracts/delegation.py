"""Delegation router protocol and persistable memory protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DelegationRouterProtocol(Protocol):
    """Controls which agents can delegate to which others.

    Implementations enforce topology constraints (e.g. max depth, allowed
    edges) and carry out the actual delegation by invoking the target agent.
    """

    def can_delegate(self, from_agent: str, to_agent: str) -> bool: ...

    async def delegate(
        self,
        from_agent: str,
        to_agent: str,
        input_data: Any,
        current_depth: int = 0,
    ) -> Any: ...


@runtime_checkable
class PersistableMemory(Protocol):
    """Protocol for memory providers that support filesystem persistence.

    Implementations of MemoryProvider that also satisfy this protocol gain
    the ability to checkpoint their state to disk and restore it across
    process restarts.
    """

    async def load_from_disk(self) -> None: ...

    async def persist_to_disk(self) -> None: ...
