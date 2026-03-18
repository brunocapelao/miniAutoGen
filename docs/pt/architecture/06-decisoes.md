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
| DA-9 | Renomeação Project→Workspace, Pipeline→Flow, EngineProfile→Engine | Terminologia alinhada com o modelo mental do developer. Drop de sufixos Config redundantes. |
| DA-10 | Agent Runtime como camada local sobre Engine | Runtime adiciona hooks, memory e policies sem reimplementar capacidades do engine. |
| DA-11 | RuntimeInterceptor com hooks tipados (Waterfall/Bail/Series) | Intervenção síncrona no fluxo de execução, complementar ao sistema de policies event-driven. |
| DA-12 | Estratégia multi-provider | "O agente é commodity. O runtime é o produto." Engines intercambiáveis, valor no runtime. |

---

## DA-9: Renomeação de conceitos de primeira classe {#da-9}

**Contexto:** A terminologia original (`Project`, `Pipeline`, `EngineProfile`, sufixos `Config`) refletia uma visão centrada no framework. Com a evolução para uma experiência developer-first, a nomenclatura precisa alinhar-se com os conceitos mentais do utilizador.

**Decisão:** Renomear os conceitos de primeira classe:
- `Project` → **Workspace** (unidade organizacional, familiar de IDEs)
- `Pipeline` → **Flow** (sequência de interações, mais intuitivo para orquestração multi-agente)
- `EngineProfile` → **Engine** (provedor de inteligência, direto e sem sufixo)
- Drop de sufixos `Config` redundantes (e.g., `AgentConfig` → campos diretos no `AgentSpec`)

**Consequências:** Requer migração de configuração (`miniautogen.yml`) e atualização da API pública. Aliases de compatibilidade serão mantidos durante uma versão de transição.

---

## DA-10: Agent Runtime como camada local sobre Engine {#da-10}

**Contexto:** Frameworks concorrentes (LangGraph, CrewAI) reimplementam capacidades do LLM (tool calling, memory) no próprio framework. Isto duplica esforço e cria atrito quando os provedores evoluem.

**Decisão:** O Agent Runtime é uma camada de **capacidades locais** sobre o Engine, não uma reimplementação. O runtime adiciona: hooks de ciclo de vida (`AgentHook`), gestão de memória (`MemoryProvider`), tool registry local e policies por agente. O Engine permanece responsável pela inferência e tool calling nativo.

**Consequências:** A anatomia do agente organiza-se em 5 camadas: Identity → Engine → Runtime → Policies → Protocol Adapters (detalhes em [`07-agent-anatomy.md`](07-agent-anatomy.md)). O runtime nunca duplica capacidades nativas do engine -- apenas as orquestra e enriquece.

---

## DA-11: RuntimeInterceptor com semântica de hooks tipados {#da-11}

**Contexto:** O sistema de policies existente (DA-7) opera lateralmente via eventos. Mas há necessidade de intervenção **síncrona** no fluxo de execução -- transformação de inputs, conditional skip, pós-processamento -- que o modelo event-driven não suporta elegantemente.

**Decisão:** Introduzir o protocolo `RuntimeInterceptor` com semântica de hooks inspirada no Tapable (webpack):
- **Waterfall** (`before_step`): cada interceptor transforma o input e passa ao próximo.
- **Bail** (`should_execute`): qualquer interceptor pode cancelar a execução do passo.
- **Series** (`after_step`): interceptors processam o resultado em série.
- **on_error**: tratamento de erros composível.

Interceptors são composíveis, sem estado global, e registados por ordem de prioridade.

**Consequências:** Complementa (não substitui) o sistema de policies. Policies continuam a operar via eventos para preocupações transversais. Interceptors operam no fluxo de execução para transformações e decisões por passo. Ver [Fluxo 9](04-fluxos.md#fluxo-9-flow-com-interceptors) para detalhes.

---

## DA-12: Estratégia multi-provider {#da-12}

**Contexto:** O mercado de LLMs é commodity em rápida evolução. Vincular o framework a um único provedor (como CrewAI fez inicialmente com OpenAI) cria fragilidade e limita a adoção. Ver [`../../competitive-landscape.md`](../../competitive-landscape.md) para análise detalhada.

**Decisão:** Adotar a filosofia **"O agente é commodity. O runtime é o produto."** O MiniAutoGen:
- Trata engines como recursos intercambiáveis via protocolos tipados (`LLMProviderProtocol`, `AgentDriver`).
- Suporta três categorias de engine: API Providers, CLI Agents e Gateway/Hub.
- Foca o valor diferencial na camada de runtime: coordenação, policies, observabilidade, interceptors e developer experience.

**Consequências:** Nenhum engine recebe tratamento preferencial no core. Novos provedores são integrados exclusivamente via `adapters/` e `backends/`. A API pública é engine-agnostic por design.

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
