"""Test that the public API exports all expected types."""


def test_api_exports_all_core_contracts() -> None:
    from miniautogen.api import Message, RunContext, RunResult, ExecutionEvent, Conversation

    assert all(t is not None for t in [Message, RunContext, RunResult, ExecutionEvent, Conversation])


def test_api_exports_agent_protocols() -> None:
    from miniautogen.api import WorkflowAgent, DeliberationAgent, ConversationalAgent

    assert all(t is not None for t in [WorkflowAgent, DeliberationAgent, ConversationalAgent])


def test_api_exports_coordination() -> None:
    from miniautogen.api import (
        CoordinationKind,
        CoordinationPlan,
        WorkflowPlan,
        DeliberationPlan,
        AgenticLoopPlan,
        SubrunRequest,
        CompositionStep,
    )

    assert all(
        t is not None
        for t in [
            CoordinationKind,
            CoordinationPlan,
            WorkflowPlan,
            DeliberationPlan,
            AgenticLoopPlan,
            SubrunRequest,
            CompositionStep,
        ]
    )


def test_api_exports_runtimes() -> None:
    from miniautogen.api import (
        AgenticLoopRuntime,
        CompositeRuntime,
        DeliberationRuntime,
        PipelineRunner,
        WorkflowRuntime,
    )

    assert all(
        t is not None
        for t in [
            AgenticLoopRuntime,
            CompositeRuntime,
            DeliberationRuntime,
            PipelineRunner,
            WorkflowRuntime,
        ]
    )


def test_api_exports_deliberation_generals() -> None:
    from miniautogen.api import Contribution, Review

    assert Contribution is not None
    assert Review is not None


def test_api_exports_policy_enforcement() -> None:
    from miniautogen.api import BudgetTracker, BudgetExceededError

    assert BudgetTracker is not None
    assert BudgetExceededError is not None


def test_api_exports_agentic_loop_contracts() -> None:
    from miniautogen.api import RouterDecision, ConversationPolicy, AgenticLoopState

    assert all(t is not None for t in [RouterDecision, ConversationPolicy, AgenticLoopState])
