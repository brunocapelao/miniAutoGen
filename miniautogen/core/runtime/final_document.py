from __future__ import annotations

from miniautogen.core.contracts.deliberation import FinalDocument


def _render_list(items: list[str]) -> str:
    if not items:
        return "- Nenhum item."
    return "\n".join(f"- {item}" for item in items)


def render_final_document_markdown(document: FinalDocument) -> str:
    sections = [
        "# Resumo Executivo",
        document.executive_summary,
        "",
        "## Decisão Recomendada",
        document.decision_summary,
        "",
        "## Fatos Aceitos",
        _render_list(document.accepted_facts),
        "",
        "## Conflitos em Aberto",
        _render_list(document.open_conflicts),
        "",
        "## Decisões Pendentes",
        _render_list(document.pending_decisions),
        "",
        "## Recomendações",
        _render_list(document.recommendations),
        "",
        "## Documento Completo",
        document.body_markdown,
    ]
    return "\n".join(sections)
