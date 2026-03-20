# Relatorio: "5 Agent Frameworks, One Pattern Won" — Insights para MiniAutoGen

> **Fonte:** [5 Agent Frameworks, One Pattern Won](https://levelup.gitconnected.com/5-agent-frameworks-one-pattern-won-54cc0eedf027)
> **Data:** 2026-03-20
> **Tese central:** Infraestrutura composavel bate frameworks monoliticos em producao.

---

## 1. Resumo do Artigo

O artigo analisa 5 abordagens para sistemas multi-agente e conclui que o padrao vencedor e **infraestrutura composavel** — progressive skill loading, filesystem-first state, e middleware modular.

### Frameworks Analisados

| Framework | Arquitetura | Forca | Fraqueza Critica |
|-----------|------------|-------|------------------|
| **AutoGen** | Conversacao broadcast via GroupChat | Simples conceptualmente | Overhead quadratico de tokens (O(n*m)) |
| **LangGraph** | Maquina de estados dirigida | Checkpointing, routing explicito | Boilerplate pesado, schema rigido |
| **CrewAI** | Delegacao baseada em papeis | Demo em ~30 linhas | Routing nao-deterministico via LLM |
| **DeerFlow** (ByteDance) | Infra composavel com 9 middlewares | Progressive loading, filesystem state | Sem benchmarks, dependencia ByteDance |
| **Anthropic** | Sem framework, 6 padroes compostos | Controlo maximo | Requer construir tudo |

### O Padrao Vencedor: 3 Pilares

```
┌─────────────────────────────────────────────────┐
│           INFRAESTRUTURA COMPOSAVEL              │
├─────────────────┬──────────────┬────────────────┤
│   Pilar 1       │   Pilar 2    │   Pilar 3      │
│   Progressive   │   Filesystem │   Middleware    │
│   Skill Loading │   First State│   Pipeline      │
├─────────────────┼──────────────┼────────────────┤
│ Tier 1: metadata│ uploads/     │ Summarization  │
│ Tier 2: body    │ workspace/   │ Memory         │
│ Tier 3: assets  │ outputs/     │ Sandbox        │
│                 │              │ Clarification  │
│ ~100 tok/skill  │ Disco > Token│ Pre/Post hooks │
└─────────────────┴──────────────┴────────────────┘
```

---

## 2. Impacto de Custo: Monolitico vs Composavel

O artigo apresenta numeros concretos para uma task "Research AAPL":

| Metrica | Monolitico | Composavel | Reducao |
|---------|-----------|-----------|---------|
| Tokens/chamada | 137,000 | 10,500 | **13x** |
| 12 chamadas | 1,644,000 | 126,000 | — |
| Custo/run | $4.93 | $0.38 | **13x** |
| 50 runs/dia × 30 dias | $7,395 | $570 | **$6,825/mes** |

**Insight:** A degradacao de qualidade por contexto irrelevante e um custo estrutural, nao apenas financeiro. Tokens mais baratos nao eliminam o problema — apenas o tornam menos visivel.

---

## 3. Mapeamento para MiniAutoGen

### 3.1 Pilar 1: Progressive Skill Loading

**O que o artigo propoe:**
```
Tier 1 (Metadata):  nome + descricao 1 linha  (~100 tokens/skill)
Tier 2 (Body):      instrucoes completas       (carregado sob demanda)
Tier 3 (Resources): assets pesados             (carregado quando referenciado)
```

**Onde estamos no MiniAutoGen:**

| Aspecto | Estado Atual | Gap |
|---------|-------------|-----|
| Definicao de agentes | `AgentSpec` em YAML com role, description, config | Tudo carregado de uma vez |
| Tool definitions | Via `AgentDriver.capabilities()` | Todas as tools no contexto |
| Skill loading | Nao temos conceito de skills tiered | Gap significativo |

**Recomendacao concreta:**

O nosso `AgentSpec` ja tem os campos necessarios para Tier 1:

```python
# Tier 1 — ja existe implicitamente
class AgentSpec:
    name: str
    role: str          # ~descricao curta
    description: str   # poderia ser o metadata tier

# Tier 2 — novo conceito: system_prompt carregado sob demanda
# Tier 3 — novo conceito: tools/resources carregados quando referenciados
```

**Acao:** Introduzir `SkillRegistry` no core que implemente lazy loading de capabilities. O `PipelineRunner` carregaria Tier 1 para todos os agentes no inicio, e Tier 2/3 apenas quando o agente e ativado num step.

**Alinhamento arquitetural:** Isso NAO viola o isolamento do core — seria um novo `Protocol` no `contracts/`:

```python
@runtime_checkable
class SkillProvider(Protocol):
    def metadata(self) -> SkillMetadata: ...           # Tier 1
    async def load_body(self) -> SkillBody: ...        # Tier 2
    async def load_resources(self) -> list[Resource]: ... # Tier 3
```

---

### 3.2 Pilar 2: Filesystem-First State

**O que o artigo propoe:**
```
/mnt/user-data/
├── uploads/      ← ficheiros do utilizador
├── workspace/    ← resultados intermediarios
└── outputs/      ← entregaveis finais
```

**Onde estamos no MiniAutoGen:**

| Aspecto | Estado Atual | Gap |
|---------|-------------|-----|
| Resultados intermediarios | Passados in-process via `StepResult` | Em memoria, nao em disco |
| Artefactos de agentes | `AgentDriver.list_artifacts()` retorna refs | Refs existem, mas sao transitorias |
| Workspace por sessao | Nao implementado | Gap significativo |
| Checkpoint recovery | `CheckpointStore` salva snapshots | Salva estado do runner, nao outputs |

**Relevancia critica:** Para o nosso `GeminiCLIDriver` e futuros backends CLI, os agentes ja operam no filesystem. O gap e que o `PipelineRunner` nao tem conceito de "workspace directory" por run.

**Recomendacao concreta:**

```python
# Novo conceito: RunWorkspace
class RunWorkspace:
    """Filesystem-backed workspace para uma execucao."""
    root: Path           # /tmp/miniautogen/runs/<run_id>/
    uploads: Path        # ficheiros de input
    workspace: Path      # intermediarios (agente A → disco → agente B)
    outputs: Path        # entregaveis finais

    def write_intermediate(self, name: str, data: Any) -> Path: ...
    def read_intermediate(self, name: str) -> Any: ...
```

**Integracao com PipelineRunner:**
- Cada `run()` cria um `RunWorkspace`
- Steps de Workflow escrevem outputs intermediarios no workspace
- Steps seguintes recebem `Path` em vez de dados completos no contexto
- `CheckpointStore` referencia paths do workspace (nao duplica dados)

**Impacto em tokens:** Para pipelines com documentos grandes (ex: analise de codigo, processamento de dados), isso reduz dramaticamente o contexto passado entre agentes.

---

### 3.3 Pilar 3: Middleware Pipeline

**O que o artigo propoe (DeerFlow):**
```
Request → [Clarification] → [Memory] → [Summary] → [Sandbox] → LLM → [Post-process]
```

9 middlewares especializados com `before()` e `after()` hooks.

**Onde estamos no MiniAutoGen:**

| Aspecto | Estado Atual | Alinhamento |
|---------|-------------|-------------|
| Pre/Post processing | `EffectInterceptor` com before/after steps | Parcial — so para effects |
| Summarization | Nao implementado | Gap |
| Memory middleware | Nao implementado | Gap |
| Sandbox | Nao implementado (backends CLI sao nativamente sandboxed) | Parcial |
| Clarification | `ApprovalGate` policy | Analogo mas nao identico |

**Insight chave:** O nosso sistema de `Policies` ja implementa o conceito de middleware lateralmente:

```python
class ReactivePolicy(Protocol):
    @property
    def subscribed_events(self) -> set[str]: ...
    async def on_event(self, event: ExecutionEvent) -> None: ...
```

**A diferenca fundamental:** As policies do MiniAutoGen sao **reactivas** (observam eventos depois de acontecerem). Os middlewares do DeerFlow sao **interceptadores** (podem modificar o request ANTES de chegar ao LLM).

**Recomendacao concreta:**

O nosso `EffectInterceptor` ja tem a anatomia certa. Precisamos generalizar:

```python
@runtime_checkable
class StepMiddleware(Protocol):
    """Middleware que envolve cada step do pipeline."""
    async def before_step(self, context: StepContext) -> StepContext: ...
    async def after_step(self, context: StepContext, result: StepResult) -> StepResult: ...

# Composicao
class MiddlewarePipeline:
    middlewares: list[StepMiddleware]

    async def execute(self, step: Step, context: StepContext) -> StepResult:
        for mw in self.middlewares:
            context = await mw.before_step(context)
        result = await step.execute(context)
        for mw in reversed(self.middlewares):
            result = await mw.after_step(context, result)
        return result
```

**Middlewares prioritarios:**
1. `SummarizationMiddleware` — comprime historico de conversacao
2. `WorkspaceMiddleware` — gere leitura/escrita de intermediarios no disco
3. `TokenBudgetMiddleware` — corta contexto quando proximo do limite

---

## 4. Problemas Reais e Solucoes (Aplicados ao MiniAutoGen)

### 4.1 Overhead Quadratico de Coordenacao (AutoGen Problem)

**O problema:** 4 agentes × 20 mensagens × 500 tokens = 40,000 tokens so para coordenacao.

**No MiniAutoGen:** O nosso modo `Deliberation` tem o mesmo risco — cada participante recebe todo o historico de contributions e reviews.

**Solucao:** O `SummarizationMiddleware` proposto acima resolve isso. Antes de cada round de deliberacao, comprimir historico anterior num resumo estruturado.

**Impacto:** Para uma deliberacao de 5 rounds com 3 participantes:
- Sem resumo: ~3,000 tokens × 5 rounds × 3 agentes = 45,000 tokens acumulados
- Com resumo: ~3,000 + 500 (resumo) × 4 rounds × 3 = 9,000 tokens

### 4.2 Rigidez de Schema (LangGraph Problem)

**O problema:** Mudancas no schema de estado invalidam checkpoints existentes.

**No MiniAutoGen:** O nosso `CheckpointStore` serializa estado via Pydantic. Mudancas em models podem quebrar deserializacao.

**Solucao (ja parcialmente coberta):** Pydantic com `model_config = {"extra": "ignore"}` permite evolucao forward-compatible. Recomendacao: adicionar versioning explicito nos checkpoints.

### 4.3 Routing Nao-Deterministico (CrewAI Problem)

**O problema:** Delegacao baseada em interpretacao do LLM nao e reproduzivel.

**No MiniAutoGen:** O nosso `AgenticLoop` usa `RouterDecision` do agente router, que tambem depende do LLM.

**Analise:** Este e um trade-off consciente no nosso design. O artigo sugere que para ambientes regulados, routing deterministico (graph-based) e obrigatorio. Para ambientes explorativos, routing via LLM e aceitavel.

**Recomendacao:** Manter ambos os modos. O `Workflow` ja e deterministico. O `AgenticLoop` aceita nao-determinismo by design. Documentar claramente qual modo usar para cada cenario regulatorio.

### 4.4 Perda de Informacao na Sumarizacao

**O problema:** Comprimir 60,000 tokens para 3,000 perde detalhes criticos.

**Solucao do artigo:** Extracao estruturada ANTES de sumarizar — campos especificos em JSON primeiro, depois sumarizar narrativa.

**Aplicacao no MiniAutoGen:** O `WorkspaceMiddleware` pode implementar isto:
1. Agente produz output completo → salvo em `workspace/`
2. Middleware extrai campos chave → JSON estruturado
3. Proximo agente recebe JSON estruturado (nao texto completo)
4. Se precisar de detalhes, le do `workspace/` path

---

## 5. Compliance e Governanca

O artigo destaca requisitos regulatorios (OCC, FINRA, Fed) que sao relevantes para MiniAutoGen como framework:

| Requisito Regulatorio | Como MiniAutoGen Cobre | Gap |
|----------------------|----------------------|-----|
| **Audit trail** (OCC 2011-12) | EventStore com 70+ tipos de evento | Coberto — cada decisao e um evento tipado |
| **Reproducibilidade** (SR 11-7) | Workflow mode e deterministico | Parcial — AgenticLoop nao e reproduzivel |
| **Sandbox isolation** | Backends CLI sao nativamente isolados | Coberto para CLI drivers |
| **Human-in-the-loop** | ApprovalGate policy | Coberto |
| **Cost governance** | BudgetPolicy + token tracking | Coberto — mas sem filesystem optimization |

**Insight:** O MiniAutoGen ja tem a infraestrutura de compliance mais robusta que qualquer framework analisado no artigo, EXCETO a gestao de custos via filesystem-first.

---

## 6. Onde MiniAutoGen se Posiciona no Espetro

```
Monolitico ◄────────────────────────────────────────► Composavel

AutoGen        CrewAI        LangGraph        DeerFlow     Anthropic
(broadcast)    (role-based)  (state machine)  (middleware)  (DIY)
                                                    │
                                              MiniAutoGen
                                              (microkernel +
                                               policies +
                                               protocols)
```

**MiniAutoGen ja esta no lado composavel** — o nosso microkernel com policies plugaveis, protocols tipados e event-driven architecture e naturalmente alinhado com o padrao vencedor.

O que FALTA para completar o alinhamento:

| Pilar | Estado | Prioridade |
|-------|--------|-----------|
| Progressive Skill Loading | Nao implementado | Media |
| Filesystem-First State | Parcial (CheckpointStore existe, workspace nao) | **Alta** |
| Middleware Pipeline | Parcial (EffectInterceptor existe, nao generalizado) | **Alta** |

---

## 7. Plano de Acao Recomendado

### Fase 1: RunWorkspace (Alta Prioridade)

**Objetivo:** Cada execucao do PipelineRunner opera com workspace em disco.

**Ficheiros a criar/modificar:**
- `miniautogen/core/contracts/workspace.py` — Protocol `WorkspaceProvider`
- `miniautogen/core/runtime/workspace.py` — Implementacao `RunWorkspace`
- Modificar `PipelineRunner` para criar workspace por run
- Modificar coordination runtimes para usar workspace entre steps

**Metricas de sucesso:**
- Resultados intermediarios salvos em disco, nao acumulados em contexto
- Reducao mensuravel de tokens em pipelines multi-step

### Fase 2: StepMiddleware (Alta Prioridade)

**Objetivo:** Generalizar EffectInterceptor para pipeline de middlewares composavel.

**Ficheiros a criar/modificar:**
- `miniautogen/core/contracts/middleware.py` — Protocol `StepMiddleware`
- `miniautogen/core/runtime/middleware.py` — `MiddlewarePipeline`
- `miniautogen/policies/summarization.py` — `SummarizationMiddleware`
- `miniautogen/policies/workspace_middleware.py` — `WorkspaceMiddleware`

**Metricas de sucesso:**
- Cada step do pipeline passa por middleware chain
- Middlewares configurados por agente (nao globais)

### Fase 3: SkillRegistry (Media Prioridade)

**Objetivo:** Progressive loading de capabilities dos agentes.

**Ficheiros a criar/modificar:**
- `miniautogen/core/contracts/skill.py` — Protocol `SkillProvider`
- `miniautogen/core/runtime/skill_registry.py` — Registry com lazy loading
- Modificar `AgentSpec` para suportar skill references

**Metricas de sucesso:**
- Agentes iniciam com ~100 tokens de metadata por skill
- Skills completas carregadas apenas quando ativadas

---

## 8. Validacao Cruzada: MiniAutoGen vs Padroes do Artigo

| Padrao Vencedor | AutoGen | LangGraph | CrewAI | DeerFlow | MiniAutoGen |
|----------------|---------|-----------|--------|----------|-------------|
| Progressive Loading | Nao | Nao | Nao | Sim | **Parcial** (agentes definidos em YAML, mas sem tiering) |
| Filesystem State | Nao | Parcial (checkpoints) | Nao | Sim | **Parcial** (CheckpointStore, sem workspace) |
| Middleware Pipeline | Nao | Parcial (nodes) | Nao | Sim | **Parcial** (EffectInterceptor, Policies reactivas) |
| Typed Contracts | Nao | Sim (TypedDict) | Nao | Parcial (Zod) | **Sim** (Protocol + Pydantic) |
| Event System | Basico | Via estado | Basico | Middleware logs | **Sim** (70+ eventos tipados) |
| Supervision/Recovery | Nao | Checkpoints | Nao | Nao | **Sim** (supervision trees) |
| Idempotency | Nao | Nao | Nao | Nao | **Sim** (EffectJournal) |

**Conclusao:** MiniAutoGen ja supera TODOS os frameworks analisados em contratos tipados, sistema de eventos, supervision e idempotencia. Os 3 gaps restantes (progressive loading, filesystem state, middleware generalizado) sao incrementais e aditivos — nao requerem refactoring do core.

---

## 9. Citacao Chave

> *"You are now programming an organization… the source code is the collection of prompts, skills, tools, and processes that make it up."* — Andrej Karpathy

Isto alinha-se perfeitamente com a filosofia MiniAutoGen: o `miniautogen.yaml` e literalmente o "codigo-fonte da organizacao" de agentes.
