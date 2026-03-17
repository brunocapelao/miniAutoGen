"""Test that the public API exports all expected types."""


def test_api_exports_all_core_contracts() -> None:
    from miniautogen.api import Conversation, ExecutionEvent, Message, RunContext, RunResult

    assert all(
        t is not None
        for t in [Message, RunContext, RunResult, ExecutionEvent, Conversation]
    )


def test_api_exports_agent_protocols() -> None:
    from miniautogen.api import ConversationalAgent, DeliberationAgent, WorkflowAgent

    assert all(t is not None for t in [WorkflowAgent, DeliberationAgent, ConversationalAgent])


def test_api_exports_coordination() -> None:
    from miniautogen.api import (
        AgenticLoopPlan,
        CompositionStep,
        CoordinationKind,
        CoordinationPlan,
        DeliberationPlan,
        SubrunRequest,
        WorkflowPlan,
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
    from miniautogen.api import BudgetExceededError, BudgetTracker

    assert BudgetTracker is not None
    assert BudgetExceededError is not None


def test_api_exports_agentic_loop_contracts() -> None:
    from miniautogen.api import AgenticLoopState, ConversationPolicy, RouterDecision

    assert all(t is not None for t in [RouterDecision, ConversationPolicy, AgenticLoopState])


def test_tool_protocol_exported() -> None:
    import miniautogen.api as api

    assert hasattr(api, "ToolProtocol")


def test_tool_result_exported() -> None:
    import miniautogen.api as api

    assert hasattr(api, "ToolResult")


def test_store_protocol_exported() -> None:
    import miniautogen.api as api

    assert hasattr(api, "StoreProtocol")


def test_all_declared_names_are_importable() -> None:
    import miniautogen.api as api

    for name in api.__all__:
        assert hasattr(api, name), f"{name} in __all__ but not importable"


def test_no_private_names_in_all() -> None:
    import miniautogen.api as api

    for name in api.__all__:
        assert not name.startswith("_"), f"Private name {name} in __all__"
