"""One-time migration utilities for serialized data format changes."""

from __future__ import annotations

from typing import Any


def migrate_run_context_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Transform a serialized v1 RunContext dict to v2 format.

    Handles:
    - execution_state (dict) -> state (dict, deserialized by FrozenState)
    - metadata (dict) -> metadata (list of [key, value] sorted pairs)

    Does not mutate the input dict.
    """
    migrated = dict(data)
    if "execution_state" in migrated:
        migrated["state"] = migrated.pop("execution_state")
    if isinstance(migrated.get("metadata"), dict):
        migrated["metadata"] = sorted(migrated["metadata"].items())
    return migrated
