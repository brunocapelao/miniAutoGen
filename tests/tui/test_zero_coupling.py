"""Verify that miniautogen.tui has zero coupling to core internals.

The TUI package must ONLY import:
- miniautogen.core.contracts.events (ExecutionEvent model)
- miniautogen.core.events.types (EventType enum)
- miniautogen.core.events.event_sink (EventSink protocol -- for isinstance checks only)
- miniautogen.policies.approval (ApprovalRequest/ApprovalResponse models)

It must NOT import:
- miniautogen.core.runtime (PipelineRunner, runtimes)
- miniautogen.stores (any store)
- miniautogen.adapters (any adapter)
- miniautogen.pipeline (any pipeline)
- miniautogen.agent (any agent)
- miniautogen.backends (any backend)
"""

from __future__ import annotations

import ast
from pathlib import Path

_TUI_ROOT = Path(__file__).resolve().parent.parent.parent / "miniautogen" / "tui"

_ALLOWED_CORE_IMPORTS = {
    "miniautogen.core.contracts.events",
    "miniautogen.core.events.types",
    "miniautogen.core.events.event_sink",
    "miniautogen.policies.approval",
}

_FORBIDDEN_PREFIXES = [
    "miniautogen.core.runtime",
    "miniautogen.stores",
    "miniautogen.adapters",
    "miniautogen.pipeline",
    "miniautogen.backends",
    "miniautogen.agent",
]


def _get_imports_from_file(path: Path) -> set[str]:
    """Extract all import module paths from a Python file using AST."""
    source = path.read_text()
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def test_tui_files_do_not_import_forbidden_modules() -> None:
    """No TUI module should import from forbidden core internals."""
    violations: list[str] = []

    for py_file in _TUI_ROOT.rglob("*.py"):
        if py_file.name == "__pycache__":
            continue
        imports = _get_imports_from_file(py_file)
        for imp in imports:
            for prefix in _FORBIDDEN_PREFIXES:
                if imp.startswith(prefix):
                    violations.append(
                        f"{py_file.name}: imports {imp} (forbidden: {prefix})"
                    )

    assert violations == [], (
        "TUI package has forbidden imports:\n" + "\n".join(violations)
    )


def test_tui_root_exists() -> None:
    """Sanity check: the TUI root directory exists."""
    assert _TUI_ROOT.is_dir(), f"TUI root not found: {_TUI_ROOT}"


def test_tui_has_python_files() -> None:
    """Sanity check: the TUI package has Python files to scan."""
    py_files = list(_TUI_ROOT.rglob("*.py"))
    assert len(py_files) > 0, "No Python files found in TUI package"


def test_allowed_imports_are_permitted() -> None:
    """Verify that allowed imports are not flagged as forbidden."""
    for allowed in _ALLOWED_CORE_IMPORTS:
        for prefix in _FORBIDDEN_PREFIXES:
            assert not allowed.startswith(prefix), (
                f"Allowed import {allowed} matches forbidden prefix {prefix}"
            )
