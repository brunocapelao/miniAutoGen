# MiniAutoGen Master Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Organize the approved MiniAutoGen architecture transformation into execution waves with clear dependencies, ownership boundaries, and readiness criteria.

**Architecture:** The transformation is intentionally staged. Wave 1 freezes behavior and introduces typed contracts; Wave 2 centralizes runtime and compatibility; Wave 3 formalizes adapters and stores; Wave 4 adds events, policies, compatibility governance, and hardening. Each wave is independently plannable and collectively aligned to the target architecture.

**Tech Stack:** Python 3.10+, Pydantic v2, pytest, pytest-asyncio, Ruff, MyPy, AnyIO, HTTPX, LiteLLM, SQLAlchemy 2.x, structlog

---

## Wave Map

| Wave | Scope | Primary Packages | Depends On |
| --- | --- | --- | --- |
| 1 | Safety net + contracts | `tests/regression`, `miniautogen/core/contracts`, `miniautogen/core/events` | none |
| 2 | Runtime + compatibility | `miniautogen/core/runtime`, `miniautogen/compat`, `miniautogen/chat` | Wave 1 |
| 3 | Adapters + stores | `miniautogen/adapters`, `miniautogen/stores`, `miniautogen/storage` | Waves 1-2 |
| 4 | Events, policies, hardening | `miniautogen/observability`, `miniautogen/policies`, `miniautogen/compat` | Waves 1-3 |

## Execution Order

1. Execute Wave 1 to freeze baseline behavior and stabilize core contracts.
2. Execute Wave 2 to centralize runtime without breaking public behavior.
3. Execute Wave 3 to formalize external boundaries and persistence.
4. Execute Wave 4 to complete events, policies, governance, and engineering hardening.

## Ready-to-Start Conditions

### Wave 1

- current repository is green or understood well enough to freeze behavior;
- no pending architectural rename decisions for `RunContext`, `RunResult`, or `ExecutionEvent`.

### Wave 2

- Wave 1 contract models and regression tests exist;
- compatibility bridge strategy is agreed.

### Wave 3

- runner shape is stable enough to integrate adapter and store boundaries;
- event model is stable enough to correlate persistence and external calls.

### Wave 4

- adapter and store seams exist;
- runtime emits canonical events or is ready to emit them;
- governance markers are approved.

## Done Conditions

- Wave 1 done: regression safety net + contract packages + event taxonomy exist and are tested.
- Wave 2 done: `PipelineRunner` exists, current pipeline behavior is preserved through compatibility facades, and regression tests remain green.
- Wave 3 done: provider-neutral adapters and initial store family exist with passing tests and no vendor leakage into core contracts.
- Wave 4 done: event sink, policies, compatibility markers, and hardening work are in place with explicit acceptance checks.

## Deliverables

- [Wave 1 Foundation Plan](2026-03-12-miniautogen-wave-1-foundation.md)
- [Wave 2 Runtime and Compatibility Plan](2026-03-12-miniautogen-wave-2-runtime-compat.md)
- [Wave 3 Adapters and Stores Plan](2026-03-12-miniautogen-wave-3-adapters-stores.md)
- [Wave 4 Events, Policies, and Hardening Plan](2026-03-12-miniautogen-wave-4-events-policies-hardening.md)

## Verification Sweep

After each wave:

```bash
PYTHONPATH=. pytest -q
```

After all waves:

```bash
PYTHONPATH=. pytest -q
PYTHONPATH=. pytest tests/regression tests/core tests/stores tests/adapters tests/policies tests/observability -q
```
