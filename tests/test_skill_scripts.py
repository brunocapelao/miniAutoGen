"""Tests for local skill helper scripts."""

from __future__ import annotations

from pathlib import Path


def test_find_polluter_script_uses_pytest_runner() -> None:
    script = Path(".agents/skills/systematic-debugging/find-polluter.sh").read_text()

    assert 'uv run pytest "$TEST_FILE"' in script
    assert "npm test" not in script
