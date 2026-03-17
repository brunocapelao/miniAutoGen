# Plano Consolidado — Side C: Microkernel de Coordenação Multiagente

> **Status:** Concluído. Ver commits recentes.

> **Substitui todos os planos anteriores em `docs/plans/`.**
> Alinhado com o Sumário Executivo do MiniAutoGen — versão 2026-03-16.
> **v2** — revisado com ajustes de contrato, generalização do modo deliberativo e subfases.

---

## 1. Situação Atual (o que já existe)

### 1.1 Kernel de Execução (funcional)

| Camada | Artefatos | Status |
|--------|-----------|--------|
| **Contratos tipados** | `Message`, `RunContext`, `RunResult`, `ExecutionEvent` | ✅ Entregue |
| **Runtime base** | `PipelineRunner` (anyio, timeout, checkpoint, eventos) | ✅ Entregue |
| **Eventos** | `EventType` enum (22 tipos), `EventSink` protocol | ✅ Entregue |
| **Stores** | `RunStore`, `CheckpointStore` (abstract + in-memory) | ✅ Entregue |
| **Policies** | `ExecutionPolicy`, `RetryPolicy`, `BudgetPolicy`, `ValidationPolicy` | ✅ Entregue |
| **Adapters** | LLM (LiteLLM, OpenAI, Gateway), Templates (Jinja2) | ✅ Entregue |
| **Pipeline** | `Pipeline`, `PipelineComponent`, `PipelineState` | ✅ Entregue |
| **Observabilidade** | Structured logging | ✅ Entregue |

### 1.2 Contratos de Modos (definidos, não executam)

| Contrato | Módulo | Status |
|----------|--------|--------|
| `RouterDecision`, `ConversationPolicy`, `AgenticLoopState` | `core/contracts/agentic_loop.py` | ✅ Entregue (untracked) |
| `ResearchOutput`, `PeerReview`, `DeliberationState`, `FinalDocument` | `core/contracts/deliberation.py` | ✅ Entregue (untracked) |

### 1.3 Helpers de Runtime (definidos, não integrados)

| Helper | Módulo | Status |
|--------|--------|--------|
| `detect_stagnation`, `should_stop_loop` | `core/runtime/agentic_loop.py` | ✅ Entregue (untracked) |
| `summarize_peer_reviews`, `build_follow_up_tasks`, `apply_leader_review` | `core/runtime/deliberation.py` | ✅ Entregue (untracked) |
| `render_final_document_markdown` | `core/runtime/final_document.py` | ✅ Entregue (untracked) |

### 1.4 Shells (estrutura sem execução)

| Shell | Módulo | Status |
|-------|--------|--------|
| `DynamicChatPipeline` | `pipeline/dynamic_chat_pipeline.py` | 🟡 Shell vazio |
| `AgenticLoopComponent` | `pipeline/components/agentic_loop.py` | 🟡 Shell vazio |

### 1.5 Testes (escritos, untracked)

19 arquivos de teste cobrindo contratos, runtime helpers, eventos e integração.

---

## 2. Gap entre Estado Atual e Visão Side C

A visão exige **4 camadas explícitas**. Segue o mapeamento de gap:

### Camada 1 — Kernel Neutro

| Requisito | Estado Atual | Gap |
|-----------|-------------|-----|
| Contratos tipados | ✅ Existem | Nenhum |
| Runtime base | ✅ PipelineRunner | Nenhum (já neutro — ver DA-1) |
| Eventos canônicos | ✅ EventType | Nenhum (já neutro) |
| Stores | ✅ Abstrações prontas | Nenhum |
| Policies | ✅ Prontas | Nenhum |
| Adapters | ✅ Prontos | Nenhum |
| Observabilidade | ✅ Logging | Nenhum (traces/metrics são evolutivos) |

**Conclusão da Camada 1**: O kernel já é semanticamente neutro. O `PipelineRunner` é o executor neutro atual — o nome é histórico, não ontológico. Os modos o consomem como dependência injetada. Não há reescrita.

### Camada 2 — Coordination Modes

| Requisito | Estado Atual | Gap |
|-----------|-------------|-----|
| `WorkflowRuntime` | Não existe como abstração | **Criar runtime** com responsabilidades próprias de coordenação (interpretação de plano, topologia, fan-out, normalização) |
| `DeliberationRuntime` | Não existe | **Criar runtime** com ciclo abstrato: contribuição → crítica → consolidação → suficiência → iteração → artefato |
| Protocol `CoordinationMode[PlanT]` | Não existe | **Criar protocol genérico tipado** que elimina `**kwargs` como escape hatch |
| Composição modo→modo | Não existe | **Criar primitiva** `workflow → deliberation → workflow` |

**Conclusão da Camada 2**: Este é o maior gap. Os contratos e helpers existem, mas nenhum runtime completo existe.

### Camada 3 — Canonical Patterns

| Requisito | Estado Atual | Gap |
|-----------|-------------|-----|
| `StructuredReviewFlow` | Não existe | Futuro — depende dos modos funcionarem |
| `ResearchSynthesisFlow` | Não existe | Futuro — primeira especialização concreta do `DeliberationRuntime` |
| `RoundRobinDebate` | `NextAgentSelectorComponent` existe | Futuro — pattern sobre `DeliberationRuntime` |
| `ModeratedDebate` | Não existe | Futuro — pattern com `RouterDecision` |

**Conclusão da Camada 3**: Não prioritário. Só faz sentido depois que os modos funcionam de ponta a ponta.

### Camada 4 — Public API / Identidade

| Requisito | Estado Atual | Gap |
|-----------|-------------|-----|
| `Agent` | Existe em `agent/` (legado) | **Manter, não refatorar agora** |
| `Message` | ✅ `core/contracts/message.py` | Nenhum |
| `Pipeline` | ✅ `pipeline/pipeline.py` | Nenhum |
| `Runtime` | Não existe como conceito público | **Criar reexport** de `WorkflowRuntime` e `DeliberationRuntime` |
| `Conversation` | Não existe como conceito tipado | **Lacuna consciente** — ver seção 4 |

**Conclusão da Camada 4**: Mínimo necessário: reexportar os runtimes como API pública.

---

## 3. Plano de Implementação

### Princípios do plano

1. **Não reescrever o que funciona** — o kernel está sólido
2. **TDD obrigatório** — teste falha antes de implementar
3. **Menor batch possível** — cada fase entrega valor verificável
4. **Contratos primeiro, execução depois**
5. **Os modos devem ser finos** — delegam para o kernel, não duplicam
6. **Modos são abstratos, patterns são concretos** — o runtime não é sinônimo de um caso de uso

---

### Fase 1 — Formalizar o Protocol de Coordenação (Contratos)

**Objetivo**: Definir a interface formal que todo modo de coordenação deve seguir, com tipagem forte o suficiente para impedir deriva silenciosa entre modos.

#### Task 1.1: `CoordinationMode` protocol genérico tipado

**Arquivo**: `miniautogen/core/contracts/coordination.py`
**Teste**: `tests/core/contracts/test_coordination.py`

```python
from typing import Protocol, TypeVar, Any, runtime_checkable
from enum import Enum
from pydantic import BaseModel

class CoordinationKind(str, Enum):
    WORKFLOW = "workflow"
    DELIBERATION = "deliberation"

class CoordinationPlan(BaseModel):
    """Envelope base para todos os planos de coordenação."""
    pass

PlanT = TypeVar("PlanT", bound=CoordinationPlan)

@runtime_checkable
class CoordinationMode(Protocol[PlanT]):
    """Interface que todo modo de coordenação deve implementar.

    Genérico em PlanT para forçar cada modo a declarar seu tipo de plano.
    Isso elimina **kwargs como escape hatch e garante type safety na composição.
    """
    kind: CoordinationKind

    async def run(self, agents: list[Any], context: "RunContext", plan: PlanT) -> "RunResult":
        """Executa coordenação com os agentes dados segundo o plano tipado."""
        ...
```

**Critério de aceite**:
- Protocol genérico com `PlanT` bound a `CoordinationPlan`
- `CoordinationKind` enum com WORKFLOW e DELIBERATION
- `CoordinationPlan` como envelope base (Pydantic BaseModel)
- Teste verifica structural subtyping: classe concreta satisfaz protocol
- Teste verifica que `run()` exige plan tipado (não aceita `**kwargs`)

#### Task 1.2: `WorkflowPlan` e `DeliberationPlan` contracts

**Arquivo**: `miniautogen/core/contracts/coordination.py` (mesmo arquivo)
**Teste**: `tests/core/contracts/test_coordination.py`

```python
from pydantic import Field

class WorkflowStep(BaseModel):
    component_name: str
    agent_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)

class WorkflowPlan(CoordinationPlan):
    """Plano de execução para WorkflowRuntime."""
    steps: list[WorkflowStep]
    fan_out: bool = False
    synthesis_agent: str | None = None

class DeliberationPlan(CoordinationPlan):
    """Plano de execução para DeliberationRuntime.

    Modela o ciclo abstrato de deliberação, não um caso de uso específico.
    O ciclo é: contribuição → crítica → consolidação → suficiência → iteração.
    """
    topic: str
    participants: list[str]
    max_rounds: int = 3
    leader_agent: str | None = None
    policy: ConversationPolicy = Field(default_factory=ConversationPolicy)
```

**Critério de aceite**:
- Ambos herdam de `CoordinationPlan`
- `WorkflowPlan` modela steps + fan-out + synthesis
- `DeliberationPlan` modela topic + participants + rounds + policy
- Sem defaults mutáveis implícitos (`Field(default_factory=...)`)
- Testes de serialização, validação e herança de `CoordinationPlan`

---

### Fase 2 — WorkflowRuntime (modo estruturado)

**Objetivo**: Runtime com responsabilidades próprias de coordenação — não apenas um wrapper sobre `PipelineRunner`.

#### Task 2.1: `WorkflowRuntime` implementation

**Arquivo**: `miniautogen/core/runtime/workflow_runtime.py`
**Teste**: `tests/core/runtime/test_workflow_runtime.py`

```python
class WorkflowRuntime:
    """Modo de coordenação estruturada.

    Responsabilidades próprias (não delegadas ao kernel):
    - Interpretação e validação do WorkflowPlan
    - Resolução da topologia de execução (sequencial vs fan-out)
    - Materialização de steps independentes para execução paralela
    - Normalização de outputs intermediários entre steps
    - Decisão de quando aplicar síntese
    - Emissão de eventos de nível de modo (não só de componente)
    """

    kind = CoordinationKind.WORKFLOW

    def __init__(
        self,
        runner: PipelineRunner,
        agent_registry: dict[str, Any] | None = None,
    ):
        self._runner = runner
        self._agents = agent_registry or {}

    async def run(
        self,
        agents: list[Any],
        context: RunContext,
        plan: WorkflowPlan,
    ) -> RunResult:
        """
        Executa workflow:
        1. Valida coerência do plan (agents referenciados existem, steps são válidos)
        2. Monta pipeline a partir do plan
        3. Se fan_out: materializa steps independentes, executa em paralelo via anyio
        4. Normaliza outputs intermediários (cada step recebe contexto do anterior)
        5. Se synthesis_agent: roda agente de síntese no final
        6. Emite eventos de nível de modo
        """
        ...
```

**Critério de aceite**:
- Valida `WorkflowPlan` antes de executar (agentes referenciados existem)
- Executa lista sequencial de steps via `PipelineRunner`
- Suporta `fan_out=True` → execução paralela de steps independentes
- Suporta `synthesis_agent` → agente final que consolida outputs
- Normaliza output de step N como input de step N+1
- Emite eventos: `RUN_STARTED`, `COMPONENT_STARTED/FINISHED`, `RUN_FINISHED`
- Respeita timeout e policies do kernel
- **Testes**:
  - 3+ steps sequenciais com ordem determinística verificada
  - Fan-out com verificação de paralelismo
  - Síntese com verificação de consolidação
  - Step que falha → RunResult com erro
  - Fan-out com 1 ramo que falha → comportamento definido

#### Task 2.2: Registrar `WorkflowRuntime` no `__init__.py`

**Arquivo**: `miniautogen/core/runtime/__init__.py`

Adicionar export de `WorkflowRuntime`.

---

### Fase 3 — DeliberationRuntime (modo conversacional)

**Objetivo**: Runtime que orquestra deliberação multiagente como **ciclo abstrato**, não como caso de uso específico.

O ciclo deliberativo é:

> **contribuição → crítica cruzada → consolidação → avaliação de suficiência → iteração ou finalização → artefato**

O "research loop" (ResearchOutput → PeerReview → LeaderConsolidation → FinalDocument) é a **primeira especialização concreta** desse ciclo, não a definição do modo.

**A Fase 3 é dividida em 3 subfases** para controlar entropia:

#### Subfase 3A — DeliberationRuntime minimal (1 rodada)

**Objetivo**: Runtime que executa 1 rodada de contribuição + consolidação.

##### Task 3A.1: `DeliberationRuntime` core

**Arquivo**: `miniautogen/core/runtime/deliberation_runtime.py`
**Teste**: `tests/core/runtime/test_deliberation_runtime.py`

```python
class DeliberationRuntime:
    """Modo de coordenação conversacional.

    Implementa o ciclo abstrato de deliberação:
    1. Contribuição — cada participante produz output estruturado
    2. Crítica cruzada — participantes revisam outputs uns dos outros
    3. Consolidação — líder (ou heurística) sintetiza contribuições e críticas
    4. Suficiência — avaliação se o resultado é bom o suficiente
    5. Iteração — se insuficiente, novo round com follow-ups direcionados
    6. Artefato — produção do resultado final

    Os contratos existentes (ResearchOutput, PeerReview, DeliberationState,
    FinalDocument) são a primeira especialização concreta deste ciclo.
    """

    kind = CoordinationKind.DELIBERATION

    def __init__(
        self,
        runner: PipelineRunner,
        agent_registry: dict[str, Any] | None = None,
    ):
        self._runner = runner
        self._agents = agent_registry or {}

    async def run(
        self,
        agents: list[Any],
        context: RunContext,
        plan: DeliberationPlan,
    ) -> RunResult:
        ...
```

**Escopo 3A (minimal)**:
- Distribui tópico para participantes
- Coleta contribuição de cada agente (1 rodada)
- Consolidação simples pelo leader (sem peer review ainda)
- Retorna `RunResult` com output consolidado

**Critério de aceite**:
- Executa 1 rodada com 2+ agentes
- Leader consolida outputs
- Emite eventos de deliberação
- Respeita `ConversationPolicy` (timeout, max_rounds=1)
- Teste com 2 agentes, 1 rodada, consolidação

#### Subfase 3B — Peer review loop

**Objetivo**: Adicionar crítica cruzada ao runtime.

##### Task 3B.1: Integrar peer review no `DeliberationRuntime`

**Arquivo**: `miniautogen/core/runtime/deliberation_runtime.py` (estende 3A)
**Teste**: `tests/core/runtime/test_deliberation_runtime.py` (novos testes)

**Escopo 3B**:
- Após contribuição, executa peer review cruzado
- Agrega reviews via `summarize_peer_reviews` (helper existente)
- Gera follow-ups via `build_follow_up_tasks` (helper existente)
- Leader consolida com reviews via `apply_leader_review` (helper existente)

**Critério de aceite**:
- Cada agente revisa outputs dos outros
- Reviews são agregadas e sintetizadas
- Follow-ups são gerados para gaps identificados
- Testes com 3 agentes, peer review cruzado, verificação de follow-ups

#### Subfase 3C — Sufficiency loop + artefato final

**Objetivo**: Fechar o ciclo com iteração e produção de artefato.

##### Task 3C.1: Loop de suficiência no `DeliberationRuntime`

**Arquivo**: `miniautogen/core/runtime/deliberation_runtime.py` (estende 3B)
**Teste**: `tests/core/runtime/test_deliberation_runtime.py` (novos testes)

**Escopo 3C**:
- Avalia `DeliberationState.is_sufficient` após cada round
- Se insuficiente e `round < max_rounds`: novo round com follow-ups direcionados
- Se suficiente ou max_rounds atingido: gera `FinalDocument`
- Renderiza via `render_final_document_markdown` (helper existente)

**Critério de aceite**:
- Multi-round: 2+ rounds quando primeira rodada é insuficiente
- Para corretamente quando suficiente (antes de max_rounds)
- Para corretamente quando max_rounds atingido (mesmo insuficiente)
- Gera `FinalDocument` com `decision_summary`
- Testes: cenário de consenso (1 round), cenário de divergência (2+ rounds), cenário de max_rounds

##### Task 3C.2: Integrar `AgenticLoopComponent` como componente injetável

**Arquivo**: `miniautogen/pipeline/components/agentic_loop.py` (já existe como shell)
**Arquivo**: `miniautogen/pipeline/dynamic_chat_pipeline.py` (já existe como shell)
**Teste**: `tests/pipeline/test_agentic_loop_component.py` (já existe)

O `AgenticLoopComponent` é um **componente de pipeline**, não um runtime nem um coordenador global. Ele executa conversação livre contida e pode ser injetado em pipelines de qualquer modo.

```python
class AgenticLoopComponent(PipelineComponent):
    """Componente que executa conversação livre com contenção sistêmica.

    IMPORTANTE: Este componente NÃO é um runtime nem um coordenador global.
    É um componente injetável que pode ser usado dentro de pipelines de
    WorkflowRuntime (como step que abre conversa livre) ou dentro de
    DeliberationRuntime (como mecanismo de debate aberto dentro de um round).
    Sua contenção é garantida por ConversationPolicy e should_stop_loop.
    """

    def __init__(self, policy: ConversationPolicy, router_agent: Any, agent_registry: dict[str, Any]):
        self.policy = policy
        self.router = router_agent
        self.agents = agent_registry

    async def process(self, state: Any) -> Any:
        """
        Loop:
        1. Router emite RouterDecision
        2. Agente selecionado responde
        3. ConversationPolicy avalia (max_turns, timeout, stagnation)
        4. Loop ou para
        """
        loop_state = AgenticLoopState(active_agent=None, turn_count=0)
        while True:
            decision: RouterDecision = await self._route(state, loop_state)
            if decision.terminate:
                break
            reply = await self._agent_reply(decision.next_agent, state)
            loop_state.turn_count += 1
            should_stop, reason = should_stop_loop(loop_state, self.policy)
            if should_stop:
                break
        return state
```

**Critério de aceite**:
- `AgenticLoopComponent.process()` executa loop completo
- Respeita `ConversationPolicy` (max_turns, stagnation)
- Pode ser injetado em pipeline de `WorkflowRuntime` ou `DeliberationRuntime`
- Testes de parada por max_turns, por terminate flag, por stagnation

---

### Fase 4 — Composição Modo→Modo

**Objetivo**: Permitir a inovação central do MiniAutoGen: `workflow → deliberation → workflow`.

#### Task 4.1: `CompositeRuntime`

**Arquivo**: `miniautogen/core/runtime/composite_runtime.py`
**Teste**: `tests/core/runtime/test_composite_runtime.py`

```python
from dataclasses import dataclass, field
from typing import Callable, Any

@dataclass
class CompositionStep:
    """Um passo na composição de modos.

    Atributos:
        mode: O runtime de coordenação a executar
        plan: O plano tipado para este modo
        label: Rótulo descritivo para eventos e rastreabilidade
        input_mapper: Função opcional que transforma o RunResult anterior
                      no formato esperado por este step. Se None, o contexto
                      é passado como está.
        output_mapper: Função opcional que transforma o RunResult deste step
                       antes de passá-lo adiante. Se None, o resultado é
                       passado como está.
    """
    mode: CoordinationMode
    plan: CoordinationPlan
    label: str = ""
    input_mapper: Callable[["RunResult", "RunContext"], "RunContext"] | None = None
    output_mapper: Callable[["RunResult"], "RunResult"] | None = None

class CompositeRuntime:
    """Compõe modos de coordenação em sequência.

    A composição é explícita: o usuário define a sequência de steps.
    Sem DSL, sem inferência automática.
    """

    kind = CoordinationKind.WORKFLOW  # composite se comporta como workflow externamente

    async def run(
        self,
        agents: list[Any],
        context: RunContext,
        plan: list[CompositionStep],
    ) -> RunResult:
        """
        Executa steps em sequência, passando output de um modo como input do próximo.
        Permite: workflow → deliberation → workflow

        Para cada step:
        1. Aplica input_mapper se presente (transforma contexto)
        2. Executa mode.run() com plan tipado
        3. Aplica output_mapper se presente (transforma resultado)
        4. Injeta resultado no contexto do próximo step
        """
        result = None
        for step in plan:
            if step.input_mapper and result:
                context = step.input_mapper(result, context)
            elif result:
                context = context.with_previous_result(result)

            result = await step.mode.run(agents, context, plan=step.plan)

            if step.output_mapper:
                result = step.output_mapper(result)
        return result
```

**Critério de aceite**:
- Compõe 2+ modos em sequência
- Output de modo N alimenta input de modo N+1
- `input_mapper` e `output_mapper` são aplicados quando presentes
- Sem mappers: usa `with_previous_result` como fallback
- Teste: workflow(2 steps) → deliberation(2 agents) → workflow(synthesis)
- Teste: composição com `input_mapper` customizado
- Emite eventos de cada modo mantendo `correlation_id` consistente

#### Task 4.2: Helper `RunContext.with_previous_result`

**Arquivo**: `miniautogen/core/contracts/run_context.py`
**Teste**: `tests/core/contracts/test_run_context.py`

Adicionar método que cria novo `RunContext` com metadata do resultado anterior.

---

### Fase 5 — Public API e Identidade

**Objetivo**: Garantir que o MiniAutoGen continue sendo reconhecível como biblioteca multiagente.

#### Task 5.1: Reexport dos runtimes na API pública

**Arquivo**: `miniautogen/__init__.py` (ou criar `miniautogen/api.py`)

```python
# Public API — MiniAutoGen
from miniautogen.core.contracts import Message, RunContext, RunResult, ExecutionEvent
from miniautogen.core.contracts.coordination import (
    CoordinationKind, CoordinationPlan, WorkflowPlan, DeliberationPlan,
)
from miniautogen.core.runtime import WorkflowRuntime, DeliberationRuntime, CompositeRuntime
from miniautogen.pipeline import Pipeline, PipelineComponent

__all__ = [
    # Core
    "Message", "RunContext", "RunResult", "ExecutionEvent",
    # Coordination
    "CoordinationKind", "CoordinationPlan", "WorkflowPlan", "DeliberationPlan",
    # Runtimes (Coordination Modes)
    "WorkflowRuntime", "DeliberationRuntime", "CompositeRuntime",
    # Pipeline
    "Pipeline", "PipelineComponent",
]
```

**Critério de aceite**:
- Import `from miniautogen import WorkflowRuntime, DeliberationRuntime` funciona
- API pública fala a linguagem do projeto: Agent, Message, Pipeline, Runtime

#### Task 5.2: Atualizar documentação de arquitetura

**Arquivo**: `docs/pt/target-architecture/03-arquitetura-alvo.md`

Alinhar com a implementação real das 4 camadas.

---

### Fase 6 — Demo: Notebook Deliberativo (DeCripto Club)

**Objetivo**: Demonstrar o sistema funcionando de ponta a ponta.

**Nota**: Esta demo usa o research loop como caso de uso. Isso é intencional — ele é a primeira especialização concreta do `DeliberationRuntime`. Mas a demo não deve dirigir a arquitetura do runtime; ela apenas o consome.

#### Task 6.1: Notebook de pesquisa deliberativa

**Arquivo**: `notebooks/decripto_club_research.ipynb`

Notebook Jupyter que:
1. Configura 5 agentes especializados via Gemini CLI Gateway
2. Usa `DeliberationRuntime` para executar pesquisa
3. Executa contribuição → peer review → leader consolidation → final document
4. Gera dossier operacional em Markdown
5. Usa `ResponseCache` para estabilidade em re-execuções

**Critério de aceite**:
- Notebook executa sem erros
- Gera documento final com seções estruturadas
- Demonstra peer review e consolidação real

---

## 4. O que NÃO entra neste plano

| Item | Razão |
|------|-------|
| **Canonical Patterns** (StructuredReviewFlow, etc.) | Dependem dos modos funcionando; próxima iteração |
| **Reescrita do kernel** | Kernel já é neutro; não precisa reescrita |
| **Refatoração do legado** (`chat/`, `compat/`) | Não bloqueia Side C; limpar depois |
| **Contabilidade real de tokens** (budget_cap) | Placeholder estrutural é suficiente por ora |
| **Replay completo de conversas** (store-backed) | Evolutivo; stores abstratos já existem |
| **Traces OpenTelemetry** | Evolutivo; structured logging é suficiente |
| **Taxonomia de eventos por modo** | Emergirá durante implementação das Fases 2-3; definir a priori seria especulação |
| **Registry formal de agentes** | O `agent_registry: dict[str, Any]` é provisório e suficiente para o MVP. Ponto arquitetural a estabilizar depois |

### Lacuna consciente: `Conversation` tipado

O conceito tipado de `Conversation` (histórico, participantes, metadata, estado resumido) **não entra neste MVP**. Isso é pragmaticamente correto — não bloqueia nenhuma fase.

Porém, há um impacto identitário: se o MiniAutoGen se posiciona como biblioteca de coordenação conversacional e não possui um tipo `Conversation` na API pública, existe uma incoerência entre narrativa e modelo. Esta lacuna será endereçada na iteração seguinte, possivelmente como envelope mínimo na camada de API pública.

---

## 5. Ordem de Execução e Dependências

```
Fase 1 ─── Contratos de Coordenação
  │          (CoordinationMode[PlanT], CoordinationPlan, WorkflowPlan, DeliberationPlan)
  │
  ├──→ Fase 2 ─── WorkflowRuntime
  │                 (interpretação de plano, topologia, fan-out, normalização)
  │
  ├──→ Fase 3A ── DeliberationRuntime minimal (1 rodada, contribuição + consolidação)
  │       │
  │       └──→ Fase 3B ── Peer review loop (crítica cruzada, síntese)
  │              │
  │              └──→ Fase 3C ── Sufficiency loop + artefato final + AgenticLoopComponent
  │
  └──→ Fase 4 ─── CompositeRuntime (depende de 2 e 3C)
                    (composição modo→modo com mappers)
         │
         └──→ Fase 5 ─── Public API + Docs
                │
                └──→ Fase 6 ─── Demo Notebook
```

**Fases 2 e 3A podem ser executadas em paralelo** — não há dependência entre elas além da Fase 1.

---

## 6. Mapeamento: Planos Anteriores → Este Plano

| Plano Anterior | Absorvido Em |
|----------------|-------------|
| `side-c-exact-architecture.md` | Fases 1-5 (simplificado — sem reescrita do kernel) |
| `side-c-coordination-kernel.md` | Fase 1 (contratos) + Fase 5 (docs) |
| `agentic-loop-component.md` | Fase 3C, Task 3C.2 (AgenticLoopComponent) |
| `agentic-loop-component-design.md` | Fase 3C, Task 3C.2 (design absorvido) |
| `agentic-loop-runtime-integration.md` | Fase 3C, Task 3C.2 (integração no runtime) |
| `deliberative-research-loop.md` | Fases 3A-3C (DeliberationRuntime) |
| `deliberative-research-loop-design.md` | Fases 3A-3C (design absorvido) |
| `deliberative-quality-hardening.md` | Fase 3B (qualidade via peer review loop) |
| `decripto-club-research-notebook.md` | Fase 6 (notebook demo) |
| `decripto-club-research-notebook-design.md` | Fase 6 (design absorvido) |

---

## 7. Métricas de Sucesso

| Métrica | Alvo |
|---------|------|
| `WorkflowRuntime` executa pipeline de 3+ steps com fan-out | ✅ |
| `DeliberationRuntime` completa ciclo abstrato: contribuição → crítica → consolidação | ✅ |
| `CompositeRuntime` compõe workflow→deliberation→workflow com mappers | ✅ |
| Todos os contratos existentes reutilizados (zero reescrita) | ✅ |
| Testes passam para cada subfase antes de avançar | ✅ |
| Notebook demo gera documento final estruturado | ✅ |
| API pública: `from miniautogen import WorkflowRuntime, DeliberationRuntime` | ✅ |

---

## 8. Decisões Arquiteturais Explícitas

### DA-1: Kernel não é renomeado

O `PipelineRunner` **não** será renomeado para `KernelRunner`. Ele já é semanticamente neutro — o nome é histórico, não ontológico. Os modos (`WorkflowRuntime`, `DeliberationRuntime`) o consomem como dependência injetada.

### DA-2: Modos são classes com protocol genérico tipado

Os runtimes implementam `CoordinationMode[PlanT]` via structural subtyping. Não herdam de uma classe base. O TypeVar `PlanT` bound a `CoordinationPlan` garante que cada modo declare explicitamente seu tipo de plano, eliminando `**kwargs` como escape hatch.

### DA-3: `AgenticLoopComponent` é componente, não runtime

O `AgenticLoopComponent` é um componente de pipeline injetável. **Não é um runtime, não é um coordenador global, não é responsável por governança de execução.** Pode ser injetado em pipelines de workflow (como step que abre conversa livre) ou usado internamente pelo `DeliberationRuntime` (como mecanismo de debate aberto dentro de um round). Sua contenção é garantida exclusivamente por `ConversationPolicy` e `should_stop_loop`.

### DA-4: Composição é explícita, não implícita

`CompositeRuntime` não é mágica. O usuário define explicitamente a sequência de `CompositionStep`. Sem DSL, sem inferência automática. Mappers opcionais (`input_mapper`, `output_mapper`) permitem transformação entre modos sem impor formato.

### DA-5: Contratos existentes são reutilizados integralmente

`ResearchOutput`, `PeerReview`, `DeliberationState`, `FinalDocument`, `RouterDecision`, `ConversationPolicy`, `AgenticLoopState` — todos são consumidos sem alteração. Novos contratos: `CoordinationMode[PlanT]`, `CoordinationPlan`, `WorkflowPlan`, `DeliberationPlan`, `CompositionStep`.

### DA-6: Legado coexiste

Os módulos `chat/`, `agent/`, `compat/` continuam existindo. Não serão tocados nem removidos. A nova arquitetura cresce ao lado, sem breaking changes.

### DA-7: DeliberationRuntime é abstrato, research loop é specialization

O `DeliberationRuntime` implementa o ciclo abstrato de deliberação (contribuição → crítica → consolidação → suficiência → iteração → artefato). O "research loop" com `ResearchOutput → PeerReview → LeaderConsolidation → FinalDocument` é a primeira especialização concreta, não a definição do modo. Futuras especializações (debate moderado, brainstorm estruturado, etc.) devem usar o mesmo runtime com contratos diferentes.
