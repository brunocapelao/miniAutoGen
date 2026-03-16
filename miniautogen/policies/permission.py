from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionPolicy:
    """Policy for action permissions."""

    allowed_actions: tuple[str, ...] = ()


class PermissionDeniedError(Exception):
    """Raised when an action is not permitted."""


def check_permission(policy: PermissionPolicy, action: str) -> None:
    """Check if action is allowed. Raises PermissionDeniedError if not.

    If allowed_actions is empty, all actions are permitted (permissive default).
    """
    if not policy.allowed_actions:
        return  # Empty = all allowed
    if action not in policy.allowed_actions:
        raise PermissionDeniedError(
            f"Action '{action}' not permitted. Allowed: {policy.allowed_actions}"
        )
