# Decisões arquiteturais

## Visão geral

Este documento consolida as decisões arquiteturais (DA) que governam o design do MiniAutoGen. Cada decisão é normativa: violações são consideradas defeitos e devem ser corrigidas antes de merge.

---

## Decisões consolidadas

| ID | Decisão | Racional |
|----|---------|----------|
| DA-1 | Protocolos sobre classes base | Tipagem estrutural via `typing.Protocol` com `@runtime_checkable`. Agentes possuem zero acoplamento ao framework -- qualquer objeto que satisfaça as assinaturas de método é aceite. |
| DA-2 | Planos tipados sobre kwargs | Cada modo de coordenação declara o seu tipo de plano (`WorkflowPlan`, `DeliberationPlan`, `AgenticLoopPlan`). Elimina escape hatches via `**kwargs` e habilita análise estática. |
| DA-3 | Modelos Pydantic com imutabilidade lógica | Todos os contratos são instâncias de `BaseModel`. `Conversation.add_message()` retorna um novo objeto em vez de alterar o existente. `RunContext.with_previous_result()` segue o mesmo padrão. |
| DA-4 | Composição sobre herança para runtimes | `CompositeRuntime` encadeia modos em sequência em vez de exigir um runtime monolítico. Cada modo é independente e testável isoladamente. |
| DA-5 | Superfície de API pública única | `miniautogen/api.py` é o único ponto de importação sancionado (54 tipos exportados). Módulos internos podem ser reestruturados sem quebrar consumidores. |
| DA-6 | Contratos gerais com extensões especializadas | `Contribution` e `Review` são propósito geral. `ResearchOutput` e `PeerReview` estendem-nos para casos de uso de pesquisa. Novos domínios estendem a base, não a bifurcam. |
| DA-7 | Enforcement de políticas como camada separada | Budget, validation, permission, retry e demais políticas residem em `miniautogen/policies/`, desacopladas da lógica de coordenação. Políticas observam e reagem a eventos -- não participam no fluxo de execução. |
| DA-8 | Observabilidade orientada a eventos | Todos os runtimes emitem `ExecutionEvent` com correlation IDs. Observabilidade não depende apenas de logging -- eventos são dados estruturados consumíveis por sinks. |

---

## Coexistência legada

Os pacotes `chat/`, `agent/` e `compat/` contêm a implementação original do MiniAutoGen. Permanecem funcionais e não estão deprecados. A arquitetura nova (Camadas 1-4 conforme descrito em `README.md`) coexiste em paralelo. O pacote `compat/` fornece shims de ponte para conectar código legado aos novos contratos quando necessário.

---

## Componentes experimentais

### SubrunRequest

Contrato definido em `core/contracts/coordination.py` para sub-execuções dentro do `CompositeRuntime`. Marcado explicitamente como experimental (`_EXPERIMENTAL_CONTRACTS`). Nenhum runtime consome este contrato no estado atual. Os campos `input_key` e `output_key` indicam intenção de mapeamento de dados entre sub-runs, mas a mecânica não está implementada.

### SessionRecovery

Classe exportada via `api.py` em `core/runtime/recovery.py`. Oferece `can_resume()`, `load_checkpoint()` e `mark_resumed()` sobre `CheckpointStore`. Funcionalidade básica de retomada de execução a partir de checkpoints. A integração com os modos de coordenação (quem invoca recovery e quando) não está formalizada nos runtimes atuais.

---

## Roadmap técnico

Os seguintes itens estão planejados ou reservados, mas não possuem implementação no estado atual do código.

**Camada 3 -- Padrões canônicos.** Reservada para padrões de composição multi-agente reutilizáveis construídos sobre as Camadas 1-2. Os campos `WorkflowStep.component_name` e `WorkflowStep.config` existem para suportar esta camada, mas nenhum padrão foi implementado.

**Integração OpenTelemetry.** A observabilidade atual utiliza exclusivamente `structlog` via `LoggingEventSink`. A integração com OpenTelemetry para traces distribuídos e métricas está planejada mas não iniciada.

**Backend drivers adicionais.** Apenas `AgentAPIDriver` (HTTP bridge para endpoints OpenAI-compatíveis) está implementado. Drivers para ACP (Agent Communication Protocol) e PTY (terminal local) estão planejados.

**Integração MCP.** O contrato `McpServerBinding` está definido em `core/contracts/mcp_binding.py` com schema para transporte (stdio, SSE, streamable-http), exposição de ferramentas e políticas de execução. A integração efetiva com servidores MCP externos não está completa.
