# Tarefas: Rich Live CLI Runner

| Campo      | Valor       |
|------------|-------------|
| Spec ID    | 012         |
| Data       | 2026-05-16  |
| Total      | 9 tarefas   |

---

## Legenda

- **Status:** TODO / IN_PROGRESS / DONE / BLOCKED
- **P:** Paralelizável (sim/não)
- **Deps:** IDs de tarefas das quais esta depende

---

## Tarefas

### T001 — Adicionar `rich` ao `pyproject.toml`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Em `pyproject.toml`, adicionar `"rich>=13.0"` a `dependencies` (não em `optional-dependencies`, pois é parte do caminho default da CLI). Rodar `uv lock` (ou `pip-compile`) e commitar `uv.lock`.

**Critério de conclusão:**
- [ ] `rich` listado em `[project] dependencies`
- [ ] `uv.lock` atualizado e commitado
- [ ] `python -c "import rich; print(rich.__version__)"` ≥ 13.0

---

### T002 — Testes falhando: gating de UI

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Criar `tests/cli/test_run_ui_gating.py` com 5 testes, todos chamando `_select_ui_sink(...)` com diferentes combinações:
1. `text + tty + !verbose` → `isinstance(sink, RichLiveEventSink)`
2. `text + tty + verbose` → `isinstance(sink, _VerboseEventSink)`
3. `json + tty + !verbose` → `sink is None`
4. `text + !tty` → `isinstance(sink, _VerboseEventSink)`
5. `MINIAUTOGEN_NO_TTY=1 + text + tty + !verbose` → `sink is None` (ou `_VerboseEventSink` se quisermos algo na CI)

Usar `monkeypatch` para forçar `sys.stderr.isatty()` e `os.environ`.

**Critério de conclusão:**
- [ ] 5 testes presentes; todos falham (função `_select_ui_sink` ainda não existe)

---

### T003 — Testes falhando: estado interno do `RichLiveEventSink`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Criar `tests/cli/test_rich_live_sink.py` que:
1. Instancia o sink **sem** entrar no `with` (modo "headless test").
2. Chama `await sink.publish(ExecutionEvent(type="run_started", payload={"flow_name": "demo", "run_id": "abc12345xx"}))`.
3. Verifica `sink._flow == "demo"` e `sink._run_id == "abc12345"` (truncado a 8).
4. Publica `agent_turn_started` → verifica `_agent` e `_round`.
5. Publica 5 `agent_thought` → verifica `len(sink._thoughts) == 3` (maxlen).
6. Publica `run_cancelled` → verifica `_action == "Saving checkpoint..."`.

**Critério de conclusão:**
- [ ] 6 asserts (1 por step) cobertos em testes separados
- [ ] Nenhum teste depende de capturar output ANSI (testa estado, não render)
- [ ] Todos falham por `ImportError` ou `AttributeError`

---

### T004 — Implementar `RichLiveEventSink`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T001, T003 |

**Descrição:** Criar `miniautogen/cli/services/rich_live_sink.py` conforme contrato no plano:
- Constructor com `console`, `refresh_per_second=8`, `thought_lines=3`
- Context manager (`__enter__`/`__exit__`) que abre `Live`
- `async def publish(event)` que atualiza estado + chama `self._live.update(self._render())`
- `_update_from_event` cobrindo: `run_started`, `agent_turn_started`, `agent_thought`/`agent_chunk`, `run_cancelled`, `run_timed_out`, `run_completed`
- `_render` produz um `Panel` com cabeçalho/atividade/footer

**Critério de conclusão:**
- [ ] `tests/cli/test_rich_live_sink.py` → 6/6 verdes
- [ ] Tipos via `mypy --strict`
- [ ] Nenhuma referência circular (`cli/` não importa `core/`)

---

### T005 — Implementar `_select_ui_sink`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T002, T004 |

**Descrição:** Em `cli/commands/run.py`, declarar `_select_ui_sink(*, output_format, verbose)` conforme plano. Mover a classe `_VerboseEventSink` para `cli/services/run_pipeline.py` (ou um módulo dedicado `cli/services/event_sinks.py`) para evitar import circular.

**Critério de conclusão:**
- [ ] `tests/cli/test_run_ui_gating.py` → 5/5 verdes
- [ ] `_Spinner` removido ou marcado `# deprecated` (preferência: remover; código morto não fica)
- [ ] Importes claros e sem ciclos

---

### T006 — Wire UI no `run_command`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T005  |

**Descrição:** Em `cli/commands/run.py::run_command`, substituir o bloco do `_Spinner` por:
```python
ui_sink = _select_ui_sink(output_format=output_format, verbose=verbose)
cm = ui_sink if isinstance(ui_sink, RichLiveEventSink) else contextlib.nullcontext()
with cm:
    result = run_async(execute_pipeline, ..., event_sink=ui_sink, console_event_sink=console_event_sink)
```

Ajustar `execute_pipeline` para receber `event_sink` e `console_event_sink` separados (já que `--console` continua válido como sink adicional). Atualizar a assinatura, atualizar callsites e testes existentes.

**Critério de conclusão:**
- [ ] `miniautogen run main` em terminal mostra UI rich
- [ ] `miniautogen run main --console` mostra UI rich + abre browser
- [ ] `miniautogen run main --verbose` mostra logs por linha (sem rich)
- [ ] `miniautogen run main --format json | jq .` produz JSON válido sem ANSI
- [ ] `MINIAUTOGEN_NO_TTY=1 miniautogen run main` não usa rich

---

### T007 — Regressão completa

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T006  |

**Descrição:** Rodar `pytest` completo. Atenção especial a `tests/cli/test_run*.py` que possam depender do spinner ou da assinatura antiga de `execute_pipeline`.

**Critério de conclusão:**
- [ ] `pytest` passa 100%
- [ ] Nenhum warning de `DeprecationWarning` introduzido

---

### T008 — Smoke visual + GIF

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | T006  |

**Descrição:** Em um workspace de exemplo com uma deliberação 3-agentes (Advogado, Engenheiro, Paralegal), rodar `miniautogen run main` e gravar com `asciinema` ou `vhs`. Converter para GIF (≤ 2 MB). Salvar em `docs/assets/rich-live-demo.gif`.

**Critério de conclusão:**
- [ ] GIF de 15-30s mostrando turno-por-turno
- [ ] Caminho relativo correto no commit
- [ ] Reproduzível: comando `vhs` versionado em `docs/assets/rich-live-demo.tape`

---

### T009 — Documentação

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | T008  |

**Descrição:** Em `docs/getting-started.md` (ou `README.md`):
1. Adicionar a GIF na seção "Running a flow".
2. Documentar `--verbose`, `--format json` e `MINIAUTOGEN_NO_TTY=1` em uma tabela compacta:

| Cenário                 | Comando                                       | UI exibida           |
|-------------------------|-----------------------------------------------|----------------------|
| Terminal interativo     | `miniautogen run main`                        | Rich Live inline     |
| Debug verboso           | `miniautogen run main --verbose`              | Logs por linha       |
| CI / pipe               | `miniautogen run main \| cat`                  | Logs por linha       |
| Output programático     | `miniautogen run main --format json`          | Sem UI (só JSON)     |
| Forçar modo CI          | `MINIAUTOGEN_NO_TTY=1 miniautogen run main`   | Logs por linha       |

**Critério de conclusão:**
- [ ] Tabela renderiza no GitHub
- [ ] GIF referenciada
- [ ] Link para spec original

---

## Grafo de Dependências

```
T001 ┐
T002 ┤
T003 ┤
     ├─> T004 ─┬─> T005 ─> T006 ─┬─> T007
     │         │                 ├─> T008 ─> T009
```

---

## Resumo

| Paralelizáveis | Sequenciais | Bloqueadas | Total |
|----------------|-------------|------------|-------|
| 5              | 4           | 0          | 9     |
