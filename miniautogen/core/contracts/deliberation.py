from __future__ import annotations

import warnings
from typing import Any

from pydantic import BaseModel, Field, model_validator


# --- General deliberation contracts ---

# Suppress Pydantic warning about ResearchOutput.role_name shadowing
# the property on Contribution. This is intentional: ResearchOutput
# promotes role_name from a read-only alias to a real field that
# syncs to participant_id via a model_validator.
warnings.filterwarnings(
    "ignore",
    message='Field name "role_name".*shadows an attribute in parent',
    category=UserWarning,
)


class Contribution(BaseModel):
    """General-purpose contribution in a deliberation cycle.

    Any participant can produce a Contribution. Specialized forms
    (e.g., ResearchOutput) extend this base.
    """

    participant_id: str
    title: str
    content: dict[str, Any] = Field(default_factory=dict)

    @property
    def role_name(self) -> str:
        """Backward-compatible alias for participant_id."""
        return self.participant_id


class Review(BaseModel):
    """General-purpose review of another participant's contribution.

    Specialized forms (e.g., PeerReview) extend this base.
    """

    reviewer_id: str
    target_id: str
    target_title: str
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


# --- Research-specific deliberation contracts (backward-compatible) ---


class ResearchOutput(Contribution):
    """Structured output produced by a specialist research agent.

    Extends Contribution with research-specific fields.
    ``participant_id`` is synced from ``role_name``.
    ``title`` is synced from ``section_title``.
    """

    role_name: str
    section_title: str
    findings: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    recommendation: str
    next_tests: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def sync_base_fields(cls, data: dict) -> dict:
        if isinstance(data, dict):
            if "participant_id" not in data and "role_name" in data:
                data["participant_id"] = data["role_name"]
            if "title" not in data and "section_title" in data:
                data["title"] = data["section_title"]
        return data


class PeerReview(Review):
    """Cross-review emitted by one specialist about another specialist output.

    Extends Review with research-specific naming.
    ``reviewer_id`` is synced from ``reviewer_role``.
    ``target_id`` is synced from ``target_role``.
    ``target_title`` is synced from ``target_section_title``.
    """

    reviewer_role: str
    target_role: str
    target_section_title: str

    @model_validator(mode="before")
    @classmethod
    def sync_base_fields(cls, data: dict) -> dict:
        if isinstance(data, dict):
            if "reviewer_id" not in data and "reviewer_role" in data:
                data["reviewer_id"] = data["reviewer_role"]
            if "target_id" not in data and "target_role" in data:
                data["target_id"] = data["target_role"]
            if "target_title" not in data and "target_section_title" in data:
                data["target_title"] = data["target_section_title"]
        return data


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
