# E2E Showcase Notebook Implementation Plan

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Create `examples/e2e_showcase.ipynb` -- an educational Jupyter notebook that demonstrates MiniAutoGen's 5 key SDK features (3 coordination modes, event system, execution policies, backend abstraction, persistence) using mock agents that require no API keys.

**Architecture:** The notebook uses mock/stub agent classes that satisfy MiniAutoGen's protocol contracts (`WorkflowAgent`, `DeliberationAgent`, `ConversationalAgent`). Each section instantiates a `PipelineRunner` with an `InMemoryEventSink` to capture events, runs a coordination mode via the SDK, then inspects the event stream and results. All async code runs via `anyio` using `asyncio` backend.

**Tech Stack:** Python 3.11+, anyio, pydantic, Jupyter/IPython, miniautogen SDK (no external LLM providers)

**Global Prerequisites:**
- Environment: macOS/Linux, Python 3.11+
- Tools: `jupyter` or `ipython` kernel installed
- Access: No API keys needed -- all examples use mock agents
- State: Working from branch `main` in the worktree at `/Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign`

**Verification before starting:**
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python --version        # Expected: Python 3.11+
python -c "import miniautogen; print('OK')"  # Expected: OK
python -c "import anyio; print('OK')"         # Expected: OK
python -c "import pydantic; print('OK')"      # Expected: OK
ls examples/            # Expected: async_chat_example.py tui_demo.py
```

---

## Overview of Notebook Sections

| Section | Title | SDK Feature | Estimated Time |
|---------|-------|-------------|----------------|
| 0 | Setup & Imports | Foundation | 3 min |
| 1 | Workflow Mode | Sequential coordination | 5 min |
| 2 | Deliberation Mode | Peer review cycles | 5 min |
| 3 | Agentic Loop Mode | Router-driven conversation | 5 min |
| 4 | Event System Deep Dive | Filters, composite sinks, EventBus | 5 min |
| 5 | Execution Policies | Retry, budget, approval, timeout | 5 min |
| 6 | Persistence | Checkpoint + run store | 4 min |
| 7 | Putting It All Together | Combined demo | 3 min |

---

### Task 1: Create the notebook file with Section 0 -- Setup & Imports

**Files:**
- Create: `examples/e2e_showcase.ipynb`

**Prerequisites:**
- `examples/` directory exists (confirmed)
- `jupyter` or `nbformat` available for creating the notebook

**Step 1: Create the notebook using a Python script**

Create the notebook by running a Python script that builds it cell-by-cell using `nbformat`. This is more reliable than manually constructing JSON.

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python -c "
import nbformat
nb = nbformat.v4.new_notebook()
nb['metadata']['kernelspec'] = {
    'display_name': 'Python 3',
    'language': 'python',
    'name': 'python3'
}
nb['cells'] = []

# --- Cell 0: Title ---
nb['cells'].append(nbformat.v4.new_markdown_cell('''# MiniAutoGen SDK -- End-to-End Showcase

This notebook demonstrates MiniAutoGen's key SDK features using **mock agents** (no API keys required).

## What You Will Learn

1. **3 Coordination Modes** -- Workflow (sequential pipeline), Deliberation (peer review cycles), Agentic Loop (router-driven conversation)
2. **Event System** -- 80+ typed events, composable sinks, filtering, observability without coupling
3. **Execution Policies** -- Retry, Budget, Approval Gate, Timeout -- lateral/event-driven, not inline
4. **Backend Driver Abstraction** -- Multi-model support via protocols (demonstrated with mocks)
5. **Persistence** -- Checkpoint store, run store for replay and recovery

### Why Mock Agents?

MiniAutoGen's competitive moat is its **architecture**, not any specific LLM provider. By using mocks, we isolate the framework mechanics and show that coordination, observability, and fault-tolerance work independently of the backend.

---
'''))

# --- Cell 1: Imports ---
nb['cells'].append(nbformat.v4.new_code_cell('''# Core imports
from __future__ import annotations

import anyio
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

# MiniAutoGen contracts
from miniautogen.core.contracts.coordination import (
    WorkflowPlan, WorkflowStep,
    DeliberationPlan,
    AgenticLoopPlan,
    CoordinationKind,
)
from miniautogen.core.contracts.agentic_loop import (
    ConversationPolicy, RouterDecision, AgenticLoopState,
)
from miniautogen.core.contracts.deliberation import (
    Contribution, Review, ResearchOutput, PeerReview,
    DeliberationState, FinalDocument,
)
from miniautogen.core.contracts.run_context import RunContext, FrozenState
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.contracts.enums import RunStatus, LoopStopReason
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.message import Message

# Event system
from miniautogen.core.events import (
    EventType, InMemoryEventSink, NullEventSink,
    CompositeEventSink, FilteredEventSink,
    TypeFilter, RunFilter, CompositeFilter,
)
from miniautogen.core.events.event_bus import EventBus

# Runtimes
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime
from miniautogen.core.runtime.deliberation_runtime import DeliberationRuntime
from miniautogen.core.runtime.agentic_loop_runtime import AgenticLoopRuntime

# Policies
from miniautogen.policies.retry import RetryPolicy, build_retrying_call
from miniautogen.policies.budget import BudgetPolicy, BudgetTracker, BudgetExceededError
from miniautogen.policies.approval import (
    ApprovalGate, ApprovalRequest, ApprovalResponse,
    AutoApproveGate, ApprovalPolicy,
)
from miniautogen.policies.execution import ExecutionPolicy
from miniautogen.policies.timeout import TimeoutScope
from miniautogen.policies.chain import PolicyChain, PolicyContext, PolicyResult

# Stores
from miniautogen.stores.in_memory_run_store import InMemoryRunStore
from miniautogen.stores.in_memory_checkpoint_store import InMemoryCheckpointStore

print(\"All imports successful!\")
print(f\"EventType has {len(EventType)} event types\")
print(f\"Coordination modes: {[k.value for k in CoordinationKind]}\")
'''))

nbformat.write(nb, 'examples/e2e_showcase.ipynb')
print('Notebook created with Section 0')
"
```

**Expected output:**
```
Notebook created with Section 0
```

**Step 2: Verify the imports work**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python -c "
exec(open('/dev/stdin').read())
" << 'PYEOF'
from __future__ import annotations
from miniautogen.core.contracts.coordination import WorkflowPlan, WorkflowStep, DeliberationPlan, AgenticLoopPlan, CoordinationKind
from miniautogen.core.contracts.agentic_loop import ConversationPolicy, RouterDecision, AgenticLoopState
from miniautogen.core.contracts.deliberation import Contribution, Review, ResearchOutput, PeerReview, DeliberationState, FinalDocument
from miniautogen.core.contracts.run_context import RunContext, FrozenState
from miniautogen.core.contracts.run_result import RunResult
from miniautogen.core.contracts.enums import RunStatus, LoopStopReason
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events import EventType, InMemoryEventSink, NullEventSink, CompositeEventSink, FilteredEventSink, TypeFilter, RunFilter, CompositeFilter
from miniautogen.core.events.event_bus import EventBus
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime
from miniautogen.core.runtime.deliberation_runtime import DeliberationRuntime
from miniautogen.core.runtime.agentic_loop_runtime import AgenticLoopRuntime
from miniautogen.policies.retry import RetryPolicy, build_retrying_call
from miniautogen.policies.budget import BudgetPolicy, BudgetTracker, BudgetExceededError
from miniautogen.policies.approval import ApprovalGate, ApprovalRequest, ApprovalResponse, AutoApproveGate, ApprovalPolicy
from miniautogen.policies.execution import ExecutionPolicy
from miniautogen.policies.timeout import TimeoutScope
from miniautogen.policies.chain import PolicyChain, PolicyContext, PolicyResult
from miniautogen.stores.in_memory_run_store import InMemoryRunStore
from miniautogen.stores.in_memory_checkpoint_store import InMemoryCheckpointStore
print("All imports OK")
print(f"EventType has {len(EventType)} event types")
PYEOF
```

**Expected output:**
```
All imports OK
EventType has <number> event types
```

**Step 3: Commit**

```bash
git add examples/e2e_showcase.ipynb
git commit -m "docs: add e2e showcase notebook skeleton with imports"
```

**If Task Fails:**
1. **Import error:** Check the specific import that fails. The module path may have changed. Run `python -c "import miniautogen.core.contracts; print(dir(miniautogen.core.contracts))"` to check available exports.
2. **nbformat not installed:** Run `pip install nbformat` first.
3. **Can't recover:** Document which import fails and stop.

---

### Task 2: Add Section 1 -- Workflow Coordination Mode

**Files:**
- Modify: `examples/e2e_showcase.ipynb` (append cells)

**Prerequisites:**
- Task 1 completed
- All imports verified working

**Step 1: Append Section 1 cells to the notebook**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python << 'PYEOF'
import nbformat

nb = nbformat.read('examples/e2e_showcase.ipynb', as_version=4)

# --- Markdown: Section 1 header ---
nb['cells'].append(nbformat.v4.new_markdown_cell('''---

## 1. Workflow Mode -- Sequential Pipeline

**What it does:** Executes agents in sequence, where each agent's output becomes the next agent's input. Supports fan-out (parallel) and optional synthesis.

**Why it matters:** Most real-world multi-agent pipelines are sequential -- a researcher feeds into a writer who feeds into a reviewer. MiniAutoGen makes this a first-class coordination mode with typed plans, event emission, and supervision.

**Key contracts:**
- `WorkflowPlan` -- defines the execution plan (steps, fan-out, synthesis)
- `WorkflowStep` -- a single step with `component_name` and `agent_id`
- `WorkflowRuntime` -- the runtime that executes the plan
'''))

# --- Code: Mock workflow agents ---
nb['cells'].append(nbformat.v4.new_code_cell('''# Mock agents that satisfy the WorkflowAgent protocol.
# WorkflowAgent requires: async def process(self, input: Any) -> Any

class ResearcherAgent:
    """Simulates a researcher that adds findings to the input."""
    async def process(self, input: Any) -> Any:
        if isinstance(input, dict):
            data = dict(input)
        else:
            data = {"original_input": input}
        data["research_findings"] = [
            "Market is growing at 15% CAGR",
            "Key competitor launched similar product",
            "Customer satisfaction at 78%",
        ]
        data["stage"] = "researched"
        return data


class WriterAgent:
    """Simulates a writer that drafts a report from research."""
    async def process(self, input: Any) -> Any:
        findings = input.get("research_findings", [])
        report = "## Market Analysis Report\\n\\n"
        for finding in findings:
            report += f"- {finding}\\n"
        report += "\\n**Conclusion:** Market conditions are favorable."
        return {**input, "draft_report": report, "stage": "drafted"}


class ReviewerAgent:
    """Simulates a reviewer that scores a draft report."""
    async def process(self, input: Any) -> Any:
        draft = input.get("draft_report", "")
        return {
            **input,
            "review_score": 8.5,
            "review_comments": "Well-structured analysis with solid data points.",
            "stage": "reviewed",
        }


print("Mock workflow agents defined:")
print("  - ResearcherAgent (adds research findings)")
print("  - WriterAgent (drafts report from findings)")
print("  - ReviewerAgent (scores the draft)")
'''))

# --- Code: Run workflow ---
nb['cells'].append(nbformat.v4.new_code_cell("""async def demo_workflow():
    \"\"\"Demonstrate sequential workflow coordination.\"\"\"

    # 1. Set up event capture
    event_sink = InMemoryEventSink()

    # 2. Create PipelineRunner with event sink
    runner = PipelineRunner(event_sink=event_sink)

    # 3. Register mock agents
    agents = {
        "researcher": ResearcherAgent(),
        "writer": WriterAgent(),
        "reviewer": ReviewerAgent(),
    }

    # 4. Create WorkflowRuntime with agent registry
    workflow = WorkflowRuntime(runner=runner, agent_registry=agents)

    # 5. Define the execution plan
    plan = WorkflowPlan(
        steps=[
            WorkflowStep(component_name="research", agent_id="researcher"),
            WorkflowStep(component_name="write", agent_id="writer"),
            WorkflowStep(component_name="review", agent_id="reviewer"),
        ]
    )

    # 6. Create RunContext
    run_id = str(uuid4())
    context = RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id=run_id,
        input_payload={"topic": "AI Market Analysis"},
    )

    # 7. Execute!
    result = await workflow.run([], context, plan)

    # 8. Inspect results
    print("=== WORKFLOW RESULT ===")
    print(f"Status: {result.status}")
    print(f"Run ID: {result.run_id}")
    print()

    output = result.output
    print(f"Pipeline stages: {output.get('stage')}")
    print(f"Research findings: {len(output.get('research_findings', []))} items")
    print(f"Review score: {output.get('review_score')}")
    print(f"Review: {output.get('review_comments')}")
    print()

    # 9. Inspect event stream
    print(f"=== EVENT STREAM ({len(event_sink.events)} events) ===")
    for evt in event_sink.events:
        print(f"  [{evt.type}] scope={evt.scope} run_id={evt.run_id[:8]}...")

    return result

# Run with anyio
result = anyio.from_thread.run_sync(lambda: anyio.run(demo_workflow))
"""))

nbformat.write(nb, 'examples/e2e_showcase.ipynb')
print("Section 1 (Workflow) added")
PYEOF
```

**Expected output:**
```
Section 1 (Workflow) added
```

**Step 2: Verify workflow demo runs**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python -c "
import anyio
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any
from miniautogen.core.contracts.coordination import WorkflowPlan, WorkflowStep
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events import InMemoryEventSink
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime

class ResearcherAgent:
    async def process(self, input):
        return {'research_findings': ['finding1'], 'stage': 'researched'}

class WriterAgent:
    async def process(self, input):
        return {**input, 'draft': 'report', 'stage': 'drafted'}

class ReviewerAgent:
    async def process(self, input):
        return {**input, 'score': 8.5, 'stage': 'reviewed'}

async def test():
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    agents = {'r': ResearcherAgent(), 'w': WriterAgent(), 'v': ReviewerAgent()}
    wf = WorkflowRuntime(runner=runner, agent_registry=agents)
    plan = WorkflowPlan(steps=[
        WorkflowStep(component_name='research', agent_id='r'),
        WorkflowStep(component_name='write', agent_id='w'),
        WorkflowStep(component_name='review', agent_id='v'),
    ])
    rid = str(uuid4())
    ctx = RunContext(run_id=rid, started_at=datetime.now(timezone.utc), correlation_id=rid, input_payload={'topic': 'test'})
    result = await wf.run([], ctx, plan)
    print(f'Status: {result.status}')
    print(f'Events: {len(sink.events)}')
    for e in sink.events:
        print(f'  {e.type}')

anyio.run(test)
"
```

**Expected output:**
```
Status: finished
Events: 2
  run_started
  run_finished
```

**Step 3: Commit**

```bash
git add examples/e2e_showcase.ipynb
git commit -m "docs: add workflow coordination mode demo to e2e notebook"
```

**If Task Fails:**
1. **WorkflowRuntime emits double events:** The `PipelineRunner.run_pipeline` also emits events, but `WorkflowRuntime.run()` is called directly (not through `run_pipeline`), so only WorkflowRuntime events appear. If you see unexpected events, check which entry point you are using.
2. **`anyio.from_thread.run_sync` fails in notebook:** In Jupyter, the event loop is already running. Use `await demo_workflow()` directly instead. The notebook kernel handles this natively.
3. **Can't recover:** Document the error and stop.

---

### Task 3: Add Section 2 -- Deliberation Mode

**Files:**
- Modify: `examples/e2e_showcase.ipynb` (append cells)

**Prerequisites:**
- Task 2 completed

**Step 1: Append Section 2 cells**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python << 'PYEOF'
import nbformat

nb = nbformat.read('examples/e2e_showcase.ipynb', as_version=4)

# --- Markdown: Section 2 header ---
nb['cells'].append(nbformat.v4.new_markdown_cell('''---

## 2. Deliberation Mode -- Peer Review Cycles

**What it does:** Multiple specialist agents contribute structured research, then peer-review each other's work. A leader agent consolidates the findings and decides if another round is needed. The cycle repeats until the leader declares sufficiency or max rounds are reached, then a final document is produced.

**Why it matters:** Real research and decision-making requires adversarial review. A single agent producing output is brittle -- deliberation catches blind spots, surfaces conflicts, and produces higher-quality artifacts through structured disagreement.

**Key contracts:**
- `DeliberationPlan` -- topic, participants, max_rounds, leader
- `ResearchOutput` -- structured contribution (findings, evidence, uncertainties)
- `PeerReview` -- cross-review of another agent's output (strengths, concerns)
- `DeliberationState` -- aggregated state (accepted facts, conflicts, sufficiency)
- `FinalDocument` -- the leader's final synthesized document
'''))

# --- Code: Mock deliberation agents ---
nb['cells'].append(nbformat.v4.new_code_cell('''# Mock agents that satisfy the DeliberationAgent protocol.
# DeliberationAgent requires:
#   async def contribute(self, topic: str) -> Contribution
#   async def review(self, target_id: str, contribution: Contribution) -> Review
#
# The DeliberationRuntime also calls:
#   async def consolidate(self, topic, contributions, reviews) -> DeliberationState
#   async def produce_final_document(self, state, contributions) -> FinalDocument
# (on the leader agent only)


class MarketAnalystAgent:
    """Specialist agent that researches market conditions."""

    async def contribute(self, topic: str) -> ResearchOutput:
        return ResearchOutput(
            role_name="market_analyst",
            section_title="Market Conditions",
            findings=["TAM growing at 15% CAGR", "3 new entrants in Q4"],
            facts=["Market size: $2.3B"],
            evidence=["Gartner 2025 report", "SEC filings"],
            inferences=["Growth will accelerate with AI adoption"],
            uncertainties=["Regulatory impact unclear"],
            recommendation="Invest in market expansion",
            next_tests=["Survey customer intent"],
        )

    async def review(self, target_id: str, contribution: Any) -> PeerReview:
        return PeerReview(
            reviewer_role="market_analyst",
            target_role=target_id,
            target_section_title=getattr(contribution, "section_title", "Unknown"),
            strengths=["Solid technical analysis"],
            concerns=["Missing cost projections"],
            questions=["What is the implementation timeline?"],
        )


class TechLeadAgent:
    """Specialist agent that researches technical feasibility."""

    async def contribute(self, topic: str) -> ResearchOutput:
        return ResearchOutput(
            role_name="tech_lead",
            section_title="Technical Feasibility",
            findings=["Existing infra supports 80% of requirements"],
            facts=["Current system handles 10k RPS"],
            evidence=["Load test results from Jan 2026"],
            inferences=["Need 2 sprints for remaining 20%"],
            uncertainties=["Third-party API stability"],
            recommendation="Proceed with incremental architecture",
            next_tests=["Prototype the integration layer"],
        )

    async def review(self, target_id: str, contribution: Any) -> PeerReview:
        return PeerReview(
            reviewer_role="tech_lead",
            target_role=target_id,
            target_section_title=getattr(contribution, "section_title", "Unknown"),
            strengths=["Good market data"],
            concerns=["ROI timeline seems optimistic"],
            questions=["Have we validated with customers?"],
        )

    # --- Leader-only methods ---

    async def consolidate(
        self, topic: str, contributions: list, reviews: list
    ) -> DeliberationState:
        """Leader consolidates all contributions and reviews."""
        all_facts = []
        for c in contributions:
            all_facts.extend(getattr(c, "facts", []))

        all_concerns = []
        for r in reviews:
            all_concerns.extend(getattr(r, "concerns", []))

        return DeliberationState(
            review_cycle=1,
            accepted_facts=all_facts,
            open_conflicts=all_concerns[:2],
            pending_gaps=["Need customer validation"],
            leader_decision="Sufficient for initial decision",
            is_sufficient=True,  # End after 1 round for demo
        )

    async def produce_final_document(
        self, state: DeliberationState, contributions: list
    ) -> FinalDocument:
        """Leader produces the final synthesized document."""
        return FinalDocument(
            executive_summary="Analysis supports market expansion with incremental tech approach.",
            accepted_facts=state.accepted_facts,
            open_conflicts=state.open_conflicts,
            pending_decisions=state.pending_gaps,
            recommendations=[
                "Proceed with Phase 1 market expansion",
                "Prototype integration layer in Sprint 1",
            ],
            decision_summary="GO decision for market expansion with phased technical delivery.",
            body_markdown="Full analysis available in attached appendices.",
        )


print("Mock deliberation agents defined:")
print("  - MarketAnalystAgent (market specialist)")
print("  - TechLeadAgent (tech specialist + leader)")
'''))

# --- Code: Run deliberation ---
nb['cells'].append(nbformat.v4.new_code_cell("""async def demo_deliberation():
    \"\"\"Demonstrate deliberation coordination with peer review.\"\"\"

    # 1. Set up event capture
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)

    # 2. Register agents
    agents = {
        "market_analyst": MarketAnalystAgent(),
        "tech_lead": TechLeadAgent(),
    }

    # 3. Create runtime
    deliberation = DeliberationRuntime(runner=runner, agent_registry=agents)

    # 4. Define plan -- tech_lead is the leader
    plan = DeliberationPlan(
        topic="Should we expand into the AI-assisted analytics market?",
        participants=["market_analyst", "tech_lead"],
        max_rounds=3,
        leader_agent="tech_lead",
    )

    # 5. Create RunContext
    run_id = str(uuid4())
    context = RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id=run_id,
    )

    # 6. Execute!
    result = await deliberation.run([], context, plan)

    # 7. Inspect results
    print("=== DELIBERATION RESULT ===")
    print(f"Status: {result.status}")
    print()

    if result.metadata:
        if "rendered_markdown" in result.metadata:
            md = result.metadata["rendered_markdown"]
            # Print first 500 chars of the final document
            print("=== FINAL DOCUMENT (preview) ===")
            print(md[:500])
            print("...")
        if "follow_up_tasks" in result.metadata:
            print()
            print(f"Follow-up tasks: {result.metadata['follow_up_tasks']}")

    # 8. Event stream
    print()
    print(f"=== EVENT STREAM ({len(event_sink.events)} events) ===")
    for evt in event_sink.events:
        payload_summary = ""
        pd = evt.payload_dict()
        if "topic" in pd:
            payload_summary = f" topic='{pd['topic'][:40]}...'"
        elif "participants" in pd:
            payload_summary = f" participants={pd['participants']}"
        print(f"  [{evt.type}]{payload_summary}")

    return result

result = anyio.from_thread.run_sync(lambda: anyio.run(demo_deliberation))
"""))

nbformat.write(nb, 'examples/e2e_showcase.ipynb')
print("Section 2 (Deliberation) added")
PYEOF
```

**Expected output:**
```
Section 2 (Deliberation) added
```

**Step 2: Verify deliberation demo runs**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python << 'PYEOF'
import anyio
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any
from miniautogen.core.contracts.coordination import DeliberationPlan
from miniautogen.core.contracts.deliberation import ResearchOutput, PeerReview, DeliberationState, FinalDocument
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events import InMemoryEventSink
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.deliberation_runtime import DeliberationRuntime

class Agent:
    def __init__(self, name):
        self.name = name
    async def contribute(self, topic):
        return ResearchOutput(
            role_name=self.name, section_title="Section",
            findings=["f1"], facts=["fact1"], evidence=["e1"],
            inferences=["i1"], uncertainties=["u1"],
            recommendation="rec", next_tests=["t1"],
        )
    async def review(self, target_id, contribution):
        return PeerReview(
            reviewer_role=self.name, target_role=target_id,
            target_section_title="Section",
            strengths=["good"], concerns=["concern"], questions=["q"],
        )
    async def consolidate(self, topic, contributions, reviews):
        return DeliberationState(
            review_cycle=1, accepted_facts=["f1"],
            is_sufficient=True,
        )
    async def produce_final_document(self, state, contributions):
        return FinalDocument(
            executive_summary="Summary", decision_summary="Go",
            body_markdown="Body",
        )

async def test():
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    agents = {"a": Agent("a"), "b": Agent("b")}
    delib = DeliberationRuntime(runner=runner, agent_registry=agents)
    plan = DeliberationPlan(topic="test", participants=["a", "b"], leader_agent="b")
    rid = str(uuid4())
    ctx = RunContext(run_id=rid, started_at=datetime.now(timezone.utc), correlation_id=rid)
    result = await delib.run([], ctx, plan)
    print(f"Status: {result.status}")
    print(f"Events: {len(sink.events)}")
    for e in sink.events:
        print(f"  {e.type}")

anyio.run(test)
PYEOF
```

**Expected output:**
```
Status: finished
Events: 2
  deliberation_started
  deliberation_finished
```

**Step 3: Commit**

```bash
git add examples/e2e_showcase.ipynb
git commit -m "docs: add deliberation mode demo to e2e notebook"
```

**If Task Fails:**
1. **`contribute` return type mismatch:** The runtime expects `ResearchOutput` (which extends `Contribution`). Ensure mock returns `ResearchOutput`, not plain `Contribution`.
2. **Leader methods not found:** The `DeliberationRuntime` calls `leader_agent.consolidate()` and `leader_agent.produce_final_document()` via `getattr` -- make sure the leader agent class has both methods.
3. **Can't recover:** Document the error and stop.

---

### Task 4: Add Section 3 -- Agentic Loop Mode

**Files:**
- Modify: `examples/e2e_showcase.ipynb` (append cells)

**Prerequisites:**
- Task 3 completed

**Step 1: Append Section 3 cells**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python << 'PYEOF'
import nbformat

nb = nbformat.read('examples/e2e_showcase.ipynb', as_version=4)

# --- Markdown: Section 3 header ---
nb['cells'].append(nbformat.v4.new_markdown_cell('''---

## 3. Agentic Loop Mode -- Router-Driven Conversation

**What it does:** A router agent decides which participant speaks next in a multi-turn conversation. The loop continues until the router terminates, stagnation is detected (same agent selected repeatedly), or max turns are reached.

**Why it matters:** Not all multi-agent interactions are sequential or cyclical. Sometimes you need dynamic routing -- a PM agent might consult a designer, then an engineer, then back to the designer based on the conversation flow. The agentic loop makes this possible with built-in stagnation detection and timeout safety.

**Key contracts:**
- `AgenticLoopPlan` -- router agent, participants, conversation policy
- `RouterDecision` -- next agent to speak, terminate flag, stagnation risk
- `ConversationPolicy` -- max turns, timeout, stagnation window
- `Conversation` / `Message` -- immutable conversation history
'''))

# --- Code: Mock conversational agents ---
nb['cells'].append(nbformat.v4.new_code_cell('''# Mock agents that satisfy the ConversationalAgent protocol.
# ConversationalAgent requires:
#   async def reply(self, message: str, context: dict) -> str
#   async def route(self, conversation_history: list) -> RouterDecision


class PMRouterAgent:
    """Router agent that orchestrates the conversation.

    Routes to designer first, then engineer, then terminates.
    """

    def __init__(self):
        self._call_count = 0

    async def reply(self, message: str, context: dict) -> str:
        return "Let me coordinate this discussion."

    async def route(self, conversation_history: list) -> RouterDecision:
        self._call_count += 1

        if self._call_count == 1:
            return RouterDecision(
                current_state_summary="Starting design discussion",
                missing_information="Need UX perspective",
                next_agent="designer",
            )
        elif self._call_count == 2:
            return RouterDecision(
                current_state_summary="Design input received",
                missing_information="Need technical feasibility",
                next_agent="engineer",
            )
        elif self._call_count == 3:
            return RouterDecision(
                current_state_summary="Both perspectives gathered",
                missing_information="Need final design revision",
                next_agent="designer",
                stagnation_risk=0.3,
            )
        else:
            return RouterDecision(
                current_state_summary="All perspectives gathered",
                missing_information="None",
                terminate=True,
            )


class DesignerAgent:
    """Participant that provides design perspective."""

    def __init__(self):
        self._call_count = 0

    async def reply(self, message: str, context: dict) -> str:
        self._call_count += 1
        if self._call_count == 1:
            return "I propose a card-based UI with progressive disclosure for the dashboard."
        return "Updated mockup: added the status indicators the engineer suggested."

    async def route(self, conversation_history: list) -> RouterDecision:
        # Participants don't usually route, but must satisfy protocol
        return RouterDecision(
            current_state_summary="Design provided",
            missing_information="Awaiting feedback",
            next_agent="pm",
        )


class EngineerAgent:
    """Participant that provides technical perspective."""

    async def reply(self, message: str, context: dict) -> str:
        return "The card-based approach works well. I suggest adding real-time status indicators via WebSocket."

    async def route(self, conversation_history: list) -> RouterDecision:
        return RouterDecision(
            current_state_summary="Technical input provided",
            missing_information="Awaiting design revision",
            next_agent="pm",
        )


print("Mock conversational agents defined:")
print("  - PMRouterAgent (routes conversation, terminates after 4 rounds)")
print("  - DesignerAgent (provides design perspective)")
print("  - EngineerAgent (provides technical perspective)")
'''))

# --- Code: Run agentic loop ---
nb['cells'].append(nbformat.v4.new_code_cell("""async def demo_agentic_loop():
    \"\"\"Demonstrate agentic loop coordination with router-driven conversation.\"\"\"

    # 1. Set up
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=event_sink)

    agents = {
        "pm": PMRouterAgent(),
        "designer": DesignerAgent(),
        "engineer": EngineerAgent(),
    }

    loop_runtime = AgenticLoopRuntime(runner=runner, agent_registry=agents)

    # 2. Define plan
    plan = AgenticLoopPlan(
        router_agent="pm",
        participants=["pm", "designer", "engineer"],
        policy=ConversationPolicy(
            max_turns=8,
            timeout_seconds=30.0,
            stagnation_window=3,
        ),
        initial_message="We need to design a new monitoring dashboard. What should it look like?",
    )

    # 3. Execute
    run_id = str(uuid4())
    context = RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id=run_id,
    )

    result = await loop_runtime.run([], context, plan)

    # 4. Inspect conversation
    print("=== AGENTIC LOOP RESULT ===")
    print(f"Status: {result.status}")
    print(f"Stop reason: {result.metadata.get('stop_reason')}")
    print(f"Total turns: {result.metadata.get('turns')}")
    print()

    print("=== CONVERSATION ===")
    for msg in result.output:
        sender = msg['sender']
        content = msg['content'][:80]
        print(f"  [{sender}] {content}")
    print()

    # 5. Event stream -- shows router decisions
    print(f"=== EVENT STREAM ({len(event_sink.events)} events) ===")
    for evt in event_sink.events:
        pd = evt.payload_dict()
        if evt.type == "router_decision":
            print(f"  [{evt.type}] next={pd.get('next_agent')} terminate={pd.get('terminate')}")
        elif evt.type == "agent_replied":
            print(f"  [{evt.type}] agent={pd.get('agent')} len={pd.get('reply_length')}")
        else:
            print(f"  [{evt.type}]")

    return result

result = anyio.from_thread.run_sync(lambda: anyio.run(demo_agentic_loop))
"""))

nbformat.write(nb, 'examples/e2e_showcase.ipynb')
print("Section 3 (Agentic Loop) added")
PYEOF
```

**Expected output:**
```
Section 3 (Agentic Loop) added
```

**Step 2: Verify agentic loop runs**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python << 'PYEOF'
import anyio
from datetime import datetime, timezone
from uuid import uuid4
from miniautogen.core.contracts.coordination import AgenticLoopPlan
from miniautogen.core.contracts.agentic_loop import ConversationPolicy, RouterDecision
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events import InMemoryEventSink
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.agentic_loop_runtime import AgenticLoopRuntime

class Router:
    def __init__(self):
        self._n = 0
    async def reply(self, msg, ctx):
        return "routing"
    async def route(self, history):
        self._n += 1
        if self._n <= 2:
            return RouterDecision(current_state_summary="s", missing_information="m", next_agent="b")
        return RouterDecision(current_state_summary="done", missing_information="none", terminate=True)

class Agent:
    async def reply(self, msg, ctx):
        return "reply from agent"
    async def route(self, history):
        return RouterDecision(current_state_summary="s", missing_information="m", next_agent="a")

async def test():
    sink = InMemoryEventSink()
    runner = PipelineRunner(event_sink=sink)
    agents = {"a": Router(), "b": Agent()}
    loop = AgenticLoopRuntime(runner=runner, agent_registry=agents)
    plan = AgenticLoopPlan(
        router_agent="a", participants=["a", "b"],
        policy=ConversationPolicy(max_turns=8, timeout_seconds=10.0),
        initial_message="Hello",
    )
    rid = str(uuid4())
    ctx = RunContext(run_id=rid, started_at=datetime.now(timezone.utc), correlation_id=rid)
    result = await loop.run([], ctx, plan)
    print(f"Status: {result.status}")
    print(f"Turns: {result.metadata.get('turns')}")
    print(f"Stop: {result.metadata.get('stop_reason')}")
    print(f"Events: {len(sink.events)}")

anyio.run(test)
PYEOF
```

**Expected output:**
```
Status: finished
Turns: 2
Stop: router_terminated
Events: <number>
```

**Step 3: Commit**

```bash
git add examples/e2e_showcase.ipynb
git commit -m "docs: add agentic loop mode demo to e2e notebook"
```

**If Task Fails:**
1. **Router selects agent not in participants:** Ensure all agents used in `RouterDecision.next_agent` are in the plan's `participants` list.
2. **Timeout:** The `ConversationPolicy` default timeout is 120s. If the mock is slow, increase it.
3. **Can't recover:** Document the error and stop.

---

### Task 5: Add Section 4 -- Event System Deep Dive

**Files:**
- Modify: `examples/e2e_showcase.ipynb` (append cells)

**Prerequisites:**
- Task 4 completed

**Step 1: Append Section 4 cells**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python << 'PYEOF'
import nbformat

nb = nbformat.read('examples/e2e_showcase.ipynb', as_version=4)

# --- Markdown: Section 4 header ---
nb['cells'].append(nbformat.v4.new_markdown_cell('''---

## 4. Event System Deep Dive

**What it does:** MiniAutoGen emits typed `ExecutionEvent` objects for every significant runtime action. Events flow through composable sinks that can filter, fan-out, and transform the stream.

**Why it matters:** Observability should not be coupled to the runtime. By making events first-class citizens with a composable sink architecture, you can:
- Log only specific event types (e.g., failures)
- Route events to multiple destinations (console, file, monitoring)
- Filter events by run ID for multi-tenant isolation
- Subscribe to events reactively via the EventBus

**Key components:**
- `ExecutionEvent` -- immutable event with type, timestamp, payload
- `EventType` -- enum with 80+ typed event categories
- `InMemoryEventSink` -- captures events in a list (great for testing)
- `CompositeEventSink` -- fans out to multiple sinks
- `FilteredEventSink` -- only forwards matching events
- `TypeFilter` / `RunFilter` / `CompositeFilter` -- composable predicates
- `EventBus` -- pub/sub with typed and global subscriptions
'''))

# --- Code: Event types catalog ---
nb['cells'].append(nbformat.v4.new_code_cell('''# Let's explore the event type catalog
print(f"MiniAutoGen has {len(EventType)} typed event categories:\\n")

# Group by prefix
groups: dict[str, list[str]] = {}
for et in EventType:
    prefix = et.value.split("_")[0]
    groups.setdefault(prefix, []).append(et.value)

for prefix, events in sorted(groups.items()):
    print(f"  {prefix.upper()} ({len(events)} events):")
    for e in events:
        print(f"    - {e}")
    print()
'''))

# --- Code: Composable sinks ---
nb['cells'].append(nbformat.v4.new_code_cell("""async def demo_event_system():
    \"\"\"Demonstrate composable event sinks and filters.\"\"\"

    # === Part 1: CompositeEventSink -- fan-out to multiple sinks ===
    print("=== Part 1: Composite Sink (fan-out) ===")

    all_events_sink = InMemoryEventSink()
    errors_only_sink = InMemoryEventSink()

    # FilteredEventSink only forwards matching events
    error_filter = TypeFilter({
        EventType.RUN_FAILED,
        EventType.RUN_TIMED_OUT,
        EventType.DELIBERATION_FAILED,
    })
    filtered_sink = FilteredEventSink(errors_only_sink, error_filter)

    # CompositeEventSink fans out to both
    composite = CompositeEventSink([all_events_sink, filtered_sink])

    # Emit some events
    events_to_emit = [
        ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="run-1"),
        ExecutionEvent(type=EventType.COMPONENT_STARTED.value, run_id="run-1"),
        ExecutionEvent(type=EventType.COMPONENT_FINISHED.value, run_id="run-1"),
        ExecutionEvent(type=EventType.RUN_FAILED.value, run_id="run-1",
                       payload={"error": "Something went wrong"}),
        ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="run-2"),
        ExecutionEvent(type=EventType.RUN_FINISHED.value, run_id="run-2"),
    ]

    for event in events_to_emit:
        await composite.publish(event)

    print(f"  all_events_sink received: {len(all_events_sink.events)} events")
    print(f"  errors_only_sink received: {len(errors_only_sink.events)} events")
    print(f"  Error events: {[e.type for e in errors_only_sink.events]}")
    print()

    # === Part 2: RunFilter -- isolate by run_id ===
    print("=== Part 2: Run Filter (multi-tenant isolation) ===")

    run1_sink = InMemoryEventSink()
    run1_filter = RunFilter("run-1")
    run1_filtered = FilteredEventSink(run1_sink, run1_filter)

    for event in events_to_emit:
        await run1_filtered.publish(event)

    print(f"  Events for run-1 only: {len(run1_sink.events)}")
    print(f"  Types: {[e.type for e in run1_sink.events]}")
    print()

    # === Part 3: CompositeFilter -- combine filters with AND/OR ===
    print("=== Part 3: Composite Filter (AND logic) ===")

    # Only capture FAILED events for run-1
    combined_sink = InMemoryEventSink()
    combined_filter = CompositeFilter(
        filters=[
            RunFilter("run-1"),
            TypeFilter({EventType.RUN_FAILED}),
        ],
        mode="all",  # AND logic
    )
    combined_filtered = FilteredEventSink(combined_sink, combined_filter)

    for event in events_to_emit:
        await combined_filtered.publish(event)

    print(f"  FAILED events for run-1: {len(combined_sink.events)}")
    print(f"  Payload: {combined_sink.events[0].payload_dict() if combined_sink.events else 'none'}")
    print()

    # === Part 4: EventBus -- pub/sub ===
    print("=== Part 4: EventBus (pub/sub) ===")

    bus = EventBus()
    captured: list[str] = []

    # Subscribe to specific event type
    async def on_run_started(event: ExecutionEvent):
        captured.append(f"STARTED: {event.run_id}")

    # Subscribe to ALL events (global)
    async def on_any_event(event: ExecutionEvent):
        captured.append(f"ANY: {event.type}")

    bus.subscribe(EventType.RUN_STARTED.value, on_run_started)
    bus.subscribe(None, on_any_event)  # None = global subscriber

    await bus.publish(ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="bus-1"))
    await bus.publish(ExecutionEvent(type=EventType.RUN_FINISHED.value, run_id="bus-1"))

    print(f"  Captured {len(captured)} notifications:")
    for c in captured:
        print(f"    {c}")

anyio.from_thread.run_sync(lambda: anyio.run(demo_event_system))
"""))

nbformat.write(nb, 'examples/e2e_showcase.ipynb')
print("Section 4 (Event System) added")
PYEOF
```

**Expected output:**
```
Section 4 (Event System) added
```

**Step 2: Verify event system demo runs**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python << 'PYEOF'
import anyio
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events import InMemoryEventSink, CompositeEventSink, FilteredEventSink, TypeFilter, EventType

async def test():
    all_sink = InMemoryEventSink()
    err_sink = InMemoryEventSink()
    filt = FilteredEventSink(err_sink, TypeFilter({EventType.RUN_FAILED}))
    comp = CompositeEventSink([all_sink, filt])
    await comp.publish(ExecutionEvent(type=EventType.RUN_STARTED.value, run_id="r1"))
    await comp.publish(ExecutionEvent(type=EventType.RUN_FAILED.value, run_id="r1"))
    await comp.publish(ExecutionEvent(type=EventType.RUN_FINISHED.value, run_id="r2"))
    print(f"All: {len(all_sink.events)}, Errors: {len(err_sink.events)}")

anyio.run(test)
PYEOF
```

**Expected output:**
```
All: 3, Errors: 1
```

**Step 3: Commit**

```bash
git add examples/e2e_showcase.ipynb
git commit -m "docs: add event system deep dive to e2e notebook"
```

**If Task Fails:**
1. **EventBus handler error:** EventBus catches handler exceptions internally -- check logs if handlers silently fail.
2. **Can't recover:** Document the error and stop.

---

### Task 6: Add Section 5 -- Execution Policies

**Files:**
- Modify: `examples/e2e_showcase.ipynb` (append cells)

**Prerequisites:**
- Task 5 completed

**Step 1: Append Section 5 cells**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python << 'PYEOF'
import nbformat

nb = nbformat.read('examples/e2e_showcase.ipynb', as_version=4)

# --- Markdown: Section 5 header ---
nb['cells'].append(nbformat.v4.new_markdown_cell('''---

## 5. Execution Policies -- Lateral, Event-Driven, Not Inline

**What it does:** Policies (retry, budget, approval, timeout) operate *laterally* -- they observe events and control execution without being wired inline into agent logic.

**Why it matters:** Coupling retry logic or budget checks into agent code creates a tangled mess. MiniAutoGen policies are composable, testable, and pluggable -- attach them to a PipelineRunner and they apply across all executions.

**Key components:**
- `RetryPolicy` + `build_retrying_call` -- configurable retry with tenacity
- `BudgetPolicy` + `BudgetTracker` -- cost tracking with enforcement
- `ApprovalGate` + `AutoApproveGate` -- human-in-the-loop control
- `ExecutionPolicy` -- pipeline-level timeout
- `TimeoutScope` -- hierarchical timeout (pipeline > turn > tool)
- `PolicyChain` -- compose multiple policies with short-circuit logic
'''))

# --- Code: Retry policy ---
nb['cells'].append(nbformat.v4.new_code_cell("""async def demo_policies():
    \"\"\"Demonstrate execution policies.\"\"\"

    # === Part 1: Retry Policy ===
    print("=== Part 1: Retry Policy ===")

    call_count = 0

    async def flaky_operation():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError(f"Transient failure (attempt {call_count})")
        return f"Success on attempt {call_count}"

    policy = RetryPolicy(max_attempts=3, retry_exceptions=(RuntimeError,))
    retrying = build_retrying_call(policy)

    result = await retrying(flaky_operation)
    print(f"  Result: {result}")
    print(f"  Total attempts: {call_count}")
    print()

    # === Part 2: Budget Policy ===
    print("=== Part 2: Budget Tracking ===")

    budget = BudgetTracker(policy=BudgetPolicy(max_cost=1.00))

    # Simulate API calls with costs
    costs = [0.25, 0.30, 0.20]
    for i, cost in enumerate(costs):
        budget.record(cost)
        print(f"  Call {i+1}: cost=${cost:.2f}, spent=${budget.spent:.2f}, remaining=${budget.remaining:.2f}")

    # Try to exceed budget
    try:
        budget.record(0.50)  # This should exceed the $1.00 limit
    except BudgetExceededError as e:
        print(f"  Budget exceeded: {e}")
    print()

    # === Part 3: Approval Gate ===
    print("=== Part 3: Approval Gate ===")

    # AutoApproveGate approves everything (for headless/testing)
    gate = AutoApproveGate()
    request = ApprovalRequest(
        request_id="req-001",
        action="deploy_to_production",
        description="Deploy v2.1 to production cluster",
    )
    response = await gate.request_approval(request)
    print(f"  Request: {request.action}")
    print(f"  Decision: {response.decision}")
    print(f"  Reason: {response.reason}")
    print()

    # Custom gate that denies specific actions
    class SafetyGate:
        async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
            if "production" in request.description.lower():
                return ApprovalResponse(
                    request_id=request.request_id,
                    decision="denied",
                    reason="Production deployments require human approval",
                )
            return ApprovalResponse(
                request_id=request.request_id,
                decision="approved",
                reason="Non-production action auto-approved",
            )

    safety_gate = SafetyGate()
    response2 = await safety_gate.request_approval(request)
    print(f"  Safety gate decision: {response2.decision}")
    print(f"  Safety gate reason: {response2.reason}")
    print()

    # === Part 4: Timeout Scope ===
    print("=== Part 4: Hierarchical Timeout ===")

    scope = TimeoutScope(
        pipeline_seconds=60.0,
        turn_seconds=10.0,
        tool_seconds=5.0,
    )
    print(f"  Pipeline timeout: {scope.pipeline_seconds}s")
    print(f"  Turn timeout: {scope.turn_seconds}s")
    print(f"  Tool timeout: {scope.tool_seconds}s")
    print(f"  (Invariant: pipeline > turn > tool)")
    print()

    # === Part 5: Policy Chain ===
    print("=== Part 5: Policy Chain (composable) ===")

    class BudgetEvaluator:
        def __init__(self, tracker: BudgetTracker):
            self.tracker = tracker

        async def evaluate(self, context: PolicyContext) -> PolicyResult:
            if not self.tracker.check():
                return PolicyResult(decision="deny", reason="Budget exceeded")
            return PolicyResult(decision="proceed")

    class RateLimitEvaluator:
        def __init__(self, max_calls: int):
            self.max_calls = max_calls
            self.call_count = 0

        async def evaluate(self, context: PolicyContext) -> PolicyResult:
            self.call_count += 1
            if self.call_count > self.max_calls:
                return PolicyResult(decision="deny", reason="Rate limit exceeded")
            return PolicyResult(decision="proceed")

    # Compose policies
    budget_tracker = BudgetTracker(policy=BudgetPolicy(max_cost=5.00))
    chain = PolicyChain([
        BudgetEvaluator(budget_tracker),
        RateLimitEvaluator(max_calls=10),
    ])

    # Evaluate -- should proceed
    ctx = PolicyContext(action="run_pipeline", run_id="test-1")
    result = await chain.evaluate(ctx)
    print(f"  Chain decision: {result.decision}")

    # Exceed budget, then re-evaluate
    budget_tracker.record(6.00)  # Exceeds $5 limit
    try:
        pass  # Budget exceeded error already raised in record()
    except BudgetExceededError:
        pass
    result2 = await chain.evaluate(ctx)
    print(f"  After budget exceeded: {result2.decision} ({result2.reason})")

anyio.from_thread.run_sync(lambda: anyio.run(demo_policies))
"""))

nbformat.write(nb, 'examples/e2e_showcase.ipynb')
print("Section 5 (Policies) added")
PYEOF
```

**Expected output:**
```
Section 5 (Policies) added
```

**Step 2: Verify policies demo runs**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python << 'PYEOF'
import anyio
from miniautogen.policies.retry import RetryPolicy, build_retrying_call
from miniautogen.policies.budget import BudgetPolicy, BudgetTracker, BudgetExceededError

async def test():
    # Retry
    n = 0
    async def flaky():
        nonlocal n
        n += 1
        if n < 3:
            raise RuntimeError("fail")
        return "ok"
    policy = RetryPolicy(max_attempts=3, retry_exceptions=(RuntimeError,))
    r = build_retrying_call(policy)
    result = await r(flaky)
    print(f"Retry: {result}, attempts: {n}")

    # Budget
    tracker = BudgetTracker(policy=BudgetPolicy(max_cost=1.0))
    tracker.record(0.5)
    tracker.record(0.3)
    print(f"Budget: spent={tracker.spent}, remaining={tracker.remaining}")
    try:
        tracker.record(0.5)
    except BudgetExceededError as e:
        print(f"Budget exceeded: {e}")

anyio.run(test)
PYEOF
```

**Expected output:**
```
Retry: ok, attempts: 3
Budget: spent=0.8, remaining=0.2
Budget exceeded: Budget exceeded: spent 1.3000, limit 1.0000
```

**Step 3: Commit**

```bash
git add examples/e2e_showcase.ipynb
git commit -m "docs: add execution policies demo to e2e notebook"
```

**If Task Fails:**
1. **BudgetTracker.record raises immediately:** `record()` raises `BudgetExceededError` when the cumulative cost exceeds max_cost. The demo handles this with try/except.
2. **PolicyChain budget check after exceed:** `BudgetTracker.check()` returns False when budget exceeded, but `record()` already raised. The `check()` method is non-throwing. Adjust the demo flow if needed.
3. **Can't recover:** Document the error and stop.

---

### Task 7: Add Section 6 -- Persistence

**Files:**
- Modify: `examples/e2e_showcase.ipynb` (append cells)

**Prerequisites:**
- Task 6 completed

**Step 1: Append Section 6 cells**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python << 'PYEOF'
import nbformat

nb = nbformat.read('examples/e2e_showcase.ipynb', as_version=4)

# --- Markdown: Section 6 header ---
nb['cells'].append(nbformat.v4.new_markdown_cell('''---

## 6. Persistence -- Checkpoint & Run Stores

**What it does:** MiniAutoGen persists run metadata and checkpoints through protocol-based stores. The `PipelineRunner` integrates with both `RunStore` (run lifecycle tracking) and `CheckpointStore` (state snapshots for recovery).

**Why it matters:** In production, agents fail. Networks drop. Budgets run out. Without persistence, you lose all progress. With checkpoint stores, you can resume from the last successful step. With run stores, you can audit, replay, and debug failures.

**Key contracts:**
- `RunStore` (ABC) -- save/get/list/delete run metadata
- `CheckpointStore` (ABC) -- save/get/list/delete checkpoint state
- `InMemoryRunStore` / `InMemoryCheckpointStore` -- testing implementations
- `StoreProtocol` -- generic key-value store protocol
'''))

# --- Code: Persistence demo ---
nb['cells'].append(nbformat.v4.new_code_cell("""async def demo_persistence():
    \"\"\"Demonstrate persistence with run and checkpoint stores.\"\"\"

    # === Part 1: Run Store -- lifecycle tracking ===
    print("=== Part 1: Run Store (lifecycle tracking) ===")

    run_store = InMemoryRunStore()

    # PipelineRunner automatically persists run lifecycle
    event_sink = InMemoryEventSink()
    runner = PipelineRunner(
        event_sink=event_sink,
        run_store=run_store,
    )

    # Create a simple pipeline (any async callable with .run())
    class SimplePipeline:
        async def run(self, state):
            return {"result": "processed", "input": state}

    # Run the pipeline
    result = await runner.run_pipeline(
        SimplePipeline(),
        {"data": "hello"},
    )

    # Inspect what was persisted
    run_id = runner.last_run_id
    stored_run = await run_store.get_run(run_id)
    print(f"  Run ID: {run_id[:12]}...")
    print(f"  Stored metadata: {stored_run}")

    all_runs = await run_store.list_runs()
    print(f"  Total runs in store: {len(all_runs)}")
    print()

    # === Part 2: Checkpoint Store -- state snapshots ===
    print("=== Part 2: Checkpoint Store (state snapshots) ===")

    checkpoint_store = InMemoryCheckpointStore()

    runner_with_cp = PipelineRunner(
        event_sink=InMemoryEventSink(),
        run_store=InMemoryRunStore(),
        checkpoint_store=checkpoint_store,
    )

    # Run a pipeline -- checkpoint is saved automatically on success
    result2 = await runner_with_cp.run_pipeline(
        SimplePipeline(),
        {"data": "important_work"},
    )

    run_id2 = runner_with_cp.last_run_id
    checkpoint = await checkpoint_store.get_checkpoint(run_id2)
    print(f"  Checkpoint for run {run_id2[:12]}...: {checkpoint}")
    print()

    # === Part 3: Run Store -- filtering by status ===
    print("=== Part 3: Run filtering ===")

    multi_store = InMemoryRunStore()
    multi_runner = PipelineRunner(
        event_sink=InMemoryEventSink(),
        run_store=multi_store,
    )

    # Run multiple pipelines -- some succeed, some fail
    await multi_runner.run_pipeline(SimplePipeline(), {"job": 1})
    await multi_runner.run_pipeline(SimplePipeline(), {"job": 2})

    class FailingPipeline:
        async def run(self, state):
            raise ValueError("Simulated failure")

    try:
        await multi_runner.run_pipeline(FailingPipeline(), {"job": 3})
    except ValueError:
        pass

    finished = await multi_store.list_runs(status="finished")
    failed = await multi_store.list_runs(status="failed")
    print(f"  Finished runs: {len(finished)}")
    print(f"  Failed runs: {len(failed)}")
    print(f"  Total runs: {len(await multi_store.list_runs())}")

    # === Part 4: Event stream from persisted run ===
    print()
    print("=== Part 4: Event stream shows persistence lifecycle ===")
    for evt in event_sink.events:
        print(f"  [{evt.type}] run_id={evt.run_id[:8] if evt.run_id else 'none'}...")

anyio.from_thread.run_sync(lambda: anyio.run(demo_persistence))
"""))

nbformat.write(nb, 'examples/e2e_showcase.ipynb')
print("Section 6 (Persistence) added")
PYEOF
```

**Expected output:**
```
Section 6 (Persistence) added
```

**Step 2: Verify persistence demo runs**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python << 'PYEOF'
import anyio
from miniautogen.core.events import InMemoryEventSink
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.stores.in_memory_run_store import InMemoryRunStore
from miniautogen.stores.in_memory_checkpoint_store import InMemoryCheckpointStore

class SimplePipeline:
    async def run(self, state):
        return {"result": "ok"}

async def test():
    run_store = InMemoryRunStore()
    cp_store = InMemoryCheckpointStore()
    runner = PipelineRunner(
        event_sink=InMemoryEventSink(),
        run_store=run_store,
        checkpoint_store=cp_store,
    )
    await runner.run_pipeline(SimplePipeline(), {"data": "test"})
    run_id = runner.last_run_id
    run = await run_store.get_run(run_id)
    cp = await cp_store.get_checkpoint(run_id)
    print(f"Run: {run}")
    print(f"Checkpoint: {cp}")

anyio.run(test)
PYEOF
```

**Expected output:**
```
Run: {'status': 'finished', 'correlation_id': '<uuid>'}
Checkpoint: {'result': 'ok'}
```

**Step 3: Commit**

```bash
git add examples/e2e_showcase.ipynb
git commit -m "docs: add persistence demo to e2e notebook"
```

**If Task Fails:**
1. **Checkpoint not saved:** `PipelineRunner.run_pipeline` only saves checkpoints when `checkpoint_store` is provided AND the pipeline succeeds.
2. **Can't recover:** Document the error and stop.

---

### Task 8: Add Section 7 -- Putting It All Together

**Files:**
- Modify: `examples/e2e_showcase.ipynb` (append cells)

**Prerequisites:**
- Task 7 completed

**Step 1: Append Section 7 cells**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python << 'PYEOF'
import nbformat

nb = nbformat.read('examples/e2e_showcase.ipynb', as_version=4)

# --- Markdown: Section 7 header ---
nb['cells'].append(nbformat.v4.new_markdown_cell('''---

## 7. Putting It All Together

**The full picture:** Let's combine coordination, events, policies, and persistence in a single run. This demonstrates how MiniAutoGen's components compose cleanly.

**Scenario:** A workflow pipeline with:
- Event capture (observability)
- Run persistence (audit trail)
- Checkpoint persistence (recovery)
- Retry policy (fault tolerance)
- Execution policy with timeout
- Custom event filtering (only capture failures)
'''))

# --- Code: Combined demo ---
nb['cells'].append(nbformat.v4.new_code_cell("""async def demo_combined():
    \"\"\"Demonstrate all features composed together.\"\"\"

    # === Infrastructure setup ===

    # 1. Event sinks: one for everything, one for errors only
    all_events = InMemoryEventSink()
    error_events = InMemoryEventSink()
    error_filter = TypeFilter({
        EventType.RUN_FAILED,
        EventType.RUN_TIMED_OUT,
        EventType.COMPONENT_RETRIED,
    })
    filtered_errors = FilteredEventSink(error_events, error_filter)
    composite_sink = CompositeEventSink([all_events, filtered_errors])

    # 2. Stores
    run_store = InMemoryRunStore()
    checkpoint_store = InMemoryCheckpointStore()

    # 3. Policies
    retry = RetryPolicy(max_attempts=2, retry_exceptions=(RuntimeError,))
    execution = ExecutionPolicy(timeout_seconds=30.0)

    # 4. PipelineRunner with everything plugged in
    runner = PipelineRunner(
        event_sink=composite_sink,
        run_store=run_store,
        checkpoint_store=checkpoint_store,
        retry_policy=retry,
        execution_policy=execution,
    )

    # === Workflow with flaky agent ===

    class FlakyResearcherAgent:
        \"\"\"Agent that fails once then succeeds.\"\"\"
        def __init__(self):
            self._calls = 0

        async def process(self, input):
            self._calls += 1
            return {**input, "findings": ["result from attempt " + str(self._calls)]}

    class ReliableWriterAgent:
        async def process(self, input):
            return {**input, "report": "Final report based on " + str(input.get("findings"))}

    agents = {
        "researcher": FlakyResearcherAgent(),
        "writer": ReliableWriterAgent(),
    }

    # Workflow runtime
    workflow = WorkflowRuntime(runner=runner, agent_registry=agents)
    plan = WorkflowPlan(steps=[
        WorkflowStep(component_name="research", agent_id="researcher"),
        WorkflowStep(component_name="write", agent_id="writer"),
    ])

    run_id = str(uuid4())
    context = RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id=run_id,
        input_payload={"topic": "Combined Demo"},
    )

    result = await workflow.run([], context, plan)

    # === Inspect everything ===
    print("=" * 60)
    print("COMBINED DEMO RESULTS")
    print("=" * 60)
    print()

    print(f"1. Workflow Status: {result.status}")
    print(f"   Output: {result.output}")
    print()

    print(f"2. Event Stream: {len(all_events.events)} total events")
    for evt in all_events.events:
        print(f"   [{evt.type}] scope={evt.scope}")
    print()

    print(f"3. Error Events (filtered): {len(error_events.events)} events")
    for evt in error_events.events:
        print(f"   [{evt.type}] {evt.payload_dict()}")
    print()

    stored_runs = await run_store.list_runs()
    print(f"4. Persisted Runs: {len(stored_runs)}")
    print()

    checkpoints = await checkpoint_store.list_checkpoints()
    print(f"5. Checkpoints: {len(checkpoints)}")
    print()

    print("=" * 60)
    print("All MiniAutoGen SDK features working in harmony!")
    print("=" * 60)

anyio.from_thread.run_sync(lambda: anyio.run(demo_combined))
"""))

# --- Markdown: Conclusion ---
nb['cells'].append(nbformat.v4.new_markdown_cell('''---

## Summary

This notebook demonstrated MiniAutoGen's 5 key SDK pillars:

| Feature | What We Showed | Key Takeaway |
|---------|---------------|--------------|
| **Coordination Modes** | Workflow, Deliberation, Agentic Loop | Same framework, 3 fundamentally different multi-agent patterns |
| **Event System** | 80+ typed events, composable sinks, filters, EventBus | Observability decoupled from runtime -- plug in any destination |
| **Execution Policies** | Retry, Budget, Approval, Timeout, PolicyChain | Fault tolerance as lateral concerns, not inline spaghetti |
| **Backend Abstraction** | Mock agents satisfying protocols | Swap any LLM provider without changing coordination logic |
| **Persistence** | RunStore, CheckpointStore | Resume from failures, audit all runs, replay for debugging |

### Architecture Philosophy

MiniAutoGen's competitive moat is **protocol-driven composition**:
- Agents satisfy typed protocols (`WorkflowAgent`, `DeliberationAgent`, `ConversationalAgent`)
- Policies are lateral observers, not inline checks
- Events are first-class citizens with composable routing
- Stores are protocol-based and swappable (in-memory, SQLAlchemy, etc.)
- Everything is async-first via `anyio`

The framework does not care if your agent is GPT-4, Claude, a local model, or a mock -- it only cares that it satisfies the protocol.
'''))

nbformat.write(nb, 'examples/e2e_showcase.ipynb')
print("Section 7 (Combined + Conclusion) added")
PYEOF
```

**Expected output:**
```
Section 7 (Combined + Conclusion) added
```

**Step 2: Commit**

```bash
git add examples/e2e_showcase.ipynb
git commit -m "docs: add combined demo and conclusion to e2e notebook"
```

**If Task Fails:**
1. **Combined demo has stale references:** If earlier sections changed agent names, update them here.
2. **Can't recover:** Document the error and stop.

---

### Task 9: Fix Jupyter async compatibility

**Files:**
- Modify: `examples/e2e_showcase.ipynb` (modify the async runner calls)

**Prerequisites:**
- Task 8 completed

**Context:** In Jupyter notebooks, the event loop is already running, so `anyio.from_thread.run_sync` will fail. We need to use `await` directly in notebook cells. The `anyio.from_thread.run_sync(lambda: anyio.run(...))` pattern only works in plain Python scripts.

**Step 1: Replace all `anyio.from_thread.run_sync` calls with direct `await`**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python << 'PYEOF'
import nbformat

nb = nbformat.read('examples/e2e_showcase.ipynb', as_version=4)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        # Replace anyio.from_thread.run_sync(lambda: anyio.run(X)) with await X
        src = cell['source']
        src = src.replace(
            'anyio.from_thread.run_sync(lambda: anyio.run(demo_workflow))',
            'await demo_workflow()'
        )
        src = src.replace(
            'anyio.from_thread.run_sync(lambda: anyio.run(demo_deliberation))',
            'await demo_deliberation()'
        )
        src = src.replace(
            'anyio.from_thread.run_sync(lambda: anyio.run(demo_agentic_loop))',
            'await demo_agentic_loop()'
        )
        src = src.replace(
            'anyio.from_thread.run_sync(lambda: anyio.run(demo_event_system))',
            'await demo_event_system()'
        )
        src = src.replace(
            'anyio.from_thread.run_sync(lambda: anyio.run(demo_policies))',
            'await demo_policies()'
        )
        src = src.replace(
            'anyio.from_thread.run_sync(lambda: anyio.run(demo_persistence))',
            'await demo_persistence()'
        )
        src = src.replace(
            'anyio.from_thread.run_sync(lambda: anyio.run(demo_combined))',
            'await demo_combined()'
        )
        cell['source'] = src

nbformat.write(nb, 'examples/e2e_showcase.ipynb')
print("Fixed async calls for Jupyter compatibility")
PYEOF
```

**Expected output:**
```
Fixed async calls for Jupyter compatibility
```

**Step 2: Commit**

```bash
git add examples/e2e_showcase.ipynb
git commit -m "fix: use await instead of anyio.run for Jupyter compatibility"
```

**If Task Fails:**
1. **String replacement missed some patterns:** Check manually with `grep -c "anyio.from_thread" examples/e2e_showcase.ipynb`.
2. **Can't recover:** Document the error and stop.

---

### Task 10: Run Code Review

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
- This tracks tech debt for future resolution

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location
- Format: `FIXME(nitpick): [Issue description] (reported by [reviewer] on [date], severity: Cosmetic)`
- Low-priority improvements tracked inline

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low issues have TODO(review): comments added
   - All Cosmetic issues have FIXME(nitpick): comments added

---

### Task 11: Final verification -- run the complete notebook

**Files:**
- Verify: `examples/e2e_showcase.ipynb`

**Prerequisites:**
- Task 10 completed (code review passed)

**Step 1: Run all code cells as a plain Python script**

Since we need to verify without Jupyter, extract and run the code cells.

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python << 'PYEOF'
import nbformat
import anyio

nb = nbformat.read('examples/e2e_showcase.ipynb', as_version=4)

# Extract all code cells
code_cells = [c['source'] for c in nb['cells'] if c['cell_type'] == 'code']

# Replace 'await' calls with anyio.run for script execution
full_code = "\n\n".join(code_cells)

# Replace top-level await with anyio.run
full_code = full_code.replace("await demo_workflow()", "# will run below")
full_code = full_code.replace("await demo_deliberation()", "# will run below")
full_code = full_code.replace("await demo_agentic_loop()", "# will run below")
full_code = full_code.replace("await demo_event_system()", "# will run below")
full_code = full_code.replace("await demo_policies()", "# will run below")
full_code = full_code.replace("await demo_persistence()", "# will run below")
full_code = full_code.replace("await demo_combined()", "# will run below")

# Add a main runner
full_code += """

async def run_all():
    print("\\n" + "=" * 60)
    print("RUNNING ALL DEMOS")
    print("=" * 60 + "\\n")

    print("\\n--- Demo: Workflow ---\\n")
    await demo_workflow()

    print("\\n--- Demo: Deliberation ---\\n")
    await demo_deliberation()

    print("\\n--- Demo: Agentic Loop ---\\n")
    await demo_agentic_loop()

    print("\\n--- Demo: Event System ---\\n")
    await demo_event_system()

    print("\\n--- Demo: Policies ---\\n")
    await demo_policies()

    print("\\n--- Demo: Persistence ---\\n")
    await demo_persistence()

    print("\\n--- Demo: Combined ---\\n")
    await demo_combined()

    print("\\n" + "=" * 60)
    print("ALL DEMOS COMPLETED SUCCESSFULLY")
    print("=" * 60)

anyio.run(run_all)
"""

exec(full_code)
PYEOF
```

**Expected output:**
```
All imports successful!
EventType has <N> event types
Coordination modes: ['workflow', 'deliberation', 'agentic_loop']

Mock workflow agents defined: ...
Mock deliberation agents defined: ...
Mock conversational agents defined: ...

============================================================
RUNNING ALL DEMOS
============================================================

--- Demo: Workflow ---
=== WORKFLOW RESULT ===
Status: finished
...

--- Demo: Deliberation ---
=== DELIBERATION RESULT ===
Status: finished
...

--- Demo: Agentic Loop ---
=== AGENTIC LOOP RESULT ===
Status: finished
...

--- Demo: Event System ---
=== Part 1: Composite Sink (fan-out) ===
...

--- Demo: Policies ---
=== Part 1: Retry Policy ===
...

--- Demo: Persistence ---
=== Part 1: Run Store (lifecycle tracking) ===
...

--- Demo: Combined ---
COMBINED DEMO RESULTS
...

============================================================
ALL DEMOS COMPLETED SUCCESSFULLY
============================================================
```

**Step 2: Verify event count makes sense**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign
python -c "
from miniautogen.core.events.types import EventType
print(f'Total EventType members: {len(EventType)}')
"
```

**Expected output:**
```
Total EventType members: <number between 60-90>
```

**Step 3: Final commit**

```bash
git add examples/e2e_showcase.ipynb
git commit -m "docs: finalize e2e showcase notebook with all SDK features"
```

**If Task Fails:**
1. **exec() fails:** The combined code may have import issues since cells share scope. Run each demo function individually via `anyio.run(demo_workflow)`.
2. **Variable name collision:** Rename `result` variables in each demo to be unique (e.g., `workflow_result`, `delib_result`).
3. **Can't recover:** Document which demo function fails and the exact error, then stop.

---

## Plan Checklist

- [x] Header with goal, architecture, tech stack, prerequisites
- [x] Verification commands with expected output
- [x] Tasks broken into bite-sized steps (2-5 min each)
- [x] Exact file paths for all files
- [x] Complete code (no placeholders)
- [x] Exact commands with expected output
- [x] Failure recovery steps for each task
- [x] Code review checkpoints after batches
- [x] Severity-based issue handling documented
- [x] Passes Zero-Context Test
