# MiniAutoGen Architecture

## Positioning

MiniAutoGen is a microkernel for multi-agent coordination. It provides three built-in coordination modes -- workflow, deliberation, and agentic loop -- that can be composed in sequence via a composite runtime. The kernel handles execution context, event emission, policy enforcement, and result propagation, while agents remain simple protocol implementations with no framework coupling.

## Architecture Layers

```
Layer 4  Public API          miniautogen/api.py
Layer 3  Canonical Patterns  (planned, not yet implemented)
Layer 2  Coordination Modes  WorkflowRuntime, DeliberationRuntime, AgenticLoopRuntime, CompositeRuntime
Layer 1  Kernel              PipelineRunner, RunContext, RunResult, stores, events, policies, adapters
```

**Layer 1 -- Kernel.** The execution foundation. `PipelineRunner` orchestrates component execution. `RunContext` carries typed state through a run. `RunResult` captures terminal output. Policies (budget, validation, permission, retry) enforce cross-cutting constraints. Events (`ExecutionEvent`) provide observability. Stores and adapters handle persistence and external integration.

**Layer 2 -- Coordination Modes.** Four runtimes that implement the `CoordinationMode` protocol, each accepting a typed plan:

- `WorkflowRuntime` executes `WorkflowPlan` (sequential steps, optional fan-out and synthesis)
- `DeliberationRuntime` executes `DeliberationPlan` (contribution, peer review, consolidation cycles)
- `AgenticLoopRuntime` executes `AgenticLoopPlan` (router-driven conversational turns)
- `CompositeRuntime` chains multiple modes in sequence (e.g., workflow -> deliberation -> workflow)

**Layer 3 -- Canonical Patterns.** Reserved for reusable multi-agent patterns built on top of Layers 1-2. The `WorkflowStep.component_name` and `WorkflowStep.config` fields exist to support this layer, but no canonical patterns have been implemented yet.

**Layer 4 -- Public API.** `miniautogen/api.py` re-exports all essential types. This is the only import path external consumers should use.

## Module Map

| Directory | Purpose |
|---|---|
| `miniautogen/core/contracts/` | Pydantic models and Protocol definitions (the type system) |
| `miniautogen/core/runtime/` | Coordination mode implementations and kernel runner |
| `miniautogen/core/events/` | Event type constants |
| `miniautogen/policies/` | Cross-cutting policy enforcement (budget, validation, permission, retry) |
| `miniautogen/pipeline/` | Pipeline and PipelineComponent abstractions |
| `miniautogen/adapters/` | External integration adapters |
| `miniautogen/stores/` | Persistence layer |
| `miniautogen/observability/` | Logging infrastructure |
| `miniautogen/llms/` | LLM provider integrations |
| `miniautogen/chat/` | Legacy chat infrastructure |
| `miniautogen/agent/` | Legacy agent implementations |
| `miniautogen/compat/` | Backward-compatibility shims |
| `miniautogen/app/` | Application-level entry points |

## Coordination Modes

### Workflow

Sequential or parallel execution of discrete steps. Each step maps to an agent by `agent_id`. Supports fan-out (parallel execution of all steps) and an optional synthesis agent that consolidates results.

Key types: `WorkflowPlan`, `WorkflowStep`, `WorkflowAgent`

### Deliberation

Multi-round deliberation with structured peer review. The cycle is: contribution -> peer review -> leader consolidation -> sufficiency check -> iterate or finalize. Each round produces `Contribution` and `Review` objects. The leader decides when the deliberation is sufficient.

Key types: `DeliberationPlan`, `Contribution`, `Review`, `ResearchOutput`, `PeerReview`, `DeliberationState`, `FinalDocument`, `DeliberationAgent`

### Agentic Loop

Router-driven conversational loop. A router agent inspects conversation history and selects the next participant via `RouterDecision`. The loop terminates on explicit termination, stagnation detection, max turns, or budget exhaustion.

Key types: `AgenticLoopPlan`, `RouterDecision`, `ConversationPolicy`, `AgenticLoopState`, `ConversationalAgent`

### Composite

Chains multiple coordination modes in sequence. Each `CompositionStep` holds a mode, a typed plan, and optional input/output mappers. The output of one step feeds into the next via `RunContext.with_previous_result()`.

Key types: `CompositeRuntime`, `CompositionStep`, `SubrunRequest`

## Backend Driver Abstraction

The `backends/` package provides a unified interface for external agent backends:

- **`AgentDriver` ABC** — 6 abstract methods: `start_session`, `send_turn`, `cancel_turn`, `list_artifacts`, `close_session`, `capabilities`
- **`AgentAPIDriver`** — HTTP bridge for OpenAI-compatible endpoints (Gemini CLI gateway, LiteLLM, vLLM)
- **`BackendResolver`** — Config-driven driver instantiation with factory registry
- **`SessionManager`** — Session lifecycle state machine (7 states)

Events follow a two-layer taxonomy: drivers emit unprefixed canonical events (`message_delta`, `turn_completed`), while the core event bus uses `BACKEND_`-prefixed `EventType` members.

## Agent Protocols

Agents are defined as `typing.Protocol` classes with `@runtime_checkable`. No base class inheritance required.

| Protocol | Required Methods | Used By |
|---|---|---|
| `WorkflowAgent` | `async process(input) -> Any` | WorkflowRuntime |
| `DeliberationAgent` | `async contribute(topic) -> Contribution`, `async review(target_id, contribution) -> Review` | DeliberationRuntime |
| `ConversationalAgent` | `async reply(conversation_history) -> str`, `async route(conversation_history) -> RouterDecision` | AgenticLoopRuntime |

## Key Contracts

| Type | Module | Purpose |
|---|---|---|
| `RunContext` | `core/contracts/run_context` | Typed execution context for a run (run_id, correlation_id, state, payload, timeout) |
| `RunResult` | `core/contracts/run_result` | Terminal result (run_id, status, output, error, metadata) |
| `Message` | `core/contracts/message` | A message exchanged between agents (sender_id, content, timestamp) |
| `Conversation` | `core/contracts/conversation` | Immutable-style typed conversation history |
| `ExecutionEvent` | `core/contracts/events` | Canonical event emitted by runtimes (type, timestamp, correlation_id, payload) |
| `CoordinationPlan` | `core/contracts/coordination` | Base model for all typed plans |
| `CoordinationKind` | `core/contracts/coordination` | Enum: `workflow`, `deliberation`, `agentic_loop` |
| `CoordinationMode` | `core/contracts/coordination` | Protocol that all runtimes implement (`run(agents, context, plan) -> RunResult`) |
| `ConversationPolicy` | `core/contracts/agentic_loop` | Shared policy for turn limits, budget caps, timeouts, stagnation detection |
| `SubrunRequest` | `core/contracts/coordination` | Request for nested coordination (mode within mode) |

## Quick Reference

```python
# Runtimes
from miniautogen.api import WorkflowRuntime, DeliberationRuntime, AgenticLoopRuntime, CompositeRuntime

# Plans
from miniautogen.api import WorkflowPlan, WorkflowStep, DeliberationPlan, AgenticLoopPlan

# Agent protocols
from miniautogen.api import WorkflowAgent, DeliberationAgent, ConversationalAgent

# Core types
from miniautogen.api import RunContext, RunResult, Message, Conversation, ExecutionEvent

# Coordination
from miniautogen.api import CoordinationKind, CoordinationPlan, CompositionStep, SubrunRequest

# Deliberation types
from miniautogen.api import Contribution, Review

# Agentic loop types
from miniautogen.api import RouterDecision, ConversationPolicy, AgenticLoopState

# Policies
from miniautogen.api import BudgetTracker, BudgetExceededError

# Pipeline
from miniautogen.api import Pipeline, PipelineComponent
```

## Architectural Decisions

| ID | Decision | Rationale |
|---|---|---|
| DA-1 | Protocols over base classes | Structural typing via `typing.Protocol` with `@runtime_checkable`. Agents have zero framework coupling -- any object satisfying the method signatures works. |
| DA-2 | Typed plans over kwargs | Each coordination mode declares its plan type (`WorkflowPlan`, `DeliberationPlan`, `AgenticLoopPlan`). Eliminates `**kwargs` escape hatches and enables static analysis. |
| DA-3 | Immutable-style Pydantic models | All contracts are Pydantic `BaseModel` instances. `Conversation.add_message()` returns a new object rather than mutating. |
| DA-4 | Composition over inheritance for runtimes | `CompositeRuntime` chains modes in sequence rather than requiring a monolithic runtime. Each mode is independent and testable. |
| DA-5 | Single public API surface | `miniautogen/api.py` is the only sanctioned import path. Internal modules can be restructured without breaking consumers. |
| DA-6 | General contracts with specialized extensions | `Contribution`/`Review` are general-purpose; `ResearchOutput`/`PeerReview` extend them for research-specific use cases. New domains extend the base, not fork it. |
| DA-7 | Policy enforcement as separate layer | Budget, validation, permission, and retry policies live in `miniautogen/policies/`, decoupled from coordination logic. |
| DA-8 | Event-driven observability | All runtimes emit `ExecutionEvent` instances with correlation IDs. No logging-only observability -- events are structured data. |

## Legacy Coexistence

The `chat/`, `agent/`, and `compat/` packages contain the original MiniAutoGen implementation. They remain functional and are not deprecated yet. The new architecture (Layers 1-4 above) coexists alongside them. The `compat/` package provides shims for bridging legacy code to the new contracts where needed.
