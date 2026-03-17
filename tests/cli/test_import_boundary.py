"""Architectural test: CLI must not import internal SDK modules.

Enforces D3 — the CLI dogfooding constraint. All SDK interaction
must go through miniautogen.api.
"""

from __future__ import annotations

import ast
from pathlib import Path

_CLI_DIR = Path(__file__).parent.parent.parent / "miniautogen" / "cli"

# These prefixes are FORBIDDEN in CLI imports
_FORBIDDEN_PREFIXES = (
    "miniautogen.core",
    "miniautogen.stores",
    "miniautogen.backends",
    "miniautogen.policies",
    "miniautogen.adapters",
    "miniautogen.pipeline",
    "miniautogen.compat",
    "miniautogen.observability",
    "miniautogen.app",
    "miniautogen.chat",
)

# These are ALLOWED
_ALLOWED_PREFIXES = (
    "miniautogen.api",
    "miniautogen.cli",
)


def _collect_imports(filepath: Path) -> list[str]:
    """Extract all import module names from a Python file."""
    source = filepath.read_text()
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def test_cli_does_not_import_internal_modules() -> None:
    """Scan all .py files in miniautogen/cli/ for forbidden imports."""
    violations: list[str] = []

    for py_file in _CLI_DIR.rglob("*.py"):
        # Skip __pycache__
        if "__pycache__" in str(py_file):
            continue

        imports = _collect_imports(py_file)
        for imp in imports:
            if not imp.startswith("miniautogen"):
                continue
            if any(imp.startswith(p) for p in _ALLOWED_PREFIXES):
                continue
            # Deny by default — any other miniautogen.* import is forbidden
            rel = py_file.relative_to(_CLI_DIR)
            violations.append(f"{rel}: imports {imp}")

    assert not violations, (
        "CLI code imports internal SDK modules (D3 violation):\n"
        + "\n".join(f"  - {v}" for v in violations)
    )
