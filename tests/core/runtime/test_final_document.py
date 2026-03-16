from miniautogen.core.contracts.deliberation import FinalDocument
from miniautogen.core.runtime.final_document import render_final_document_markdown


def test_render_final_document_markdown_includes_decision_sections() -> None:
    document = FinalDocument(
        executive_summary="Resumo",
        accepted_facts=["Fato confirmado"],
        open_conflicts=["Conflito aberto"],
        pending_decisions=["Decisão pendente"],
        recommendations=["Próximo passo"],
        decision_summary="Go para diligência",
        body_markdown="## Corpo",
    )

    markdown = render_final_document_markdown(document)

    assert "# Resumo Executivo" in markdown
    assert "Go para diligência" in markdown
    assert "## Fatos Aceitos" in markdown
    assert "## Conflitos em Aberto" in markdown
