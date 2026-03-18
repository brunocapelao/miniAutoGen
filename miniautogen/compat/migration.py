"""One-time migration utilities for serialized data format changes."""

from __future__ import annotations

from typing import Any


def migrate_run_context_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Transform a serialized v1 RunContext dict to v2 format.

    Handles:
    - execution_state (dict) -> state (dict, deserialized by FrozenState)
    - metadata (dict) -> metadata (list of [key, value] sorted pairs)

    Does not mutate the input dict.
    Raises ValueError if both 'state' and 'execution_state' are present.
    """
    migrated = dict(data)
    if "execution_state" in migrated:
        if "state" in migrated:
            raise ValueError(
                "Ambiguous migration: both 'state' and 'execution_state' present"
            )
        migrated["state"] = migrated.pop("execution_state")
    if isinstance(migrated.get("metadata"), dict):
        migrated["metadata"] = tuple(sorted(migrated["metadata"].items()))
    return migrated
