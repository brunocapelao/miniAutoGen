from miniautogen.core.contracts.deliberation import (
    DeliberationState,
    FinalDocument,
    PeerReview,
    ResearchOutput,
)


def test_research_output_separates_facts_from_inferences() -> None:
    output = ResearchOutput(
        role_name="Regulatory Analyst",
        section_title="Licenciamento",
        findings=["Há janela de transição até 30/10/2026."],
        facts=["A janela regulatória termina em 30/10/2026."],
        evidence=["Briefing base indica prazo de protocolo."],
        inferences=[
            "A cooperativa precisa protocolar antes do prazo para preservar opcionalidade."
        ],
        uncertainties=["Falta parecer formal sobre continuidade operacional."],
        recommendation="Contratar parecer jurídico antes de estruturar o capital.",
        next_tests=[
            "Validar a elegibilidade da operação ao regime transitório com parecer externo."
        ],
    )

    assert output.role_name == "Regulatory Analyst"
    assert output.facts == ["A janela regulatória termina em 30/10/2026."]
    assert output.inferences == [
        "A cooperativa precisa protocolar antes do prazo para preservar opcionalidade."
    ]
    assert output.next_tests == [
        "Validar a elegibilidade da operação ao regime transitório com parecer externo."
    ]


def test_peer_review_tracks_strengths_concerns_and_questions() -> None:
    review = PeerReview(
        reviewer_role="Market Analyst",
        target_role="Regulatory Analyst",
        target_section_title="Licenciamento",
        strengths=["Identifica o risco central do projeto."],
        concerns=["Não quantifica o impacto financeiro do risco."],
        questions=["Qual é o cenário sem elegibilidade à transição?"],
    )

    assert review.target_role == "Regulatory Analyst"
    assert review.concerns == ["Não quantifica o impacto financeiro do risco."]


def test_deliberation_state_defaults_to_open_decision_space() -> None:
    state = DeliberationState()

    assert state.review_cycle == 0
    assert state.accepted_facts == []
    assert state.open_conflicts == []
    assert state.pending_gaps == []
    assert state.leader_decision is None


def test_final_document_exposes_decision_trace() -> None:
    document = FinalDocument(
        executive_summary="Projeto depende de validação jurídica antes da implantação.",
        accepted_facts=["A operação atual tem TPV aproximado de R$ 50M/mês."],
        open_conflicts=["Enquadramento regulatório da rota com stablecoin."],
        pending_decisions=["Definir escopo da licença VASP."],
        recommendations=["Executar diligência jurídica externa."],
        decision_summary=(
            "Go para diligência jurídica e regulatória antes da abertura da cooperativa."
        ),
        body_markdown="# Dossiê\n\nConteúdo consolidado.",
    )

    assert document.pending_decisions == ["Definir escopo da licença VASP."]
    assert (
        document.decision_summary
        == "Go para diligência jurídica e regulatória antes da abertura da cooperativa."
    )
    assert document.body_markdown.startswith("# Dossiê")
