"""Tests for SubrunRequest contract."""
from miniautogen.core.contracts.coordination import (
    SubrunRequest,
    CoordinationKind,
    CoordinationPlan,
    WorkflowPlan,
    DeliberationPlan,
    WorkflowStep,
)
from miniautogen.core.contracts.agentic_loop import ConversationPolicy


def test_subrun_request_has_required_fields() -> None:
    plan = WorkflowPlan(steps=[WorkflowStep(component_name="step1")])
    req = SubrunRequest(
        mode=CoordinationKind.WORKFLOW,
        plan=plan,
        label="sub-workflow",
    )
    assert req.mode == CoordinationKind.WORKFLOW
    assert req.label == "sub-workflow"
    assert isinstance(req.plan, WorkflowPlan)


def test_subrun_request_defaults() -> None:
    plan = DeliberationPlan(
        topic="test",
        participants=["a"],
    )
    req = SubrunRequest(
        mode=CoordinationKind.DELIBERATION,
        plan=plan,
    )
    assert req.label == ""
    assert req.input_key is None
    assert req.output_key is None
    assert req.metadata == {}


def test_subrun_request_with_io_keys() -> None:
    plan = WorkflowPlan(steps=[WorkflowStep(component_name="s1")])
    req = SubrunRequest(
        mode=CoordinationKind.WORKFLOW,
        plan=plan,
        input_key="previous_output",
        output_key="subrun_result",
    )
    assert req.input_key == "previous_output"
    assert req.output_key == "subrun_result"


def test_subrun_request_serialization_roundtrip() -> None:
    plan = WorkflowPlan(steps=[WorkflowStep(component_name="s1")])
    req = SubrunRequest(
        mode=CoordinationKind.WORKFLOW,
        plan=plan,
        label="test",
    )
    data = req.model_dump()
    restored = SubrunRequest.model_validate(data)
    assert restored.label == "test"
    assert restored.mode == CoordinationKind.WORKFLOW
