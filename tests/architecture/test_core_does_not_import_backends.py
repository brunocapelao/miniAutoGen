from __future__ import annotations

import ast
from pathlib import Path

_CORE_DIR = Path(__file__).parent.parent.parent / "miniautogen" / "core"

_FORBIDDEN_IMPORTS = (
    "miniautogen.backends",
)

_ALLOWED_IMPORTS = (
    "miniautogen.backends.engine_resolver",  # pre-existing, to fix in Sprint 2
    "miniautogen.backends.models",
)


def _collect_imports(filepath: Path) -> list[str]:
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


def test_core_does_not_import_backends() -> None:
    violations: list[str] = []
    for py_file in sorted(_CORE_DIR.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        imports = _collect_imports(py_file)
        for imp in imports:
            if not imp.startswith("miniautogen"):
                continue
            if any(imp.startswith(a) for a in _ALLOWED_IMPORTS):
                continue
            if any(imp.startswith(f) for f in _FORBIDDEN_IMPORTS):
                rel = py_file.relative_to(_CORE_DIR)
                violations.append(f"{rel}: imports {imp}")
    assert not violations, (
        "Core code imports from backends/ (invariant violation):\n"
        + "\n".join(f"  - {v}" for v in violations)
    )
