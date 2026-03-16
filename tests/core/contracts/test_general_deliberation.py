"""Tests for generalized deliberation contracts."""

from miniautogen.core.contracts.deliberation import (
    Contribution,
    Review,
    ResearchOutput,
    PeerReview,
)


def test_contribution_base_model_has_required_fields() -> None:
    contrib = Contribution(
        participant_id="analyst",
        title="Market Analysis",
        content={"findings": ["finding-1"], "recommendation": "proceed"},
    )
    assert contrib.participant_id == "analyst"
    assert contrib.title == "Market Analysis"
    assert contrib.content["findings"] == ["finding-1"]


def test_review_base_model_has_required_fields() -> None:
    review = Review(
        reviewer_id="critic",
        target_id="analyst",
        target_title="Market Analysis",
        strengths=["solid methodology"],
        concerns=["missing data"],
        questions=["what about Q4?"],
    )
    assert review.reviewer_id == "critic"
    assert review.target_id == "analyst"
    assert len(review.concerns) == 1


def test_research_output_is_subclass_of_contribution() -> None:
    ro = ResearchOutput(
        role_name="analyst",
        section_title="Findings",
        findings=["f1"],
        facts=["fact1"],
        recommendation="proceed",
    )
    assert isinstance(ro, Contribution)
    assert ro.participant_id == "analyst"
    assert ro.title == "Findings"


def test_peer_review_is_subclass_of_review() -> None:
    pr = PeerReview(
        reviewer_role="critic",
        target_role="analyst",
        target_section_title="Findings",
        strengths=["good"],
        concerns=["bad"],
        questions=["why?"],
    )
    assert isinstance(pr, Review)
    assert pr.reviewer_id == "critic"
    assert pr.target_id == "analyst"
    assert pr.target_title == "Findings"
