"""Unifying store protocol for the MiniAutoGen SDK.

Provides a minimal structural protocol for new key-value stores.
Existing stores (RunStore, CheckpointStore) use different method
names (save_run/get_run) and require adapters or migration to
satisfy this protocol.

Implementations SHOULD validate keys (alphanumeric + hyphens/
underscores, max 256 chars) and enforce payload size limits.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StoreProtocol(Protocol):
    """Structural protocol for key-value stores.

    Any object with async save, get, exists, and delete methods
    satisfies this protocol via duck typing.
    """

    async def save(self, key: str, payload: dict[str, Any]) -> None: ...

    async def get(self, key: str) -> dict[str, Any] | None: ...

    async def exists(self, key: str) -> bool: ...

    async def delete(self, key: str) -> bool: ...
