# Plano Técnico: Graceful Cancel Checkpoint

| Campo         | Valor       |
|---------------|-------------|
| Spec ID       | 011         |
| Data          | 2026-05-16  |
| Complexidade  | Short       |

---

## Arquitetura Proposta

### Módulos Afetados

| Módulo / Caminho                                              | Tipo de Alteração       |
|---------------------------------------------------------------|-------------------------|
| `miniautogen/core/runtime/pipeline_runner.py`                 | Alterado                |
| `miniautogen/api.py` (ou onde está `ExecutionPolicy`)          | Alterado (campo novo)   |
| `miniautogen/core/events/types.py`                            | Alterado (2 eventos novos) |
| `miniautogen/cli/services/run_pipeline.py`                    | Alterado                |
| `miniautogen/cli/commands/run.py`                             | Alterado (exit codes)   |
| `tests/runtime/test_cancel_checkpoint.py`                     | Novo                    |
| `tests/cli/test_run_exit_codes.py`                            | Novo                    |

### Diagrama de fluxo

```
CLI (Click) ─── KeyboardInterrupt ─┐
                                   │
                                   ▼
       PipelineRunner.run_pipeline (anyio.CancelScope root)
                                   │
                                   ├── cancel scope triggered
                                   │
                                   ▼
       SHIELDED region (CancelScope(shield=True), TTL=5s)
                                   │
                                   ├── emit run_cancelled / run_timed_out
                                   ├── policy.on_cancel(state)
                                   │      └── SQLAlchemyCheckpointStore.save_checkpoint
                                   │
                                   ▼
       re-raise KeyboardInterrupt / TimeoutError
                                   │
                                   ▼
       CLI maps to exit code (130 / 124)
```

---

## Contratos e Interfaces

### Extensão `ExecutionPolicy`

```python
# miniautogen/api.py (ou módulo correspondente)
from typing import Awaitable, Callable, Literal

CheckpointReason = Literal["cancelled", "timed_out", "completed", "failed"]
OnCancelCallback = Callable[[CheckpointReason, dict], Awaitable[None]]


class ExecutionPolicy(BaseModel):
    timeout_seconds: float | None = None
    graceful_save_timeout: float = 5.0  # TTL do save shielded
    on_cancel: OnCancelCallback | None = None  # injetado pela CLI / harness
```

### Novos eventos canônicos

```python
# miniautogen/core/events/types.py
class EventType(str, Enum):
    ...
    RUN_CANCELLED = "run_cancelled"
    RUN_TIMED_OUT = "run_timed_out"
```

### `PipelineRunner.run_pipeline` (estrutura)

```python
async def run_pipeline(self, pipeline, context):
    self._run_id = self._new_run_id()
    await self._emit("run_started", run_id=self._run_id)
    state: dict = {"run_id": self._run_id, ...}

    try:
        if self._policy and self._policy.timeout_seconds:
            with anyio.fail_after(self._policy.timeout_seconds):
                result = await self._execute(pipeline, context, state)
        else:
            result = await self._execute(pipeline, context, state)
    except TimeoutError:
        await self._graceful_save("timed_out", state)
        await self._emit("run_timed_out", run_id=self._run_id)
        raise
    except (KeyboardInterrupt, anyio.get_cancelled_exc_class()):
        await self._graceful_save("cancelled", state)
        await self._emit("run_cancelled", run_id=self._run_id)
        raise
    else:
        await self._emit("run_completed", run_id=self._run_id)
        return result


async def _graceful_save(self, reason: str, state: dict) -> None:
    if not self._policy or not self._policy.on_cancel:
        return
    ttl = self._policy.graceful_save_timeout
    with anyio.CancelScope(shield=True):
        try:
            with anyio.fail_after(ttl):
                await self._policy.on_cancel(reason, state)
        except TimeoutError:
            logger.warning("checkpoint_save_timed_out", ttl=ttl)
        except Exception as exc:  # noqa: BLE001
            logger.warning("checkpoint_save_failed", error=str(exc))
```

### CLI `cli/commands/run.py` — mapeamento de exit codes

```python
try:
    result = run_async(execute_pipeline, ...)
except KeyboardInterrupt:
    echo_warning("Cancelled. Checkpoint saved (use --resume to continue).")
    raise SystemExit(130)
except TimeoutError:
    echo_warning("Timeout reached. Checkpoint saved (use --resume to continue).")
    raise SystemExit(124)
```

### `cli/services/run_pipeline.py` — wiring do `on_cancel`

```python
checkpoint_store = SQLAlchemyCheckpointStore(config.database.url)
await checkpoint_store.init_db()

async def _on_cancel(reason: str, state: dict) -> None:
    await checkpoint_store.save_checkpoint(
        run_id=state["run_id"],
        flow_name=pipeline_name,
        state=state,
        terminal_reason=reason,
    )

execution_policy = ExecutionPolicy(
    timeout_seconds=timeout,
    on_cancel=_on_cancel,
)
```

---

## Riscos e Mitigações

| Risco                                                                 | Impacto | Mitigação                                                                 |
|-----------------------------------------------------------------------|---------|---------------------------------------------------------------------------|
| Save shielded trava por mais de 5s (DB lento) e bloqueia o exit       | Alto    | `fail_after(graceful_save_timeout)` aborta; loga `checkpoint_save_timed_out` |
| Segundo Ctrl+C durante o save mata o processo                         | Alto    | Shield protege o save; documentar que "double Ctrl+C força exit imediato" |
| Race entre `run_completed` e `cancelled`                              | Médio   | `try/else` garante mutua exclusão; testes de race                          |
| Database não configurado mas usuário pressiona Ctrl+C                 | Baixo   | `_on_cancel` curto-circuita se `config.database is None`                  |
| Eventos novos quebram consumers existentes do EventSink               | Baixo   | Membros de enum aditivos; testes verificam que `unknown` events são logados, não quebram |

---

## Estimativa de Complexidade

| Aspecto              | Estimativa |
|----------------------|------------|
| Ficheiros novos      | 2 (testes) |
| Ficheiros alterados  | 5          |
| Testes novos         | ~8         |
| Esforço estimado     | Short (1-2 dias) |

---

## Sequência de Implementação

1. **Test-first:** escrever `tests/runtime/test_cancel_checkpoint.py` com 4 cenários: cancel após N agentes, timeout, double-cancel (segundo é ignorado), DB ausente. Todos falham.
2. **Test-first:** escrever `tests/cli/test_run_exit_codes.py` com 3 cenários: SIGINT → 130, timeout → 124, sucesso → 0. Todos falham.
3. Adicionar `RUN_CANCELLED` e `RUN_TIMED_OUT` em `EventType`.
4. Estender `ExecutionPolicy` com `graceful_save_timeout` e `on_cancel`.
5. Refatorar `PipelineRunner.run_pipeline` conforme estrutura do plano (CancelScope + shielded save).
6. Wire `on_cancel` no `run_pipeline.py` (CLI service).
7. Ajustar `cli/commands/run.py` para mapear exit codes.
8. Rodar testes novos → 7/7 verdes.
9. Rodar suite completa → 0 regressões.
10. Smoke test manual: `miniautogen run main --timeout 3` → cancela → `miniautogen run main --resume <run_id>` → retoma.

---

## Notas

- **Por que CancelScope shielded em vez de `try/finally`?** O `finally` em AnyIO pode ser cancelado se o scope pai já estiver cancelando. `shield=True` é a garantia oficial AnyIO para "este bloco precisa concluir".
- **Double Ctrl+C:** intencionalmente não tratamos; usuário força a saída e o save fica parcial. Documentado em `--help` do `run`.
- **Relação com Item 4 (per-agent-timeouts):** independente. Se Item 4 também for entregue, o `on_cancel` recebe automaticamente o `agent_id` que estava ativo no momento — o state já carrega.
