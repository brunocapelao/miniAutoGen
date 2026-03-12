from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionPolicy:
    allowed_actions: tuple[str, ...] = ()
