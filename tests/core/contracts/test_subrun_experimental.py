"""Tests for SubrunRequest experimental marking."""

from miniautogen.core.contracts.coordination import (
    _EXPERIMENTAL_CONTRACTS,
    CoordinationKind,
    SubrunRequest,
    WorkflowPlan,
    WorkflowStep,
)


def test_subrun_request_is_marked_experimental() -> None:
    assert "SubrunRequest" in _EXPERIMENTAL_CONTRACTS


def test_subrun_request_docstring_mentions_experimental() -> None:
    assert "experimental" in (SubrunRequest.__doc__ or "").lower()


def test_subrun_request_can_be_instantiated() -> None:
    plan = WorkflowPlan(steps=[WorkflowStep(component_name="step1")])
    req = SubrunRequest(
        mode=CoordinationKind.WORKFLOW,
        plan=plan,
        label="test-subrun",
    )
    assert req.mode == CoordinationKind.WORKFLOW
