"""Root conftest.py -- shared test fixtures and helpers."""

from __future__ import annotations

from typing import Any

from deepdiff import DeepDiff


def assert_no_mutation(
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
    label: str = "",
    ignore_order: bool = False,
) -> None:
    """Assert that two snapshots are structurally identical.

    Uses DeepDiff for deep comparison. Raises AssertionError with
    a detailed diff message if any mutation is detected.

    Args:
        before_snapshot: State captured before the operation.
        after_snapshot: State captured after the operation.
        label: Optional label for the error message.
        ignore_order: Whether to ignore list ordering during comparison.
            Defaults to False (order matters) for strict mutation detection.
    """
    diff = DeepDiff(before_snapshot, after_snapshot, ignore_order=ignore_order)
    assert diff == {}, f"Immutability violation{' in ' + label if label else ''}: {diff}"
