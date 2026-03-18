# Instruções para GitHub Copilot — MiniAutoGen

Este arquivo orienta o GitHub Copilot no repositório MiniAutoGen.

> **Contexto de operação:** O Copilot opera no contexto de autocomplete e sugestões inline no editor. Ao sugerir código, respeite as invariantes abaixo — especialmente isolamento de adapters (nunca sugerir imports de LLM providers dentro de `core/`) e AnyIO canônico (nunca sugerir `threading` ou `asyncio.run` no core).

> **Fonte canônica:** Todas as regras, invariantes e workflows estão definidos no [`CLAUDE.md`](/CLAUDE.md) na raiz do repositório. Este arquivo apenas resume e referencia — **não duplica**.

---

## Invariantes Arquiteturais (resumo — ver CLAUDE.md §3)

1. **Isolamento de Adapters** — Adapters concretos nunca vazam para `miniautogen/core/`; comunicação apenas via protocolos tipados.
2. **PipelineRunner como único executor** — Proibido criar loops de execução paralelos fora do runner oficial.
3. **Assincronismo com AnyIO** — Código bloqueante no fluxo principal é proibido.
4. **Policies event-driven** — Policies observam e reagem a eventos canônicos, nunca interferem diretamente no core.

Para detalhes completos, consulte [`docs/pt/architecture/05-invariantes.md`](/docs/pt/architecture/05-invariantes.md).

---

## Condições de Rejeição (resumo — ver CLAUDE.md §4)

1. Lógica de provedores externos no `core` ou contratos sem tipagem forte.
2. Classes de erro fora da Taxonomia Canônica (`transient`, `permanent`, `validation`, `timeout`, `cancellation`, `adapter`, `configuration`, `state_consistency`).
3. Declarar tarefa concluída sem testes passando a 100%.
4. Omitir `ExecutionEvent` ao adicionar componente ao ciclo de vida.

---

## Workflow Mandatório (resumo — ver CLAUDE.md §2)

1. **Especificação** — Preencher spec em `/.specs/` antes de codificar.
2. **Test-First** — Escrever testes (AnyIO) antes da implementação.
3. **Contrato G/C/FC** — Declarar Goal, Constraint e Failure Condition.
4. **Commits Atômicos** — Isolados por funcionalidade, atrelados a testes.

---

## Taxonomia de Erros

Todas as classes de erro devem pertencer a: `transient`, `permanent`, `validation`, `timeout`, `cancellation`, `adapter`, `configuration`, `state_consistency`.

---

Para detalhes completos, consulte o [`CLAUDE.md`](/CLAUDE.md) na raiz do repositório.
