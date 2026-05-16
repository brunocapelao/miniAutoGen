# Tarefas: Graceful Cancel Checkpoint

| Campo      | Valor       |
|------------|-------------|
| Spec ID    | 011         |
| Data       | 2026-05-16  |
| Total      | 8 tarefas   |

---

## Legenda

- **Status:** TODO / IN_PROGRESS / DONE / BLOCKED
- **P:** Paralelizável (sim/não)
- **Deps:** IDs de tarefas das quais esta depende

---

## Tarefas

### T001 — Testes falhando: runtime cancel/timeout

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Criar `tests/runtime/test_cancel_checkpoint.py`. Cenários (cada um vira um teste):
1. `test_cancel_after_first_agent_saves_checkpoint`: pipeline com 3 agentes; cancela após o 1º; verifica que checkpoint contém estado do agente 1.
2. `test_timeout_emits_run_timed_out_event`: `move_on_after(0.1)`; pipeline com `anyio.sleep(1)`; verifica evento canônico + checkpoint.
3. `test_double_cancel_does_not_corrupt_db`: dispara 2 cancels via task group; segundo é absorvido pelo shield.
4. `test_no_db_configured_no_save`: `on_cancel=None`; cancel não levanta erro.

**Critério de conclusão:**
- [ ] 4 testes presentes; todos falham com `AttributeError` ou similar (implementação ausente)
- [ ] Usa `anyio.from_thread.run` ou backend pytest-anyio

---

### T002 — Testes falhando: CLI exit codes

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Criar `tests/cli/test_run_exit_codes.py`. Usa `click.testing.CliRunner`. Cenários:
1. `test_sigint_exits_130`: simula `KeyboardInterrupt` em `execute_pipeline` mock; verifica `result.exit_code == 130`.
2. `test_timeout_exits_124`: idem para `TimeoutError`.
3. `test_success_exits_0`: caso happy path mantém zero.

**Critério de conclusão:**
- [ ] 3 testes presentes e falhando
- [ ] Mensagens `echo_warning("Saving checkpoint...")` aparecem nos casos 1 e 2

---

### T003 — Adicionar eventos canônicos

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Em `miniautogen/core/events/types.py`, adicionar `RUN_CANCELLED = "run_cancelled"` e `RUN_TIMED_OUT = "run_timed_out"` ao `EventType` enum. Atualizar `__all__`/exports se necessário. Verificar com `tests/events/test_event_types.py` (ou criar smoke test).

**Critério de conclusão:**
- [ ] `EventType.RUN_CANCELLED` e `EventType.RUN_TIMED_OUT` existem
- [ ] Membros listados em qualquer set de "tipos válidos" do `EventSink`
- [ ] `ruff` limpo

---

### T004 — Estender `ExecutionPolicy`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Adicionar a `ExecutionPolicy` (em `miniautogen/api.py` ou módulo correspondente) os campos:
- `graceful_save_timeout: float = 5.0`
- `on_cancel: OnCancelCallback | None = None`

Definir `CheckpointReason = Literal["cancelled", "timed_out", "completed", "failed"]` e `OnCancelCallback = Callable[[CheckpointReason, dict], Awaitable[None]]` no mesmo módulo (ou em `core/contracts/`).

**Critério de conclusão:**
- [ ] Campos presentes e tipados
- [ ] `mypy --strict` passa
- [ ] Construção sem `on_cancel` continua funcionando (backward compat)

---

### T005 — Refatorar `PipelineRunner.run_pipeline`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T001, T003, T004 |

**Descrição:** Implementar o esqueleto do plano em `pipeline_runner.py`:
- envolver execução em `anyio.fail_after(timeout)` quando policy define timeout
- capturar `KeyboardInterrupt` e `anyio.get_cancelled_exc_class()`
- chamar `_graceful_save(reason, state)` que usa `CancelScope(shield=True)` + `fail_after(graceful_save_timeout)`
- emitir os eventos canônicos antes de re-raise
- preservar o `run_id` no `state` para o callback

**Critério de conclusão:**
- [ ] `tests/runtime/test_cancel_checkpoint.py` → 4/4 verdes
- [ ] Nenhum `signal.signal` introduzido
- [ ] `ruff` e `mypy` passam no arquivo

---

### T006 — Wire `on_cancel` na CLI service

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T005  |

**Descrição:** Em `cli/services/run_pipeline.py`, criar `_on_cancel(reason, state)` que abre o `SQLAlchemyCheckpointStore` (reusando `config.database.url`) e chama `save_checkpoint(...)`. Passar a callback no `ExecutionPolicy`. Se `config.database is None`, não passar `on_cancel` (curto-circuita).

**Critério de conclusão:**
- [ ] Smoke test: `miniautogen run main --timeout 1` em workspace com DB salva checkpoint
- [ ] Mesmo comando em workspace sem DB termina sem erro
- [ ] `await checkpoint_store.engine.dispose()` é chamado sempre

---

### T007 — Mapeamento de exit codes na CLI

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T005  |

**Descrição:** Em `cli/commands/run.py`, envolver a chamada a `run_async(execute_pipeline, ...)` com try/except mapeando `KeyboardInterrupt → 130`, `TimeoutError → 124`. Exibir `echo_warning("Saving checkpoint before exit...")` no ponto onde o sinal é capturado. Garantir que o `spinner.stop()` é chamado em todos os paths (mover para `finally`).

**Critério de conclusão:**
- [ ] `tests/cli/test_run_exit_codes.py` → 3/3 verdes
- [ ] Spinner não vaza linha quebrada em terminal após cancel
- [ ] `--help` documenta o comportamento (uma linha nova)

---

### T008 — Smoke test end-to-end + doc

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | T006, T007 |

**Descrição:** Rodar manualmente:
1. `miniautogen run main` (deliberation longa) → Ctrl+C após 30s.
2. Capturar `run_id` no output.
3. `miniautogen sessions show <run_id>` → confirmar `terminal_reason=cancelled`.
4. `miniautogen run main --resume <run_id>` → verifica que retoma do último agente salvo.

Atualizar `docs/getting-started.md` seção "Cancelando runs longos" com este fluxo. Adicionar nota: "Double Ctrl+C força exit imediato sem salvar — use uma vez só e aguarde a mensagem `Saving checkpoint...`".

**Critério de conclusão:**
- [ ] Fluxo manual passa
- [ ] Doc atualizada com snippet copiável
- [ ] PR review aprova

---

## Grafo de Dependências

```
T001 ┐
T002 ┤
T003 ┤
T004 ┤
     └─> T005 ─┬─> T006 ─┐
               └─> T007 ─┴─> T008
```

---

## Resumo

| Paralelizáveis | Sequenciais | Bloqueadas | Total |
|----------------|-------------|------------|-------|
| 5              | 3           | 0          | 8     |
