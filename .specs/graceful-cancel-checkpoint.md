# Spec: Graceful Cancel Checkpoint — Salvar estado em SIGINT/timeout

| Campo      | Valor                                          |
|------------|------------------------------------------------|
| Data       | 2026-05-16                                     |
| Autor      | DX Sprint 3                                    |
| Status     | Rascunho                                       |
| Spec ID    | 011                                            |
| Origem     | `docs/plans/AVALIACAO-MINIAUTOGEN.md` §7.3     |

---

## Contrato de Prompt (G/C/FC)

### 🎯 Goal

Quando o usuário aborta um `miniautogen run` em andamento (Ctrl+C, `--timeout` estourado, ou SIGTERM via sistema), o framework deve **salvar um checkpoint do estado atual** antes de encerrar o processo, para que `miniautogen run <flow> --resume <run_id>` seja capaz de continuar. Hoje o `--resume` já existe (`cli/commands/run.py:107`), mas o save-on-cancel não é garantido — o usuário só consegue retomar runs que terminaram graciosamente, o que é o caso oposto do que ele precisa.

### 🚧 Constraint

1. **AnyIO canônico:** o cancelamento é estruturado via `anyio.CancelScope` / `fail_after`. Não usar `signal.signal` no fluxo principal — apenas em um setup pontual e idempotente da CLI.
2. **PipelineRunner é o único executor:** o save-on-cancel é responsabilidade do `PipelineRunner` (ou de uma policy event-driven `ExecutionPolicy`), não do código de Click.
3. **Idempotência:** o checkpoint salvo durante cancelamento não pode corromper checkpoints normais. Usa o mesmo schema e o mesmo store; apenas marca `terminal_reason = "cancelled" | "timeout"`.
4. **Não engolir o sinal:** após salvar, propaga `KeyboardInterrupt`/`TimeoutError` para o caller para que `exit code` reflita o cancelamento (≠0).

### 🛑 Failure Condition

- Após `Ctrl+C` em um run com pelo menos um agente já executado, `miniautogen sessions show <run_id>` não retorna o checkpoint parcial.
- `miniautogen run <flow> --resume <run_id>` falha com `No checkpoint found` para um run que foi cancelado mid-execution.
- Exit code do `miniautogen run` interrompido é `0` (deveria ser `130` para SIGINT ou `124` para timeout).
- Race condition: receber 2× Ctrl+C mata o processo durante o save e corrompe o DB.
- Cancelamento durante save dispara `RuntimeError: cancel scope exited prematurely` (vazamento de `AnyIO`).

---

## User Stories

- Como **engenheiro testando uma deliberation de 10 minutos**, quero pressionar Ctrl+C quando perceber que o caminho está errado, e retomar do último round salvo após corrigir o prompt — para não perder 8 minutos de inferência.
- Como **operador de SLA**, quero que `--timeout 600` salve o checkpoint quando estourar, para que eu possa investigar **onde** o sistema travou (qual agente, qual turno).
- Como **mantenedor do framework**, quero que o exit code reflita a razão do término, para que CI/CD não trate timeout como sucesso.

---

## Critérios de Aceitação

- [ ] `PipelineRunner.run_pipeline` envolve a execução em um `anyio.CancelScope` que, ao ser cancelado, dispara o save antes de propagar a exceção.
- [ ] Um novo `ExecutionPolicy.on_cancel(checkpoint_callable)` permite registrar a função de salvamento sem acoplar Runner ↔ Store.
- [ ] O checkpoint salvo contém: `run_id`, `flow_name`, `state` (current round/agent/turn), `terminal_reason` ∈ {`"cancelled"`, `"timeout"`}, `timestamp`.
- [ ] `cli/commands/run.py` registra um handler de `KeyboardInterrupt` (apenas no entry-point) que aciona o cancel do scope raiz **uma única vez** e exibe `echo_warning("Saving checkpoint before exit...")`.
- [ ] Exit code: `130` (SIGINT), `124` (timeout), `1` (erro genérico), `0` (sucesso).
- [ ] `--resume <run_id>` funciona para um run cancelado, retomando do estado salvo.
- [ ] Evento canônico `run_cancelled` ou `run_timed_out` é emitido ao event sink (CLAUDE.md §4.4).
- [ ] Teste de integração: simula `anyio.move_on_after(0.5)` em um pipeline com 3 agentes — verifica que o checkpoint contém o agente que executou antes do timeout.
- [ ] Teste de stress: 2 cancelamentos consecutivos não corrompem o DB (segundo Ctrl+C é ignorado durante save).

---

## Invariantes Afetadas

- [ ] **Isolamento de Adapters**
- [x] **Microkernel / PipelineRunner** — o runner ganha responsabilidade de cancel-and-save; nenhum executor paralelo é criado.
- [x] **Assincronismo Canônico (AnyIO)** — `CancelScope` + `move_on_after` são a base; nada de `signal.alarm` ou `threading`.
- [x] **Policies Event-Driven** — usa-se uma policy (`ExecutionPolicy.on_cancel`) que observa o evento de cancel e dispara o save lateralmente; o Runner não chama o store diretamente.

> O save executa em uma região **shielded** (`anyio.CancelScope(shield=True)`) durante um TTL curto (default 5s, configurável). Isso evita o cenário "cancel cancela o save".

---

## Dependências

| Dependência                                                          | Tipo     | Estado                          |
|----------------------------------------------------------------------|----------|---------------------------------|
| `anyio.CancelScope`, `anyio.fail_after`                              | Externa  | Já em uso no runner             |
| `miniautogen.api.SQLAlchemyCheckpointStore`                          | Interna  | Já existe                       |
| `miniautogen.api.ExecutionPolicy`                                    | Interna  | Existe; estender com `on_cancel`|
| Eventos `run_cancelled` / `run_timed_out`                            | Interna  | A criar em `core/events/types.py` se ausentes |
| Taxonomia de erros (`cancellation`, `timeout`)                       | Interna  | Já canônica                     |

---

## Notas Adicionais

- **Por que não `signal.signal(SIGINT, ...)`?** Em ambientes async, sinais POSIX disparam fora do event loop. `Click` já converte SIGINT em `KeyboardInterrupt` no entry-point; o Runner intercepta lá.
- **Diferença de cancelled vs. timed_out:** ambos salvam, mas o `terminal_reason` distinto permite que `sessions list` mostre o motivo e o `--resume` informe `Resuming from cancelled run...` vs `Resuming from timed-out run (last agent: X)...`.
- O save shielded usa um TTL curto (`graceful_save_timeout`, default 5s). Se o save em si estourar, propaga normalmente e loga `checkpoint_save_failed` — preserva o exit code original.
