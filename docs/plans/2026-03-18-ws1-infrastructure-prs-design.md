# WS1: Infrastructure PRs --- Design Spec

**Date:** 2026-03-18
**Status:** Draft
**Scope:** Three independent, low-risk PRs that upgrade serialization, build tooling, and QA validation.

---

## Summary

Workstream 1 delivers three foundational infrastructure improvements to the MiniAutoGen runtime:

1. **orjson** -- Replace stdlib `json` and default Pydantic serialization with a Rust-backed JSON engine.
2. **uv** -- Replace Poetry with uv for dependency resolution and virtual-environment management in CI and local development.
3. **deepdiff** -- Introduce deep-comparison assertions in the test suite to enforce the Immutability Invariant across RunContext, ExecutionEvent, and checkpoint payloads.

Each PR is independent and can be merged in any order.

---

## Motivation (Why)

### orjson

The framework serializes JSON on every critical path: Event Sourcing (`LoggingEventSink.publish`), Atomic Checkpoints (`SQLAlchemyCheckpointStore.save_checkpoint` / `get_checkpoint`), Run Store persistence (`SQLAlchemyRunStore`), CLI output, and Pydantic model round-trips. Today all of these go through CPython's `json` module, which is pure-Python and allocates heavily. orjson is a drop-in replacement written in Rust that is typically 3--10x faster for serialization and 2--5x faster for deserialization, with native `datetime` and `UUID` support that eliminates the need for `default=str` hacks.

### uv

Poetry's dependency resolver is notoriously slow. Local `poetry lock` runs take 30--90 seconds; in CI the install step dominates wall-clock time. uv resolves and installs the same dependency graph 10--100x faster, materially improving PR feedback loops and developer experience. It also produces a standard `pyproject.toml` (PEP 621) so the project stops depending on Poetry-specific metadata.

### deepdiff

Architectural Invariant 1 (Immutability) has no automated enforcement today. Two concrete violations already exist in the codebase:

- `ExecutionEvent.infer_run_id_from_payload` mutates `self.run_id` inside a `model_validator(mode="after")` (line 31 of `miniautogen/core/contracts/events.py`).
- `RunContext.execution_state` is a bare `dict[str, Any]` with no copy-on-read protection (line 13 of `miniautogen/core/contracts/run_context.py`).

Without deep-comparison tests, future changes can silently introduce shared mutable references between pipeline stages. deepdiff provides structural equality and identity checks that catch these regressions at test time.

---

## Changes

### 1. orjson Integration

#### 1.1 Pydantic Configuration (Global)

Create a shared base model that forces orjson for all framework models:

- **File:** `miniautogen/core/contracts/base.py` (new)
- Defines `MiniAutoGenBaseModel(pydantic.BaseModel)` with:
  ```python
  model_config = ConfigDict(
      json_encoders={datetime: lambda v: v.isoformat()},  # fallback only
  )

  @classmethod
  def model_json_loads(cls, data):
      import orjson
      return orjson.loads(data)

  @classmethod
  def model_json_dumps(cls, data, **kwargs):
      import orjson
      return orjson.dumps(data).decode()
  ```
- **Rationale:** Pydantic v2 allows overriding `model_json_loads` / `model_json_dumps` at the class level. A single base model propagates the change to every contract.

#### 1.2 Existing Models to Rebase

| Model | Current Base | File |
|-------|-------------|------|
| `ExecutionEvent` | `pydantic.BaseModel` | `miniautogen/core/contracts/events.py` |
| `RunContext` | `pydantic.BaseModel` | `miniautogen/core/contracts/run_context.py` |

Both must inherit from `MiniAutoGenBaseModel` instead of `pydantic.BaseModel`.

#### 1.3 JSON Shim Module (`miniautogen/_json.py`)

To support platforms where orjson wheels are unavailable (see Risks), all modules must import JSON functions from a centralized shim instead of importing `json` or `orjson` directly.

**File:** `miniautogen/_json.py` (new)

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
        return orjson.loads(data)

    HAS_ORJSON = True

except ImportError:  # pragma: no cover — fallback for exotic platforms
    import json as _json

    def dumps(obj: object, *, indent: bool = False) -> str:  # type: ignore[misc]
        return _json.dumps(obj, indent=2 if indent else None, default=str)

    def loads(data: str | bytes) -> object:  # type: ignore[misc]
        return _json.loads(data)

    HAS_ORJSON = False
```

**Integration rules:**

- Every module that currently does `import json` must switch to `from miniautogen._json import dumps, loads`.
- No module outside `_json.py` may import `orjson` or `json` for serialization purposes.
- orjson natively handles `datetime`, `date`, `time`, `UUID`, and `Enum` — this is transparent to Pydantic v2's `.model_dump_json()` / `.model_validate_json()` when orjson is injected via the base model (Section 1.1).

#### 1.4 Store Layer -- Replace `import json`

All `json.dumps` / `json.loads` calls in the store layer must switch to `from miniautogen._json import dumps, loads`. The shim handles the `bytes`-to-`str` conversion internally, so call-sites simply use `dumps(x)` / `loads(x)` with no `.decode()` needed.

| File | Lines affected | Change |
|------|---------------|--------|
| `miniautogen/stores/sqlalchemy_checkpoint_store.py` | 1, 46, 51, 61, 78 | `import json` -> `from miniautogen._json import dumps, loads`; `json.dumps(x)` -> `dumps(x)`; `json.loads(x)` -> `loads(x)` |
| `miniautogen/stores/sqlalchemy_run_store.py` | 1, 46, 51, 61, 72 | Same pattern |
| `miniautogen/stores/sqlalchemy.py` | 49, 65 | Same pattern |
| `miniautogen/app/notebook_cache.py` | 21, 26 | Same pattern |
| `miniautogen/backends/cli/driver.py` | 107 | Same pattern |
| `miniautogen/pipeline/components/components.py` | 169 | `json.loads` -> `loads` (from shim) |
| `miniautogen/cli/output.py` | 33 | `json.dumps(data, indent=2, default=str)` -> `dumps(data, indent=True)` |

#### 1.5 Structlog Processor (DEFERRED -- not in this PR)

> **Status:** Out of scope for the orjson PR. Tracked here for completeness; will be addressed in a future observability PR.

The current `configure_logging()` in `miniautogen/observability/logging.py` does not set an explicit processor chain -- it relies on structlog defaults (no `processors=` kwarg in `structlog.configure()`). To add an orjson-backed JSON renderer, a full processor chain would need to be defined, e.g.:

```python
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(serializer=orjson.dumps),  # <-- orjson here
    ],
    wrapper_class=structlog.make_filtering_bound_logger(level),
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
```

The `JSONRenderer` must be the **last** processor in the chain (it is a formatter, not a filter). This change is non-trivial because it alters log output format for all consumers and should be validated separately. It is therefore **deferred**.

**Note:** `structlog >= 24.0.0` is already a declared dependency in `pyproject.toml` (line 19), so no new dependency is needed for this future work.

#### 1.6 Dependency Declaration

- **File:** `pyproject.toml`
- Add `orjson = ">=3.10.0"` to `[tool.poetry.dependencies]` (or `"orjson>=3.10.0"` in `[project.dependencies]` after uv migration).
- **Note:** `structlog >= 24.0.0` is already a declared runtime dependency (see `pyproject.toml` line 19). No new dependency is needed for the deferred structlog integration (Section 1.5).

#### 1.7 Expected Performance Impact

- Checkpoint save/load: ~3--5x faster serialization.
- Event logging: reduced allocation pressure per event.
- CLI `--json` output: negligible user-visible difference (small payloads), but consistent codepath.

---

### 2. uv Migration

#### 2.1 pyproject.toml -- Convert to PEP 621

Replace Poetry-specific tables with standard PEP 621 metadata.

**File:** `pyproject.toml`

| Section | Before (Poetry) | After (uv / PEP 621) |
|---------|-----------------|----------------------|
| `[tool.poetry]` | name, version, description, authors, license, readme | `[project]` with the same fields in PEP 621 format |
| `[tool.poetry.dependencies]` | All runtime deps | `[project.dependencies]` as a list of PEP 508 strings |
| `[tool.poetry.extras]` | tui, anthropic, google, all-providers, all | `[project.optional-dependencies]` |
| `[tool.poetry.group.dev.dependencies]` | pytest, ruff, mypy, etc. | `[dependency-groups]` dev group (PEP 735) |
| `[tool.poetry.scripts]` | miniautogen CLI | `[project.scripts]` |
| `[build-system]` | `poetry-core` | `hatchling` (or keep `poetry-core`; uv is resolver-agnostic) |

The `[tool.ruff]` and `[tool.mypy]` sections remain unchanged.

**Concrete before/after example:**

Before (Poetry):

```toml
[tool.poetry]
name = "miniautogen"
version = "0.1.0"
description = "Lightweight and flexible library for creating multi-agent agents and conversations."
authors = ["Bruno Capelão <brcapelao@gmail.com>"]
license = "MIT License"
readme = "README.md"

[tool.poetry.dependencies]
python = ">3.10, <3.12"
openai = ">=1.3.9"
python-dotenv = "1.0.0"
sqlalchemy = ">=2.0.23"
litellm = ">=1.16.12"
pydantic = ">=2.5.0"
aiosqlite = ">=0.19.0"
anyio = ">=4.0.0"
jinja2 = ">=3.1.0"
structlog = ">=24.0.0"
tenacity = ">=8.2.0"
fastapi = ">=0.115.0"
uvicorn = ">=0.32.0"
httpx = ">=0.28.0"
click = ">=8.0"
pyyaml = ">=6.0"
ruamel-yaml = ">=0.18.0"
textual = {version = ">=1.0.0", optional = true}
anthropic = {version = ">=0.40.0", optional = true}
google-genai = {version = ">=1.0.0", optional = true}

[tool.poetry.extras]
tui = ["textual"]
anthropic = ["anthropic"]
google = ["google-genai"]
all-providers = ["openai", "anthropic", "google-genai"]
all = ["textual", "openai", "anthropic", "google-genai"]

[tool.poetry.group.dev.dependencies]
ipykernel = "6.28.0"
pytest = "^7.4.0"
pytest-asyncio = "^0.23.0"
ruff = "^0.15.0"
mypy = "^1.9.0"
hypothesis = "^6.130.0"

[tool.poetry.scripts]
miniautogen = "miniautogen.cli.main:cli"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

After (PEP 621 / uv):

```toml
[project]
name = "miniautogen"
version = "0.1.0"
description = "Lightweight and flexible library for creating multi-agent agents and conversations."
authors = [{name = "Bruno Capelão", email = "brcapelao@gmail.com"}]
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

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Note: `orjson` is included in the `[project.dependencies]` list above (added by the orjson PR). The `[tool.ruff]` and `[tool.mypy]` sections carry over verbatim and are omitted for brevity.

#### 2.2 Lock File

- Delete `poetry.lock` (if present).
- Generate `uv.lock` via `uv lock`.
- Add `uv.lock` to version control.

#### 2.3 Local Development

Update developer-facing instructions:

| Task | Before | After |
|------|--------|-------|
| Create venv + install | `poetry install --all-extras` | `uv sync --all-extras` |
| Add a dependency | `poetry add <pkg>` | `uv add <pkg>` |
| Run a script | `poetry run pytest` | `uv run pytest` |
| Lock deps | `poetry lock` | `uv lock` |

#### 2.4 CI/CD Pipeline

> **OUT OF SCOPE:** GitHub Actions workflow creation is **not** part of this workstream. No `.github/workflows/` files will be created or modified in the uv PR. CI/CD setup will be handled as a separate, dedicated task.

The notes below are included for reference only, to guide the future CI task:

1. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh` (or use `astral-sh/setup-uv@v4`).
2. Cache: `~/.cache/uv` instead of Poetry's cache directory.
3. Install: `uv sync --frozen --all-extras` (uses lockfile, does not re-resolve).
4. Run checks: `uv run pytest`, `uv run ruff check`, `uv run mypy`.

#### 2.5 Files Affected

| File | Action |
|------|--------|
| `pyproject.toml` | Rewrite metadata sections |
| `poetry.lock` | Delete (if exists) |
| `uv.lock` | Generate (new) |
| `README.md` | Update install instructions (if they reference Poetry) |
| `.github/workflows/*.yml` | **OUT OF SCOPE** -- no workflow files will be created in this PR |
| `Makefile` / `justfile` | Update if task-runner references Poetry |

#### 2.6 Python Version Constraint

Current: `>3.10, <3.12`. In PEP 621 this becomes `requires-python = ">=3.10,<3.12"`. No functional change, but the syntax must be valid PEP 440.

---

### 3. deepdiff for QA

#### 3.1 Purpose

deepdiff enables two categories of assertions that stdlib does not support:

1. **Structural equality** -- `DeepDiff(obj_before, obj_after)` returns an empty diff if the objects are semantically identical, regardless of insertion order or type coercion.
2. **Identity tracking** -- Verifying that two references do not share the same mutable object (i.e., a pipeline stage did not accidentally alias a dict instead of copying it).

#### 3.2 Test Patterns

**Pattern A: Pre/Post Immutability Guard**

Capture the state of a model before an operation, run the operation, then assert no mutation occurred on the original.

```
# Pseudocode
snapshot = run_context.model_dump(mode="python")
result = some_pipeline_operation(run_context)
diff = DeepDiff(snapshot, run_context.model_dump(mode="python"))
assert diff == {}, f"RunContext was mutated: {diff}"
```

**Pattern B: No Shared References**

After creating a derived context (e.g., `with_previous_result`), assert that mutable containers are distinct objects.

```
# Pseudocode
child = run_context.with_previous_result({"key": "value"})
assert child.metadata is not run_context.metadata
assert child.execution_state is not run_context.execution_state
diff = DeepDiff(
    run_context.execution_state,
    child.execution_state,
    ignore_order=True,
)
# diff should reflect only the intended changes, nothing leaked
```

**Pattern C: Checkpoint Round-Trip Fidelity**

Serialize a checkpoint payload, deserialize it, and assert zero diff.

```
# Pseudocode
original = {"run_id": "abc", "state": {"step": 3, "data": [1, 2, 3]}}
serialized = orjson.dumps(original)
restored = orjson.loads(serialized)
diff = DeepDiff(original, restored)
assert diff == {}, f"Round-trip fidelity violation: {diff}"
```

#### 3.3 Example Test Cases

| Test | Target | Asserts |
|------|--------|---------|
| `test_execution_event_payload_not_mutated_by_validator` | `ExecutionEvent` | Creating an event with `run_id` in payload does not mutate the input dict |
| `test_run_context_execution_state_isolated_on_copy` | `RunContext.with_previous_result` | `execution_state` dict is a distinct object in the copy |
| `test_run_context_metadata_isolated_on_copy` | `RunContext.with_previous_result` | `metadata` dict is a distinct object in the copy |
| `test_checkpoint_round_trip_zero_diff` | `SQLAlchemyCheckpointStore` | Save then load produces `DeepDiff == {}` |
| `test_run_store_round_trip_zero_diff` | `SQLAlchemyRunStore` | Save then load produces `DeepDiff == {}` |
| `test_event_serialization_round_trip` | `ExecutionEvent` | `model_dump_json` -> `model_validate_json` produces `DeepDiff == {}` |

#### 3.4 Integration with pytest

- Use deepdiff inside standard `assert` statements; no pytest plugin required.
- Create a shared fixture or helper in `tests/conftest.py`:
  ```
  def assert_no_mutation(before_snapshot: dict, after_snapshot: dict, label: str = ""):
      diff = DeepDiff(before_snapshot, after_snapshot, ignore_order=True)
      assert diff == {}, f"Immutability violation{' in ' + label if label else ''}: {diff}"
  ```
- This helper can be used by any test file.

#### 3.5 Files Affected

| File | Action |
|------|--------|
| `pyproject.toml` | Add `deepdiff = ">=7.0.0"` to dev dependencies |
| `tests/conftest.py` | Add `assert_no_mutation` helper |
| `tests/unit/core/test_immutability.py` | New file: all immutability tests |
| `tests/unit/stores/test_store_round_trip.py` | New or extend: round-trip fidelity tests |

---

## Dependencies & Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| orjson wheels unavailable for a target platform | Low | orjson publishes wheels for Linux/macOS/Windows on x86_64 and aarch64. The `miniautogen/_json.py` shim (Section 1.3) provides an automatic stdlib `json` fallback via try/except at import time. All modules import from the shim, never from orjson directly. |
| orjson `bytes` return type causes `TypeError` at call-sites | Low (mitigated) | The `miniautogen/_json.py` shim handles `.decode()` internally — `dumps()` always returns `str`. Call-sites never touch `bytes`. The only exception is `MiniAutoGenBaseModel.model_json_dumps` (Section 1.1), which also decodes explicitly. |
| uv migration breaks editable installs for contributors | Low | `uv sync` supports editable installs natively. Document the one-time migration step in the PR description. |
| uv lockfile format changes between versions | Low | Pin uv version in CI (`astral-sh/setup-uv@v4` with `version:` input). |
| deepdiff false positives from floating-point or datetime precision | Low | Use `significant_digits` and `truncate_datetime` parameters where needed. |
| Ordering: orjson PR must merge before deepdiff round-trip tests reference orjson | Low | deepdiff tests can use stdlib `json` initially. The orjson PR can update them afterward, or both merge in the same cycle. |

---

## Success Criteria

1. **orjson PR:**
   - Zero `import json` or `import orjson` remaining in `miniautogen/stores/`, `miniautogen/core/contracts/`, and `miniautogen/cli/output.py` -- all serialization goes through `miniautogen._json`.
   - `miniautogen/_json.py` shim exists with `dumps()` / `loads()` and automatic stdlib fallback.
   - All existing tests pass with orjson as the serializer.
   - Pydantic models use `MiniAutoGenBaseModel` with orjson-backed `model_json_loads` / `model_json_dumps`.

2. **uv PR:**
   - `poetry.lock` removed; `uv.lock` committed.
   - `uv sync --frozen --all-extras` succeeds from a clean checkout.
   - `pyproject.toml` validates as PEP 621 (`uv` does not emit warnings).
   - All existing tests pass via `uv run pytest`.
   - **PEP 621 validation checklist** (all must pass before merge):
     - [ ] `uv lock` completes without errors or warnings.
     - [ ] `uv sync --all-extras` installs all dependencies including optional groups.
     - [ ] `uv run python -c "import miniautogen"` succeeds (package is importable).
     - [ ] `uv run pip install --dry-run .` succeeds (standard tooling can parse the metadata).
     - [ ] `uv run pytest` — full test suite passes.
     - [ ] `uv run ruff check .` — no new lint violations.
     - [ ] `uv run mypy miniautogen/` — no new type errors.

3. **deepdiff PR:**
   - At least 6 immutability tests (see Section 3.3) pass.
   - The `ExecutionEvent.infer_run_id_from_payload` mutation is documented as a known violation (test marked `xfail` or the validator is refactored in-PR).
   - `assert_no_mutation` helper is available in `tests/conftest.py`.

---

## Estimated Effort

| PR | Size | Estimated Time | Dependencies |
|----|------|---------------|--------------|
| orjson Integration | Small--Medium | 2--3 hours | None |
| uv Migration | Small | 1--2 hours | None |
| deepdiff QA Tests | Small--Medium | 2--3 hours | None (can reference orjson or stdlib json) |
| **Total** | | **5--8 hours** | All three are independent |
