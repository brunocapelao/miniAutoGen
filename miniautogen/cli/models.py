"""CLI validation models.

Reuses SDK contract models from miniautogen.api for YAML validation.
Adds CLI-specific helpers for project-level validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class CheckResult:
    """Result of a single validation check."""

    name: str
    passed: bool
    message: str
    category: Literal["static", "environment"]
    warning: bool = False
