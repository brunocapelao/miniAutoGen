# MiniAutoGen

> **O agente é commodity. O runtime é o produto.**

## Sumário executivo

MiniAutoGen é um **runtime Python de orquestração multi-agente multi-provider**. Não reinventa o agente — orquestra agentes reais de qualquer provider (Claude, GPT, Gemini, modelos locais, CLI agents, gateways) em Flows customizados com interceptors composáveis, policies formais e coordenação tipada.

O mercado de agentes convergiu para dois extremos com problemas estruturais: agentes monolíticos poderosos que são silos (Claude Code, Kimi CLI) e frameworks que reinventam o agente mais fraco que o nativo (CrewAI, LangGraph). Recentemente, uma nova onda de "agent harnesses" (DeerFlow, Open SWE, Bit Office) valida a tese de que **infraestrutura composável bate frameworks monolíticos** — mas cada um resolve apenas um caso de uso específico (research, coding, visual office). O MiniAutoGen ocupa o meio inexplorado: o **runtime genérico que coordena o que agentes de diferentes providers fazem juntos**, servindo como base para construir qualquer um desses sistemas especializados.

---

## Os 5 pilares

| Pilar | O que significa |
|---|---|
| **Multi-provider nativo** | Qualquer agente externo é um Engine — API, CLI ou gateway. O framework abstrai a conexão sem enfraquecer o provider. |
| **O agente é o que ele já é** | Cada provider expõe suas capacidades nativas. O MiniAutoGen não reimplementa tool calling, code execution ou memory — usa o que o agente já sabe fazer e adiciona camadas de coordenação. |
| **Runtime customizável** | Interceptors transformam o fluxo. Policies observam e reagem lateralmente. Coordination Modes definem como agentes colaboram. Tudo composável. |
| **Contratos tipados** | Protocols runtime-checkable + Pydantic garantem que agentes de diferentes providers se compõem com segurança. A composição multi-provider é verificada, não assumida. |
| **Operação contínua** | Agentes que operam 24/7 com scheduling, destilação de memória e self-healing. *(roadmap — sem validação de mercado ainda)* |

---

## O modelo mental

O MiniAutoGen organiza-se em torno de **4 conceitos de primeira classe**:

```
Workspace (miniautogen.yml)
├── Engines        — conexão com agentes externos
├── Agents         — Engines enriquecidos com superpoderes locais
├── Flows          — como os Agents colaboram entre si
└── Server/Gateway — como o mundo externo interage com o Workspace
```

### Engines: o agente externo como commodity

O Engine é a conexão com um agente externo. Pode ser uma API stateless (OpenAI, Anthropic, Google), um CLI agent stateful (Claude Code, Gemini CLI, Codex CLI), ou um gateway/hub (OpenClaw). O MiniAutoGen não se importa com a implementação interna do Engine — só precisa que ele fale o protocolo.

Múltiplas instâncias do mesmo provider com configurações diferentes são suportadas (ex: "claude-architect" com skills de arquitetura vs "claude-reviewer" com skills de code review). O agente é o mesmo; o runtime que o envolve é diferente.

### Agents: o Engine + superpoderes

O Agent é um Engine enriquecido com capacidades que o provider sozinho não fornece: tool calling unificado, memória persistente, hooks composáveis, enforcement de permissões e delegação controlada. Essas camadas são adicionadas pelo runtime, não reimplementadas sobre o agente.

A ideia central: **o Agent herda tudo o que o Engine já sabe fazer e ganha coordenação, observabilidade e governança por cima.**

> Para a anatomia completa das 5 camadas do Agent, ver [architecture/07-agent-anatomy.md](architecture/07-agent-anatomy.md).

### Flows: o grande diferencial

O Flow define **como** múltiplos Agents colaboram. Quatro modos de coordenação nativos, composáveis entre si:

| Modo | Quando usar |
|---|---|
| **Workflow** | Tarefas decomponiveis em steps sequenciais ou paralelos |
| **Agentic Loop** | Conversação roteada onde um agente decide quem fala a seguir |
| **Deliberation** | Revisão por pares multi-round com consolidação |
| **Composite** | Encadeamento de sub-Flows de modos diferentes |

**Interceptors** transformam o fluxo em cada step (before, after, on_error) — não apenas observam, modificam. **Policies** observam eventos e reagem lateralmente (budget, timeout, approval, retry). Ambos são composáveis e configuráveis por Flow.

> Para detalhes de implementação dos runtimes, ver [architecture/04-fluxos.md](architecture/04-fluxos.md).

---

## Posicionamento competitivo

> Para análises detalhadas, ver [competitive-landscape.md](../competitive-landscape.md) e [análises de concorrentes](../../.specs/)

### vs Frameworks genéricos

| Dimensão | LangGraph | CrewAI | AutoGen | MiniAutoGen |
|---|---|---|---|---|
| Multi-provider | Acoplado a LangChain | Custom tools/LLMs | Extensions + MCP | **Multi-driver com Protocols formais** |
| Coordenação | Grafo livre (boilerplate pesado) | 2 processos (não-determinístico) | 1 modo (GroupChat, overhead O(n×m)) | **4 modos + composição** |
| Type safety | TypedDict | Nenhum | Parcial | **Protocols + Pydantic** |
| Middleware | Callbacks (observacionais) | Nenhum | Nenhum | **Interceptors (transformativos)** |
| Observabilidade | Via estado | Básico | Básico | **69+ eventos tipados** |
| Tolerância a falhas | Checkpoint recovery | Nenhum | Nenhum | **Supervision trees + circuit breakers** |
| Idempotência | Nenhum | Nenhum | Nenhum | **EffectJournal** |
| Durable execution | Best-in-class | Nenhum | Efémero | Roadmap |

### vs Agent harnesses especializados

| Dimensão | DeerFlow (ByteDance) | Open SWE (LangChain) | Bit Office |
|---|---|---|---|
| **Propósito** | Research agent | Coding agent | Visual multi-agent office |
| **Inovação** | Progressive skill loading, filesystem state, 9 middlewares | Deterministic backstops, SandboxProtocol, ~15 tools curados | Git worktree isolation, memória com feedback loop |
| **Coordenação** | 1 modo | 1 modo | 1 modo |
| **O que lhes falta** | Supervision, idempotência, type safety, múltiplos modos | Generalidade, observabilidade built-in | Persistência robusta, flexibilidade |

Cada harness valida a tese do MiniAutoGen — e poderia ser **construído usando MiniAutoGen como runtime base**.

### vs Padrões Anthropic

A Anthropic documenta [6 padrões compostos](https://www.anthropic.com/engineering/building-effective-agents) para sistemas agênticos. O MiniAutoGen cobre todos nativamente:

| Padrão | Runtime correspondente |
|---|---|
| Prompt Chaining | Workflow (steps sequenciais) |
| Routing | Agentic Loop (router decide speaker) |
| Parallelization | Workflow (fan-out + synthesis) |
| Orchestrator-Workers | Composite (orquestrador + workers) |
| Evaluator-Optimizer | Deliberation (contribute → review → refine) |
| Autonomous Agents | Agentic Loop (com detecção de estagnação) |

### Quadrante único

```
     Flexibilidade de composição
          ▲
          │
          │  LangGraph ●
          │                    ★ MiniAutoGen
          │
          │  AutoGen ●              DeerFlow ●
          │
          │  CrewAI ●
          │
          └──────────────────────────────────► Type safety
```

**Alta flexibilidade + Alta type safety.** Nenhum concorrente ocupa este quadrante.

---

## Validação de mercado

A análise de 7 concorrentes e 1 artigo de referência confirma as 3 teses centrais:

**Tese 1 — O agente é commodity, o runtime é o produto.**
Bit Office trata Claude/Codex/Gemini como processos intercambiáveis. Open SWE troca modelo em 1 linha. DeerFlow lista 4+ modelos como opções equivalentes. O artigo "5 Agent Frameworks, One Pattern Won" prova que **13× de diferença de custo** vem do runtime, não do modelo.

**Tese 2 — Infraestrutura composável bate monolítica.**
Progressive skill loading + filesystem-first state + middleware pipeline reduz custos de $4.93 para $0.38 por run (13×). DeerFlow e Open SWE validam este padrão. O MiniAutoGen já está alinhado: microkernel com policies plugáveis, protocols tipados e arquitetura event-driven.

**Tese 3 — Nenhum concorrente oferece 4 modos de coordenação com type safety.**
AutoGen tem 1 modo. CrewAI tem 2 (não-determinísticos). DeerFlow tem 1. Open SWE tem 1. LangGraph tem grafos livres sem type safety forte. **Nenhum combina múltiplos modos + Protocols runtime-checkable.**

> Análises completas: [Bit Office](../../.specs/analysis-bit-office-vs-miniautogen.md) · [5 Frameworks](../../.specs/analysis-5-frameworks-one-pattern.md) · [Deep Dive Concorrentes](../../.specs/analysis-competitors-deep-dive.md) · [Open SWE](../../.specs/analysis-open-swe.md)

---

## Documentação

### Estratégia e posicionamento

| Documento | Conteúdo |
|---|---|
| **Este README** | Visão, pilares, modelo mental, posicionamento competitivo |
| [competitive-landscape.md](../competitive-landscape.md) | 10+ frameworks, tese estratégica, roadmap 4 fases |
| [agent-frameworks-research-2026.md](../agent-frameworks-research-2026.md) | A2A, Agent SDK, ACP, Swarm, ADK |

### Arquitetura

| # | Documento | Conteúdo |
|---|---|---|
| 1 | [Contexto do sistema](architecture/01-contexto.md) | Posicionamento e fronteiras externas |
| 2 | [Containers lógicos](architecture/02-containers.md) | Workspace, Core, CLI, TUI, Adapters |
| 3 | [Componentes internos](architecture/03-componentes.md) | Módulos, contratos, protocols |
| 4 | [Fluxos de execução](architecture/04-fluxos.md) | Coordenação, workspace, interceptors |
| 5 | [Invariantes e taxonomias](architecture/05-invariantes.md) | Regras invioláveis, 69+ event types |
| 6 | [Decisões arquiteturais](architecture/06-decisoes.md) | 12 ADRs (DA-1 a DA-12) |
| 7 | [Anatomia do agente](architecture/07-agent-anatomy.md) | 5 layers, comparação com 10+ protocols |
| 8 | [Stack tecnológica](architecture/08-tech-stack.md) | Dependências e justificativas |
| 9 | [Invariantes do SO](architecture/09-invariantes-sistema-operacional.md) | 6 invariantes invioláveis |

### Operacional

| Documento | Conteúdo |
|---|---|
| [Retrospectiva arquitetural](../architecture-retrospective.md) | v0 vs atual, plano de recuperação |
| [Plano LangGraph](plano-langgraph.md) | Spec para durable execution |
| [Referência rápida](quick-reference.md) | Índice compacto de módulos e API pública |
| [Guia Gemini CLI](guides/gemini-cli-gateway.md) | Configuração do backend Gemini CLI |
| [Spec funcional E2E](e2e-funcional.md) | Jornada completa CLI-First |

---

## Leitura recomendada

**5 minutos →** Este README.

**30 minutos →** Este README + [competitive-landscape.md](../competitive-landscape.md).

**Vai contribuir →** Sequência de arquitetura (1→9) + [e2e-funcional.md](e2e-funcional.md).
