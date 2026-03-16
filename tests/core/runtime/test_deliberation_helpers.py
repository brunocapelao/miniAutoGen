from miniautogen.core.contracts.deliberation import DeliberationState, PeerReview, ResearchOutput
from miniautogen.core.runtime.deliberation import (
    apply_leader_review,
    build_follow_up_tasks,
    summarize_peer_reviews,
)


def test_summarize_peer_reviews_groups_reviews_by_target_role() -> None:
    reviews = [
        PeerReview(
            reviewer_role="Market Analyst",
            target_role="Regulatory Analyst",
            target_section_title="Licenciamento",
            strengths=["Boa priorização dos riscos."],
            concerns=["Falta quantificação do impacto."],
            questions=["Qual o fallback sem transição?"],
        ),
        PeerReview(
            reviewer_role="Operations Analyst",
            target_role="Regulatory Analyst",
            target_section_title="Licenciamento",
            strengths=["Relaciona bem o cronograma e a operação."],
            concerns=["Não conecta com os parceiros BaaS."],
            questions=["Qual licença adicional seria necessária?"],
        ),
    ]

    summary = summarize_peer_reviews(reviews)

    assert "Regulatory Analyst" in summary
    assert len(summary["Regulatory Analyst"]) == 2


def test_build_follow_up_tasks_generates_deduplicated_action_items() -> None:
    reviews = [
        PeerReview(
            reviewer_role="Market Analyst",
            target_role="Regulatory Analyst",
            target_section_title="Licenciamento",
            strengths=["Boa priorização dos riscos."],
            concerns=["Falta quantificação do impacto."],
            questions=["Qual o fallback sem transição?"],
        ),
        PeerReview(
            reviewer_role="Operations Analyst",
            target_role="Regulatory Analyst",
            target_section_title="Licenciamento",
            strengths=["Relaciona bem o cronograma e a operação."],
            concerns=["Falta quantificação do impacto."],
            questions=["Qual licença adicional seria necessária?"],
        ),
    ]

    tasks = build_follow_up_tasks(summarize_peer_reviews(reviews))

    assert tasks["Regulatory Analyst"] == [
        "Responder concern: Falta quantificação do impacto.",
        "Responder question: Qual o fallback sem transição?",
        "Responder question: Qual licença adicional seria necessária?",
    ]


def test_apply_leader_review_updates_deliberation_state() -> None:
    state = DeliberationState(review_cycle=1)
    outputs = [
        ResearchOutput(
            role_name="Regulatory Analyst",
            section_title="Licenciamento",
            findings=["Capital regulatório depende do escopo da licença."],
            evidence=["Briefing base."],
            uncertainties=["Classificação de stablecoin ainda aberta."],
            recommendation="Validar com parecer jurídico.",
        )
    ]

    updated = apply_leader_review(
        state=state,
        research_outputs=outputs,
        accepted_facts=["Existe exigência de capital regulatório mínimo."],
        open_conflicts=["Classificação de stablecoin."],
        pending_gaps=["Parecer jurídico formal."],
        leader_decision="go_for_validation",
        is_sufficient=False,
        rejection_reasons=["Falta evidência primária sobre o enquadramento da rota cambial."],
    )

    assert updated.review_cycle == 2
    assert updated.leader_decision == "go_for_validation"
    assert updated.is_sufficient is False
    assert updated.rejection_reasons == [
        "Falta evidência primária sobre o enquadramento da rota cambial."
    ]
    assert updated.accepted_facts == ["Existe exigência de capital regulatório mínimo."]
    assert updated.open_conflicts == ["Classificação de stablecoin."]
