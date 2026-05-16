# Tarefas: Per-Agent Timeouts

| Campo      | Valor       |
|------------|-------------|
| Spec ID    | 013         |
| Data       | 2026-05-16  |
| Total      | 10 tarefas  |

---

## Legenda

- **Status:** TODO / IN_PROGRESS / DONE / BLOCKED
- **P:** Paralelizável (sim/não)
- **Deps:** IDs de tarefas das quais esta depende

---

## Tarefas

### T001 — Testes falhando: validação `FlowConfig`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Criar `tests/cli/test_flow_config_timeouts.py`. Cenários:
1. `test_no_timeout_fields_is_valid`: YAML sem `agent_timeouts`/`round_timeouts` valida.
2. `test_agent_timeouts_dict_accepted`: dict de `{"engenheiro": 60.0}` é aceito.
3. `test_timeout_below_one_second_rejected`: `60.0` ok, `0.5` levanta `ValidationError`.
4. `test_on_timeout_action_invalid_rejected`: `"foo"` levanta erro; `"continue"`, `"abort"` aceitos.
5. `test_unknown_agent_id_in_timeouts_warns`: chave de agente desconhecido emite deprecation/warning (não erro fatal).

**Critério de conclusão:**
- [ ] 5 testes presentes; todos falham (campos novos ausentes em `FlowConfig`)

---

### T002 — Testes falhando: `resolve_timeout`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Criar `tests/contracts/test_timeout_resolution.py`. Cobrir a matriz:
1. agente preenchido → fonte `"agent"`
2. agente ausente, round preenchido → fonte `"round"`
3. agente e round ausentes, flow preenchido → fonte `"flow"`
4. todos ausentes → fonte `"engine"`
5. agente preenchido **e** round preenchido → agente vence (precedência)

**Critério de conclusão:**
- [ ] 5 testes presentes; falham por `ImportError` (módulo ausente)

---

### T003 — Testes falhando: `TimeoutPolicy`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Criar `tests/policies/test_timeout_policy.py`. Use pytest-anyio. Cenários:
1. `test_timeout_emits_event_and_continues`: dentro do `scope_for_turn` faz `anyio.sleep(2)` com timeout 0.1; verifica que evento `agent_turn_timed_out` foi emitido e a exceção foi suprimida (action=continue).
2. `test_abort_action_propagates_timeout_error`: idem, com `on_timeout_action="abort"`; verifica que `TimeoutError` é re-raised.
3. `test_nested_flow_timeout_overrides_agent_timeout`: flow_timeout=0.1, agent=10; verifica que o flow vence (escopo externo cancela primeiro).
4. `test_emits_payload_with_source_agent`: agente tem timeout próprio; evento carrega `source="agent"`.

**Critério de conclusão:**
- [ ] 4 testes presentes; todos falham

---

### T004 — Adicionar evento canônico

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Em `miniautogen/core/events/types.py`, adicionar `AGENT_TURN_TIMED_OUT = "agent_turn_timed_out"`. Atualizar listas de validação se houver.

**Critério de conclusão:**
- [ ] `EventType.AGENT_TURN_TIMED_OUT` existe
- [ ] Smoke test verificando que `ExecutionEvent(type="agent_turn_timed_out", ...)` é válido

---

### T005 — Implementar `resolve_timeout`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T002  |

**Descrição:** Criar `miniautogen/core/contracts/timeout_resolution.py` com `ResolvedTimeout` (frozen dataclass) e `resolve_timeout(...)` conforme plano.

**Critério de conclusão:**
- [ ] `tests/contracts/test_timeout_resolution.py` → 5/5 verdes
- [ ] `mypy --strict` passa

---

### T006 — Implementar `TimeoutPolicy`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T003, T004, T005 |

**Descrição:** Criar (ou estender) `miniautogen/policies/timeout_policy.py`. Implementar `scope_for_turn` como `asynccontextmanager` que usa `anyio.fail_after`, emite o evento, e respeita `on_timeout_action`.

**Critério de conclusão:**
- [ ] `tests/policies/test_timeout_policy.py` → 4/4 verdes
- [ ] Nenhum `time.sleep` ou wrapper síncrono
- [ ] Logs estruturados (`structlog`) em vez de `print`

---

### T007 — Estender `FlowConfig`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T001  |

**Descrição:** Em `miniautogen/cli/config.py::FlowConfig`, adicionar:
- `agent_timeouts: dict[str, float] = Field(default_factory=dict)`
- `round_timeouts: dict[str, float] = Field(default_factory=dict)`
- `on_timeout_action: Literal["continue", "abort"] = "continue"`
- `@model_validator(mode="after")` que rejeita valores `< 1.0`.

**Critério de conclusão:**
- [ ] `tests/cli/test_flow_config_timeouts.py` → 5/5 verdes
- [ ] YAMLs existentes em `examples/` continuam carregando

---

### T008 — Wire da policy no Runtime

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T006, T007 |

**Descrição:** Identificar os pontos onde turnos de agentes são executados:
1. **Coordination Runtime** (deliberação): envolver `agent.run(turn_input)` em `async with timeout_policy.scope_for_turn(...)`.
2. **Workflow Runtime** (sequencial): idem, com `round_name=None`.

Construir `TimeoutPolicy` a partir do `FlowConfig` + `EngineConfig` em `cli/services/run_pipeline.py` e injetar no `PipelineRunner`.

Quando `on_timeout_action="continue"`, o coordenador trata a contribuição como `incomplete=True` (campo a adicionar em `Contribution` se ausente).

**Critério de conclusão:**
- [ ] Testes de integração com deliberação 2-agentes onde o 2º agente tem timeout 0.5 + sleep 1 → primeiro agente sobrevive, segundo é marcado incompleto
- [ ] `abort` em workflow encerra com exit 124 (interage com Item 2)

---

### T009 — Exemplo YAML + regressão

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | T008  |

**Descrição:** Criar `examples/config/per-agent-timeouts.yaml` com o YAML completo (3 níveis: agent / round / flow). Garantir que o exemplo é carregável e o `miniautogen flow show especificacao` exibe os timeouts.

Rodar `pytest` completo para verificar regressões.

**Critério de conclusão:**
- [ ] `miniautogen flow show especificacao` (com este YAML) imprime os timeouts
- [ ] `pytest` 100%
- [ ] `ruff`, `mypy` limpos

---

### T010 — Documentação

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | T009  |

**Descrição:** Em `docs/getting-started.md`, adicionar seção "Configurando SLAs por agente" com:
1. Snippet YAML do exemplo.
2. Tabela de precedência (cópia do plano).
3. Distinção `continue` vs `abort` com casos de uso.
4. Link para o spec `per-agent-timeouts.md` e para Item 2 (cancel checkpoint) como leitura complementar.

**Critério de conclusão:**
- [ ] Seção renderiza no GitHub
- [ ] Tabela de precedência clara
- [ ] PR review aprova

---

## Grafo de Dependências

```
T001 ┐
T002 ┤
T003 ┤        ┌─> T005 ─┐
T004 ┤        │         ├─> T006 ─┐
     └────────┘         │         ├─> T008 ─> T009 ─> T010
              T007 ─────┘─────────┘
```

---

## Resumo

| Paralelizáveis | Sequenciais | Bloqueadas | Total |
|----------------|-------------|------------|-------|
| 5              | 5           | 0          | 10    |
