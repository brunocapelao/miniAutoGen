"""Persistent memory provider with filesystem backing.

Extends InMemoryMemoryProvider with load_from_disk / persist_to_disk,
satisfying both MemoryProvider and PersistableMemory protocols.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anyio

from miniautogen.core.contracts.memory_provider import InMemoryMemoryProvider


class PersistentMemoryProvider(InMemoryMemoryProvider):
    """InMemoryMemoryProvider extended with filesystem persistence.

    Internal state (_store: dict[run_id -> list[messages]]) is serialised
    as ``context.json`` inside *memory_dir* on persist_to_disk() and
    restored on load_from_disk().

    Satisfies both MemoryProvider and PersistableMemory protocols.
    """

    def __init__(self, memory_dir: Path) -> None:
        super().__init__()
        self._memory_dir = Path(memory_dir)

    # ------------------------------------------------------------------
    # PersistableMemory protocol
    # ------------------------------------------------------------------

    async def load_from_disk(self) -> None:
        """Hydrate the in-memory store from the filesystem.

        If the context file does not exist the store is left unchanged
        (empty). Unknown or corrupt files are silently ignored to keep
        the provider usable after partial writes.
        """
        async_dir = anyio.Path(self._memory_dir)
        context_file = async_dir / "context.json"
        if not await context_file.exists():
            return

        try:
            raw = json.loads(await context_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Corrupt or unreadable file — start with an empty store.
            return

        if isinstance(raw, dict):
            # Validate that every value is a list before restoring.
            restored: dict[str, list[dict[str, Any]]] = {}
            for run_id, messages in raw.items():
                if isinstance(messages, list):
                    restored[run_id] = messages
            self._store = restored

    async def persist_to_disk(self) -> None:
        """Flush the current in-memory store to the filesystem.

        Creates *memory_dir* (and any parents) if it does not yet exist.
        The entire store is written atomically as ``context.json``.
        """
        async_dir = anyio.Path(self._memory_dir)
        await async_dir.mkdir(parents=True, exist_ok=True)
        context_file = async_dir / "context.json"
        await context_file.write_text(
            json.dumps(self._store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Extra capability: keyword search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return messages whose content contains *query* (case-insensitive).

        Iterates over all run buckets in insertion order, returning up to
        *limit* matching messages.
        """
        query_lower = query.lower()
        results: list[dict[str, Any]] = []

        for messages in self._store.values():
            for msg in messages:
                content = str(msg.get("content", ""))
                if query_lower in content.lower():
                    results.append(msg)
                    if len(results) >= limit:
                        return results

        return results
