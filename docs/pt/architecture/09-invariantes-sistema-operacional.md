# Definição Arquitetural: Invariantes do Sistema Operacional MiniAutoGen

**Versão:** 1.1.0
**Data:** 2025-06-18
**Tipo:** Auditoria Arquitetural + Definição de Invariantes
**Classificação:** Constituição da Engenharia

> Este documento estabelece as 8 invariantes invioláveis que governam o MiniAutoGen como Sistema Operacional de Agentes. Não é um guia — é uma **constituição**. Qualquer commit que viole estas invariantes deve ser rejeitado em code review.

---

## 1. Resumo Executivo

A transição do MiniAutoGen para um paradigma de **Sistema Operacional Distribuído** com Modelo de Atores (Microkernel + Erlang/OTP) estabelece alicerces contratuais invioláveis para a orquestração multiagente. A adoção de oito invariantes arquiteturais estritas garante concorrência massiva, execução durável (24/7) e tolerância a falhas extremas.

Este rigor técnico elimina categoricamente o risco de:
- Corrupção de estado por concorrência
- Repetição de efeitos colaterais em replays
- Kernel Panics induzidos por agentes externos
- Processos "zumbis" consumindo recursos indefinidamente

> Para contexto estratégico, ver [competitive-landscape.md](../../competitive-landscape.md). Para evolução da arquitetura, ver [architecture-retrospective.md](../../architecture-retrospective.md).

---

## 2. Pontos Fortes da Arquitetura Atual

Antes de apontar o que precisa mudar, é essencial reconhecer o que já funciona:

### 2.1 Contratos Fortemente Tipados (Rejeição do Texto Livre)

O banimento de dicionários genéricos e `**kwargs` em favor de validação estrutural frozen garante que erros de contrato sejam capturados na compilação ou na borda da aplicação. Em um ambiente onde a saída do LLM é inerentemente probabilística, a infraestrutura de orquestração deve ser de ferro.

**Evidência no codebase:**
- 30+ modelos Pydantic em `core/contracts/`
- `RouterDecision` valida `terminate XOR next_agent` via `@model_validator`
- `ToolResult` enforce `success=True → no error` e `success=False → error required`
- Todos os drivers normalizam para `AgentEvent` canônico

### 2.2 Event Sourcing como Fonte Única de Verdade

O estado da aplicação ser derivado da dobra temporal (left-fold) de eventos canônicos viabiliza:
- Auditoria criptográfica perfeita (cada evento tem `correlation_id` + `timestamp`)
- Time-travel para simulações e dry-runs
- Schema Evolution facilitada
- Observabilidade completa (72 event types em 13 categorias)

**Evidência no codebase:**
- `ExecutionEvent` com type, timestamp, run_id, correlation_id, scope, payload
- `CompositeEventSink` para fan-out de eventos para múltiplos consumers
- `FilteredEventSink` para subscrição seletiva
- `InMemoryEventSink` para testes determinísticos

### 2.3 Isolamento de Adapters

A separação rigorosa entre core e adapters blinda o kernel contra mudanças de providers. Nenhum SDK de LLM é importado dentro de `core/`.

**Evidência no codebase:**
- 7 drivers implementados, todos em `backends/`, nenhum em `core/`
- `AgentDriver` como Protocol (não classe concreta)
- `EngineResolver` como ponto único de resolução
- `BaseDriver` para sanitização e normalização antes de chegar ao core

---

## 3. Críticas Técnicas (Dívida Arquitetural)

As invariantes deste documento existem **porque** a dívida técnica abaixo foi identificada. Cada crítica justifica uma invariante específica.

### 3.1 Mutabilidade Concorrente no RunContext

**Problema:** `RunContext.execution_state` é um `dict[str, Any]` mutável. Em um ambiente de alta concorrência (fan-out paralelo via `anyio.create_task_group()`), múltiplos agentes podem mutar o mesmo dicionário simultaneamente.

**Risco:** Race conditions indetectáveis estaticamente. Corrupção silenciosa de estado em cenários de paralelismo.

**Invariante que resolve:** [Invariante 1 — Estado Isolado e Imutabilidade Estrita](#invariante-1-estado-isolado-e-imutabilidade-estrita)

### 3.2 Processos "Zumbis" e Fragilidade Transacional

**Problema:** Sem commits atômicos de checkpoint e árvores de supervisão, o sistema permite que agentes tentem recuperar indefinidamente falhas semânticas (ex: loops de alucinação de LLM). Isso consome recursos de forma descontrolada e deixa "meios-estados" corrompidos após crashes de infraestrutura.

**Risco:** Degradação progressiva de performance. Estados inconsistentes após restart.

**Invariantes que resolvem:** [Invariante 2 — Delegação de Falhas](#invariante-2-delegação-de-falhas) e [Invariante 3 — Transacionalidade de Passos](#invariante-3-transacionalidade-de-passos)

### 3.3 Descontrole de Efeitos Colaterais

**Problema:** Ausência de mecanismo de idempotência nas Tools. O reprocessamento (replay) de um flow após falha transiente pode duplicar operações no mundo externo (requisições de compra, alterações em banco de dados, envio de emails).

**Risco:** Desastre em produção. A promessa de "Execução Durável" é vazia sem idempotência.

**Invariante que resolve:** [Invariante 4 — Efeitos Colaterais Controlados](#invariante-4-efeitos-colaterais-controlados)

---

## 4. As 8 Invariantes Arquiteturais

### Invariante 1: Estado Isolado e Imutabilidade Estrita

> **Zero Shared Mutable State**

**A Regra:** Nenhum componente, runtime ou agente pode compartilhar estado mutável em memória. O design do `RunContext.execution_state` como dicionário mutável deve ser abolido em favor de estruturas frozen.

**Justificativa Técnica:** Em sistemas concorrentes, estado compartilhado gera race conditions e inviabiliza o paralelismo seguro (fan-out dinâmico). Todo estado deve ser local ao "Ator" (Runtime/Agente). Comunicação ocorre estritamente via troca de mensagens assíncronas imutáveis (cópias ou Pydantic frozen).

**Implementação:**
```python
# ANTES (violação)
class RunContext(BaseModel):
    execution_state: dict[str, Any] = {}  # mutável, compartilhado

# DEPOIS (invariante)
class RunContext(BaseModel):
    model_config = ConfigDict(frozen=True)
    execution_state: FrozenDict[str, Any] = FrozenDict()

    def with_state(self, **updates) -> "RunContext":
        """Retorna NOVA instância com estado atualizado."""
        new_state = {**self.execution_state, **updates}
        return self.model_copy(update={"execution_state": FrozenDict(new_state)})
```

**Validação CI/CD:**
- Lint rule: proibir `dict[str, Any]` mutável em qualquer contrato do core
- Test: execução paralela de 100 agentes não deve produzir race conditions

---

### Invariante 2: Delegação de Falhas

> **Supervision & "Let it Crash"**

**A Regra:** Um agente ou passo computacional nunca deve tentar recuperar suas próprias falhas semânticas críticas ou crashes de infraestrutura. A falha deve causar interrupção isolada do nó e propagação imediata para o Supervisor na árvore hierárquica.

**Justificativa Técnica:** Evita processos "zumbis". O supervisor possui contexto global para decidir a estratégia: restart, resume, escalate ou stop. Resiliência estilo Erlang/OTP sem poluir código de negócio com `try/catch` genéricos.

**Implementação:**
```python
class StepSupervision(BaseModel):
    """Estratégia de supervisão por step — inspirado em Akka/OTP."""
    model_config = ConfigDict(frozen=True)

    on_error: Literal["restart", "resume", "stop", "escalate"] = "stop"
    max_restarts: int = 0
    restart_window_seconds: float | None = None
    timeout_seconds: float | None = None
    circuit_breaker_threshold: int | None = None
```

**Hierarquia de supervisão:**
```
PipelineRunner (executor de Flows, Supervisor raiz)
└── FlowSupervisor (por flow)
    ├── StepSupervisor (por step)
    │   └── AgentRuntime (leaf — "let it crash")
    └── StepSupervisor
        └── AgentRuntime
```

**Validação CI/CD:**
- Test: agente que entra em loop de alucinação deve ser terminado pelo supervisor em < timeout
- Test: crash de um agente não deve corromper estado de outros agentes no mesmo flow

---

### Invariante 3: Transacionalidade de Passos

> **Checkpoint Atômico**

**A Regra:** A transição de estado de qualquer "processo" (Flow) só é considerada válida e observável pelo sistema se o novo estado, os eventos gerados e o ponteiro de execução forem confirmados atomicamente em um `CheckpointStore`.

**Justificativa Técnica:** Fundação da Execução Durável. Se o processo falhar abruptamente no meio de um passo, na retomada (resume) o sistema carrega o último checkpoint atômico e reexecuta a transição sem "meios-estados" corrompidos.

**Implementação:**
```python
class CheckpointManager:
    """Commit atômico de checkpoint — estado + eventos + cursor."""

    async def commit(
        self,
        run_id: str,
        step_cursor: str,
        state: FrozenDict,
        events: list[ExecutionEvent],
        effects: list[EffectRecord],
    ) -> str:
        """Persiste tudo atomicamente. Retorna checkpoint_id."""
        async with self.store.transaction() as tx:
            checkpoint_id = generate_checkpoint_id()
            await tx.save_state(run_id, checkpoint_id, state)
            await tx.save_events(run_id, checkpoint_id, events)
            await tx.save_effects(run_id, checkpoint_id, effects)
            await tx.save_cursor(run_id, step_cursor)
            return checkpoint_id
```

**Validação CI/CD:**
- Test: kill -9 no meio de um step → resume carrega último checkpoint válido
- Test: nenhum evento é observável por consumers antes do commit atômico

> **Status de implementação (2026-03):** `CheckpointManager` está implementado em `core/runtime/checkpoint_manager.py` via composição (`atomic_transition()` coordena CheckpointStore + EventStore sequencialmente). A atomicidade é lógica, não ACID — um crash entre `save_checkpoint` e `append_events` pode resultar em estado inconsistente. Uma implementação com transação SQLAlchemy é trabalho futuro.

---

### Invariante 4: Efeitos Colaterais Controlados

> **Idempotência Estrita**

**A Regra:** Toda interação com o mundo externo (chamadas de API, execução de scripts, escrita em banco de dados) realizada por Tool ou Agent deve ser governada por uma `EffectPolicy` e possuir uma `idempotency_key` registrada em um Effect Journal atrelado ao checkpoint.

**Justificativa Técnica:** Em um sistema replayable (time-travel, forks), um flow pode ser reexecutado múltiplas vezes. Se uma transferência financeira for repetida, a chave de idempotência garante que a API de destino rejeite a duplicação.

**Implementação:**
```python
class EffectPolicy(BaseModel):
    """Política de controle de efeitos colaterais."""
    model_config = ConfigDict(frozen=True)

    idempotency_key: str  # hash determinístico de (step_id + input + run_id)
    effect_type: Literal["api_call", "shell_exec", "db_write", "file_write", "message_send"]
    compensable: bool = False  # pode ser revertido?
    compensation_handler: str | None = None

class EffectJournal:
    """Registro de efeitos colaterais executados."""

    async def record_intent(self, effect: EffectPolicy, checkpoint_id: str) -> None:
        """Registra a INTENÇÃO de executar o efeito (antes da execução)."""
        ...

    async def record_completion(self, idempotency_key: str, result: Any) -> None:
        """Registra a CONCLUSÃO do efeito (após execução bem-sucedida)."""
        ...

    async def was_executed(self, idempotency_key: str) -> bool:
        """Verifica se o efeito já foi executado (para replay)."""
        ...
```

**Validação CI/CD:**
- Test: replay de flow com tool calls → nenhuma tool é executada duas vezes
- Test: tool sem idempotency_key → rejeição em tempo de composição

---

### Invariante 5: A Verdade Baseada em Eventos

> **Event Sourcing**

**A Regra:** O estado atual de qualquer flow longo não é o que está armazenado em uma tabela CRUD, mas sim a dobra temporal determinística (left-fold) de todos os eventos canônicos emitidos no `EventSink` desde o início.

**Justificativa Técnica:** Garantir emissão de eventos para toda transição com `correlation_id` e `timestamp` permite:
- Bifurcação (fork) do estado para simulações (dry-runs)
- Migração de schemas (Schema Evolution)
- Auditoria criptográfica perfeita
- Comportamento de journaling de sistema de arquivos

**Implementação:**
```python
class EventSourcedState:
    """Reconstrói estado a partir de eventos."""

    @staticmethod
    def fold(events: list[ExecutionEvent]) -> dict[str, Any]:
        """Left-fold determinístico: events → state."""
        state = {}
        for event in sorted(events, key=lambda e: e.timestamp):
            state = EventSourcedState._apply(state, event)
        return FrozenDict(state)

    @staticmethod
    def fork(events: list[ExecutionEvent], from_checkpoint: str) -> list[ExecutionEvent]:
        """Cria branch de eventos a partir de um checkpoint."""
        ...
```

**Validação CI/CD:**
- Test: `fold(events_from_store) == current_state` para qualquer flow
- Test: fork de checkpoint N + novos eventos produz estado diferente do original

> **Status de implementação (2026-03):** O sistema emite 72 event types canónicos via EventStore (InMemory + SQLAlchemy). `EventSourcedState.fold()` e `fork()` estão implementados. O event sourcing é operacional com replay determinístico e bifurcação de estado.

---

### Invariante 6: Rejeição do Texto Livre

> **Contratos Fortemente Tipados**

**A Regra:** A passagem de parâmetros estruturais entre Kernel, Runtimes e Agentes deve ser estritamente tipada. O uso de dicionários genéricos soltos ou `**kwargs` como escape hatch é terminantemente proibido.

**Justificativa Técnica:** Num ambiente onde a saída do LLM é inerentemente probabilística e imprevisível, a infraestrutura de orquestração deve ser de ferro. Validação estrutural via Protocols e Pydantic garante que erros de contrato sejam capturados em tempo de compilação ou validação de borda.

**Implementação existente (manter e expandir):**
```python
# Isto já existe e funciona — MANTER
class AgentSpec(BaseModel):
    model_config = ConfigDict(frozen=True)
    # 20+ campos tipados, nenhum dict genérico

class RouterDecision(BaseModel):
    model_config = ConfigDict(frozen=True)
    next_agent: str | None = None
    terminate: bool = False
    stagnation_risk: float = Field(ge=0.0, le=1.0, default=0.0)
    # @model_validator enforce: terminate XOR next_agent

# Isto deve ser BANIDO
def process(self, **kwargs) -> Any:  # PROIBIDO
    state = kwargs.get("state", {})  # PROIBIDO
```

**Validação CI/CD:**
- Lint rule (ruff custom): proibir `**kwargs` em interfaces do core
- Lint rule: proibir `dict[str, Any]` como tipo de retorno em Protocols
- MyPy strict: `check_untyped_defs = true`

---

### Invariante 7: Separação Prompt↔Runtime

> **O AgentRuntime é compositor, não instrutor**

**A Regra:** O AgentRuntime NUNCA dita ao agente o formato de resposta ou constrói prompts de coordenação. Prompts de coordenação (contribute, review, consolidate) são responsabilidade do Coordination Runtime. O AgentRuntime enriquece com contexto local (memória, tools, system prompt) e delega ao backend.

**Justificativa Técnica:** O AgentRuntime deve ser agnóstico ao tipo de coordenação. O mesmo AgentRuntime pode participar em deliberações, workflows ou loops agentic sem modificação. A separação prompt/runtime permite que diferentes estratégias de interação coexistam sem alterar o compositor.

**Implementação:**
```python
# ANTES (violação)
class AgentRuntime:
    async def contribute(self, topic: str) -> Contribution:
        prompt = f"Contribute to: {topic}. Respond with JSON: ..."  # PROIBIDO

# DEPOIS (invariante)
class AgentRuntime:
    async def contribute(self, topic: str) -> Contribution:
        prompt = await resolve_prompt(  # Cascade: Strategy -> YAML -> default
            action="contribute",
            context={"topic": topic},
            strategy=self._interaction_strategy,
            flow_prompts=self._flow_prompts,
            default_prompt=build_default_contribute_prompt(topic=topic),
        )
        return await self.execute(prompt)  # compositor puro
```

**Validação CI/CD:**
- Grep: `AgentRuntime` não contém strings de prompt hardcoded (exceto em `default_prompts.py`)
- Test: AgentRuntime com `InteractionStrategy` customizada funciona sem alteração do core

---

### Invariante 8: Formato pertence ao Flow

> **response_format é propriedade do Flow config**

**A Regra:** O `response_format` é propriedade do Flow config, não do Agent. O mesmo agente pode participar em flows que esperam JSON e flows que esperam texto livre. O Coordination Runtime adapta o parsing conforme o `response_format` do flow.

**Justificativa Técnica:** Acoplar o formato de resposta ao agente limita a reutilização. Um agente que funciona com JSON num flow de deliberação pode precisar de free text num flow de brainstorming. A separação permite máxima composabilidade.

**Implementação:**
```yaml
# YAML — formato definido no Flow, não no Agent
flows:
  review:
    mode: deliberation
    response_format: free_text  # propriedade do flow
    prompts:
      contribute: "Review {topic} from your perspective."
```

**Validação CI/CD:**
- Test: mesmo agente participa em flow JSON e flow free_text sem configuração adicional
- Lint: `response_format` não existe em nenhum AgentSpec ou contrato de agente

---

## 5. Veredito de Eficácia

**Nota de Resiliência Arquitetural: 9.5 / 10**

A adoção formal destas 8 invariantes elimina as classes mais complexas e destrutivas de bugs em sistemas distribuídos:
- Race conditions → Invariante 1 (imutabilidade)
- Processos zumbis → Invariante 2 (supervisão)
- Estados corrompidos → Invariante 3 (checkpoint atômico)
- Side-effects duplicados → Invariante 4 (idempotência)
- Estado inconsistente → Invariante 5 (event sourcing)
- Erros de contrato em runtime → Invariante 6 (tipagem estrita)
- Prompt leaking no compositor → Invariante 7 (separação prompt/runtime)
- Formato acoplado ao agente → Invariante 8 (formato no flow)

A arquitetura deixa de ser uma "biblioteca de orquestração de LLMs" para se tornar uma **infraestrutura de computação autônoma, confiável e previsível**.

**A margem deduzida (0.5):** O pedágio na Developer Experience (DX). Tipagem estrita e imutabilidade absoluta aumentam a curva de aprendizado. Isso exige esforço pragmático para construir abstrações de alto nível (Quickstart mode, Fase 1 do roadmap) que escondam a maquinaria durante prototipagem.

---

## 6. Plano de Ação Tático

Para materializar estas invariantes no codebase, as 3 ações prioritárias:

### Ação 1: Imutabilidade no Core (Refatoração Crítica)

> Resolve: Invariante 1

Refatorar `RunContext` e todas as passagens de parâmetros entre Runtimes para estruturas frozen. Eliminar `execution_state` como dicionário mutável. Adotar pattern `with_state()` que retorna nova instância.

**Alinha com:** Roadmap Fase 2 — RunStateMachine (item #5)

> **✅ CONCLUÍDA (PR #32, 2026-03).** `RunContext` e `ExecutionEvent` são frozen. `FrozenState` substitui `dict` mutável. Pattern `model_copy()` para atualizações.

### Ação 2: EffectPolicy e Effect Journal

> Resolve: Invariante 4

Implementar interceptor que atua antes de qualquer tool call. Gera hashes determinísticos baseados em (step_id + input + run_id) como `idempotency_key`. Registra intenção de execução (journaling) atomicamente antes do disparo real.

**Alinha com:** Roadmap Fase 3 — EffectPolicy + idempotency_key + effect journal (item #11)

> **✅ CONCLUÍDA (PRs #33-34, 2026-03).** `EffectRecord`, `EffectJournal` (InMemory + SQLAlchemy), `EffectInterceptor` com idempotency key (SHA-256 sem attempt). `EffectPolicy` como frozen model.

### Ação 3: Árvores de Supervisão (Supervisor Trees)

> Resolve: Invariante 2

Substituir tratamento de erros linear no `PipelineRunner` por hierarquia de `Supervisor`. Classes encapsulam lógica de decisão per-step (restart, resume, stop, escalate) e políticas de circuit breaker.

**Alinha com:** Roadmap Fase 2 — RunStateMachine (item #5) + Research W3 (Akka supervision patterns)

> **✅ CONCLUÍDA (PRs #35-39, 2026-03).** `StepSupervisor` + `FlowSupervisor` com hierarquia OTP. Todos os 3 runtimes supervisionados. `RunStateMachine` com transições formais. `CircuitBreakerRegistry` e `HeartbeatToken` implementados.

---

## 7. Relação com os Documentos do Sistema

| Invariante | Roadmap Item | Doc de Referência |
|---|---|---|
| 1. Imutabilidade | #5 RunStateMachine | [05-invariantes.md](05-invariantes.md) |
| 2. Supervisão | #5 RunStateMachine | [07-agent-anatomy.md](07-agent-anatomy.md) §6 |
| 3. Checkpoint Atômico | #6 CheckpointManager | [plano-langgraph.md](../plano-langgraph.md) §Fase 1 |
| 4. Idempotência | #11 EffectPolicy | [competitive-landscape.md](../../competitive-landscape.md) §Fase 3 |
| 5. Event Sourcing | Existente (expandir) | [05-invariantes.md](05-invariantes.md) §Taxonomia |
| 6. Tipagem Estrita | Existente (manter) | [CLAUDE.md](../../../CLAUDE.md) §Invariantes |
| 7. Separação Prompt↔Runtime | AgentRuntime Agnostic | [spec agnostic](../../superpowers/specs/2026-03-21-agentruntime-agnostic-design.md) |
| 8. Formato no Flow | AgentRuntime Agnostic | [spec agnostic](../../superpowers/specs/2026-03-21-agentruntime-agnostic-design.md) |

---

*Documento de Auditoria e Definição Arquitetural — MiniAutoGen 2025-06-18*
*Baseado em análise do codebase, [architecture-retrospective.md](../../architecture-retrospective.md), pesquisa de runtime patterns (Akka/OTP, Temporal), e [competitive-landscape.md](../../competitive-landscape.md)*
