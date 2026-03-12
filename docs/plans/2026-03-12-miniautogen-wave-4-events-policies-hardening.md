# MiniAutoGen Wave 4 Events Policies and Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the Wave 4 architecture slice for canonical events, observability baseline, policy categories, compatibility governance markers, and hardening quality gates without destabilizing the earlier waves.

**Architecture:** This wave assumes the earlier contracts, runner, compatibility bridges, adapters, and store scaffolding already exist. The work adds canonical event publication, structured logging, policy boundaries, explicit public stability markers, and a hardening layer of tests and typing so the runtime becomes operable and governable without prematurely coupling to full OpenTelemetry instrumentation.

**Tech Stack:** Python 3.10+, Pydantic v2, pytest, pytest-asyncio, Hypothesis, Ruff, MyPy, structlog, Tenacity

---

## Wave Scope

- canonical execution event types
- event publication and in-memory sinks
- structured logging baseline
- policy category scaffolding
- compatibility governance markers
- hardening tests and static typing

## Out of Scope

- full OpenTelemetry exporter wiring
- MCP integration
- advanced budgets or permission enforcement
- external dashboards or tracing backends

## Preconditions

- `RunContext`, `RunResult`, and `ExecutionEvent` contracts exist
- `PipelineRunner` exists and can run current pipelines via compatibility bridges
- regression suite from Wave 1 exists and is green

### Task 1: Complete Canonical Event Taxonomy

**Files:**
- Modify: `miniautogen/core/events/types.py`
- Modify: `miniautogen/core/contracts/events.py`
- Create: `tests/core/events/test_event_taxonomy.py`
- Create: `tests/core/events/test_execution_event_model.py`

**Step 1: Write failing tests for the full event taxonomy**

```python
from miniautogen.core.events.types import EventType


def test_event_taxonomy_contains_operational_events():
    assert EventType.COMPONENT_RETRIED.value == "component_retried"
    assert EventType.CHECKPOINT_SAVED.value == "checkpoint_saved"
    assert EventType.POLICY_APPLIED.value == "policy_applied"


def test_event_taxonomy_contains_terminal_run_events():
    assert EventType.RUN_CANCELLED.value == "run_cancelled"
    assert EventType.RUN_TIMED_OUT.value == "run_timed_out"
```

**Step 2: Run event taxonomy tests to verify failure**

Run: `PYTHONPATH=. pytest tests/core/events/test_event_taxonomy.py -q`
Expected: FAIL because the full taxonomy is not implemented yet.

**Step 3: Implement the canonical event type set**

```python
from enum import Enum


class EventType(str, Enum):
    RUN_STARTED = "run_started"
    RUN_FINISHED = "run_finished"
    RUN_CANCELLED = "run_cancelled"
    RUN_TIMED_OUT = "run_timed_out"
    COMPONENT_STARTED = "component_started"
    COMPONENT_FINISHED = "component_finished"
    COMPONENT_SKIPPED = "component_skipped"
    COMPONENT_RETRIED = "component_retried"
    TOOL_INVOKED = "tool_invoked"
    TOOL_SUCCEEDED = "tool_succeeded"
    TOOL_FAILED = "tool_failed"
    CHECKPOINT_SAVED = "checkpoint_saved"
    CHECKPOINT_RESTORED = "checkpoint_restored"
    ADAPTER_FAILED = "adapter_failed"
    VALIDATION_FAILED = "validation_failed"
    POLICY_APPLIED = "policy_applied"
    BUDGET_EXCEEDED = "budget_exceeded"
```

**Step 4: Add a minimal typed execution event model**

```python
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExecutionEvent(BaseModel):
    type: str
    timestamp: datetime
    run_id: str
    correlation_id: str
    scope: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
```

**Step 5: Run event model tests**

Run: `PYTHONPATH=. pytest tests/core/events/test_event_taxonomy.py tests/core/events/test_execution_event_model.py -q`
Expected: PASS

**Step 6: Commit**

```bash
git add miniautogen/core/events/types.py miniautogen/core/contracts/events.py tests/core/events
git commit -m "feat: complete canonical event taxonomy for runtime operations"
```

### Task 2: Add EventSink Implementations and Runner Publishing Hooks

**Files:**
- Modify: `miniautogen/core/events/event_sink.py`
- Modify: `miniautogen/core/runtime/pipeline_runner.py`
- Create: `tests/core/events/test_event_sink.py`
- Create: `tests/core/runtime/test_runner_event_publication.py`

**Step 1: Write failing tests for event sink behavior**

```python
import pytest

from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.events.types import EventType


@pytest.mark.asyncio
async def test_in_memory_event_sink_records_published_events():
    sink = InMemoryEventSink()
    await sink.publish({"type": EventType.RUN_STARTED.value})

    assert len(sink.events) == 1
    assert sink.events[0]["type"] == EventType.RUN_STARTED.value
```

**Step 2: Run event sink tests**

Run: `PYTHONPATH=. pytest tests/core/events/test_event_sink.py -q`
Expected: FAIL if sink implementation is missing or incomplete.

**Step 3: Implement minimal sink types**

```python
from typing import Protocol, Any


class EventSink(Protocol):
    async def publish(self, event: Any) -> None:
        ...


class InMemoryEventSink:
    def __init__(self):
        self.events = []

    async def publish(self, event):
        self.events.append(event)


class NullEventSink:
    async def publish(self, event):
        return None
```

**Step 4: Publish runner start and finish events**

```python
await sink.publish({"type": EventType.RUN_STARTED.value, "run_id": run_id})
result = await self.run_pipeline(pipeline, state)
await sink.publish({"type": EventType.RUN_FINISHED.value, "run_id": run_id})
```

**Step 5: Run event sink and runner tests**

Run: `PYTHONPATH=. pytest tests/core/events/test_event_sink.py tests/core/runtime/test_runner_event_publication.py -q`
Expected: PASS

**Step 6: Commit**

```bash
git add miniautogen/core/events/event_sink.py miniautogen/core/runtime/pipeline_runner.py tests/core/events tests/core/runtime
git commit -m "feat: add event sinks and runner event publication hooks"
```

### Task 3: Add Structured Logging Baseline Without OTel Coupling

**Files:**
- Create: `miniautogen/observability/__init__.py`
- Create: `miniautogen/observability/logging.py`
- Modify: `miniautogen/chat/chatadmin.py`
- Modify: `miniautogen/pipeline/components/components.py`
- Create: `tests/observability/test_structured_logging.py`

**Step 1: Write failing tests for structured logger configuration**

```python
from miniautogen.observability.logging import get_logger


def test_get_logger_returns_bound_logger():
    logger = get_logger("miniautogen.test")
    assert logger is not None
```

**Step 2: Run logging tests**

Run: `PYTHONPATH=. pytest tests/observability/test_structured_logging.py -q`
Expected: FAIL because observability module does not exist yet.

**Step 3: Implement minimal structlog wrapper**

```python
import logging
import structlog


def configure_logging():
    logging.basicConfig(level=logging.INFO)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


def get_logger(name: str):
    return structlog.get_logger(name)
```

**Step 4: Replace ad hoc prints or direct logger creation in orchestration paths**

```python
self.logger = get_logger(__name__).bind(agent_id=self.agent_id)
```

Keep this as a baseline. Do not add OpenTelemetry exporters in this task.

**Step 5: Run logging and regression tests**

Run: `PYTHONPATH=. pytest tests/observability/test_structured_logging.py tests/regression -q`
Expected: PASS

**Step 6: Commit**

```bash
git add miniautogen/observability miniautogen/chat/chatadmin.py miniautogen/pipeline/components/components.py tests/observability
git commit -m "feat: add structured logging baseline for runtime observability"
```

### Task 4: Introduce Explicit Policy Categories and Retry Policy Surface

**Files:**
- Create: `miniautogen/policies/__init__.py`
- Create: `miniautogen/policies/execution.py`
- Create: `miniautogen/policies/retry.py`
- Create: `miniautogen/policies/validation.py`
- Create: `miniautogen/policies/budget.py`
- Create: `miniautogen/policies/permission.py`
- Create: `tests/policies/test_policy_categories.py`
- Create: `tests/policies/test_retry_policy.py`

**Step 1: Write failing tests for policy type boundaries**

```python
from miniautogen.policies.execution import ExecutionPolicy
from miniautogen.policies.retry import RetryPolicy


def test_execution_policy_exposes_timeout_configuration():
    policy = ExecutionPolicy(timeout_seconds=5)
    assert policy.timeout_seconds == 5


def test_retry_policy_defaults_to_disabled_retries():
    policy = RetryPolicy(max_attempts=1)
    assert policy.max_attempts == 1
```

**Step 2: Run policy tests**

Run: `PYTHONPATH=. pytest tests/policies -q`
Expected: FAIL because policy modules do not exist yet.

**Step 3: Implement minimal declarative policy classes**

```python
from dataclasses import dataclass


@dataclass
class ExecutionPolicy:
    timeout_seconds: float | None = None


@dataclass
class RetryPolicy:
    max_attempts: int = 1
```

Keep policy classes declarative in this wave. Do not let them turn into a second runtime.

**Step 4: Add a thin Tenacity integration seam without global auto-retry**

```python
def build_retrying_call(policy: RetryPolicy):
    ...
```

The function may return a callable wrapper or a retry configuration object, but it must stay outside `Agent`, `ChatAdmin`, and the core contracts.

**Step 5: Run policy tests**

Run: `PYTHONPATH=. pytest tests/policies -q`
Expected: PASS

**Step 6: Commit**

```bash
git add miniautogen/policies tests/policies
git commit -m "feat: add explicit policy categories and retry seam"
```

### Task 5: Add Public Stability Markers and Compatibility Governance Helpers

**Files:**
- Modify: `miniautogen/__init__.py`
- Create: `miniautogen/compat/public_api.py`
- Create: `tests/compat/test_public_api_markers.py`

**Step 1: Write failing tests for public stability markers**

```python
from miniautogen.compat.public_api import (
    STABILITY_STABLE,
    STABILITY_EXPERIMENTAL,
    STABILITY_INTERNAL,
)


def test_stability_markers_are_available():
    assert STABILITY_STABLE == "stable"
    assert STABILITY_EXPERIMENTAL == "experimental"
    assert STABILITY_INTERNAL == "internal"
```

**Step 2: Run compatibility marker tests**

Run: `PYTHONPATH=. pytest tests/compat/test_public_api_markers.py -q`
Expected: FAIL because marker module does not exist yet.

**Step 3: Implement compatibility metadata helpers**

```python
STABILITY_STABLE = "stable"
STABILITY_EXPERIMENTAL = "experimental"
STABILITY_INTERNAL = "internal"
```

Optionally add helper decorators or metadata registries only if they stay simple and do not rewrite runtime behavior.

**Step 4: Export markers from the package root only if stable**

```python
from miniautogen.compat.public_api import STABILITY_STABLE
```

**Step 5: Run compatibility tests**

Run: `PYTHONPATH=. pytest tests/compat/test_public_api_markers.py -q`
Expected: PASS

**Step 6: Commit**

```bash
git add miniautogen/__init__.py miniautogen/compat/public_api.py tests/compat
git commit -m "feat: add public stability markers for compatibility governance"
```

### Task 6: Harden the Wave with Property Tests, MyPy Baseline, and Documentation Backlog

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/properties/test_event_payloads.py`
- Create: `tests/properties/test_policy_models.py`
- Create: `docs/plans/backlog/wave-4-events-policies-hardening.md`

**Step 1: Write failing property-based tests for event and policy invariants**

```python
from hypothesis import given, strategies as st


@given(st.text(min_size=1))
def test_event_type_payload_accepts_non_empty_type(event_type: str):
    assert isinstance(event_type, str)
```

Add a real invariant-backed property test for event payload shape or policy defaults once the target classes exist.

**Step 2: Run property tests**

Run: `PYTHONPATH=. pytest tests/properties -q`
Expected: FAIL initially because property test files do not exist yet.

**Step 3: Add MyPy baseline configuration**

```toml
[tool.mypy]
python_version = "3.10"
warn_unused_ignores = true
warn_redundant_casts = true
```

**Step 4: Create a wave-specific backlog doc with definition of done**

```md
# Wave 4 Events Policies and Hardening

- Epic: events and observability baseline
- Epic: policy category scaffolding
- Epic: compatibility governance markers
- Done when:
  - canonical event taxonomy is published
  - event sink exists
  - structured logging baseline is active
  - policy categories are present
  - MyPy baseline and property tests are in place
```

**Step 5: Run wave hardening checks**

Run: `PYTHONPATH=. pytest tests/observability tests/policies tests/compat tests/properties -q`
Expected: PASS

Run: `python -m mypy miniautogen/core/events miniautogen/policies miniautogen/compat`
Expected: PASS or only known baseline issues explicitly documented.

**Step 6: Commit**

```bash
git add pyproject.toml tests/properties docs/plans/backlog/wave-4-events-policies-hardening.md
git commit -m "test: harden wave 4 with property tests and typing baseline"
```

## Wave 4 Exit Criteria

- canonical event taxonomy implemented and tested
- event publication baseline exists in runner paths
- structured logging baseline active without full OTel dependency
- policy categories defined without policy blob behavior
- compatibility governance markers exposed and tested
- property tests and MyPy baseline added for the touched packages

## Final Verification

Run:

```bash
PYTHONPATH=. pytest tests/core/events tests/core/runtime tests/observability tests/policies tests/compat tests/properties -q
PYTHONPATH=. pytest tests/regression -q
python -m mypy miniautogen/core/events miniautogen/core/runtime miniautogen/observability miniautogen/policies miniautogen/compat
```

Expected:

- Wave 4 packages behave as specified
- current behavior remains intact
- governance and hardening baselines are active
