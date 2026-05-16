# Plano Técnico: Per-Agent Timeouts

| Campo         | Valor       |
|---------------|-------------|
| Spec ID       | 013         |
| Data          | 2026-05-16  |
| Complexidade  | Medium      |

---

## Arquitetura Proposta

### Módulos Afetados

| Módulo / Caminho                                              | Tipo de Alteração      |
|---------------------------------------------------------------|------------------------|
| `miniautogen/cli/config.py`                                   | Alterado (FlowConfig)  |
| `miniautogen/core/events/types.py`                            | Alterado (1 evento novo) |
| `miniautogen/policies/timeout_policy.py`                      | Novo (ou alterado)     |
| `miniautogen/core/runtime/pipeline_runner.py`                 | Alterado (wire policy) |
| `miniautogen/core/contracts/timeout_resolution.py`            | Novo (helper)          |
| `tests/policies/test_timeout_policy.py`                       | Novo                   |
| `tests/cli/test_flow_config_timeouts.py`                      | Novo                   |
| `examples/config/per-agent-timeouts.yaml`                     | Novo                   |
| `docs/getting-started.md`                                     | Alterado (seção SLA)   |

### Diagrama de precedência

```
                  ┌─ agent_timeouts[agent_id]?   sim ─> use it
                  │
resolve_timeout ──┼─ round_timeouts[round_name]? sim ─> use it
                  │
                  ├─ flow_timeout?               sim ─> use it
                  │
                  └─ engine.timeout_seconds            (sempre presente, default 120s)
```

---

## Contratos e Interfaces

### Schema YAML estendido

```yaml
# miniautogen.yaml
flows:
  especificacao:
    mode: deliberation
    participants: [advogado, paralegal, engenheiro]
    leader: advogado
    max_rounds: 5

    # NOVO — opcionais, retrocompatível
    agent_timeouts:
      advogado: 300.0
      engenheiro: 60.0
      paralegal: 120.0
    round_timeouts:
      contribute: 60.0
      review: 90.0
      synthesize: 180.0
    on_timeout_action: continue   # continue | abort
```

### `FlowConfig` (Pydantic)

```python
# miniautogen/cli/config.py
from typing import Literal

class FlowConfig(BaseModel):
    # ... campos existentes
    agent_timeouts: dict[str, float] = Field(default_factory=dict)
    round_timeouts: dict[str, float] = Field(default_factory=dict)
    on_timeout_action: Literal["continue", "abort"] = "continue"

    @model_validator(mode="after")
    def validate_timeout_values(self) -> "FlowConfig":
        for k, v in self.agent_timeouts.items():
            if v < 1.0:
                raise ValueError(f"agent_timeouts[{k}] must be >= 1.0 (got {v})")
        for k, v in self.round_timeouts.items():
            if v < 1.0:
                raise ValueError(f"round_timeouts[{k}] must be >= 1.0 (got {v})")
        return self
```

### Helper de resolução

```python
# miniautogen/core/contracts/timeout_resolution.py
from dataclasses import dataclass
from typing import Literal

TimeoutSource = Literal["agent", "round", "flow", "engine"]


@dataclass(frozen=True)
class ResolvedTimeout:
    seconds: float
    source: TimeoutSource


def resolve_timeout(
    *,
    agent_id: str,
    round_name: str | None,
    agent_timeouts: dict[str, float],
    round_timeouts: dict[str, float],
    flow_timeout: float | None,
    engine_timeout: float,
) -> ResolvedTimeout:
    if agent_id in agent_timeouts:
        return ResolvedTimeout(agent_timeouts[agent_id], "agent")
    if round_name and round_name in round_timeouts:
        return ResolvedTimeout(round_timeouts[round_name], "round")
    if flow_timeout is not None:
        return ResolvedTimeout(flow_timeout, "flow")
    return ResolvedTimeout(engine_timeout, "engine")
```

### Novo evento

```python
# miniautogen/core/events/types.py
class EventType(str, Enum):
    ...
    AGENT_TURN_TIMED_OUT = "agent_turn_timed_out"
```

Payload esperado:

```python
{
    "agent_id": "engenheiro",
    "round_name": "contribute",
    "applied_timeout": 60.0,
    "source": "agent",
}
```

### `TimeoutPolicy`

```python
# miniautogen/policies/timeout_policy.py
from __future__ import annotations

import anyio
import structlog
from contextlib import asynccontextmanager
from typing import AsyncIterator

from miniautogen.core.contracts.timeout_resolution import resolve_timeout, ResolvedTimeout

logger = structlog.get_logger()


class TimeoutPolicy:
    """Lateral policy that wraps each agent turn in a fail_after scope.

    Subscribes to agent_turn_started; opens a CancelScope; on expiration,
    cancels the turn and emits agent_turn_timed_out.
    """

    def __init__(
        self,
        *,
        agent_timeouts: dict[str, float],
        round_timeouts: dict[str, float],
        flow_timeout: float | None,
        engine_timeout: float,
        on_timeout_action: str = "continue",
    ) -> None:
        self._agent_timeouts = agent_timeouts
        self._round_timeouts = round_timeouts
        self._flow_timeout = flow_timeout
        self._engine_timeout = engine_timeout
        self._on_timeout_action = on_timeout_action

    @asynccontextmanager
    async def scope_for_turn(
        self,
        *,
        agent_id: str,
        round_name: str | None,
        emit,
    ) -> AsyncIterator[ResolvedTimeout]:
        resolved = resolve_timeout(
            agent_id=agent_id,
            round_name=round_name,
            agent_timeouts=self._agent_timeouts,
            round_timeouts=self._round_timeouts,
            flow_timeout=self._flow_timeout,
            engine_timeout=self._engine_timeout,
        )
        try:
            with anyio.fail_after(resolved.seconds):
                yield resolved
        except TimeoutError:
            await emit(
                "agent_turn_timed_out",
                agent_id=agent_id,
                round_name=round_name,
                applied_timeout=resolved.seconds,
                source=resolved.source,
            )
            if self._on_timeout_action == "abort":
                raise
            # continue: o coordenador trata como contribuição incompleta
            logger.warning(
                "timeout_policy.continue_after_timeout",
                agent_id=agent_id,
                round_name=round_name,
                applied=resolved.seconds,
            )
```

### Integração com Runner / Coordenação

Para deliberação (Coordination Runtime existente), o ponto de turn é envolvido pela policy:

```python
async with timeout_policy.scope_for_turn(
    agent_id=agent.id,
    round_name=current_role,
    emit=self._emit,
) as resolved:
    contribution = await agent.run(turn_input)
# se TimeoutError suprimido (continue), 'contribution' não foi atribuída
# o coordenador trata via 'has_contribution' flag
```

Para fluxos workflow (sequenciais), idem por step, com `round_name=None`.

---

## Riscos e Mitigações

| Risco                                                                          | Impacto | Mitigação                                                              |
|--------------------------------------------------------------------------------|---------|------------------------------------------------------------------------|
| Nome de round nem sempre disponível (workflow puro)                            | Médio   | `round_name` é `Optional[str]`; helper aceita `None`                   |
| Validar `agent_timeouts` contra agentes inexistentes                            | Médio   | Pydantic root validator no `WorkspaceConfig` que cruza com `agents/`   |
| Continue após timeout deixa estado inconsistente                                | Alto    | Default `on_timeout_action="continue"` documentado; tests do flow      |
| Aninhamento `fail_after` (per-turn) dentro de `fail_after` (flow) confunde      | Médio   | Documentar precedência; testar caso `flow=5s, agent=10s` → flow vence  |
| Item 2 ainda não pronto — save shielded ausente                                 | Baixo   | `agent_turn_timed_out` é emitido independentemente; save é melhoria   |

---

## Estimativa de Complexidade

| Aspecto              | Estimativa |
|----------------------|------------|
| Ficheiros novos      | 4 (helper + policy + 2 testes) |
| Ficheiros alterados  | 4          |
| Testes novos         | ~10        |
| Esforço estimado     | Medium (2-3 dias) |

---

## Sequência de Implementação

1. **Test-first:** `tests/cli/test_flow_config_timeouts.py` — 4 testes de validação Pydantic (campos opcionais; rejeitar `< 1.0`; YAMLs existentes continuam válidos; cruzar com `agent_specs`).
2. **Test-first:** `tests/contracts/test_timeout_resolution.py` — 5 testes da matriz de precedência.
3. **Test-first:** `tests/policies/test_timeout_policy.py` — 4 testes: timeout dispara; ação `continue` segue; ação `abort` propaga; nested fail_after (flow vs agent).
4. Adicionar `AGENT_TURN_TIMED_OUT` em `EventType`.
5. Implementar `resolve_timeout` em `core/contracts/timeout_resolution.py`.
6. Implementar `TimeoutPolicy` em `policies/timeout_policy.py`.
7. Estender `FlowConfig` em `cli/config.py`.
8. Wire da policy no Coordination Runtime (deliberação) e no Workflow Runtime.
9. Rodar todos os testes → verde.
10. Criar `examples/config/per-agent-timeouts.yaml` com YAML completo (3 níveis).
11. Doc em `docs/getting-started.md`, seção "Configurando SLAs por agente".

---

## Notas

- **Why context manager em vez de decorator?** O escopo precisa receber `emit` (callable de evento) e devolver `ResolvedTimeout` para que o coordenador saiba qual nível disparou. Context manager é o idioma canônico AnyIO.
- **Interação com cancel hierárquico (Item 2):** quando `on_timeout_action=abort`, a exceção propaga até o root cancel scope do Runner, dispara o save shielded e termina com exit code 124.
- **Coordenação com Item 3:** o evento `agent_turn_timed_out` é capturado pelo `RichLiveEventSink._update_from_event` e exibido como `_action="Timeout (X: 60s)"`.
- **Per-round limitations:** "round" em deliberation é `contribute|review|synthesize` (nomes do contrato). Adicionar enum/literal se quisermos restringir; por ora aceitar string arbitrária.
