# Anatomia do Agente MiniAutoGen

> **Status de Implementação:** Todas as 5 camadas estão implementadas. Camadas 1 (Identity) e 2 (Engine) desde a versão inicial. Camadas 3 (Agent Runtime), 4 (Policies per-agent) e 5 (CoordinatorAgent) implementadas em 2026-03.

**Versão:** 1.0.0
**Data:** 2025-06-18
**Tipo:** Analítico + Prescritivo

> Este documento define a anatomia completa do Agente no MiniAutoGen: o que ele é, como se compara com o mercado, e como deve ser implementado. Serve simultaneamente como análise competitiva e especificação técnica.

---

## Índice

1. [Tese Fundamental](#1-tese-fundamental)
2. [Evolução: do v0 ao Agente Atual](#2-evolução-do-v0-ao-agente-atual)
3. [Análise Comparativa de Mercado](#3-análise-comparativa-de-mercado)
4. [Anatomia Prescritiva do Agente](#4-anatomia-prescritiva-do-agente)
5. [O Agente e seus Engines](#5-o-agente-e-seus-engines)
6. [Runtime do Agente](#6-runtime-do-agente)
7. [Interoperabilidade e Protocols](#7-interoperabilidade-e-protocols)
8. [Diferenciais e Posicionamento](#8-diferenciais-e-posicionamento)

---

## 1. Tese Fundamental

> **O agente é commodity. O runtime é o produto.**

MiniAutoGen não reinventa o agente. Agentes nativos (Claude, GPT, Gemini) são mais capazes que qualquer agente construído por framework. O valor do MiniAutoGen está em:

1. **Abstrair** agentes de qualquer provider via Engines (AgentDriver)
2. **Enriquecer** o agente com runtime próprio (tools, memory, permissions, delegation)
3. **Orquestrar** múltiplos agentes em Flows com interceptors, policies e coordenação composável
4. **Monitorar** tudo com eventos canônicos e observabilidade built-in

O Agente MiniAutoGen é uma **camada de capacidades** sobre um Engine, não uma reimplementação do Engine.

```
┌─────────────────────────────────────────────────┐
│                   Agent                          │
│  ┌───────────┬──────────┬────────────────────┐  │
│  │ Identity  │ Policies │ Agent Runtime       │  │
│  │ (spec)    │ (limits) │ (tools, memory,     │  │
│  │           │          │  permissions, hooks) │  │
│  └─────┬─────┴────┬─────┴──────────┬─────────┘  │
│        │          │                │             │
│  ┌─────▼──────────▼────────────────▼─────────┐  │
│  │              Engine (AgentDriver)          │  │
│  │  Claude Code │ GPT API │ Gemini CLI │ ... │  │
│  └────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

---

## 2. Evolução: do v0 ao Agente Atual

> Para análise completa, ver [architecture-retrospective.md](../../architecture-retrospective.md)

### v0 (commit 9d2ee2f) — O Agente Simples

```python
class Agent:
    agent_id: str
    name: str
    role: str
    pipeline: Optional[Pipeline] = None
    status: str = "available"

    async def generate_reply(state: ChatPipelineState) -> str: ...

class ChatAdmin(Agent):  # Orquestrador ERA um agente
    chat: Chat
    goal: str
    max_rounds: int
```

**O que funcionava:**
- Simplicidade radical — usável em 5 minutos
- `ChatAdmin extends Agent` — composição recursiva natural
- `from_json()` — instanciação declarativa
- Pipeline como runtime do agente — cada agente tinha sua cadeia de componentes

**O que não funcionava:**
- Sem tipagem (duck typing, dict mutável como state)
- Síncrono (sem async/await)
- Sem contratos (qualquer coisa podia ser agente)
- Sem observabilidade (logging.info apenas)

### Atual (main) — O Agente Tipado

```python
# 3 protocolos de capacidade
class WorkflowAgent(Protocol):
    async def process(self, input: Any) -> Any: ...

class DeliberationAgent(Protocol):
    async def contribute(self, topic: str) -> Contribution: ...
    async def review(self, target_id: str, contribution: Contribution) -> Review: ...

class ConversationalAgent(Protocol):
    async def reply(self, message: str, context: dict) -> str: ...
    async def route(self, history: list) -> RouterDecision: ...

# Spec declarativa
class AgentSpec(BaseModel):
    id, version, name, description, role, goal, backstory
    skills, tool_access, mcp_access, memory, delegation, runtime, permissions
    engine_profile: str | None
```

**O que ganhou:**
- Contratos tipados (Protocols + Pydantic)
- 4 modos de participação (workflow, deliberation, conversational, coordinator)
- AgentSpec como spec declarativa YAML completa
- Engine como abstração do backend (6 drivers implementados)

**O que perdeu:**
- `ChatAdmin extends Agent` (composição recursiva)
- Pipeline como runtime do agente (agente não tem runtime próprio)
- Simplicidade de instanciação (5 min → 30 min)

### Alvo — O Agente Completo

O agente deve recuperar o que se perdeu (runtime próprio, composição recursiva, simplicidade) com a robustez do que se ganhou (tipos, protocols, observabilidade).

---

## 3. Análise Comparativa de Mercado

### 3.1 Matriz de Protocolos e Frameworks

| Dimensão | Google A2A | Anthropic Agent SDK | ACP | OpenAI Swarm | Google ADK | MiniAutoGen |
|---|---|---|---|---|---|---|
| **Foco** | Inter-agente (descoberta + comunicação) | Construir agentes com Claude | Comunicação padronizada | Handoff entre agentes | Construir agentes com Gemini | Orquestrar agentes de qualquer provider |
| **Agent Model** | Agent Card (JSON-LD) | Agent com tools + guardrails | Agent com endpoints | Função Python + instructions | Agent com tools + sub-agents | AgentSpec (Pydantic) + Engine |
| **Comunicação** | HTTP + JSON-RPC (Tasks) | Tool calls via API | Mensagens padronizadas | Return values + handoff() | gRPC/HTTP entre agents | EventSink + Conversation |
| **Multi-provider** | Agnóstico (protocol) | Claude only | Agnóstico (protocol) | OpenAI only | Gemini only | ✅ Qualquer via AgentDriver |
| **Runtime próprio** | Não (só protocol) | Sim (loop + tools) | Não (só protocol) | Mínimo (loop simples) | Sim (loop + tools) | ✅ Agent Runtime (implementado) |
| **Tool calling** | Via provider | Nativo + guardrails | Via provider | Nativo | Nativo + MCP | ✅ ToolProtocol + MCP |
| **Observabilidade** | Não | Básica | Não | Não | Tracing built-in | ✅ 63 EventTypes |

### 3.2 Google A2A (Agent-to-Agent Protocol)

**O que é:** Protocol aberto para descoberta e comunicação inter-agente. Não é um framework — é um protocolo. Não define como construir agentes, define como agentes se encontram e conversam via HTTP + JSON-RPC.

**Conceitos-chave:**
- **Agent Card** — Documento JSON-LD que descreve capacidades, skills, endpoints e mecanismos de autenticação do agente. Funciona como um "cartão de visita" machine-readable
- **Tasks** — Unidade de trabalho com lifecycle completo (submitted → working → completed/failed). Cada task tem estado, artefatos e histórico
- **Comunicação** — HTTP + JSON-RPC como transporte. Sem opinião sobre o runtime interno do agente
- **Streaming** — SSE (Server-Sent Events) para updates em tempo real durante execução de tasks
- **Push Notifications** — Webhooks para notificações assíncronas quando tasks mudam de estado
- **Provider-agnostic** — É apenas um protocolo. Qualquer agente (Claude, GPT, Gemini, custom) pode implementá-lo
- **Sem runtime, sem tools** — A2A não fornece nenhuma infraestrutura de execução. Apenas define a interface de comunicação

**Relevância para MiniAutoGen:** A2A é complementar, não competitivo. MiniAutoGen poderia **expor** seus agentes via A2A Agent Cards (o AgentSpec já contém toda a informação necessária para gerar um Agent Card) **e consumir** agentes A2A como Engines via um futuro `A2ADriver`. O Agent Card é análogo ao AgentSpec — ambos descrevem capacidades declarativamente. A diferença: AgentSpec é interno (configuração do runtime), Agent Card é externo (descoberta por outros agentes).

### 3.3 Anthropic Agent SDK

**O que é:** SDK Python que empacota o agent loop do Claude Code como biblioteca. Filosofia: "dar ao Claude acesso a um computador." Config-driven — não existe classe `Agent`; agentes são definidos implicitamente via `query()` ou `ClaudeSDKClient` com `ClaudeAgentOptions`.

**Conceitos-chave:**
- **Config-driven (sem classe Agent)** — Agentes definidos via `ClaudeAgentOptions`: `system_prompt`, `allowed_tools`, `mcp_servers`, `agents` (subagents), `cwd`, `model`, `max_turns`, `permission_mode`. Wrapa o Claude Code CLI via subprocess NDJSON
- **Rich built-in tools** — Mesmo toolset do Claude Code: Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, AskUserQuestion, Agent (delegação a subagents)
- **Guardrails como first-class** — Pipeline de permissão em cascata: `allowed_tools` (auto-approve) → `disallowed_tools` (block) → `permission_mode` → `can_use_tool` (callback customizado). Hooks em cada ponto do lifecycle: `PreToolUse`, `PostToolUse`, `Stop`, `SessionStart`, `SessionEnd`, `UserPromptSubmit`
- **Subagent delegation** — Agentes delegam para subagents nomeados via tool `Agent`. Subagents correm em contexto isolado e retornam resultado ao parent. Tracking via `parent_tool_use_id`
- **MCP built-in** — Suporte a MCP servers externos (stdio/SSE) e in-process SDK MCP servers (zero overhead de subprocess)
- **Session persistence** — Sessões stateful via `ClaudeSDKClient` com resume via `session_id`
- **Claude-only** — Fortemente acoplado à API da Anthropic. Suporta Bedrock, Vertex AI e Azure AI Foundry, mas sempre Claude como modelo

**Relevância para MiniAutoGen:** O Agent SDK reinventa o agent loop — constrói uma abstração completa sobre Claude. MiniAutoGen delega ao Claude nativamente via `AgentAPIDriver` ou `CLIAgentDriver` sem precisar do Agent SDK. Contudo, dois patterns são valiosos para absorver: (1) o pattern de **guardrails** como hooks composáveis com validação de input/output (análogo ao `PermissionsEnforcerHook` e `BudgetGuardHook` propostos no Agent Runtime), e (2) o pattern de **handoff** entre agentes com contexto isolado (análogo ao `RouterDecision` no `AgenticLoopRuntime`, mas com tipagem e detecção de stagnation mais robustas no MiniAutoGen).

### 3.4 OpenAI Swarm → Agents SDK

**O que é:** Swarm foi um framework educacional para multi-agente com handoff; agora supersedido pelo **OpenAI Agents SDK** (Março 2025), a evolução production-ready. Modelo limpo de 4 primitivas: Agents, Handoffs, Guardrails, Tools.

**Conceitos-chave:**
- **4 primitivas** — `Agent` (instructions + tools + handoffs + guardrails), `Handoff` (transferência de controlo), `Guardrail` (validação input/output), `Tool` (funções com schema automático via type hints)
- **Dois patterns de delegação** — (1) **Handoffs**: transferem controlo completamente para outro agente (one-way, sem retorno). (2) **Agents-as-tools** via `agent.as_tool()`: delegação com retorno ao caller (pattern manager). Distinção fundamental para orquestração
- **Guardrails paralelas com tripwire** — Input guardrails podem correr em paralelo com o agente (latência zero). Output guardrails validam após output. Mecanismo tripwire: falha levanta exceção e interrompe execução imediatamente
- **Context genérico** — `Agent[ContextType]` com `RunContextWrapper` injeta dependências/estado em tools, handoffs e callbacks
- **Handoff customizável** — `handoff()` com `on_handoff` callback, `input_filter` (filtra histórico), `input_type` (metadata Pydantic), `is_enabled` (toggle runtime)
- **Structured outputs** — `output_type` como modelo Pydantic para outputs tipados
- **Tracing built-in** — Compatível com ferramentas de eval/fine-tuning da OpenAI
- **OpenAI-centric** — Documentação para providers não-OpenAI existe, mas o ecossistema é centrado na API OpenAI

**Relevância para MiniAutoGen:** A distinção entre handoffs (transferência) e agents-as-tools (delegação com retorno) é a insight mais valiosa. No MiniAutoGen, `RouterDecision` trata o caso handoff; `ToolProtocol` trata o caso invoke-as-tool. Ambos os patterns devem existir como cidadãos de primeira classe. O mecanismo de guardrails paralelas com tripwire é superior ao modelo callback simples — worth absorbing no `AgentHook` system.

### 3.5 Google ADK (Agent Development Kit)

**O que é:** O framework de agentes mais completo do mercado. Cobre o ciclo completo: definição, orquestração, ferramentas, deployment e avaliação. SDKs em Python, TypeScript, Go e Java. Complementar ao A2A: ADK constrói agentes, A2A conecta-os.

**Conceitos-chave:**
- **Três tipos de agente** — `LlmAgent` (non-deterministic, language-driven), `WorkflowAgent` (determinístico: Sequential, Parallel, Loop), `CustomAgent` (extend `BaseAgent` para lógica única). Separação clara entre orquestração adaptativa e determinística
- **6 patterns canónicos de multi-agente** — Coordinator/Dispatcher, Sequential Pipeline, Parallel Fan-Out/Gather, Hierarchical Decomposition, Generator-Critic, Iterative Refinement. Todos documentados com implementações de referência
- **60+ tool integrations** — Function tools, MCP tools (+ MCP Toolbox para 30+ data sources), OpenAPI tools, AgentTool (agents-as-tools), code execution, computer use, Google Search, BigQuery, MongoDB, GitHub, Slack, etc. O ecossistema de tools mais rico
- **Shared session state** — Agentes que partilham `InvocationContext` acedem ao mesmo `session.state`. Um agente escreve via `output_key`, agentes subsequentes lêem. Coordenação passiva e assíncrona
- **LLM-driven delegation** — `transfer_to_agent(agent_name='target')` interceptado pelo AutoFlow. Requer `description` clara nos agentes-alvo para routing pelo LLM
- **Instructions dinâmicas** — Suporte a `{var}` interpolation com state variables, permitindo prompts que se adaptam ao contexto da sessão
- **Evaluation framework built-in** — Test cases para medir qualidade dos agentes ao longo do tempo
- **A2A-compatible** — Agentes ADK podem ser expostos como serviços A2A para comunicação inter-sistema
- **Gemini-centric** — Apesar de declarar model-agnosticism, o ecossistema é centrado no Gemini. `output_schema` + `tools` só funciona com Gemini 3.0+

**Relevância para MiniAutoGen:** A separação LLM agent + Workflow agent mapeia diretamente para `ConversationalAgent` + `WorkflowAgent` do MiniAutoGen. A coordenação de session state via `RunContext` é análoga. O pattern de **sub-agent delegation** é diretamente análogo ao `CoordinatorCapability` proposto — um agente coordenador que instancia sub-Flows com participantes selecionados. O **evaluation framework** é um diferenciador futuro: MiniAutoGen deveria considerar um `EvaluationPolicy`. MiniAutoGen já usa Gemini via `GoogleGenAIDriver` ou `CLIAgentDriver` (gemini-cli), tornando a abstração do ADK redundante para quem usa MiniAutoGen.

### 3.6 MCP (Model Context Protocol)

**O que é:** Protocolo JSON-RPC 2.0 da Anthropic para expor ferramentas, recursos e prompts a modelos de linguagem via servers. Adoptado como standard de facto por Anthropic, OpenAI e Google ADK para integração de tools.

**Conceitos-chave:**
- **4 primitivas de servidor** — (1) **Resources**: dados read-only que o cliente pode consultar (ficheiros, schemas, docs). (2) **Tools**: funções invocáveis pelo modelo (o modelo decide quando chamar). (3) **Prompts**: workflows templated que o utilizador pode selecionar. (4) **Sampling**: servidor pede ao cliente que invoque o LLM (inversão de controlo — o server não precisa de API key)
- **Transporte dual** — `stdio` para servers locais (subprocess, latência mínima) e `Streamable HTTP` para servers remotos (substituiu SSE). Ambos suportam streaming bidireccional
- **Lifecycle** — Handshake com capability negotiation → operação normal com requests/notifications → shutdown gracioso
- **Ecossistema universal** — Claude Agent SDK, OpenAI Agents SDK e Google ADK suportam MCP nativamente. Centenas de servers disponíveis para bases de dados, APIs, file systems, browsers, etc.

**Relevância para MiniAutoGen:** MiniAutoGen pode **consumir** MCP servers como tools via Python SDK `ClientSession` — qualquer MCP server torna-se uma tool disponível para agentes. MiniAutoGen pode **expor-se** como MCP server via `FastMCP` — agentes MiniAutoGen ficam acessíveis a Claude Code, Cursor, etc. `McpAccessConfig` já existe no `AgentSpec` para configuração declarativa de MCP servers por agente.

### 3.7 Padrões Emergentes

Além dos frameworks principais, vários projectos validam teses arquitecturais relevantes para o MiniAutoGen:

| Projecto | O que é | Insight para MiniAutoGen |
|---|---|---|
| **Perplexity Computer** | Orquestrador de 19 modelos com task decomposition e isolamento via Firecracker VMs | Valida a tese multi-provider: orquestração sobre múltiplos modelos especializados é superior a modelo único. Isolamento de execução via VMs é análogo ao subprocess isolation do `CLIAgentDriver` |
| **Replit Agent 4** | Execução multi-agente em paralelo com scope isolation e sub-agentes de conflict resolution | Valida o pattern fan-out do MiniAutoGen. Conflict resolution como sub-agente dedicado é um pattern interessante para o `CoordinatorCapability` |
| **CCManager** | Session manager para 8+ AI agents em git worktrees paralelos | Gere sessões, não orquestração. Valida a necessidade de session management robusto. Análogo ao `SessionProvider` do MiniAutoGen mas focado em workspace isolation |
| **Agent-Deck** | TUI mission control com conductor pattern, MCP socket pooling (85-90% redução de overhead) e integração multi-channel | O conductor pattern = `CoordinatorCapability` do MiniAutoGen. MCP socket pooling é uma optimização importante: reutilizar conexões MCP entre agentes em vez de instanciar por agente |
| **OpenMolt** | Framework Node.js para agentes com 30+ integrações, zero-trust credentials e event hooks por step | Benchmark para catálogo de integrações. Zero-trust credentials (agente nunca vê credenciais em plaintext) é um pattern de segurança worth absorbing no `PermissionsConfig` |

---

## 4. Anatomia Prescritiva do Agente

### 4.1 Camadas do Agente

```
Agent
├── Layer 1: Identity (AgentSpec)
│   ├── id, version, name, role, goal, backstory
│   └── capabilities: list[AgentCapability]
│
├── Layer 2: Engine Binding
│   ├── engine: str → resolved via EngineResolver → AgentDriver
│   └── O engine é quem executa (Claude, GPT, Gemini, local, CLI agent)
│
├── Layer 3: Agent Runtime (NOVO — o diferencial)
│   ├── tools: list[ToolProtocol]           # ferramentas locais do agente
│   ├── mcp_servers: list[McpServerBinding]  # ferramentas via MCP
│   ├── memory: MemoryProvider               # session + long-term
│   ├── hooks: list[AgentHook]               # before/after cada turn
│   └── delegation: DelegationConfig         # pode delegar para outros agentes
│
├── Layer 4: Policies (limites)
│   ├── limits: max_turns, timeout_seconds
│   ├── permissions: shell, network, filesystem
│   ├── budget: max_cost, max_tokens
│   └── retry: RetryPolicy
│
└── Layer 5: Protocol Adapters (como participa de Flows)
    ├── WorkflowAgent → process(input) → output
    ├── DeliberationAgent → contribute(topic) → Contribution
    ├── ConversationalAgent → reply(message) → str
    └── CoordinatorAgent → coordinate(plan) → RunResult  (NOVO)
```

### 4.2 AgentSpec Atualizado

```python
class AgentSpec(BaseModel):
    """Especificação declarativa completa de um agente."""

    # === Layer 1: Identity ===
    id: str
    version: str = "1.0.0"
    name: str
    description: str = ""
    role: str
    goal: str
    backstory: str = ""
    capabilities: list[str] = []  # ["workflow", "deliberation", "conversational", "coordinator"]

    # === Layer 2: Engine Binding ===
    engine: str | None = None  # ref to Engine name in workspace config

    # === Layer 3: Agent Runtime ===
    # Python class names retain *Config suffix; YAML keys drop it (tools, permissions, memory, delegation, limits)
    tools: ToolAccessConfig = ToolAccessConfig()
    mcp_access: McpAccessConfig = McpAccessConfig()
    memory: MemoryConfig = MemoryConfig()
    delegation: DelegationConfig = DelegationConfig()
    hooks: list[str] = []  # refs to AgentHook implementations

    # === Layer 4: Policies ===
    limits: LimitsConfig = LimitsConfig()
    permissions: PermissionsConfig = PermissionsConfig()
    budget: BudgetConfig | None = None

    # === Layer 5: Protocol Adapters ===
    # Determined at runtime based on capabilities + Flow coordination mode

    # === Metadata ===
    skills: list[str] = []  # refs to SkillSpec names
    vendor_extensions: dict[str, Any] = {}
```

### 4.3 [IMPLEMENTADO] Agent Runtime — O Diferencial

O Agent Runtime é a camada que separa MiniAutoGen de frameworks que apenas wrappam APIs. Ele adiciona **capacidades locais** ao agente que o Engine não fornece:

```python
# IMPLEMENTADO no codebase atual
class AgentRuntime:
    """Runtime local que enriquece o Engine com capacidades adicionais."""

    agent_spec: AgentSpec
    driver: AgentDriver  # Engine resolvido
    tool_registry: ToolRegistry  # tools locais + MCP
    memory_provider: MemoryProvider  # session + long-term
    hooks: list[AgentHook]  # before/after turn
    event_sink: EventSink  # observabilidade

    async def execute_turn(
        self,
        messages: list[dict],
        context: RunContext,
    ) -> AsyncIterator[AgentEvent]:
        """Executa um turn com todas as camadas do runtime."""
        # 1. Hooks before_turn
        for hook in self.hooks:
            messages = await hook.before_turn(messages, context)

        # 2. Inject tools/memory into messages
        messages = self._inject_tool_definitions(messages)
        messages = await self._inject_memory_context(messages, context)

        # 3. Send to Engine
        request = SendTurnRequest(
            session_id=context.run_id,
            messages=messages,
            metadata=context.metadata,
        )
        async for event in self.driver.send_turn(request):
            # 4. Handle tool calls locally
            if event.type == "tool_call_requested":
                result = await self.tool_registry.execute(event.payload)
                yield AgentEvent(type="tool_call_executed", ...)
                continue

            # 5. Hooks after_event
            for hook in self.hooks:
                event = await hook.after_event(event, context)

            yield event

        # 6. Persist to memory
        await self.memory_provider.save_turn(messages, context)
```

**O que o Agent Runtime faz que o Engine sozinho não faz:**

| Capacidade | Engine sozinho | Engine + Agent Runtime |
|---|---|---|
| Tool calling local | Depende do provider | ToolProtocol unificado |
| MCP tools | Depende do provider | McpAccessConfig → qualquer MCP server |
| Memory persistence | Depende do provider (alguns têm, outros não) | MemoryProvider agnóstico |
| Hooks before/after | Não | AgentHook composáveis |
| Budget/cost tracking | Não | BudgetPolicy lateral |
| Permissions enforcement | Não | PermissionsConfig enforced localmente |
| Observabilidade | Depende do provider | EventSink com 63 event types |
| Delegation | Não (ou provider-specific) | DelegationConfig + CoordinatorCapability |

---

## 5. O Agente e seus Engines

> Para análise detalhada de engines, ver [competitive-landscape.md](../../competitive-landscape.md) secção 5.3

### 5.1 Tipos de Engine

O EngineResolver já suporta 7 tipos de driver, que se agrupam em 3 categorias:

```
Engines
├── API Providers (stateless, per-call)
│   ├── openai → OpenAISDKDriver
│   ├── anthropic → AnthropicSDKDriver
│   ├── google → GoogleGenAIDriver
│   ├── litellm → LiteLLMDriver (multi-provider)
│   └── openai-compat → AgentAPIDriver (qualquer endpoint compatível)
│
├── CLI Agents (stateful, subprocess)
│   ├── claude-code → CLIAgentDriver (["claude", "--agent"])
│   ├── gemini-cli → CLIAgentDriver (["gemini"])
│   └── codex-cli → CLIAgentDriver (["codex"])
│
└── Gateway/Hub (stateful, WebSocket/HTTP)
    └── (proposto) openclaw → WebSocketDriver ou AgentAPIDriver
```

### 5.2 Instâncias Nativas de CLI Agents

O CLIAgentDriver permite criar **múltiplas instâncias do mesmo CLI agent com configurações diferentes**. Cada instância é um subprocess isolado com seu próprio contexto, skills e limites.

**Claude Agent SDK** expõe `ClaudeAgentOptions` com os seguintes eixos de personalização:
- `system_prompt` — Persona e instruções do agente
- `allowed_tools` / `disallowed_tools` — Allowlist/blocklist de ferramentas
- `mcp_servers` — MCP servers externos ou in-process
- `agents` — Subagents nomeados para delegação via tool `Agent`
- `cwd` — Working directory (diferentes `cwd` = diferentes CLAUDE.md automaticamente)
- `model` — Modelo específico (claude-sonnet, claude-opus, etc.)
- `hooks` — Lifecycle callbacks (`PreToolUse`, `PostToolUse`, `Stop`, etc.)
- `max_turns` — Limite de execução
- `permission_mode` — 'ask', 'acceptEdits', 'rejectEdits'
- `session_id` — Resume de sessão anterior

Múltiplas instâncias são criadas via diferentes combinações destes parâmetros: diferente `cwd` (diferente CLAUDE.md), diferente `allowed_tools`, diferente `system_prompt`.

**Gemini CLI** oferece personalização via:
- `GEMINI.md` — Ficheiro de instruções injectado automaticamente (análogo a CLAUDE.md)
- `.gemini/agents/*.md` — Subagents customizados definidos como ficheiros markdown
- Free tier disponível para experimentação

```yaml
engines:
  # Claude como arquiteto — cwd aponta para workspace com CLAUDE.md de arquitetura
  - name: "claude-architect"
    kind: cli
    provider: claude-code
    config:
      command: ["claude", "--agent"]
      cwd: "/project/.workspaces/architect"  # CLAUDE.md com skills de arquitetura
      allowed_tools: ["Read", "Grep", "Glob", "Bash", "Agent"]
      system_prompt: "You are a senior architect. Focus on design decisions."
      max_turns: 20
      timeout_seconds: 300

  # Claude como reviewer — ferramentas limitadas, sem escrita
  - name: "claude-reviewer"
    kind: cli
    provider: claude-code
    config:
      command: ["claude", "--agent"]
      cwd: "/project/.workspaces/reviewer"  # CLAUDE.md com checklist de review
      allowed_tools: ["Read", "Grep", "Glob"]
      permission_mode: "rejectEdits"
      max_turns: 10
      timeout_seconds: 120

  # Claude com session resume — continua trabalho anterior
  - name: "claude-persistent"
    kind: cli
    provider: claude-code
    config:
      command: ["claude", "--agent"]
      session_id: "session-abc123"  # retoma sessão anterior
      timeout_seconds: 300

  # Gemini como researcher — free tier, GEMINI.md com instruções de pesquisa
  - name: "gemini-researcher"
    kind: cli
    provider: gemini-cli
    config:
      command: ["gemini"]
      cwd: "/project/.workspaces/researcher"  # GEMINI.md com skills de pesquisa
      timeout_seconds: 180
```

O mesmo Claude Code pode ser "arquiteto" numa instância e "reviewer" noutra — o que muda são os parâmetros de configuração injectados pelo `CLIAgentDriver`.

### 5.3 Engines como Gateway

Um gateway engine permite ao MiniAutoGen consumir agentes externos que correm fora do seu processo — hubs multi-agente, serviços A2A, ou endpoints OpenAI-compatible.

**OpenClaw Gateway** — Hub multi-agente acessível via WebSocket JSON-RPC:
- Protocolo: `ws://127.0.0.1:18789` com métodos `agent/send`, `tools.catalog`, `memory/search`
- Autenticação: Ed25519 key pairs
- Cada sessão expõe um agente específico do hub

**A2A-compatible agents** — Qualquer agente que implemente o protocolo A2A pode ser consumido como engine via HTTP:
- Descoberta via `/.well-known/agent.json` (AgentCard)
- Comunicação via JSON-RPC (`SendMessage`, `GetTask`, etc.)
- Suporte a streaming via SSE

**OpenAI-compatible endpoints** — Qualquer serviço que exponha a API OpenAI Chat Completions pode ser consumido via `AgentAPIDriver`:
- LLM routers (LiteLLM, OpenRouter)
- Modelos self-hosted (vLLM, Ollama, LocalAI)
- Serviços managed (Azure OpenAI, AWS Bedrock com proxy)

```yaml
engines:
  # OpenClaw gateway — agente "monica" via WebSocket JSON-RPC
  - name: "openclaw-monica"
    kind: gateway
    provider: openclaw
    config:
      endpoint: "ws://127.0.0.1:18789"
      session: "monica"
      auth:
        type: ed25519
        key_path: ".keys/openclaw.pem"

  # A2A-compatible agent — agente externo via HTTP
  - name: "external-researcher"
    kind: gateway
    provider: a2a
    config:
      agent_card_url: "https://research-agent.example.com/.well-known/agent.json"
      auth:
        type: oauth2
        token_url: "https://auth.example.com/token"

  # OpenAI-compatible endpoint — modelo local via Ollama
  - name: "local-llama"
    kind: api
    provider: openai-compat
    config:
      base_url: "http://localhost:11434/v1"
      model: "llama3.3:70b"
      timeout_seconds: 120
```

---

## 6. [IMPLEMENTADO] Runtime do Agente

### 6.1 [IMPLEMENTADO] AgentHook Protocol

Inspirado nos patterns de middleware (Express, ASP.NET, Django) e hooks (Temporal, Pytest):

```python
class AgentHook(Protocol):
    """Hook composável que intercepta o ciclo de vida do agente."""

    async def before_turn(
        self,
        messages: list[dict],
        context: RunContext,
    ) -> list[dict]:
        """Transforma mensagens antes de enviar ao Engine."""
        return messages  # default: pass-through

    async def after_event(
        self,
        event: AgentEvent,
        context: RunContext,
    ) -> AgentEvent:
        """Transforma eventos recebidos do Engine."""
        return event  # default: pass-through

    async def on_error(
        self,
        error: Exception,
        context: RunContext,
    ) -> AgentEvent | None:
        """Trata erros. Retorna evento de fallback ou None para propagar."""
        return None  # default: propaga o erro
```

**Hooks built-in propostos:**

| Hook | Tipo | O que faz |
|---|---|---|
| `MemoryInjectionHook` | before_turn | Injeta context de memória nas mensagens |
| `ToolDefinitionHook` | before_turn | Injeta definições de tools disponíveis |
| `BudgetGuardHook` | before_turn | Aborta se budget excedido |
| `PermissionsEnforcerHook` | after_event | Bloqueia tool calls não permitidos |
| `EventEmitterHook` | after_event | Emite ExecutionEvents para observabilidade |
| `MemoryPersistenceHook` | after_event | Salva turn na memória |
| `CostTrackerHook` | after_event | Contabiliza custo do turn |

### 6.2 [IMPLEMENTADO] MemoryProvider

```python
class MemoryProvider(Protocol):
    """Abstração de memória do agente."""

    async def get_context(
        self,
        agent_id: str,
        context: RunContext,
        max_tokens: int | None = None,
    ) -> list[dict]:
        """Retorna mensagens de memória relevantes para o contexto."""
        ...

    async def save_turn(
        self,
        messages: list[dict],
        context: RunContext,
    ) -> None:
        """Persiste um turn na memória."""
        ...

    async def distill(
        self,
        agent_id: str,
    ) -> None:
        """Destila memória de curto prazo em longo prazo."""
        ...
```

Inspirado no pattern de **memory distillation** validado no caso OpenClaw 24/7 — daily logs → curated long-term memory.

### 6.3 [IMPLEMENTADO] CoordinatorCapability

Recupera o insight mais profundo do v0 (ChatAdmin extends Agent):

```python
class CoordinatorCapability(Protocol):
    """Agente que pode instanciar e executar sub-Flows."""

    async def coordinate(
        self,
        plan: CoordinationPlan,
        participants: list[AgentSpec],
        context: RunContext,
    ) -> RunResult:
        """Executa um sub-Flow com participantes selecionados."""
        ...
```

Um agente com capability `coordinator` pode:
- Instanciar um sub-Flow dentro do Flow pai
- Selecionar participantes dinamicamente
- Passar contexto do Flow pai para o sub-Flow
- Receber o resultado e continuar no Flow pai

---

## 7. Interoperabilidade e Protocols

### 7.1 Compatibilidade com Protocols de Mercado

| Protocol | Relação com MiniAutoGen | Implementação |
|---|---|---|
| **MCP** | MiniAutoGen consome MCP servers como tools via `ClientSession` E pode expor-se como MCP server via `FastMCP` | McpAccessConfig (existe) + MCP Server adapter (proposto) |
| **A2A** | MiniAutoGen expõe agentes via Agent Cards E consome agentes A2A como Engines. ACP foi absorvido pelo A2A (Set 2025) — standard unificado sob Linux Foundation | A2A adapter (proposto) |
| **OpenAI API** | MiniAutoGen consome via OpenAISDKDriver E AgentAPIDriver | ✅ Implementado |
| **OpenAI Agents SDK** | Compatibilidade via handoff/agents-as-tools patterns. MiniAutoGen implementa ambos os patterns nativamente: `RouterDecision` (handoff) e `ToolProtocol` (invoke-as-tool) | Patterns alinhados; sem dependência directa |
| **Anthropic API** | MiniAutoGen consome via AnthropicSDKDriver | ✅ Implementado |

### 7.2 MiniAutoGen como Servidor

```
Consumidores externos → MiniAutoGen Server/Gateway → Flows → Agents → Engines
    ↑                         ↑
    MCP client               A2A client
    ACP client               HTTP client
    WebSocket client
```

O Workspace (container) atua como servidor/gateway, expondo os Flows e Agents internos para consumo externo.

---

## 8. Diferenciais e Posicionamento

### 8.1 O que MiniAutoGen oferece que ninguém oferece

| Diferencial | Por que é único |
|---|---|
| **Agent = Spec + Engine + Runtime** | Nenhum framework separa claramente identidade, backend e capacidades locais |
| **Multi-provider real** | 7 drivers implementados; mesmo agente pode trocar de Engine sem mudar spec |
| **Agent Runtime com hooks** | Capacidades locais (tools, memory, permissions) independentes do provider |
| **CoordinatorCapability** | Agente que orquestra sub-Flows — composição recursiva com type safety |
| **Observabilidade built-in** | 63 event types canônicos; qualquer Engine é observável |
| **Memory lifecycle** | Session → long-term → distillation como policy do runtime |

### 8.2 O que MiniAutoGen NÃO faz (e por quê)

| O que não faz | Por quê |
|---|---|
| Não constrói agentes do zero | Engines nativos são superiores — o valor está na orquestração |
| Não implementa reasoning/planning | Isso é responsabilidade do Engine (Claude, GPT, etc.) |
| Não treina/fine-tuna modelos | Fora do escopo — usa modelos as-is via API/CLI |
| Não compete com MCP/A2A | São protocols complementares — MiniAutoGen os consome e expõe |

---

*Documento gerado em 2025-06-18 | Baseado em análise do codebase, [architecture-retrospective.md](../../architecture-retrospective.md), [competitive-landscape.md](../../competitive-landscape.md), e pesquisa de mercado*
