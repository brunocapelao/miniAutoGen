# Analise: Open SWE (LangChain) — Insights para MiniAutoGen

> **Repositorio:** [langchain-ai/open-swe](https://github.com/langchain-ai/open-swe)
> **Data:** 2026-03-20
> **Stars:** 7,409 | **Forks:** 900 | **Licenca:** MIT
> **Linguagem:** Python | **Framework base:** LangGraph + Deep Agents

---

## 1. O Que e o Open SWE

Open SWE e um **coding agent assincrono open-source** desenhado para ser o "agente de engenharia interno" de uma organizacao. Inspirado nos padroes de Stripe, Ramp e Coinbase, e construido sobre o framework **Deep Agents** (LangChain) e LangGraph.

**Nao e um framework generico** — e um agente especializado em tarefas de engenharia de software: recebe issues (Linear, Slack, GitHub), implementa codigo num sandbox isolado, corre testes, e abre PRs.

**Posicionamento:** Enquanto MiniAutoGen e um framework para CONSTRUIR sistemas multi-agente, Open SWE e um sistema multi-agente JA CONSTRUIDO para um caso de uso especifico (coding).

---

## 2. Arquitetura

### 2.1 Visao Geral

```
┌─────────────────────────────────────────────────────────┐
│                   Invocation Layer                        │
│   ┌─────────┐   ┌─────────┐   ┌──────────┐             │
│   │  Slack   │   │ Linear  │   │  GitHub  │             │
│   │  trigger │   │ trigger │   │  trigger │             │
│   └────┬─────┘   └────┬────┘   └────┬─────┘             │
│        └───────────────┼─────────────┘                   │
│                        ▼                                  │
│              ┌─────────────────┐                         │
│              │   get_agent()   │ ← assembly point         │
│              │   (server.py)   │                          │
│              └────────┬────────┘                         │
│                       ▼                                  │
│        ┌──────────────────────────────┐                  │
│        │      Deep Agent Runtime      │                  │
│        │  ┌────────────────────────┐  │                  │
│        │  │   Middleware Pipeline   │  │                  │
│        │  │  • ToolErrorMiddleware  │  │                  │
│        │  │  • check_message_queue  │  │                  │
│        │  │  • ensure_no_empty_msg  │  │                  │
│        │  │  • open_pr_if_needed   │  │                  │
│        │  └────────────────────────┘  │                  │
│        │                              │                  │
│        │  ┌────────────────────────┐  │                  │
│        │  │   Tools (~15 curated)  │  │                  │
│        │  │  Custom: commit_pr,    │  │                  │
│        │  │    fetch_url, http,    │  │                  │
│        │  │    linear, slack,      │  │                  │
│        │  │    github_comment      │  │                  │
│        │  │  Built-in: read, write,│  │                  │
│        │  │    edit, ls, glob,     │  │                  │
│        │  │    grep, execute,      │  │                  │
│        │  │    write_todos, task   │  │                  │
│        │  └────────────────────────┘  │                  │
│        └──────────────┬───────────────┘                  │
│                       ▼                                  │
│        ┌──────────────────────────────┐                  │
│        │     Sandbox (pluggable)      │                  │
│        │  LangSmith│Modal│Daytona│... │                  │
│        │  (Linux isolado + git repo)  │                  │
│        └──────────────────────────────┘                  │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Assembly Point: `get_agent()`

Todo o agente e montado numa unica funcao:

```python
# agent/server.py
return create_deep_agent(
    model=make_model("anthropic:claude-opus-4-6", temperature=0, max_tokens=20_000),
    system_prompt=construct_system_prompt(repo_dir, ...),
    tools=[http_request, fetch_url, commit_and_open_pr, linear_comment, slack_thread_reply],
    backend=sandbox_backend,
    middleware=[
        ToolErrorMiddleware(),
        check_message_queue_before_model,
        ensure_no_empty_msg,
        open_pr_if_needed,
    ],
)
```

**Principio de design:** Um unico ponto de composicao onde model, tools, sandbox e middleware sao plugaveis. Isto e o oposto de frameworks com configuracao dispersa.

### 2.3 Sandbox: Isolamento por Task

| Provider | Ficheiro | Isolamento |
|----------|---------|-----------|
| **LangSmith** (default) | `integrations/langsmith.py` | Cloud sandbox Linux |
| **Modal** | `integrations/modal.py` | Container serverless |
| **Daytona** | `integrations/daytona.py` | Cloud dev environment |
| **Runloop** | `integrations/runloop.py` | Cloud sandbox |
| **Local** | `integrations/local.py` | Nenhum (dev only) |

**Protocolo:**
```python
class SandboxBackendProtocol:
    id: str                                              # identidade
    def ls_info() -> ...: ...                            # file ops
    def read() -> ...: ...
    def write() -> ...: ...
    def edit() -> ...: ...
    def glob_info() -> ...: ...
    def grep_raw() -> ...: ...
    def execute(command, timeout=None) -> ExecuteResponse: ...  # shell
```

**Caracteristicas:**
- Cada thread recebe sandbox **persistente e reutilizavel**
- Auto-recreacao quando inacessivel
- Execucao paralela — sem filas entre tasks
- `BaseSandbox` implementa file ops delegando a `execute()`, so precisa implementar shell

### 2.4 Middleware Pipeline

4 middlewares com papeis distintos:

| Middleware | Ficheiro | Funcao |
|-----------|---------|--------|
| `ToolErrorMiddleware` | `tool_error_handler.py` | Graceful error handling em tool calls |
| `check_message_queue_before_model` | `check_message_queue.py` | Injeta mensagens mid-run antes da proxima chamada ao modelo |
| `ensure_no_empty_msg` | `ensure_no_empty_msg.py` | Previne mensagens vazias no contexto |
| `open_pr_if_needed` | `open_pr.py` | **Safety net deterministico**: garante criacao de PR mesmo que LLM esqueca |

**Insight critico:** O `open_pr_if_needed` e um padrao de **deterministic backstop** — comportamento critico que NAO depende do LLM. Se o agente esquece de abrir PR, o middleware garante que acontece.

### 2.5 Context Engineering

Duas fontes de contexto:

1. **AGENTS.md** — ficheiro no repo injetado no system prompt:
   - Convencoes de codigo
   - Requisitos de testes
   - Decisoes arquiteturais
   - Lido do sandbox via `read_agents_md_in_sandbox()`

2. **Source Context** — contexto completo da issue/thread:
   - Linear: issue completa com comentarios
   - Slack: thread completa
   - GitHub: issue/PR com review comments
   - Montado ANTES de invocar o agente, reduzindo tool calls de discovery

### 2.6 Subagents via `task` Tool

O Deep Agents fornece uma tool `task` que spawna sub-agentes:
- Cada sub-agente recebe middleware stack isolado
- Operacoes de ficheiros isoladas
- Execucao paralela para subtasks independentes
- `write_todos` para tracking de progresso

### 2.7 Workflow de Execucao

```
1. UNDERSTAND — Ler issue, explorar ficheiros relevantes
2. IMPLEMENT  — Mudancas focadas, minimas, dentro do escopo
3. VERIFY     — Linters + testes RELACIONADOS (nao suite completa)
4. SUBMIT     — commit_and_open_pr (draft PR)
5. COMMENT    — Notificar no canal de origem (Linear/Slack/GitHub)
```

**Regra critica:** "You must call `commit_and_open_pr` before posting any completion message." — PRs sao pre-requisito para claims de conclusao.

---

## 3. Inovacoes Relevantes

### 3.1 Deterministic Backstops

O padrao mais valioso do Open SWE: **middlewares que garantem comportamento critico independentemente do LLM.**

```python
# open_pr.py — se o agente termina sem abrir PR, o middleware faz
async def open_pr_if_needed(state, config):
    if has_changes and not pr_opened:
        # Forcar criacao de PR
        ...
```

**Relevancia MiniAutoGen:** As nossas `Policies` sao reactivas (observam eventos). O padrao de backstop e **proactivo** — garante que algo aconteca. Poderiamos implementar `DeterministicBackstop` como um tipo especial de policy que executa na finalizacao de um step.

### 3.2 AGENTS.md como Configuracao In-Repo

O ficheiro `AGENTS.md` no repositorio do utilizador serve como configuracao per-repo do agente. Isto e analogo ao nosso `miniautogen.yaml`, mas vive DENTRO do repo alvo (nao no repo do framework).

**Relevancia MiniAutoGen:** Para backends CLI que operam em repos externos, um `AGENTS.md` ou `.miniautogen/config.yaml` no repo alvo seria valioso para injetar contexto.

### 3.3 Curation over Accumulation (~15 tools)

O Open SWE deliberadamente limita tools a ~15, vs. frameworks que oferecem centenas:

> *Stripe: ~500 tools per agent*
> *Open SWE: ~15 curated tools*

**Filosofia:** Menos tools = menos tokens em descricoes = melhor tool selection pelo LLM.

**Relevancia MiniAutoGen:** Alinha-se com o principio de **progressive skill loading** do DeerFlow. Nao carregar todas as tools no contexto — apenas as relevantes.

### 3.4 Message Queue Injection Mid-Run

O `check_message_queue_before_model` permite injetar mensagens no meio de uma execucao:
- Utilizador envia follow-up no Slack enquanto agente trabalha
- Middleware injeta a mensagem antes da proxima chamada ao modelo
- Agente recebe contexto atualizado sem reiniciar

**Relevancia MiniAutoGen:** O nosso `ApprovalGate` bloqueia execucao. O padrao de message injection e mais fluido — nao bloqueia, apenas enriquece o proximo step.

### 3.5 SandboxBackendProtocol como Contrato

O protocolo de sandbox e minimalista e extensivel:
- File ops: `ls_info`, `read`, `write`, `edit`, `glob_info`, `grep_raw`
- Shell: `execute(command, timeout) -> ExecuteResponse`
- Identity: `id` property

`BaseSandbox` implementa tudo delegando a `execute()` — para adicionar um provider, so precisa implementar execucao de shell.

**Relevancia MiniAutoGen:** O nosso `AgentDriver` tem interface mais complexa (sessions, turns, artifacts, capabilities). Para backends que operam em sandboxes (tipo o `GeminiCLIDriver`), um `SandboxProtocol` simplificado poderia ser uma camada abaixo do `AgentDriver`.

---

## 4. Comparacao com MiniAutoGen

### 4.1 Posicionamento

```
                    ┌──────────────────────────────────┐
                    │        AGENTE ESPECIALIZADO        │
                    │                                    │
                    │     ★ Open SWE                     │
                    │     (coding agent pronto)          │
                    │                                    │
                    ├────────────────────────────────────┤
                    │        FRAMEWORK GENERICO           │
                    │                                    │
                    │            ★ MiniAutoGen            │
                    │     (constroi qualquer sistema      │
                    │      multi-agente)                  │
                    │                                    │
                    └──────────────────────────────────┘
```

**NAO sao concorrentes diretos.** Open SWE poderia ser CONSTRUIDO usando MiniAutoGen como base.

### 4.2 Matriz Comparativa

| Dimensao | Open SWE | MiniAutoGen |
|----------|----------|-------------|
| **Tipo** | Agente pronto (coding) | Framework generico |
| **Base** | LangGraph + Deep Agents | Microkernel proprio |
| **Sandbox** | 5 providers plugaveis | Backend CLI (parcial) |
| **Middleware** | 4 middlewares especificos | EffectInterceptor (parcial) |
| **Tools** | ~15 curated | Via AgentDriver.capabilities() |
| **Context engineering** | AGENTS.md + source context pre-loaded | YAML config |
| **Subagents** | `task` tool (Deep Agents) | Coordination modes (3) |
| **Invocation** | Slack, Linear, GitHub | CLI, TUI |
| **Determinismo** | Backstop middlewares | Workflow mode |
| **Observabilidade** | LangSmith (externo) | 70+ eventos built-in |
| **Supervision** | Nenhuma | Trees + circuit breakers |
| **Checkpointing** | Via LangGraph | CheckpointStore |
| **Idempotencia** | Nenhuma | EffectJournal |
| **Dependencias** | LangGraph + LangChain + Deep Agents | AnyIO (minimo) |

### 4.3 O Que Open SWE Faz Melhor

1. **Sandbox Protocol** — abstraccao limpa para isolamento de execucao
2. **Deterministic backstops** — middlewares que garantem comportamento critico
3. **AGENTS.md per-repo** — configuracao contextual por repositorio
4. **Tool curation** — menos e mais
5. **Message injection mid-run** — contexto atualizado sem restart
6. **Multi-channel triggers** — Slack, Linear, GitHub nativos

### 4.4 O Que MiniAutoGen Faz Melhor

1. **Generico vs especializado** — constroi qualquer sistema, nao so coding
2. **3 modos de coordenacao** — vs 1 modo (agent loop)
3. **Supervision trees** — tolerancia a falhas robusta
4. **70+ eventos tipados** — observabilidade built-in
5. **EffectJournal** — idempotencia nativa
6. **Zero lock-in** — sem dependencia de LangChain/LangGraph
7. **Protocol contracts** — composabilidade tipada

---

## 5. Insights Acionaveis para MiniAutoGen

### 5.1 Deterministic Backstop Pattern (Alta Prioridade)

**O que e:** Middleware que executa na finalizacao de um step/run para garantir que acoes criticas aconteceram, independentemente do comportamento do LLM.

**Como implementar no MiniAutoGen:**

```python
@runtime_checkable
class CompletionBackstop(Protocol):
    """Garante acao critica na finalizacao de step/run."""
    async def check(self, context: StepContext, result: StepResult) -> StepResult:
        """Se acao critica nao aconteceu, executa-la."""
        ...
```

**Exemplos de uso:**
- Garantir que testes correm antes de um commit
- Garantir que eventos de conclusao sao emitidos
- Garantir que artefactos sao persistidos

**Alinhamento:** NAO viola invariantes — e uma policy lateral, event-driven.

### 5.2 SandboxProtocol Simplificado (Media Prioridade)

**O que e:** Interface minima para execucao isolada.

```python
@runtime_checkable
class SandboxProtocol(Protocol):
    @property
    def id(self) -> str: ...
    async def execute(self, command: str, timeout: int | None = None) -> ExecuteResult: ...
    async def read_file(self, path: str) -> str: ...
    async def write_file(self, path: str, content: str) -> None: ...
```

**Relevancia:** Para o `GeminiCLIDriver` e futuros backends CLI, ter um sandbox protocol standard simplifica integracao. O `AgentDriver` continuaria como interface de alto nivel, com `SandboxProtocol` como primitiva de baixo nivel.

### 5.3 Context Pre-Loading (Media Prioridade)

**O que e:** Montar contexto completo (issue, ficheiros relevantes, convencoes) ANTES de invocar o agente, em vez de depender do agente para fazer discovery.

**No MiniAutoGen:** Os nossos coordination modes poderiam aceitar um `InitialContext` que e montado pelo PipelineRunner antes de iniciar o primeiro step:

```python
@dataclass
class InitialContext:
    source: str                    # de onde veio a task
    description: str               # o que fazer
    relevant_files: list[Path]     # ficheiros pre-identificados
    conventions: str | None        # AGENTS.md ou equivalente
```

### 5.4 Message Injection (Baixa Prioridade)

**O que e:** Permitir injecao de mensagens mid-run sem bloquear execucao.

**Diferenca do ApprovalGate:** ApprovalGate bloqueia (sync). Message injection enriquece o proximo step (async).

**Implementacao possivel:** Um `MessageQueue` no PipelineRunner que middlewares consultam antes de cada step.

---

## 6. Open SWE como Caso de Uso para MiniAutoGen

### 6.1 Poderiamos Construir um Open SWE com MiniAutoGen?

**Sim**, e seria uma excelente validacao do framework. Mapeamento:

| Open SWE Component | MiniAutoGen Equivalent |
|--------------------|----------------------|
| `create_deep_agent()` | `PipelineRunner.run()` com AgenticLoop mode |
| `SandboxBackendProtocol` | Novo `SandboxProtocol` no contracts |
| Middleware pipeline | `StepMiddleware` (proposto) |
| `task` subagent tool | `Workflow` mode com fan-out |
| `commit_and_open_pr` | Tool no `AgentDriver` |
| `AGENTS.md` reading | `InitialContext` pre-loading |
| Deterministic backstops | `CompletionBackstop` policy |
| LangSmith observability | `EventStore` + `TUI Events` |

### 6.2 O Que Faltaria

1. **Sandbox providers** (LangSmith, Modal, Daytona, Runloop)
2. **Integration triggers** (Slack, Linear, GitHub webhooks)
3. **Git operations** como tools nativos
4. **AGENTS.md parser** per-repo

Os items 1-2 sao adapters (fora do core). Items 3-4 sao tools/utils.

---

## 7. Posicionamento Atualizado (Com Open SWE)

```
     Especializacao
          ▲
          │
Open SWE  ● (coding agent pronto)
          │
Bit Office● (visual multi-agent office)
          │
          │
          │               DeerFlow ● (research agent harness)
          │
          │
          │                        ★ MiniAutoGen (framework generico)
          │
          └──────────────────────────────────────────► Generalidade
```

**MiniAutoGen e o UNICO framework generico neste grupo.** Todos os outros sao ou frameworks opinados (AutoGen, LangGraph, CrewAI) ou agentes especializados (Open SWE, Bit Office, DeerFlow).

A oportunidade: MiniAutoGen pode servir como **base para construir** qualquer um desses sistemas especializados, validando a arquitetura microkernel.

---

## 8. Resumo de Gaps Atualizados

Adicionando insights do Open SWE ao backlog de gaps:

| Gap | Fonte | Prioridade | Justificacao |
|-----|-------|-----------|-------------|
| **Filesystem workspace por run** | DeerFlow + Open SWE | **Alta** | Ambos usam workspace em disco |
| **Middleware pipeline generalizado** | DeerFlow + Open SWE | **Alta** | Ambos validam o padrao |
| **Deterministic backstop policy** | Open SWE | **Alta** | Garante comportamento critico sem depender do LLM |
| **Tool scoping per agent** | DeerFlow | Media | Menos tokens em tool descriptions |
| **Progressive skill loading** | DeerFlow | Media | ~100 tok vs ~1000 tok por skill |
| **SandboxProtocol** | Open SWE | Media | Interface minima para execucao isolada |
| **Context pre-loading** | Open SWE | Media | Montar contexto antes de invocar agente |
| **Conditional branching em Workflow** | LangGraph | Media | Workflows mais expressivos |
| **Memoria cross-session** | DeerFlow + Bit Office | Media | Agentes melhoram entre sessoes |
| **Message injection mid-run** | Open SWE | Baixa | Contexto atualizado sem restart |
| **AGENTS.md per-repo convention** | Open SWE | Baixa | Configuracao contextual |
