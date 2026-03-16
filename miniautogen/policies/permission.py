from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionPolicy:
    """Policy for action permissions.

    By default, if no ``allowed_actions`` are configured and ``allow_all``
    is False, all actions are **denied**. Set ``allow_all=True`` for
    an explicit permissive policy, or configure specific ``allowed_actions``.
    """

    allowed_actions: tuple[str, ...] = ()
    allow_all: bool = False


class PermissionDeniedError(Exception):
    """Raised when an action is not permitted."""


def check_permission(policy: PermissionPolicy, action: str) -> None:
    """Check if action is allowed. Raises PermissionDeniedError if not."""
    if policy.allow_all:
        return
    if action not in policy.allowed_actions:
        raise PermissionDeniedError(
            f"Action '{action}' not permitted. Allowed: {policy.allowed_actions}"
        )
