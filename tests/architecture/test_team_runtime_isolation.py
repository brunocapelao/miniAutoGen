"""Architectural test: TeamRuntime must NOT import adapters or SDKs.

Verifies the import boundary of team_runtime.py:
- Permitted: stdlib, anyio, miniautogen.core.contracts.*, miniautogen.core.events.*, observability
- Forbidden: miniautogen.adapters.*, litellm, openai, google.generativeai, etc.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

TEAM_RUNTIME_PATH = Path("miniautogen/core/runtime/team_runtime.py")

ALLOWED_IMPORTS: set[str] = {
    "anyio",
    "datetime",
    "uuid",
    "typing",
    "pydantic",
    "miniautogen.core.contracts",
    "miniautogen.core.events",
    "miniautogen.observability",
    "miniautogen.policies.timeout_policy",
    "miniautogen.core.runtime.pipeline_runner",
    "miniautogen.core.runtime.classifier",
}

FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "miniautogen.adapters",
    "miniautogen.backends",
    "miniautogen.cli",
    "miniautogen.schemas",
    "litellm",
    "openai",
    "google",
    "jinja2",
    "langchain",
    "sqlalchemy",
    "redis",
)


def test_team_runtime_module_exists() -> None:
    """The module must exist — this test fails first (RED)."""
    assert TEAM_RUNTIME_PATH.is_file(), (
        f"{TEAM_RUNTIME_PATH} not found — TeamRuntime not yet implemented"
    )


def test_team_runtime_import_boundary() -> None:
    """TeamRuntime must not import adapters or external SDKs."""
    if not TEAM_RUNTIME_PATH.is_file():
        pytest.skip("team_runtime.py not yet implemented")

    source = TEAM_RUNTIME_PATH.read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_import(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            _check_import(node.module)


def _check_import(module_name: str) -> None:
    """Assert a module import is in the allowed list."""
    # Relative imports are fine within the core package
    if module_name.startswith("."):
        return
    # Check that the import is not forbidden
    for prefix in FORBIDDEN_PREFIXES:
        if module_name.startswith(prefix) or module_name == prefix:
            msg = (
                f"FORBIDDEN import '{module_name}' in team_runtime.py. "
                f"TeamRuntime must not import from {prefix}."
            )
            raise AssertionError(msg)
