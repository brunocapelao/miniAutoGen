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

#### 1.3 Store Layer -- Replace `import json`

All `json.dumps` / `json.loads` calls in the store layer must switch to `orjson.dumps` / `orjson.loads`. orjson returns `bytes`, not `str`, so each call-site needs a `.decode()` on the dumps side.

| File | Lines affected | Change |
|------|---------------|--------|
| `miniautogen/stores/sqlalchemy_checkpoint_store.py` | 1, 46, 51, 61, 78 | `import json` -> `import orjson`; `json.dumps(x)` -> `orjson.dumps(x).decode()`; `json.loads(x)` -> `orjson.loads(x)` |
| `miniautogen/stores/sqlalchemy_run_store.py` | 1, 46, 51, 61, 72 | Same pattern |
| `miniautogen/stores/sqlalchemy.py` | 49, 65 | Same pattern |
| `miniautogen/app/notebook_cache.py` | 21, 26 | Same pattern |
| `miniautogen/backends/cli/driver.py` | 107 | Same pattern |
| `miniautogen/pipeline/components/components.py` | 169 | `json.loads` -> `orjson.loads` |
| `miniautogen/cli/output.py` | 33 | `json.dumps(data, indent=2, default=str)` -> `orjson.dumps(data, option=orjson.OPT_INDENT_2).decode()` |

#### 1.4 Structlog Processor

Add an orjson-backed JSON renderer to the structlog pipeline so that log output also benefits.

- **File:** `miniautogen/observability/logging.py`
- In `configure_logging`, add `structlog.processors.JSONRenderer(serializer=orjson.dumps)` to the processor chain (or use `orjson.dumps` as the `serializer` kwarg if rendering JSON logs).
- This is only relevant when the application configures JSON-formatted log output (production). For local dev, the default console renderer remains.

#### 1.5 Dependency Declaration

- **File:** `pyproject.toml`
- Add `orjson = ">=3.10.0"` to `[tool.poetry.dependencies]` (or the PEP 621 equivalent after uv migration).

#### 1.6 Expected Performance Impact

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

No GitHub Actions workflow files exist yet in the repository. When CI is configured, the workflow should:

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
| `.github/workflows/*.yml` | Update when created |
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
| orjson wheels unavailable for a target platform | Low | orjson publishes wheels for Linux/macOS/Windows on x86_64 and aarch64. Pure-Python fallback: keep `import json` behind a try/except in a `miniautogen/core/contracts/_json.py` shim. |
| orjson `bytes` return type causes `TypeError` at call-sites | Medium | Every `orjson.dumps()` must be followed by `.decode()` when a `str` is expected. Grep-and-replace is mechanical but must not miss a site. CI type-checking (`mypy`) will catch mismatches. |
| uv migration breaks editable installs for contributors | Low | `uv sync` supports editable installs natively. Document the one-time migration step in the PR description. |
| uv lockfile format changes between versions | Low | Pin uv version in CI (`astral-sh/setup-uv@v4` with `version:` input). |
| deepdiff false positives from floating-point or datetime precision | Low | Use `significant_digits` and `truncate_datetime` parameters where needed. |
| Ordering: orjson PR must merge before deepdiff round-trip tests reference orjson | Low | deepdiff tests can use stdlib `json` initially. The orjson PR can update them afterward, or both merge in the same cycle. |

---

## Success Criteria

1. **orjson PR:**
   - Zero `import json` remaining in `miniautogen/stores/`, `miniautogen/core/contracts/`, and `miniautogen/cli/output.py`.
   - All existing tests pass with orjson as the serializer.
   - Pydantic models use `MiniAutoGenBaseModel` with orjson-backed `model_json_loads` / `model_json_dumps`.

2. **uv PR:**
   - `poetry.lock` removed; `uv.lock` committed.
   - `uv sync --frozen --all-extras` succeeds from a clean checkout.
   - `pyproject.toml` validates as PEP 621 (`uv` does not emit warnings).
   - All existing tests pass via `uv run pytest`.

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
