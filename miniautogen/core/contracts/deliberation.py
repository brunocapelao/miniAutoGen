from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchOutput(BaseModel):
    """Structured output produced by a specialist research agent."""

    role_name: str
    section_title: str
    findings: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    recommendation: str
    next_tests: list[str] = Field(default_factory=list)


class PeerReview(BaseModel):
    """Cross-review emitted by one specialist about another specialist output."""

    reviewer_role: str
    target_role: str
    target_section_title: str
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class DeliberationState(BaseModel):
    """Aggregated state of a deliberative research workflow."""

    review_cycle: int = 0
    accepted_facts: list[str] = Field(default_factory=list)
    open_conflicts: list[str] = Field(default_factory=list)
    pending_gaps: list[str] = Field(default_factory=list)
    leader_decision: str | None = None
    is_sufficient: bool = False
    rejection_reasons: list[str] = Field(default_factory=list)


class FinalDocument(BaseModel):
    """Structured envelope for the final decision-oriented document."""

    executive_summary: str
    accepted_facts: list[str] = Field(default_factory=list)
    open_conflicts: list[str] = Field(default_factory=list)
    pending_decisions: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    decision_summary: str
    body_markdown: str
