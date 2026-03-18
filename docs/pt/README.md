# MiniAutoGen

> **O agente é commodity. O runtime é o produto.**

## Sumário executivo

MiniAutoGen é um **runtime Python de orquestração multi-agente multi-provider**. Não reinventa o agente — orquestra agentes reais de qualquer provider (Claude, GPT, Gemini, modelos locais, CLI agents) em Flows customizados com interceptors composáveis, policies formais e coordenação tipada.

O mercado de agentes convergiu para dois extremos com problemas estruturais: agentes monolíticos poderosos que são silos (Claude Code, Kimi CLI) e frameworks que reinventam o agente mais fraco que o nativo (CrewAI, LangGraph). O MiniAutoGen ocupa o meio inexplorado: o **runtime que coordena o que agentes de diferentes providers fazem juntos**.

### Os 5 pilares

| Pilar | O que faz |
|---|---|
| **Multi-provider nativo** | AgentDriver abstrai Claude, GPT, Gemini, modelos locais, CLI agents, gateways |
| **Runtime customizável** | Interceptors + Policies + Coordination Modes composáveis em Flows |
| **O agente é o que ele já é** | Cada provider expõe suas capacidades nativas — o framework não as enfraquece |
| **Contratos tipados** | Protocols + Pydantic garantem segurança na composição multi-provider |
| **Operação contínua** | Scheduler + MemoryDistiller + self-healing para agentes 24/7 (roadmap) |

---

## Conceitos de primeira classe

O MiniAutoGen organiza-se em torno de **4 conceitos de primeira classe**:

```
Workspace (miniautogen.yml)
├── Engines        — conexão com agentes externos (Claude Code, GPT API, Gemini CLI, ...)
├── Agents         — abstração sobre Engines com runtime próprio (tools, memory, hooks)
├── Flows          — orquestração com interceptors, policies e coordenação composável
└── Server/Gateway — exposição externa (capacidade do Workspace)
```

### Workspace

O container de mais alto nível. Define Engines, Agents, Flows e Defaults num único ficheiro `miniautogen.yml`. Também atua como servidor/gateway para interação externa.

### Engines

A conexão com agentes monolíticos externos — a peça-chave da estratégia multi-provider. Três categorias:

| Categoria | Exemplos | Driver |
|---|---|---|
| **API Providers** (stateless) | OpenAI, Anthropic, Google, LiteLLM | OpenAISDKDriver, AnthropicSDKDriver, GoogleGenAIDriver |
| **CLI Agents** (stateful, subprocess) | Claude Code, Gemini CLI, Codex CLI | CLIAgentDriver |
| **Gateway/Hub** (stateful, WebSocket) | OpenClaw | WebSocketDriver (proposto) |

Múltiplas instâncias do mesmo provider com configurações diferentes são suportadas (ex: "claude-architect" com skills de arquitetura vs "claude-reviewer" com skills de code review).

### Agents

Abstração sobre Engines com **5 camadas**:

```
Agent
├── Layer 1: Identity      — AgentSpec (name, role, goal, capabilities)
├── Layer 2: Engine        — Binding para o driver concreto
├── Layer 3: Agent Runtime — Tools, memory, hooks, delegation (O DIFERENCIAL)
├── Layer 4: Policies      — Limits, permissions, budget, retry
└── Layer 5: Protocols     — Como participa de Flows (workflow/deliberation/conversational/coordinator)
```

O Agent Runtime (Layer 3) adiciona capacidades locais que o Engine sozinho não fornece: tool calling unificado, memória persistente, hooks composáveis, enforcement de permissões e delegação controlada. Para anatomia completa, ver [architecture/07-agent-anatomy.md](architecture/07-agent-anatomy.md).

### Flows

O **grande diferencial competitivo**. Quatro modos de coordenação nativos, composáveis via CompositeRuntime:

| Modo | Como funciona |
|---|---|
| **WorkflowRuntime** | Steps sequenciais ou fan-out paralelo com synthesis opcional |
| **AgenticLoopRuntime** | Router seleciona próximo speaker, com detecção de estagnação |
| **DeliberationRuntime** | Rounds de contribuição + peer review + consolidação por líder |
| **CompositeRuntime** | Encadeia sub-Flows de modos diferentes numa única execução |

**RuntimeInterceptors** (proposto): middleware composável e transformativo nos Flows. Tipos de hook inspirados no Tapable (Webpack): Waterfall (transforma), Bail (short-circuit), Series (observa). Boundary-aware: FlowInterceptor, StepInterceptor, AgentInterceptor. Nenhum framework concorrente oferece middleware transformativo em runtimes agênticos.

---

## Arquitetura

A arquitetura segue o pattern **Microkernel** com 4 camadas:

| Camada | Responsabilidade | Módulos |
|---|---|---|
| **Core/Kernel** | Contratos, eventos, runtimes de coordenação | `core/contracts/`, `core/events/`, `core/runtime/` |
| **Policies** | Regras transversais (retry, budget, approval, timeout) | `policies/` |
| **Adapters** | Drivers de backend, templates, LLM providers | `backends/`, `adapters/` |
| **Shell** | CLI, TUI Dashboard, Server | `cli/`, `tui/`, `app/` |

O sistema emite **47+ tipos de evento** canônicos em 12 categorias, garantindo observabilidade completa. Oito políticas transversais operam **lateralmente** ao kernel, reagindo a eventos sem acoplar-se à lógica central.

**Invariante central:** Adapters concretos NUNCA vazam para o domínio interno. O Core comunica apenas através de Protocols tipados.

---

## Como funciona

```
Developer define:                    MiniAutoGen executa:
┌──────────────┐                    ┌─────────────────────────────┐
│ miniautogen  │                    │ PipelineRunner              │
│ .yml         │                    │  ├── Resolve Engines        │
│              │───────────────────►│  ├── Build Agent Runtimes   │
│ engines:     │                    │  ├── Apply Interceptors     │
│ agents:      │                    │  ├── Execute Flow           │
│ flows:       │                    │  │   ├── Coordination Mode  │
│ defaults:    │                    │  │   ├── Agent Turns        │
└──────────────┘                    │  │   └── Event Emission     │
                                    │  └── Persist Results        │
                                    └─────────────────────────────┘
```

1. O Workspace define Engines, Agents e Flows declarativamente
2. O EngineResolver converte engine names em AgentDrivers concretos
3. O Agent Runtime enriquece cada Engine com tools, memory e hooks locais
4. O PipelineRunner executa o Flow com o Coordination Mode selecionado
5. Interceptors transformam o fluxo em cada step (before, after, on_error)
6. Policies observam eventos e aplicam regras (budget, timeout, approval)
7. EventSink emite eventos canônicos para observabilidade

---

## Posicionamento competitivo

> Para análise detalhada, ver [competitive-landscape.md](../competitive-landscape.md)

| Dimensão | LangGraph | Agno | CrewAI | MiniAutoGen |
|---|---|---|---|---|
| Multi-provider | Acoplado a LangChain | Sim (types fracos) | Custom tools/LLMs | **7 drivers, Protocols formais** |
| Composição | Grafo estático | 3 team modes (mutuamente exclusivos) | Process fixo | **4 runtimes + CompositeRuntime + Interceptors** |
| Type safety | Typed state | Básico | Nenhum | **Protocols + Pydantic** |
| Middleware | Callbacks (observacionais) | Guardrails (validação) | Nenhum | **Interceptors (transformativos)** |
| Durable execution | Best-in-class | Session-level | Nenhum | Roadmap Fase 2 |

**Quadrante único:** Alta flexibilidade de composição + Alta type safety. Nenhum concorrente ocupa este quadrante.

---

## Navegação da documentação

### Documentos estratégicos

- [Análise competitiva](../competitive-landscape.md) — 10+ frameworks, tese estratégica, roadmap 4 fases
- [Retrospectiva arquitetural](../architecture-retrospective.md) — v0 vs atual, features perdidas, plano de recuperação
- [Pesquisa de frameworks](../agent-frameworks-research-2026.md) — A2A, Agent SDK, ACP, Swarm, ADK
- [Plano de superação do LangGraph](plano-langgraph.md) — spec para durable execution e composição superior

### Documentos de arquitetura

1. [Contexto do sistema](architecture/01-contexto.md) — posicionamento e fronteiras externas
2. [Containers lógicos](architecture/02-containers.md) — Workspace, Core, CLI, TUI, Adapters
3. [Componentes internos](architecture/03-componentes.md) — módulos, contratos, protocols
4. [Fluxos de execução](architecture/04-fluxos.md) — 9 fluxos (coordenação, workspace, interceptors)
5. [Invariantes e taxonomias](architecture/05-invariantes.md) — regras invioláveis, 47+ event types
6. [Decisões arquiteturais](architecture/06-decisoes.md) — 12 ADRs (DA-1 a DA-12)
7. [Anatomia do agente](architecture/07-agent-anatomy.md) — 5 layers, comparação com 10+ protocols de mercado
8. [Stack tecnológica](architecture/08-tech-stack.md) — dependências, justificativas, diagrama de dependências
9. [Invariantes do Sistema Operacional](architecture/09-invariantes-sistema-operacional.md) — 6 invariantes invioláveis, auditoria arquitetural, plano de ação

### Referências

- [Referência rápida dos módulos](quick-reference.md) — índice compacto de pacotes
- [Guia do Gemini CLI Gateway](guides/gemini-cli-gateway.md) — configuração do backend Gemini CLI
- [Especificação funcional E2E](e2e-funcional.md) — jornada completa CLI-First (v3.2.0)

---

## Leitura recomendada

Para compreensão completa, recomenda-se:

**Se tem 5 minutos:** Leia apenas este README.

**Se tem 30 minutos:** Este README + [competitive-landscape.md](../competitive-landscape.md) (posicionamento + roadmap).

**Se vai contribuir:** Sequência completa de arquitetura (1→7) + [e2e-funcional.md](e2e-funcional.md).

---

## API pública

O módulo `miniautogen/api.py` exporta 54+ tipos e constitui o ponto de entrada único para consumidores da biblioteca:

```python
from miniautogen.api import (
    WorkflowRuntime, DeliberationRuntime, AgenticLoopRuntime,
    PipelineRunner, AgentSpec, RunContext, EventSink,
)
```
