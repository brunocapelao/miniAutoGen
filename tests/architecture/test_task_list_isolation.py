"""Architectural test: team_task_list and team_task_tools must NOT import adapters.

Verifies the import boundary:
- Permitted: stdlib, anyio, pydantic, miniautogen.core.contracts.*, miniautogen.core.events.*
- Forbidden: miniautogen.adapters.*, sqlalchemy, redis, litellm, etc.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

MODULES_TO_CHECK = [
    Path("miniautogen/core/runtime/team_task_list.py"),
    Path("miniautogen/core/runtime/team_task_tools.py"),
]

ALLOWED_IMPORTS: set[str] = {
    "anyio",
    "datetime",
    "uuid",
    "typing",
    "collections",
    "pydantic",
    "miniautogen.core.contracts",
    "miniautogen.core.events",
    "miniautogen.observability",
    "miniautogen.core.runtime.tool_registry",
    "miniautogen.core.runtime.composite_tool_registry",
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


def _check_import(module_name: str) -> None:
    if module_name.startswith("."):
        return
    for prefix in FORBIDDEN_PREFIXES:
        if module_name.startswith(prefix) or module_name == prefix:
            msg = (
                f"FORBIDDEN import '{module_name}' in team_task_list.py. "
                f"Must not import from {prefix}."
            )
            raise AssertionError(msg)


def test_task_list_module_exists() -> None:
    assert MODULES_TO_CHECK[0].is_file()


def test_task_tools_module_exists() -> None:
    assert MODULES_TO_CHECK[1].is_file()


@pytest.mark.parametrize("module_path", MODULES_TO_CHECK, ids=lambda p: p.name)
def test_import_boundary(module_path: Path) -> None:
    if not module_path.is_file():
        pytest.skip(f"{module_path} not yet implemented")
    source = module_path.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_import(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            _check_import(node.module)
