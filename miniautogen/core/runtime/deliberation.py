from __future__ import annotations

from collections import defaultdict

from miniautogen.core.contracts.deliberation import DeliberationState, PeerReview, ResearchOutput, Review


def summarize_peer_reviews(reviews: list[Review]) -> dict[str, list[Review]]:
    grouped: dict[str, list[Review]] = defaultdict(list)
    for review in reviews:
        grouped[review.target_id].append(review)
    return dict(grouped)


def build_follow_up_tasks(grouped_reviews: dict[str, list[Review]]) -> dict[str, list[str]]:
    follow_ups: dict[str, list[str]] = {}
    for target_role, reviews in grouped_reviews.items():
        ordered_items: list[str] = []
        seen_items: set[str] = set()
        for review in reviews:
            for concern in review.concerns:
                item = f"Responder concern: {concern}"
                if item not in seen_items:
                    ordered_items.append(item)
                    seen_items.add(item)
            for question in review.questions:
                item = f"Responder question: {question}"
                if item not in seen_items:
                    ordered_items.append(item)
                    seen_items.add(item)
        follow_ups[target_role] = ordered_items
    return follow_ups


def apply_leader_review(
    *,
    state: DeliberationState,
    research_outputs: list[ResearchOutput],
    accepted_facts: list[str],
    open_conflicts: list[str],
    pending_gaps: list[str],
    leader_decision: str | None,
    is_sufficient: bool,
    rejection_reasons: list[str],
) -> DeliberationState:
    del research_outputs
    return DeliberationState(
        review_cycle=state.review_cycle + 1,
        accepted_facts=list(accepted_facts),
        open_conflicts=list(open_conflicts),
        pending_gaps=list(pending_gaps),
        leader_decision=leader_decision,
        is_sufficient=is_sufficient,
        rejection_reasons=list(rejection_reasons),
    )
