# AgentDriverProtocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate architectural violation P0.1 — core/runtime/ imports AgentDriver from backends/driver.py. Create AgentDriverProtocol in core/contracts/, refactor the runtime to depend on the Protocol, and add an architecture test to prevent regression.

**Architecture:** Create a `@runtime_checkable` Protocol in `core/contracts/agent_driver.py` mirroring the 6-method AgentDriver ABC. Make AgentDriver inherit from both ABC and the Protocol (zero changes to concrete drivers). Change agent_runtime.py to import and type-annotate with the Protocol. Add AST-scan architecture test gating backends imports in core.

**Tech Stack:** Python 3.11, typing.Protocol, ABC, AST (test), pytest, mypy, ruff

---

### Task 1: Create AgentDriverProtocol

**Files:**
- Create: `miniautogen/core/contracts/agent_driver.py`
- Modify: `miniautogen/core/contracts/__init__.py:52,108` (add to `__all__`)

- [ ] **Step 1: Create the Protocol file**

`miniautogen/core/contracts/agent_driver.py`:

```python
from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)


@runtime_checkable
class AgentDriverProtocol(Protocol):
    """Structural protocol for backend drivers.

    Mirrors AgentDriver ABC exactly. Any object with these methods
    satisfies this protocol via duck typing.
    """

    async def start_session(
        self,
        request: StartSessionRequest,
    ) -> StartSessionResponse:
        ...

    def send_turn(
        self,
        request: SendTurnRequest,
    ) -> AsyncIterator[AgentEvent]:
        ...

    async def cancel_turn(
        self,
        request: CancelTurnRequest,
    ) -> None:
        ...

    async def list_artifacts(
        self,
        session_id: str,
    ) -> list[ArtifactRef]:
        ...

    async def close_session(
        self,
        session_id: str,
    ) -> None:
        ...

    async def capabilities(
        self,
    ) -> BackendCapabilities:
        ...
```

- [ ] **Step 2: Register in contracts __init__.py**

Add import and `__all__` entry to `miniautogen/core/contracts/__init__.py`:

After line `from .store import StoreProtocol` (line 48), add:
```python
from .agent_driver import AgentDriverProtocol
```

In `__all__` after `"AgentHook"` (line 54), add:
```python
    "AgentDriverProtocol",
```

- [ ] **Step 3: Run ruff to verify formatting**

```bash
uv run ruff check miniautogen/core/contracts/agent_driver.py
```
Expected: no errors.

- [ ] **Step 4: Run mypy to verify type validity**

```bash
uv run mypy miniautogen/core/contracts/agent_driver.py
```
Expected: Success, no issues.

- [ ] **Step 5: Commit**

```bash
git add miniautogen/core/contracts/agent_driver.py miniautogen/core/contracts/__init__.py
git commit -m "feat(contracts): add AgentDriverProtocol to core/contracts/"
```

---

### Task 2: Make AgentDriver implement the Protocol

**Files:**
- Modify: `miniautogen/backends/driver.py:10-24`

- [ ] **Step 1: Add import and inherit AgentDriverProtocol**

In `miniautogen/backends/driver.py`:

After line 11 (`from typing import AsyncIterator`), add:
```python
from miniautogen.core.contracts.agent_driver import AgentDriverProtocol
```

Change line 24 from:
```python
class AgentDriver(ABC):
```
to:
```python
class AgentDriver(ABC, AgentDriverProtocol):
```

- [ ] **Step 2: Run ruff**

```bash
uv run ruff check miniautogen/backends/driver.py
```
Expected: no errors.

- [ ] **Step 3: Run mypy**

```bash
uv run mypy miniautogen/backends/driver.py
```
Expected: Success.

- [ ] **Step 4: Run isinstance verification**

```bash
uv run python -c "
from miniautogen.backends.driver import AgentDriver
from miniautogen.core.contracts.agent_driver import AgentDriverProtocol
print(isinstance(AgentDriver, type))  # True — it's a class
print(issubclass(AgentDriver, AgentDriverProtocol))  # True
"
```
Expected: both prints `True`.

- [ ] **Step 5: Commit**

```bash
git add miniautogen/backends/driver.py
git commit -m "refactor(backends): make AgentDriver implement AgentDriverProtocol"
```

---

### Task 3: Update AgentRuntime to use the Protocol

**Files:**
- Modify: `miniautogen/core/runtime/agent_runtime.py:27,71`

- [ ] **Step 1: Change import**

In `miniautogen/core/runtime/agent_runtime.py:27`:

Before:
```python
from miniautogen.backends.driver import AgentDriver
```

After:
```python
from miniautogen.core.contracts.agent_driver import AgentDriverProtocol
```

- [ ] **Step 2: Change type annotation**

In `miniautogen/core/runtime/agent_runtime.py:71`:

Before:
```python
        driver: AgentDriver,
```

After:
```python
        driver: AgentDriverProtocol,
```

- [ ] **Step 3: Run mypy on agent_runtime.py**

```bash
uv run mypy miniautogen/core/runtime/agent_runtime.py
```
Expected: Success, no issues (the Protocol has same methods as ABC so all internal usage remains valid).

- [ ] **Step 4: Run ruff**

```bash
uv run ruff check miniautogen/core/runtime/agent_runtime.py
```
Expected: no errors.

- [ ] **Step 5: Run core tests to verify no regressions**

```bash
uv run pytest tests/core/ -x --tb=short -q
```
Expected: all passing.

- [ ] **Step 6: Commit**

```bash
git add miniautogen/core/runtime/agent_runtime.py
git commit -m "refactor(runtime): use AgentDriverProtocol instead of concrete AgentDriver"
```

---

### Task 4: Add architecture regression test

**Files:**
- Create: `tests/architecture/`
- Create: `tests/architecture/test_core_does_not_import_backends.py`

- [ ] **Step 1: Create the test directory**

```bash
mkdir -p tests/architecture
```

- [ ] **Step 2: Write the test**

`tests/architecture/test_core_does_not_import_backends.py`:

```python
from __future__ import annotations

import ast
from pathlib import Path

_CORE_DIR = Path(__file__).parent.parent.parent / "miniautogen" / "core"

_FORBIDDEN_IMPORTS = (
    "miniautogen.backends",
)

_ALLOWED_IMPORTS = (
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
```

- [ ] **Step 3: Run the new test to verify it passes**

```bash
uv run pytest tests/architecture/test_core_does_not_import_backends.py -v
```
Expected: PASS (no violations — the only backends import in core is `backends.models` from `agent_driver.py`, which is in `_ALLOWED_IMPORTS`).

- [ ] **Step 4: Commit**

```bash
git add tests/architecture/test_core_does_not_import_backends.py
git commit -m "test(architecture): add gate for backends imports in core"
```

---

### Task 5: Full validation — run entire test suite

- [ ] **Step 1: Run ruff on the entire project**

```bash
uv run ruff check miniautogen/ tests/
```
Expected: no errors.

- [ ] **Step 2: Run mypy on core and backends**

```bash
uv run mypy miniautogen/core/ miniautogen/backends/
```
Expected: Success.

- [ ] **Step 3: Run the full test suite**

```bash
uv run pytest -x --tb=short -q
```
Expected: all tests passing (except pre-existing failures unrelated to this change, e.g. TUI collection errors).

- [ ] **Step 4: Verify import boundary test still passes**

```bash
uv run pytest tests/cli/test_import_boundary.py -v
```
Expected: PASS (CLI import violations are a separate concern — this test checks CLI, not core. Verify it was not affected.)

- [ ] **Step 5: Final commit if any fixes needed**

```bash
git add -A
git commit -m "chore: final validation pass for AgentDriverProtocol"
```
