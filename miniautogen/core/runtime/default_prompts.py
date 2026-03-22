"""Default prompt builders — extracted from AgentRuntime hardcoded prompts.

These serve as the last-resort fallback in the cascade resolution:
InteractionStrategy -> YAML templates -> defaults (this module).

These prompts preserve exact backward compatibility with the original
AgentRuntime prompts that were hardcoded before the agnostic refactor.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from miniautogen.core.contracts.deliberation import (
        Contribution,
        DeliberationState,
        Review,
    )


def build_default_contribute_prompt(*, topic: str) -> str:
    """Build the default contribute prompt (extracted from AgentRuntime.contribute)."""
    return (
        f"Contribute to the topic: {topic}. "
        "Respond with JSON: "
        '{"title":"...","content":{...}}'
    )


def build_default_review_prompt(
    *, target_id: str, contribution: Contribution
) -> str:
    """Build the default review prompt (extracted from AgentRuntime.review)."""
    return (
        f"Review contribution from {target_id}: "
        f"title='{contribution.title}', content={contribution.content}. "
        "Respond with JSON: "
        '{"strengths":[...],"concerns":[...],"questions":[...]}'
    )


def build_default_consolidate_prompt(
    *,
    topic: str,
    contributions: list[Contribution],
    reviews: list[Review],
) -> str:
    """Build the default consolidate prompt (extracted from AgentRuntime.consolidate)."""
    contrib_summary = "\n".join(
        f"- {c.participant_id}: {c.title}" for c in contributions
    )
    review_summary = "\n".join(
        f"- {r.reviewer_id} on {r.target_id}: strengths={r.strengths}, concerns={r.concerns}"
        for r in reviews
    )
    return (
        f"As leader, consolidate the deliberation on: {topic}\n\n"
        f"Contributions:\n{contrib_summary}\n\n"
        f"Reviews:\n{review_summary}\n\n"
        "Respond with JSON:\n"
        '{"accepted_facts":["..."],"open_conflicts":["..."],'
        '"pending_gaps":["..."],"leader_decision":"...",'
        '"is_sufficient":true/false,"rejection_reasons":["..."]}'
    )


def build_default_final_document_prompt(
    *,
    state: DeliberationState,
    contributions: list[Contribution],
) -> str:
    """Build the default final document prompt (extracted from AgentRuntime.produce_final_document)."""
    contrib_text = "\n".join(
        f"- {c.participant_id}: {json.dumps(c.content)[:500]}"
        for c in contributions
    )
    return (
        "Produce a final document summarizing the deliberation.\n\n"
        f"State: decision={state.leader_decision}, "
        f"accepted_facts={state.accepted_facts}, "
        f"open_conflicts={state.open_conflicts}\n\n"
        f"Contributions:\n{contrib_text}\n\n"
        "Respond with JSON:\n"
        '{"executive_summary":"...","accepted_facts":["..."],'
        '"open_conflicts":["..."],"pending_decisions":["..."],'
        '"recommendations":["..."],"decision_summary":"...",'
        '"body_markdown":"..."}'
    )


def build_default_route_prompt() -> str:
    """Build the default route prompt (extracted from AgentRuntime.route)."""
    return (
        "Based on the conversation history, decide which agent should "
        "speak next. Respond with JSON: "
        '{"current_state_summary":"...","missing_information":"...",'
        '"next_agent":"...","terminate":false,"stagnation_risk":0.0}'
    )
