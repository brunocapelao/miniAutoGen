# Especificação: [Nome da Feature]

| Campo      | Valor                          |
|------------|--------------------------------|
| Data       | YYYY-MM-DD                     |
| Autor      |                                |
| Status     | Rascunho / Em Revisão / Aprovada / Implementada |
| Spec ID    | NNN                            |

---

## Contrato de Prompt (G/C/FC)

### 🎯 Goal (Objetivo)

> O que estamos a construir e porquê.

### 🚧 Constraint (Restrição)

> Que regra arquitetural NÃO será violada.

### 🛑 Failure Condition (Condição de Falha)

> Como provaremos que a implementação falhou. Critérios objetivos e mensuráveis.

---

## User Stories

- Como **[persona]**, quero **[ação]**, para que **[benefício]**.
- Como **[persona]**, quero **[ação]**, para que **[benefício]**.

---

## Critérios de Aceitação

- [ ] Critério 1
- [ ] Critério 2
- [ ] Critério 3
- [ ] Testes unitários passam a 100%
- [ ] Nenhuma regressão introduzida

---

## Invariantes Afetadas

Referência às Regras de Ouro (CLAUDE.md §3). Marque quais são relevantes:

- [ ] **Isolamento de Adapters** — Adapters não vazam para `core/`
- [ ] **Microkernel / PipelineRunner** — Executor único, sem loops paralelos
- [ ] **Assincronismo Canônico (AnyIO)** — Sem código bloqueante no fluxo principal
- [ ] **Policies Event-Driven** — Policies observam e reagem, não controlam

Notas sobre invariantes:
> Descreva como esta feature interage com as invariantes marcadas.

---

## Dependências

| Dependência         | Tipo           | Estado   |
|---------------------|----------------|----------|
| Exemplo: SDK core   | Interna        | Pronta   |
| Exemplo: LiteLLM    | Externa (pip)  | v1.x     |

---

## Notas Adicionais

> Contexto extra, referências, decisões prévias relevantes.
