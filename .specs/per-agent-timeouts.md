# Spec: Per-Agent Timeouts — SLA Granular no YAML

| Campo      | Valor                                          |
|------------|------------------------------------------------|
| Data       | 2026-05-16                                     |
| Autor      | DX Sprint 3                                    |
| Status     | Rascunho                                       |
| Spec ID    | 013                                            |
| Origem     | `docs/plans/AVALIACAO-MINIAUTOGEN.md` §7.7     |

---

## Contrato de Prompt (G/C/FC)

### 🎯 Goal

Permitir declarar timeouts em três níveis de granularidade no `miniautogen.yaml`:

1. **Por agente** (ex: o `engenheiro` tem 120s, o `advogado` tem 300s).
2. **Por papel/round na deliberação** (ex: `contribute=60s`, `review=90s`, `synthesize=180s`).
3. **Global do flow** (já existe via CLI `--timeout`).

A precedência é `agente > round > flow > engine`. Quando um timeout granular dispara, o sistema emite um evento canônico (`agent_turn_timed_out`), salva checkpoint (interage com Item 2) e continua o flow se a policy de deliberação permitir — caso contrário, encerra o flow inteiro.

### 🚧 Constraint

1. **Schema retrocompatível:** YAMLs existentes sem campos novos continuam válidos. Os campos são todos opcionais (`Optional[float]` com `default=None`).
2. **AnyIO canônico:** os timeouts são implementados via `anyio.fail_after` em escopos aninhados; nada de `signal.alarm` ou wrappers síncronos.
3. **Policies event-driven:** uma `TimeoutPolicy` (nova) observa o evento `agent_turn_started`, abre um cancel scope, e na expiração emite `agent_turn_timed_out`. O Runner não conhece o detalhe — apenas reage aos eventos canônicos.
4. **Sem hardcoded prompts:** o Runtime continua sem qualquer instrução textual. Timeout é puramente temporal.

### 🛑 Failure Condition

- Um `miniautogen.yaml` existente (sem campos novos) falha validation.
- Timeout por agente expira mas o evento `agent_turn_timed_out` não é emitido.
- Timeout global do flow é mais curto que timeout por agente e **não** vence (precedência invertida).
- O turno seguinte do flow não recebe sinal de que o agente anterior timed-out.
- Em deliberação, o líder não consegue distinguir contribuição completa de contribuição interrompida por timeout.
- Não há teste que verifique a precedência completa (agente > round > flow).

---

## User Stories

- Como **operador SLA**, quero que o `Engenheiro de Dados` tenha 60s para responder e o `Advogado` tenha 300s, porque a natureza dos prompts é radicalmente diferente — e quero declarar isso em YAML, não em código.
- Como **mantenedor de pipeline**, quero que uma fase `review` em deliberação tenha o dobro do tempo de `contribute`, porque revisar exige ler todas as contribuições anteriores.
- Como **engenheiro debugando**, quero ver no evento `agent_turn_timed_out` qual nível de timeout disparou (agente, round, flow), para entender onde ajustar.

---

## Critérios de Aceitação

- [ ] `FlowConfig` ganha o campo opcional `agent_timeouts: dict[str, float] = {}` (chave = `agent_id`, valor = segundos).
- [ ] `FlowConfig` ganha o campo opcional `round_timeouts: dict[str, float] = {}` (chave = nome do round/role como `contribute`, `review`, `synthesize`, valor = segundos).
- [ ] `EngineConfig.timeout_seconds` (já existe) continua sendo o fallback final.
- [ ] Função `resolve_timeout(agent_id, round_name, flow_timeout, engine_timeout) → float` implementa a precedência: agente > round > flow > engine.
- [ ] Novo evento canônico `AGENT_TURN_TIMED_OUT` em `EventType`.
- [ ] Nova `TimeoutPolicy(ExecutionPolicy)` ou extensão de policy existente, que abre `anyio.fail_after(resolved)` por turno e emite o evento na expiração.
- [ ] O payload do evento carrega: `agent_id`, `round_name`, `applied_timeout`, `source` ∈ {`"agent"`, `"round"`, `"flow"`, `"engine"`}.
- [ ] Quando o timeout expira em deliberação, o Coordination Runtime registra a contribuição como `incomplete=True` e continua (ou aborta segundo `on_timeout_action: continue|abort` configurável; default `continue`).
- [ ] Quando o timeout expira em workflow (sequencial), o flow encerra com `terminal_reason="agent_timeout"` (interage com Item 2 para salvar checkpoint).
- [ ] Validação YAML: timeout < 1s é rejeitado (`min 1.0`).
- [ ] Pelo menos 6 testes cobrindo a tabela de precedência + ação `continue`/`abort`.
- [ ] Doc/exemplo em `docs/getting-started.md` com YAML de 3-níveis.

---

## Invariantes Afetadas

- [ ] **Isolamento de Adapters** — mudança puramente no `core` + `cli/config`; sem toque em adapters.
- [x] **Microkernel / PipelineRunner** — runner respeita o cancel scope aninhado da policy; sem mudança estrutural.
- [x] **Assincronismo Canônico (AnyIO)** — `fail_after` é a ferramenta canônica; aninhamento explícito documentado.
- [x] **Policies Event-Driven** — a `TimeoutPolicy` observa `agent_turn_started`/`agent_turn_finished`, reage com cancel scope.

---

## Dependências

| Dependência                                                | Tipo     | Estado                          |
|------------------------------------------------------------|----------|---------------------------------|
| `anyio.fail_after`, `anyio.move_on_after`                  | Externa  | Em uso                          |
| Schema `FlowConfig` em `cli/config.py`                     | Interna  | Estender com 2 dicts opcionais  |
| `EventType.AGENT_TURN_TIMED_OUT`                           | Interna  | Adicionar                       |
| `ExecutionPolicy` (Item 2 estende; ordem importa)          | Interna  | Estender ou compor              |
| Spec 011 (Graceful Cancel Checkpoint)                      | Interna  | Coupling soft: usa o save shielded |

---

## Notas Adicionais

- **Ordem de implementação preferida:** Item 2 antes do Item 4, porque Item 4 dispara um save shielded que reusa o mecanismo do Item 2. Não bloqueante — se Item 4 sair antes, basta logar e seguir.
- **Por que dicionários em vez de listas tipadas?** Chaves arbitrárias (nomes de agentes definidos pelo usuário) impedem usar Enum. Validação de "chave é um agente conhecido" acontece em `WorkspaceConfig.model_validator` que cruza com `agent_specs`.
- **`on_timeout_action`:** poderia ser por agente, mas isso é over-engineering inicial. Começar no nível do flow (`flow.on_timeout_action`).
- **Composability com Item 3 (Rich Live):** o evento novo é capturado e exibido como `_action = "Timeout (agent: 120s)"` na UI.
