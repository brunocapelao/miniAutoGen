from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ValidationPolicy:
    """Policy for input/output validation."""

    enabled: bool = True


class ValidationError(Exception):
    """Raised when validation fails."""


@runtime_checkable
class Validator(Protocol):
    """Protocol for validators that can check arbitrary data."""

    def validate(self, data: Any) -> None:
        """Validate data. Raise ValidationError if invalid."""
        ...


def validate_with_policy(
    policy: ValidationPolicy,
    validator: Validator,
    data: Any,
) -> None:
    """Apply validator if policy is enabled. Raises ValidationError on failure."""
    if not policy.enabled:
        return
    validator.validate(data)
