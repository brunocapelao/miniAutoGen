#!/usr/bin/env python3
"""Standalone architectural linter for miniAutoGen.

Enforces the 4 architectural invariants via AST analysis:
  1. Adapter isolation   – core/ must not import adapters/backends/LLM libs
  2. Runner exclusivity  – no parallel executors outside core/runtime/
  3. AnyIO compliance    – core/ must not use blocking concurrency primitives
  4. Event emission      – runtime classes with run/execute must emit events

Uses only stdlib (ast, pathlib, sys). Works without installing miniautogen.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "miniautogen"
CORE = SRC / "core"
RUNTIME = CORE / "runtime"

# Modules that must never appear in core/ imports
FORBIDDEN_ADAPTER_MODULES = {
    "miniautogen.adapters",
    "miniautogen.backends",
    "litellm",
    "openai",
    "google.generativeai",
    "anthropic",
    "gemini",
}

# Modules / symbols that violate anyio-only concurrency in core/
FORBIDDEN_SYNC_MODULES = {"threading", "multiprocessing", "concurrent.futures"}
FORBIDDEN_ASYNCIO_ATTRS = {
    "asyncio.run",
    "asyncio.get_event_loop",
    "loop.run_until_complete",
}

# Event-related identifiers that signal proper emission
EVENT_MARKERS = {"ExecutionEvent", "emit", "publish", "send_event"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def py_files(directory: Path) -> list[Path]:
    """Return sorted .py files under *directory*, recursively."""
    if not directory.is_dir():
        return []
    return sorted(directory.rglob("*.py"))


def parse_file(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return None


def rel(path: Path) -> str:
    """Return path relative to project root for display."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _import_module_name(node: ast.Import | ast.ImportFrom) -> list[str]:
    """Extract all top-level module strings from an import node."""
    names: list[str] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            names.append(alias.name)
    elif isinstance(node, ast.ImportFrom) and node.module:
        names.append(node.module)
    return names


# ---------------------------------------------------------------------------
# Check 1: Adapter Isolation
# ---------------------------------------------------------------------------


def check_adapter_isolation() -> list[str]:
    """Core/ must not import from adapters, backends, or external LLM libs."""
    violations: list[str] = []
    for path in py_files(CORE):
        tree = parse_file(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for mod in _import_module_name(node):
                    for forbidden in FORBIDDEN_ADAPTER_MODULES:
                        if mod == forbidden or mod.startswith(forbidden + "."):
                            violations.append(
                                f"  {rel(path)}:{node.lineno} imports {mod}"
                            )
    return violations


# ---------------------------------------------------------------------------
# Check 2: Runner Exclusivity
# ---------------------------------------------------------------------------


def _method_has_infinite_loop(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True if the method body contains ``while True`` or ``while not ...``."""
    for node in ast.walk(func_node):
        if isinstance(node, ast.While):
            test = node.test
            # while True
            if isinstance(test, ast.Constant) and test.value is True:
                return True
            # while not <expr>
            if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                return True
    return False


def _method_references_runtime_types(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True if the method body references RunContext or RunResult."""
    for node in ast.walk(func_node):
        if isinstance(node, ast.Name) and node.id in ("RunContext", "RunResult"):
            return True
        if isinstance(node, ast.Attribute) and node.attr in ("RunContext", "RunResult"):
            return True
    return False


def check_runner_exclusivity() -> list[str]:
    """No class outside core/runtime/ should act as a parallel executor."""
    violations: list[str] = []
    runtime_prefix = RUNTIME.resolve()

    for path in py_files(SRC):
        # Skip files inside core/runtime/
        if path.resolve().is_relative_to(runtime_prefix):
            continue
        tree = parse_file(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name not in ("run", "execute"):
                            continue
                        if _method_has_infinite_loop(item) and _method_references_runtime_types(item):
                            violations.append(
                                f"  {rel(path)}:{item.lineno} "
                                f"class {node.name}.{item.name}() looks like a parallel executor"
                            )
    return violations


# ---------------------------------------------------------------------------
# Check 3: AnyIO Compliance
# ---------------------------------------------------------------------------


def check_anyio_compliance() -> list[str]:
    """Core/ must not import blocking concurrency primitives."""
    violations: list[str] = []
    for path in py_files(CORE):
        tree = parse_file(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            # Check direct module imports: import threading, etc.
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for mod in _import_module_name(node):
                    if mod in FORBIDDEN_SYNC_MODULES or any(
                        mod.startswith(f + ".") for f in FORBIDDEN_SYNC_MODULES
                    ):
                        violations.append(
                            f"  {rel(path)}:{node.lineno} imports {mod}"
                        )

            # Check attribute access: asyncio.run, asyncio.get_event_loop, etc.
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    full = f"{node.value.id}.{node.attr}"
                    if full in FORBIDDEN_ASYNCIO_ATTRS:
                        violations.append(
                            f"  {rel(path)}:{node.lineno} uses {full}"
                        )
                # loop.run_until_complete (where 'loop' is any name)
                if node.attr == "run_until_complete":
                    violations.append(
                        f"  {rel(path)}:{node.lineno} uses .run_until_complete()"
                    )

            # Check from-imports: from asyncio import run, get_event_loop
            if isinstance(node, ast.ImportFrom) and node.module == "asyncio":
                for alias in node.names:
                    if alias.name in ("run", "get_event_loop"):
                        violations.append(
                            f"  {rel(path)}:{node.lineno} imports asyncio.{alias.name}"
                        )
    return violations


# ---------------------------------------------------------------------------
# Check 4: Event Emission
# ---------------------------------------------------------------------------


def _class_has_event_references(cls_node: ast.ClassDef) -> bool:
    """Return True if the class body references event-related identifiers."""
    for node in ast.walk(cls_node):
        if isinstance(node, ast.Name) and node.id in EVENT_MARKERS:
            return True
        if isinstance(node, ast.Attribute) and node.attr in EVENT_MARKERS:
            return True
    return False


def _class_has_run_or_execute(cls_node: ast.ClassDef) -> list[str]:
    """Return names of run/execute methods defined on the class."""
    methods: list[str] = []
    for item in cls_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name in ("run", "execute"):
                methods.append(item.name)
    return methods


def check_event_emission() -> list[str]:
    """Runtime classes with run/execute must reference event emission."""
    violations: list[str] = []
    for path in py_files(RUNTIME):
        tree = parse_file(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = _class_has_run_or_execute(node)
                if methods and not _class_has_event_references(node):
                    violations.append(
                        f"  {rel(path)}:{node.lineno} "
                        f"class {node.name} has {'/'.join(methods)}() but no event emission"
                    )
    return violations


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    results: list[tuple[str, str, list[str]]] = []

    # Warn about missing directories
    if not CORE.is_dir():
        print(f"[WARN] {rel(CORE)} does not exist — skipping all checks")
        return 0
    if not RUNTIME.is_dir():
        print(f"[WARN] {rel(RUNTIME)} does not exist — skipping runtime checks")

    checks = [
        ("adapter_isolation", "core/ has no adapter imports", check_adapter_isolation),
        ("runner_exclusivity", "no parallel executors found", check_runner_exclusivity),
        ("anyio_compliance", "core/ uses only AnyIO for concurrency", check_anyio_compliance),
        ("event_emission", "all runtime classes emit events", check_event_emission),
    ]

    failed = 0
    passed = 0

    for name, ok_msg, fn in checks:
        violations = fn()
        if violations:
            failed += 1
            print(f"[FAIL] {name}:")
            for v in violations:
                print(v)
        else:
            passed += 1
            print(f"[PASS] {name}: {ok_msg}")

    print()
    print(f"Result: {failed} FAILED, {passed} PASSED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
