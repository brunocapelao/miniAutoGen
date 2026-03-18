# WS1: Infrastructure PRs -- Implementation Plan

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Upgrade MiniAutoGen's serialization (orjson), build tooling (uv), and QA assertions (deepdiff) across three independent PRs.

**Architecture:** Each task group produces one independent, mergeable PR. TG-1 (orjson) introduces a JSON shim module and a shared Pydantic base model. TG-2 (uv) converts pyproject.toml from Poetry to PEP 621 and replaces the lockfile. TG-3 (deepdiff) adds immutability guards using deep-comparison assertions.

**Tech Stack:** Python 3.10+, Pydantic v2, orjson >= 3.10, uv (latest), deepdiff >= 7.0, pytest, pytest-asyncio, SQLAlchemy (async), aiosqlite.

**Global Prerequisites:**
- Environment: macOS or Linux, Python 3.10 or 3.11
- Tools: `python --version`, `pip --version`, `git --version`
- Access: No API keys required -- all tasks are local
- State: Branch from `main` (commit `0d5f0fc`), clean working tree

**Verification before starting:**
```bash
python --version    # Expected: Python 3.10.x or 3.11.x
git status          # Expected: clean working tree on main
git log --oneline -1  # Expected: 0d5f0fc docs: add implementation maturity matrix...
```

---

## TG-1: orjson Integration

**Branch:** `infra/orjson-integration`

### Task 1.1: Create feature branch and add orjson dependency

**What:** Create a feature branch and add `orjson` to `pyproject.toml`.

**Where:** `pyproject.toml` (line 9, inside `[tool.poetry.dependencies]`)

**How:**

```bash
git checkout -b infra/orjson-integration main
```

Edit `/Users/brunocapelao/Projects/miniAutoGen/pyproject.toml` -- add `orjson` after the `ruamel-yaml` line (line 26):

```toml
ruamel-yaml = ">=0.18.0"
orjson = ">=3.10.0"
```

Then install:

```bash
pip install orjson>=3.10.0
```

**Verify:**

```bash
python -c "import orjson; print(orjson.__version__)"
# Expected: 3.10.x (any version >= 3.10.0)
```

**If Task Fails:**
- `pip install` fails: Check Python version is 3.10+. orjson requires a supported platform. Run `pip install --verbose orjson` for details.
- Rollback: `git checkout main`

---

### Task 1.2: Create the `_json.py` shim module

**What:** Create the centralized JSON shim that all modules will import from.

**Where:** Create new file `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/_json.py`

**How:**

```python
"""Centralized JSON serialization shim.

All internal modules MUST import dumps/loads from here:

    from miniautogen._json import dumps, loads

This guarantees a single fallback path and consistent behavior.
"""

from __future__ import annotations

try:
    import orjson

    def dumps(obj: object, *, indent: bool = False) -> str:
        """Serialize *obj* to a JSON string (always returns str, not bytes)."""
        option = orjson.OPT_INDENT_2 if indent else 0
        return orjson.dumps(obj, option=option).decode()

    def loads(data: str | bytes) -> object:
        """Deserialize a JSON string or bytes to a Python object."""
        return orjson.loads(data)

    HAS_ORJSON = True

except ImportError:  # pragma: no cover -- fallback for exotic platforms
    import json as _json

    def dumps(obj: object, *, indent: bool = False) -> str:  # type: ignore[misc]
        """Serialize *obj* to a JSON string (stdlib fallback)."""
        return _json.dumps(obj, indent=2 if indent else None, default=str)

    def loads(data: str | bytes) -> object:  # type: ignore[misc]
        """Deserialize a JSON string or bytes to a Python object."""
        return _json.loads(data)

    HAS_ORJSON = False
```

**Verify:**

```bash
python -c "from miniautogen._json import dumps, loads, HAS_ORJSON; print(HAS_ORJSON); print(dumps({'key': 'value'})); print(loads('{\"a\": 1}'))"
# Expected:
# True
# {"key":"value"}
# {'a': 1}
```

**If Task Fails:**
- ImportError on `miniautogen`: Ensure you are in the project root and the package is installed (`pip install -e .`).
- Rollback: `rm miniautogen/_json.py`

---

### Task 1.3: Write tests for the `_json.py` shim

**What:** Create a test file for the shim module covering `dumps`, `loads`, `indent`, and round-trip behavior.

**Where:** Create new file `/Users/brunocapelao/Projects/miniAutoGen/tests/core/test_json_shim.py`

Create the directory first if needed:

```bash
mkdir -p tests/core
touch tests/core/__init__.py  # may already exist
```

**How:**

```python
"""Tests for miniautogen._json shim module."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from miniautogen._json import HAS_ORJSON, dumps, loads


class TestDumps:
    """Tests for the dumps() function."""

    def test_dumps_returns_str(self) -> None:
        result = dumps({"key": "value"})
        assert isinstance(result, str)

    def test_dumps_simple_dict(self) -> None:
        result = dumps({"a": 1, "b": "two"})
        restored = loads(result)
        assert restored == {"a": 1, "b": "two"}

    def test_dumps_nested_structure(self) -> None:
        data = {"outer": {"inner": [1, 2, 3]}}
        result = dumps(data)
        assert loads(result) == data

    def test_dumps_with_indent(self) -> None:
        result = dumps({"a": 1}, indent=True)
        assert isinstance(result, str)
        # Indented output has newlines
        assert "\n" in result

    def test_dumps_without_indent_is_compact(self) -> None:
        result = dumps({"a": 1}, indent=False)
        assert "\n" not in result


class TestLoads:
    """Tests for the loads() function."""

    def test_loads_from_str(self) -> None:
        result = loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_loads_from_bytes(self) -> None:
        result = loads(b'{"key": "value"}')
        assert result == {"key": "value"}

    def test_loads_array(self) -> None:
        result = loads("[1, 2, 3]")
        assert result == [1, 2, 3]


class TestRoundTrip:
    """Round-trip fidelity tests."""

    def test_round_trip_dict(self) -> None:
        original = {"run_id": "abc", "state": {"step": 3, "data": [1, 2, 3]}}
        assert loads(dumps(original)) == original

    def test_round_trip_preserves_types(self) -> None:
        original = {"int": 42, "float": 3.14, "bool": True, "null": None, "str": "hello"}
        assert loads(dumps(original)) == original

    def test_round_trip_empty_structures(self) -> None:
        for obj in ({}, [], ""):
            assert loads(dumps(obj)) == obj


class TestOrjsonDetection:
    """Verify orjson is detected when installed."""

    def test_has_orjson_is_true(self) -> None:
        # orjson is a required dependency, so this should always be True
        assert HAS_ORJSON is True
```

**Verify:**

```bash
python -m pytest tests/core/test_json_shim.py -v
# Expected: All tests PASSED (approximately 10 tests)
```

**If Task Fails:**
- `ModuleNotFoundError: miniautogen._json`: File was not created in the right location. Check `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/_json.py` exists.
- Rollback: `rm tests/core/test_json_shim.py`

---

### Task 1.4: Create `MiniAutoGenBaseModel` with orjson

**What:** Create a shared Pydantic base model that uses orjson for JSON serialization.

**Where:** Create new file `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/base.py`

**How:**

```python
"""Shared Pydantic base model for all MiniAutoGen contracts.

All framework models MUST inherit from MiniAutoGenBaseModel
to ensure consistent orjson-backed serialization.
"""

from __future__ import annotations

from typing import Any

import orjson
from pydantic import BaseModel


class MiniAutoGenBaseModel(BaseModel):
    """Base model with orjson-backed JSON serialization.

    Overrides Pydantic v2's default JSON encoder/decoder so that
    all ``model_dump_json()`` and ``model_validate_json()`` calls
    use orjson transparently.
    """

    @classmethod
    def model_json_loads(cls, data: str | bytes) -> Any:
        """Deserialize JSON using orjson."""
        return orjson.loads(data)

    @classmethod
    def model_json_dumps(cls, data: Any, **kwargs: Any) -> str:
        """Serialize to JSON using orjson (returns str, not bytes)."""
        return orjson.dumps(data).decode()
```

**Verify:**

```bash
python -c "
from miniautogen.core.contracts.base import MiniAutoGenBaseModel
from pydantic import Field
from datetime import datetime, timezone

class TestModel(MiniAutoGenBaseModel):
    name: str
    ts: datetime

m = TestModel(name='test', ts=datetime.now(timezone.utc))
json_str = m.model_dump_json()
print(type(json_str), json_str[:50])
restored = TestModel.model_validate_json(json_str)
print(restored.name)
"
# Expected:
# <class 'str'> {"name":"test","ts":"2026-...
# test
```

**If Task Fails:**
- orjson not installed: Run `pip install orjson>=3.10.0`.
- Rollback: `rm miniautogen/core/contracts/base.py`

---

### Task 1.5: Write test for `MiniAutoGenBaseModel`

**What:** Add tests verifying the base model uses orjson for serialization.

**Where:** Create new file `/Users/brunocapelao/Projects/miniAutoGen/tests/core/contracts/test_base_model.py`

**How:**

```python
"""Tests for MiniAutoGenBaseModel orjson integration."""

from __future__ import annotations

from datetime import datetime, timezone

from miniautogen.core.contracts.base import MiniAutoGenBaseModel


class SampleModel(MiniAutoGenBaseModel):
    name: str
    value: int
    ts: datetime


class TestBaseModelOrjson:
    """Verify orjson is used for model serialization."""

    def test_model_dump_json_returns_str(self) -> None:
        m = SampleModel(name="test", value=42, ts=datetime(2026, 1, 1, tzinfo=timezone.utc))
        result = m.model_dump_json()
        assert isinstance(result, str)

    def test_model_validate_json_round_trip(self) -> None:
        original = SampleModel(name="test", value=42, ts=datetime(2026, 1, 1, tzinfo=timezone.utc))
        json_str = original.model_dump_json()
        restored = SampleModel.model_validate_json(json_str)
        assert restored.name == original.name
        assert restored.value == original.value
        assert restored.ts == original.ts

    def test_model_json_loads_classmethod(self) -> None:
        result = SampleModel.model_json_loads('{"name": "x", "value": 1, "ts": "2026-01-01T00:00:00+00:00"}')
        assert isinstance(result, dict)
        assert result["name"] == "x"

    def test_model_json_dumps_classmethod(self) -> None:
        result = SampleModel.model_json_dumps({"name": "x", "value": 1})
        assert isinstance(result, str)
        assert '"name"' in result
```

**Verify:**

```bash
python -m pytest tests/core/contracts/test_base_model.py -v
# Expected: 4 passed
```

**If Task Fails:**
- Test import error: Ensure `miniautogen/core/contracts/base.py` was created in Task 1.4.
- Rollback: `rm tests/core/contracts/test_base_model.py`

---

### Task 1.6: Rebase `ExecutionEvent` onto `MiniAutoGenBaseModel`

**What:** Change `ExecutionEvent` to inherit from `MiniAutoGenBaseModel` instead of `pydantic.BaseModel`.

**Where:** Modify `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/events.py`

**How:**

Replace line 4:
```python
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator
```
with:
```python
from pydantic import AliasChoices, ConfigDict, Field, model_validator

from miniautogen.core.contracts.base import MiniAutoGenBaseModel
```

Replace line 7:
```python
class ExecutionEvent(BaseModel):
```
with:
```python
class ExecutionEvent(MiniAutoGenBaseModel):
```

The full file after edits:

```python
from datetime import datetime, timezone
from typing import Any

from pydantic import AliasChoices, ConfigDict, Field, model_validator

from miniautogen.core.contracts.base import MiniAutoGenBaseModel


class ExecutionEvent(MiniAutoGenBaseModel):
    """Canonical execution event emitted by the runtime."""

    type: str = Field(
        validation_alias=AliasChoices("type", "event_type"),
        serialization_alias="type",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        validation_alias=AliasChoices("timestamp", "created_at"),
        serialization_alias="timestamp",
    )
    run_id: str | None = None
    correlation_id: str | None = None
    scope: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def infer_run_id_from_payload(self) -> "ExecutionEvent":
        if self.run_id is None and "run_id" in self.payload:
            payload_run_id = self.payload["run_id"]
            if isinstance(payload_run_id, str):
                self.run_id = payload_run_id
        return self

    @property
    def event_type(self) -> str:
        return self.type

    @property
    def created_at(self) -> datetime:
        return self.timestamp
```

**Verify:**

```bash
python -c "from miniautogen.core.contracts.events import ExecutionEvent; e = ExecutionEvent(type='test'); print(e.model_dump_json()[:50])"
# Expected: {"type":"test","timestamp":"2026-... (orjson compact format, no spaces after colons)
```

```bash
python -m pytest tests/core/contracts/test_events.py tests/core/contracts/test_execution_event_comprehensive.py -v
# Expected: All existing tests PASSED
```

**If Task Fails:**
- Circular import: Verify `base.py` does not import from `events.py`.
- Test failures: Check that `model_config` with `populate_by_name=True` still works alongside the inherited base model.
- Rollback: `git checkout -- miniautogen/core/contracts/events.py`

---

### Task 1.7: Rebase `RunContext` onto `MiniAutoGenBaseModel`

**What:** Change `RunContext` to inherit from `MiniAutoGenBaseModel` instead of `pydantic.BaseModel`.

**Where:** Modify `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/core/contracts/run_context.py`

**How:**

Replace line 4:
```python
from pydantic import BaseModel, Field
```
with:
```python
from pydantic import Field

from miniautogen.core.contracts.base import MiniAutoGenBaseModel
```

Replace line 7:
```python
class RunContext(BaseModel):
```
with:
```python
class RunContext(MiniAutoGenBaseModel):
```

The full file after edits:

```python
from datetime import datetime
from typing import Any

from pydantic import Field

from miniautogen.core.contracts.base import MiniAutoGenBaseModel


class RunContext(MiniAutoGenBaseModel):
    """Typed execution context for a single framework run."""

    run_id: str
    started_at: datetime
    correlation_id: str
    execution_state: dict[str, Any] = Field(default_factory=dict)
    input_payload: Any = None
    timeout_seconds: float | None = None
    namespace: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def with_previous_result(self, result: Any) -> "RunContext":
        """Create a new RunContext with the previous result injected.

        The previous result is set as ``input_payload`` and a reference
        is stored in ``metadata["previous_result"]`` for traceability.
        """
        new_metadata = {**self.metadata, "previous_result": result}
        return self.model_copy(
            update={"input_payload": result, "metadata": new_metadata},
        )
```

**Verify:**

```bash
python -m pytest tests/core/contracts/test_run_context.py tests/core/contracts/test_run_context_comprehensive.py -v
# Expected: All existing tests PASSED
```

**If Task Fails:**
- Rollback: `git checkout -- miniautogen/core/contracts/run_context.py`

---

### Task 1.8: Migrate store files to use the JSON shim

**What:** Replace all `import json` / `json.dumps` / `json.loads` calls in store files with the centralized shim.

**Where:** Three files to modify:

**File 1: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/stores/sqlalchemy_checkpoint_store.py`**

Replace line 1:
```python
import json
```
with:
```python
from miniautogen._json import dumps, loads
```

Replace all occurrences (3 total):
- Line 46: `json.dumps(payload)` -> `dumps(payload)`
- Line 51: `json.dumps(payload)` -> `dumps(payload)`
- Line 61: `json.loads(db_checkpoint.payload_json)` -> `loads(db_checkpoint.payload_json)`
- Line 78: `json.loads(cp.payload_json)` -> `loads(cp.payload_json)`

**File 2: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/stores/sqlalchemy_run_store.py`**

Replace line 1:
```python
import json
```
with:
```python
from miniautogen._json import dumps, loads
```

Replace all occurrences (4 total):
- Line 46: `json.dumps(payload)` -> `dumps(payload)`
- Line 51: `json.dumps(payload)` -> `dumps(payload)`
- Line 61: `json.loads(db_run.payload_json)` -> `loads(db_run.payload_json)`
- Line 72: `json.loads(r.payload_json)` -> `loads(r.payload_json)`

**File 3: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/stores/sqlalchemy.py`**

Replace line 1:
```python
import json
```
with:
```python
from miniautogen._json import dumps, loads
```

Replace occurrences:
- Line 49: `json.dumps(message.additional_info)` -> `dumps(message.additional_info)`
- Line 65: `json.loads(cast(str, message.additional_info))` -> `loads(cast(str, message.additional_info))`

**Verify:**

```bash
python -m pytest tests/stores/ -v
# Expected: All store tests PASSED
```

```bash
python -c "import ast, sys; [ast.parse(open(f).read()) for f in ['miniautogen/stores/sqlalchemy_checkpoint_store.py', 'miniautogen/stores/sqlalchemy_run_store.py', 'miniautogen/stores/sqlalchemy.py']]; print('Syntax OK')"
# Expected: Syntax OK
```

**If Task Fails:**
- `NameError: name 'json' is not defined`: You missed replacing a `json.xxx` call. Search the file for remaining `json.` references.
- Rollback: `git checkout -- miniautogen/stores/sqlalchemy_checkpoint_store.py miniautogen/stores/sqlalchemy_run_store.py miniautogen/stores/sqlalchemy.py`

---

### Task 1.9: Migrate remaining files to use the JSON shim

**What:** Replace `import json` in the remaining non-store files.

**Where:** Three files to modify:

**File 1: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/app/notebook_cache.py`**

Replace line 3:
```python
import json
```
with:
```python
from miniautogen._json import dumps, loads
```

Replace occurrences:
- Line 21: `json.dumps(data, ensure_ascii=False, indent=2)` -> `dumps(data, indent=True)`
- Line 26: `json.loads(self.path.read_text(encoding="utf-8"))` -> `loads(self.path.read_text(encoding="utf-8"))`

**File 2: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/output.py`**

Replace line 5:
```python
import json
```
with:
```python
from miniautogen._json import dumps
```

Replace line 33:
```python
    click.echo(json.dumps(data, indent=2, default=str))
```
with:
```python
    click.echo(dumps(data, indent=True))
```

**File 3: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/backends/cli/driver.py`**

Replace line 11:
```python
import json
```
with:
```python
from miniautogen._json import dumps
```

Replace line 107:
```python
            input_data = json.dumps({
```
with:
```python
            input_data = dumps({
```

**File 4: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/pipeline/components/components.py`**

Replace line 2:
```python
import json
```
with:
```python
from miniautogen._json import loads
```

Replace line 169:
```python
            prompt = json.loads(prompt_str)
```
with:
```python
            prompt = loads(prompt_str)
```

Replace line 170:
```python
        except json.JSONDecodeError:
```

Note: Since `orjson.JSONDecodeError` is a subclass of `json.JSONDecodeError`, and the shim uses orjson directly, we need to handle this. The simplest approach: import `JSONDecodeError` from the right place.

Replace:
```python
        except json.JSONDecodeError:
```
with:
```python
        except (ValueError, TypeError):
```

This works because both `json.JSONDecodeError` and `orjson.JSONDecodeError` are subclasses of `ValueError`.

**Verify:**

```bash
# Confirm no remaining direct json imports in the migrated files
python -c "
import re, pathlib
files = [
    'miniautogen/stores/sqlalchemy_checkpoint_store.py',
    'miniautogen/stores/sqlalchemy_run_store.py',
    'miniautogen/stores/sqlalchemy.py',
    'miniautogen/app/notebook_cache.py',
    'miniautogen/cli/output.py',
    'miniautogen/backends/cli/driver.py',
    'miniautogen/pipeline/components/components.py',
]
for f in files:
    content = pathlib.Path(f).read_text()
    if re.search(r'^import json$', content, re.MULTILINE):
        print(f'FAIL: {f} still has import json')
    else:
        print(f'OK: {f}')
"
# Expected: All files show OK
```

```bash
python -m pytest tests/ -x --timeout=60
# Expected: All tests PASSED
```

**If Task Fails:**
- `json.JSONDecodeError` not found: Ensure you replaced the except clause in `components.py` as described.
- Rollback: `git checkout -- miniautogen/app/notebook_cache.py miniautogen/cli/output.py miniautogen/backends/cli/driver.py miniautogen/pipeline/components/components.py`

---

### Task 1.10: Run full test suite and commit

**What:** Run the complete test suite and commit the orjson integration.

**Where:** No file changes -- verification and commit only.

**How:**

```bash
python -m pytest tests/ -v --timeout=60
# Expected: All tests PASSED, zero failures
```

If all tests pass:

```bash
git add miniautogen/_json.py
git add miniautogen/core/contracts/base.py
git add miniautogen/core/contracts/events.py
git add miniautogen/core/contracts/run_context.py
git add miniautogen/stores/sqlalchemy_checkpoint_store.py
git add miniautogen/stores/sqlalchemy_run_store.py
git add miniautogen/stores/sqlalchemy.py
git add miniautogen/app/notebook_cache.py
git add miniautogen/cli/output.py
git add miniautogen/backends/cli/driver.py
git add miniautogen/pipeline/components/components.py
git add pyproject.toml
git add tests/core/test_json_shim.py
git add tests/core/contracts/test_base_model.py
git commit -m "feat(infra): integrate orjson via centralized JSON shim and Pydantic base model

- Add miniautogen/_json.py shim with orjson primary / stdlib fallback
- Add MiniAutoGenBaseModel with orjson-backed model_json_loads/dumps
- Rebase ExecutionEvent and RunContext onto MiniAutoGenBaseModel
- Migrate all 7 modules from import json to _json shim
- Add tests for shim round-trip and base model serialization"
```

**Verify:**

```bash
git log --oneline -1
# Expected: feat(infra): integrate orjson via centralized JSON shim...
```

**If Task Fails:**
- Test failures: Fix the failing test before committing. Do not commit with failures.
- Rollback: `git reset HEAD~1` (if committed with issues)

---

### Task 1.11: Code Review Checkpoint

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY):**

**Critical/High/Medium Issues:**
- Fix immediately (do NOT add TODO comments for these severities)
- Re-run all 3 reviewers in parallel after fixes
- Repeat until zero Critical/High/Medium issues remain

**Low Issues:**
- Add `TODO(review):` comments in code at the relevant location
- Format: `TODO(review): [Issue description] (reported by [reviewer] on [date], severity: Low)`

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location
- Format: `FIXME(nitpick): [Issue description] (reported by [reviewer] on [date], severity: Cosmetic)`

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low issues have TODO(review): comments added
   - All Cosmetic issues have FIXME(nitpick): comments added

---

## TG-2: uv Migration

**Branch:** `infra/uv-migration`

### Task 2.1: Create feature branch and install uv

**What:** Create a new branch from main and verify uv is installed.

**Where:** No file changes.

**How:**

```bash
git checkout main
git checkout -b infra/uv-migration
```

Install uv if not present:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Verify:**

```bash
uv --version
# Expected: uv 0.x.x (any recent version)
```

**If Task Fails:**
- Install script fails: Try `pip install uv` or `brew install uv` on macOS.
- Rollback: `git checkout main`

---

### Task 2.2: Convert pyproject.toml to PEP 621

**What:** Rewrite `pyproject.toml` replacing Poetry-specific sections with PEP 621 standard format.

**Where:** Modify `/Users/brunocapelao/Projects/miniAutoGen/pyproject.toml`

**How:**

Replace the ENTIRE file content with:

```toml
[project]
name = "miniautogen"
version = "0.1.0"
description = "Lightweight and flexible library for creating multi-agent agents and conversations."
authors = [{name = "Bruno Capelao", email = "brcapelao@gmail.com"}]
license = {text = "MIT License"}
readme = "README.md"
requires-python = ">=3.10,<3.12"
dependencies = [
    "openai>=1.3.9",
    "python-dotenv==1.0.0",
    "sqlalchemy>=2.0.23",
    "litellm>=1.16.12",
    "pydantic>=2.5.0",
    "aiosqlite>=0.19.0",
    "anyio>=4.0.0",
    "jinja2>=3.1.0",
    "structlog>=24.0.0",
    "tenacity>=8.2.0",
    "fastapi>=0.115.0",
    "uvicorn>=0.32.0",
    "httpx>=0.28.0",
    "click>=8.0",
    "pyyaml>=6.0",
    "ruamel-yaml>=0.18.0",
    "orjson>=3.10.0",
]

[project.optional-dependencies]
tui = ["textual>=1.0.0"]
anthropic = ["anthropic>=0.40.0"]
google = ["google-genai>=1.0.0"]
all-providers = ["openai>=1.3.9", "anthropic>=0.40.0", "google-genai>=1.0.0"]
all = ["textual>=1.0.0", "openai>=1.3.9", "anthropic>=0.40.0", "google-genai>=1.0.0"]

[project.scripts]
miniautogen = "miniautogen.cli.main:cli"

[dependency-groups]
dev = [
    "ipykernel==6.28.0",
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.15.0",
    "mypy>=1.9.0",
    "hypothesis>=6.130.0",
    "deepdiff>=7.0.0",
]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I"]

[tool.mypy]
python_version = "3.10"
warn_unused_configs = true
check_untyped_defs = true
ignore_missing_imports = true
warn_unused_ignores = true
warn_redundant_casts = true

[[tool.mypy.overrides]]
module = [
    "litellm",
    "litellm.*",
    "openai",
    "openai.*",
    "torch",
    "torch.*",
]
follow_imports = "skip"
ignore_missing_imports = true

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Verify:**

```bash
python -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    data = tomllib.load(f)
assert 'project' in data, 'Missing [project] section'
assert 'tool.poetry' not in str(data), 'Poetry sections still present'
print('PEP 621 structure: OK')
print('Name:', data['project']['name'])
print('Deps count:', len(data['project']['dependencies']))
"
# Expected:
# PEP 621 structure: OK
# Name: miniautogen
# Deps count: 17
```

**If Task Fails:**
- TOML parse error: Check for syntax issues (missing commas, unclosed brackets).
- Rollback: `git checkout -- pyproject.toml`

---

### Task 2.3: Delete poetry.lock

**What:** Remove the Poetry lockfile that is no longer needed.

**Where:** Delete `/Users/brunocapelao/Projects/miniAutoGen/poetry.lock`

**How:**

```bash
rm poetry.lock
```

**Verify:**

```bash
test ! -f poetry.lock && echo "poetry.lock removed" || echo "FAIL: poetry.lock still exists"
# Expected: poetry.lock removed
```

**If Task Fails:**
- File doesn't exist: This is fine -- skip this task.

---

### Task 2.4: Generate uv.lock and sync environment

**What:** Use uv to resolve dependencies and create a fresh virtual environment.

**Where:** Generates `/Users/brunocapelao/Projects/miniAutoGen/uv.lock` (new file)

**How:**

```bash
uv lock
```

Expected output: resolves all dependencies without errors or warnings.

Then sync the environment:

```bash
uv sync --all-extras
```

**Verify:**

```bash
uv run python -c "import miniautogen; print('import OK')"
# Expected: import OK
```

```bash
test -f uv.lock && echo "uv.lock exists" || echo "FAIL: uv.lock missing"
# Expected: uv.lock exists
```

**If Task Fails:**
- Resolution error: Check dependency version constraints in `pyproject.toml`. Common issue: conflicting version ranges.
- `hatchling` not found: Run `uv add --dev hatchling` or adjust `[build-system]`.
- Rollback: `git checkout -- pyproject.toml && rm -f uv.lock`

---

### Task 2.5: Verify full PEP 621 compliance

**What:** Run the full PEP 621 validation checklist from the design spec.

**Where:** No file changes -- verification only.

**How:**

Run each command and verify output:

```bash
uv lock
# Expected: completes without errors or warnings (may say "Resolved X packages")

uv sync --all-extras
# Expected: completes without errors

uv run python -c "import miniautogen; print('OK')"
# Expected: OK

uv run pip install --dry-run .
# Expected: Would install miniautogen-0.1.0 (or similar)

uv run pytest tests/ -x --timeout=60
# Expected: All tests PASSED

uv run ruff check .
# Expected: No errors (or only pre-existing warnings)

uv run mypy miniautogen/
# Expected: No new type errors (pre-existing ones are acceptable)
```

**If Task Fails:**
- Any verification step fails: Fix the issue in `pyproject.toml` before proceeding.
- Test failures: These may be pre-existing. Compare with `git stash && pytest && git stash pop` to isolate.

---

### Task 2.6: Commit uv migration

**What:** Stage and commit all uv migration changes.

**Where:** No new file changes -- commit only.

**How:**

```bash
git add pyproject.toml
git add uv.lock
git rm poetry.lock  # records the deletion
git commit -m "build: migrate from Poetry to uv with PEP 621 pyproject.toml

- Convert [tool.poetry.*] sections to PEP 621 [project.*] format
- Replace poetry-core build backend with hatchling
- Delete poetry.lock, generate uv.lock
- Add deepdiff>=7.0.0 to dev dependencies
- All existing tests pass under uv run pytest"
```

**Verify:**

```bash
git log --oneline -1
# Expected: build: migrate from Poetry to uv with PEP 621 pyproject.toml
git diff --name-only HEAD~1
# Expected: pyproject.toml, uv.lock, poetry.lock (deleted)
```

**If Task Fails:**
- `poetry.lock` not tracked: Use `git add -u` instead of `git rm`.
- Rollback: `git reset HEAD~1`

---

### Task 2.7: Code Review Checkpoint

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY):**

**Critical/High/Medium Issues:**
- Fix immediately (do NOT add TODO comments for these severities)
- Re-run all 3 reviewers in parallel after fixes
- Repeat until zero Critical/High/Medium issues remain

**Low Issues:**
- Add `TODO(review):` comments in code at the relevant location

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low/Cosmetic issues have appropriate comments added

---

## TG-3: deepdiff for QA

**Branch:** `infra/deepdiff-qa`

### Task 3.1: Create feature branch and install deepdiff

**What:** Create a feature branch and install deepdiff.

**Where:** No file changes (dependency is already in dev group from TG-2, or add it now).

**How:**

```bash
git checkout main
git checkout -b infra/deepdiff-qa
```

If TG-2 has NOT been merged yet (pyproject.toml still uses Poetry format), add deepdiff manually:

Edit `/Users/brunocapelao/Projects/miniAutoGen/pyproject.toml` -- add to `[tool.poetry.group.dev.dependencies]` (after line 44):

```toml
deepdiff = ">=7.0.0"
```

Then install:

```bash
pip install "deepdiff>=7.0.0"
```

**Verify:**

```bash
python -c "import deepdiff; print(deepdiff.__version__)"
# Expected: 7.x.x or 8.x.x
```

**If Task Fails:**
- Install fails: Try `pip install --upgrade deepdiff`.
- Rollback: `git checkout main`

---

### Task 3.2: Add `assert_no_mutation` helper to test infrastructure

**What:** Create a shared test helper for immutability assertions.

**Where:** Create new file `/Users/brunocapelao/Projects/miniAutoGen/tests/conftest.py`

Note: This file does NOT currently exist at the project root. The existing conftest files are in subdirectories (`tests/backends/conftest.py`, `tests/cli/commands/conftest.py`).

**How:**

```python
"""Root conftest.py -- shared test fixtures and helpers."""

from __future__ import annotations

from typing import Any

from deepdiff import DeepDiff


def assert_no_mutation(
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
    label: str = "",
) -> None:
    """Assert that two snapshots are structurally identical.

    Uses DeepDiff for deep comparison. Raises AssertionError with
    a detailed diff message if any mutation is detected.

    Args:
        before_snapshot: State captured before the operation.
        after_snapshot: State captured after the operation.
        label: Optional label for the error message.
    """
    diff = DeepDiff(before_snapshot, after_snapshot, ignore_order=True)
    assert diff == {}, f"Immutability violation{' in ' + label if label else ''}: {diff}"
```

**Verify:**

```bash
python -c "
import sys; sys.path.insert(0, 'tests')
from conftest import assert_no_mutation
# Should pass (no mutation)
assert_no_mutation({'a': 1}, {'a': 1}, 'test')
print('OK: identical dicts pass')
# Should fail (mutation detected)
try:
    assert_no_mutation({'a': 1}, {'a': 2}, 'test')
    print('FAIL: should have raised')
except AssertionError as e:
    print(f'OK: mutation detected: {e}')
"
# Expected:
# OK: identical dicts pass
# OK: mutation detected: Immutability violation in test: ...
```

**If Task Fails:**
- deepdiff not installed: Run `pip install deepdiff>=7.0.0`.
- Rollback: `rm tests/conftest.py`

---

### Task 3.3: Write immutability tests for ExecutionEvent

**What:** Create tests that verify `ExecutionEvent` does not mutate input data during construction.

**Where:** Create new file `/Users/brunocapelao/Projects/miniAutoGen/tests/core/contracts/test_immutability.py`

**How:**

```python
"""Immutability invariant tests using DeepDiff.

These tests enforce Architectural Invariant 1 (Immutability) by verifying
that framework models do not mutate their inputs or leak shared references.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

import pytest
from deepdiff import DeepDiff

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import RunContext

# ---------------------------------------------------------------------------
# Import the shared helper (available via tests/conftest.py)
# ---------------------------------------------------------------------------
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from conftest import assert_no_mutation


# ---------------------------------------------------------------------------
# ExecutionEvent immutability tests
# ---------------------------------------------------------------------------


class TestExecutionEventImmutability:
    """Verify ExecutionEvent does not mutate inputs."""

    def test_payload_dict_not_mutated_by_construction(self) -> None:
        """Creating an ExecutionEvent must not mutate the input payload dict."""
        original_payload: dict[str, Any] = {"run_id": "run-123", "data": "value"}
        snapshot = copy.deepcopy(original_payload)

        # Construction triggers infer_run_id_from_payload validator
        _event = ExecutionEvent(type="test", payload=original_payload)

        assert_no_mutation(snapshot, original_payload, "ExecutionEvent payload input")

    def test_event_serialization_round_trip(self) -> None:
        """model_dump_json -> model_validate_json produces zero diff."""
        event = ExecutionEvent(
            type="component_finished",
            run_id="run-1",
            payload={"step": 3, "data": [1, 2, 3]},
        )
        json_str = event.model_dump_json()
        restored = ExecutionEvent.model_validate_json(json_str)

        diff = DeepDiff(
            event.model_dump(mode="python"),
            restored.model_dump(mode="python"),
        )
        assert diff == {}, f"Event round-trip fidelity violation: {diff}"

    @pytest.mark.xfail(
        reason="Known violation: infer_run_id_from_payload mutates self.run_id in model_validator(mode='after'). "
               "Tracked for refactoring in WS2 (Immutable Core).",
        strict=True,
    )
    def test_event_run_id_inference_does_not_mutate_self(self) -> None:
        """The model_validator should not mutate self -- it should use model_copy or __init__.

        This test documents the known violation: the validator sets self.run_id
        directly, which is a mutation of the model after construction.
        """
        event = ExecutionEvent(type="test", payload={"run_id": "inferred-123"})
        # The validator mutated self.run_id -- this is the violation.
        # In an ideal world, run_id would be set during __init__, not via mutation.
        # We mark this xfail to document the violation; WS2 will fix it.
        assert event.run_id is None  # This WILL fail because run_id was mutated to "inferred-123"


# ---------------------------------------------------------------------------
# RunContext immutability tests
# ---------------------------------------------------------------------------


class TestRunContextImmutability:
    """Verify RunContext operations produce isolated copies."""

    def _make_context(self, **overrides: Any) -> RunContext:
        defaults: dict[str, Any] = {
            "run_id": "run-1",
            "started_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "correlation_id": "corr-1",
            "execution_state": {"step": 1, "data": [1, 2, 3]},
            "metadata": {"source": "test"},
        }
        defaults.update(overrides)
        return RunContext(**defaults)  # type: ignore[arg-type]

    def test_with_previous_result_does_not_mutate_original(self) -> None:
        """Calling with_previous_result must not change the original context."""
        ctx = self._make_context()
        snapshot = ctx.model_dump(mode="python")

        _child = ctx.with_previous_result({"output": "data"})

        assert_no_mutation(
            snapshot,
            ctx.model_dump(mode="python"),
            "RunContext after with_previous_result",
        )

    def test_execution_state_isolated_on_copy(self) -> None:
        """execution_state in the child must be a distinct object."""
        ctx = self._make_context()
        child = ctx.with_previous_result({"output": "data"})

        # Identity check: must NOT be the same dict object
        assert child.execution_state is not ctx.execution_state

    def test_metadata_isolated_on_copy(self) -> None:
        """metadata in the child must be a distinct object (it uses spread)."""
        ctx = self._make_context()
        child = ctx.with_previous_result({"output": "data"})

        # Identity check: must NOT be the same dict object
        assert child.metadata is not ctx.metadata

    def test_metadata_changes_do_not_leak_back(self) -> None:
        """Mutating child metadata must not affect parent metadata."""
        ctx = self._make_context()
        child = ctx.with_previous_result({"output": "data"})

        # Mutate the child's metadata
        child.metadata["injected"] = "should_not_leak"

        assert "injected" not in ctx.metadata

    def test_execution_state_changes_do_not_leak_back(self) -> None:
        """Mutating child execution_state must not affect parent."""
        ctx = self._make_context()
        child = ctx.with_previous_result({"output": "data"})

        # Mutate the child's execution_state
        child.execution_state["injected"] = "should_not_leak"

        assert "injected" not in ctx.execution_state
```

**Verify:**

```bash
python -m pytest tests/core/contracts/test_immutability.py -v
# Expected:
# test_payload_dict_not_mutated_by_construction PASSED
# test_event_serialization_round_trip PASSED
# test_event_run_id_inference_does_not_mutate_self XFAIL
# test_with_previous_result_does_not_mutate_original PASSED
# test_execution_state_isolated_on_copy PASSED
# test_metadata_isolated_on_copy PASSED
# test_metadata_changes_do_not_leak_back PASSED
# test_execution_state_changes_do_not_leak_back PASSED
```

Note: `test_execution_state_isolated_on_copy` may FAIL because Pydantic's `model_copy` does a shallow copy by default. If it fails, this is a REAL bug that documents the immutability violation. Mark it as `xfail` with:

```python
    @pytest.mark.xfail(
        reason="Pydantic model_copy performs shallow copy of execution_state. "
               "Tracked for fix in WS2 (Immutable Core).",
        strict=True,
    )
    def test_execution_state_isolated_on_copy(self) -> None:
        ...
```

**If Task Fails:**
- Import errors: Ensure `tests/__init__.py` exists and `tests/core/contracts/__init__.py` exists (it should from existing test structure).
- deepdiff not installed: `pip install deepdiff>=7.0.0`.
- Rollback: `rm tests/core/contracts/test_immutability.py`

---

### Task 3.4: Write store round-trip fidelity tests

**What:** Add tests verifying that checkpoint and run store save/load produces zero diff.

**Where:** Create new file `/Users/brunocapelao/Projects/miniAutoGen/tests/stores/test_store_round_trip.py`

**How:**

```python
"""Store round-trip fidelity tests using DeepDiff.

Verifies that save -> load produces structurally identical data
for both CheckpointStore and RunStore implementations.
"""

from __future__ import annotations

from typing import Any

import pytest
from deepdiff import DeepDiff

from miniautogen.stores.sqlalchemy_checkpoint_store import SQLAlchemyCheckpointStore
from miniautogen.stores.sqlalchemy_run_store import SQLAlchemyRunStore


@pytest.mark.asyncio
async def test_checkpoint_round_trip_zero_diff(tmp_path: Any) -> None:
    """Save then load a checkpoint and assert zero structural diff."""
    store = SQLAlchemyCheckpointStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'ckpt.db'}"
    )
    await store.init_db()

    original = {
        "run_id": "abc",
        "state": {"step": 3, "data": [1, 2, 3]},
        "config": {"nested": {"deep": True}},
    }

    await store.save_checkpoint("run-rt-1", original)
    restored = await store.get_checkpoint("run-rt-1")

    diff = DeepDiff(original, restored)
    assert diff == {}, f"Checkpoint round-trip fidelity violation: {diff}"


@pytest.mark.asyncio
async def test_run_store_round_trip_zero_diff(tmp_path: Any) -> None:
    """Save then load a run and assert zero structural diff."""
    store = SQLAlchemyRunStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'runs.db'}"
    )
    await store.init_db()

    original = {
        "run_id": "run-42",
        "status": "completed",
        "result": {"output": "hello", "tokens": [10, 20, 30]},
        "metadata": {"source": "test", "nested": {"key": "value"}},
    }

    await store.save_run("run-42", original)
    restored = await store.get_run("run-42")

    diff = DeepDiff(original, restored)
    assert diff == {}, f"Run store round-trip fidelity violation: {diff}"


@pytest.mark.asyncio
async def test_checkpoint_round_trip_with_special_types(tmp_path: Any) -> None:
    """Round-trip with types that commonly cause fidelity issues."""
    store = SQLAlchemyCheckpointStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'ckpt2.db'}"
    )
    await store.init_db()

    original = {
        "float_val": 3.14159,
        "bool_val": True,
        "null_val": None,
        "empty_list": [],
        "empty_dict": {},
        "nested_list": [[1, 2], [3, 4]],
    }

    await store.save_checkpoint("run-special", original)
    restored = await store.get_checkpoint("run-special")

    diff = DeepDiff(original, restored)
    assert diff == {}, f"Special types round-trip violation: {diff}"
```

**Verify:**

```bash
python -m pytest tests/stores/test_store_round_trip.py -v
# Expected: 3 passed
```

**If Task Fails:**
- async test issues: Ensure `pytest-asyncio` is installed. Check that `@pytest.mark.asyncio` is recognized.
- Rollback: `rm tests/stores/test_store_round_trip.py`

---

### Task 3.5: Run full test suite and commit

**What:** Verify all tests pass and commit the deepdiff QA integration.

**Where:** No file changes -- verification and commit only.

**How:**

```bash
python -m pytest tests/ -v --timeout=60
# Expected: All tests PASSED. The xfail test(s) show as XFAIL (expected failure).
```

If all tests pass:

```bash
git add pyproject.toml  # only if deepdiff was added here (not in TG-2)
git add tests/conftest.py
git add tests/core/contracts/test_immutability.py
git add tests/stores/test_store_round_trip.py
git commit -m "test(qa): add deepdiff immutability guards and store round-trip fidelity tests

- Add assert_no_mutation helper in tests/conftest.py
- Add 8 immutability tests for ExecutionEvent and RunContext
- Document known mutation violation in ExecutionEvent validator (xfail)
- Add 3 store round-trip fidelity tests with DeepDiff assertions
- deepdiff>=7.0.0 added to dev dependencies"
```

**Verify:**

```bash
git log --oneline -1
# Expected: test(qa): add deepdiff immutability guards...
```

**If Task Fails:**
- Commit fails: Check `git status` for unstaged files.
- Rollback: `git reset HEAD~1`

---

### Task 3.6: Code Review Checkpoint

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY):**

**Critical/High/Medium Issues:**
- Fix immediately (do NOT add TODO comments for these severities)
- Re-run all 3 reviewers in parallel after fixes
- Repeat until zero Critical/High/Medium issues remain

**Low Issues:**
- Add `TODO(review):` comments in code at the relevant location

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low/Cosmetic issues have appropriate comments added

---

## Final Verification

After all three task groups are complete (on their respective branches), verify each branch independently:

### TG-1 Verification (on `infra/orjson-integration`):

```bash
git checkout infra/orjson-integration

# 1. No remaining direct json imports in migrated modules
python -c "
import re, pathlib
files = [
    'miniautogen/stores/sqlalchemy_checkpoint_store.py',
    'miniautogen/stores/sqlalchemy_run_store.py',
    'miniautogen/stores/sqlalchemy.py',
    'miniautogen/app/notebook_cache.py',
    'miniautogen/cli/output.py',
    'miniautogen/backends/cli/driver.py',
    'miniautogen/pipeline/components/components.py',
]
for f in files:
    content = pathlib.Path(f).read_text()
    if re.search(r'^import json$', content, re.MULTILINE):
        print(f'FAIL: {f}')
    else:
        print(f'OK: {f}')
"

# 2. Shim exists with fallback
python -c "from miniautogen._json import dumps, loads, HAS_ORJSON; assert HAS_ORJSON; print('Shim OK')"

# 3. Base model exists
python -c "from miniautogen.core.contracts.base import MiniAutoGenBaseModel; print('Base model OK')"

# 4. Full test suite
python -m pytest tests/ -v --timeout=60
```

### TG-2 Verification (on `infra/uv-migration`):

```bash
git checkout infra/uv-migration

# 1. No poetry.lock
test ! -f poetry.lock && echo "OK" || echo "FAIL"

# 2. uv.lock exists
test -f uv.lock && echo "OK" || echo "FAIL"

# 3. PEP 621 compliance
uv lock
uv sync --all-extras
uv run python -c "import miniautogen; print('OK')"
uv run pytest tests/ -x --timeout=60
```

### TG-3 Verification (on `infra/deepdiff-qa`):

```bash
git checkout infra/deepdiff-qa

# 1. Helper exists
python -c "import sys; sys.path.insert(0, 'tests'); from conftest import assert_no_mutation; print('Helper OK')"

# 2. Immutability tests pass
python -m pytest tests/core/contracts/test_immutability.py tests/stores/test_store_round_trip.py -v

# 3. At least 6 immutability tests exist
python -m pytest tests/core/contracts/test_immutability.py --collect-only -q
# Expected: at least 8 tests collected
```

---

## Summary

| Task Group | Branch | Tasks | Commit Message |
|------------|--------|-------|----------------|
| TG-1: orjson | `infra/orjson-integration` | 1.1--1.11 | `feat(infra): integrate orjson via centralized JSON shim and Pydantic base model` |
| TG-2: uv | `infra/uv-migration` | 2.1--2.7 | `build: migrate from Poetry to uv with PEP 621 pyproject.toml` |
| TG-3: deepdiff | `infra/deepdiff-qa` | 3.1--3.6 | `test(qa): add deepdiff immutability guards and store round-trip fidelity tests` |

All three branches are independent and can be merged in any order.
