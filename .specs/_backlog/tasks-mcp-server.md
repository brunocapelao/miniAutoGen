# Tarefas: MCP Server (mcp-out)

| Campo      | Valor       |
|------------|-------------|
| Spec ID    | 014         |
| Data       | 2026-05-16  |
| Total      | 14 tarefas  |

---

## Legenda

- **Status:** TODO / IN_PROGRESS / DONE / BLOCKED
- **P:** Paralelizável (sim/não)
- **Deps:** IDs de tarefas das quais esta depende

---

## Tarefas

### T001 — Adicionar dependência `mcp` ao `pyproject.toml`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Em `pyproject.toml`, adicionar `"mcp>=1.0,<2.0"` em `[project] dependencies`. Rodar `uv lock` (ou `poetry lock`). Confirmar que `python -c "import mcp"` funciona no ambiente.

**Critério de conclusão:**
- [ ] `mcp` aparece em `uv.lock`
- [ ] `python -c "from mcp.server import Server"` sucede
- [ ] Nenhum outro test do projeto regrediu por upgrade transitivo

---

### T002 — Fixture: workspace de teste

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Criar `tests/mcp/fixtures/sample_workspace/` com:
1. `miniautogen.yaml` mínimo (1 engine InMemory/echo, 1 agente, 1 flow workflow trivial chamado `hello`).
2. Helper `tests/mcp/fixtures/__init__.py` exportando `WORKSPACE_PATH = Path(__file__).parent / "sample_workspace"`.

O flow `hello` deve completar em <1s e produzir resultado determinístico (string "hello world").

**Critério de conclusão:**
- [ ] `miniautogen run hello --workspace tests/mcp/fixtures/sample_workspace` retorna "hello world" e exit 0
- [ ] Mesmo workspace funciona como CWD para `require_project_config`

---

### T003 — Teste falhando: handshake do servidor

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | T001  |

**Descrição:** Criar `tests/mcp/test_server_handshake.py`. Cenários:
1. `test_build_server_returns_named_instance`: `build_server(workspace)` retorna `Server` cujo `name == "miniautogen"`.
2. `test_capabilities_declare_tools_and_resources`: capabilities anunciam `tools` e `resources` como suportados.

**Critério de conclusão:**
- [ ] 2 testes presentes; falham por `ImportError` em `miniautogen.mcp.server`

---

### T004 — Teste falhando: listagem de tools

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | T001  |

**Descrição:** Criar `tests/mcp/test_tools_listing.py`. Cenários (use `pytest-anyio`):
1. `test_lists_seven_tools`: nomes exatos = `{list_flows, list_agents, list_engines, run_flow, get_run, tail_events, cancel_run}`.
2. `test_each_tool_has_valid_json_schema`: cada `Tool.inputSchema` valida via `jsonschema.Draft202012Validator.check_schema`.
3. `test_run_flow_requires_flow_name`: schema marca `flow_name` como `required`.

**Critério de conclusão:**
- [ ] 3 testes presentes; todos falham

---

### T005 — Teste falhando: listagem de resources

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | T001, T002 |

**Descrição:** Criar `tests/mcp/test_resources_listing.py`. Cenários:
1. `test_workspace_config_resource_exists`: `resources/list` contém `workspace://config`.
2. `test_flow_template_listed`: `resourceTemplates` contém `flow://{name}`.
3. `test_run_templates_listed`: `resourceTemplates` contém `run://{run_id}/result` e `run://{run_id}/events`.
4. `test_read_workspace_config_returns_yaml`: `read_resource("workspace://config")` retorna conteúdo equivalente a `yaml.safe_load(miniautogen.yaml)`.

**Critério de conclusão:**
- [ ] 4 testes presentes; todos falham

---

### T006 — Teste falhando: paridade `run_flow` vs `miniautogen run`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | T002  |

**Descrição:** Criar `tests/mcp/test_run_flow_e2e.py`. Esta é a **guarda de paridade observacional** declarada no FC da spec. Cenário principal:

1. `test_mcp_run_flow_matches_cli_event_sequence`:
   - Executar `hello` via `cli/services/run_pipeline.execute_pipeline` coletando `ExecutionEvent`s num `InMemoryEventSink`.
   - Executar `hello` via tool MCP `run_flow` (chamada direta ao handler, sem transport) coletando eventos via mesmo sink.
   - Assertar: mesma sequência de `event.type`; mesmo resultado final.
2. `test_run_flow_returns_run_id_and_status`: payload de `run_flow` contém `run_id` (UUID), `status="completed"`, `result` string.
3. `test_unknown_flow_returns_configuration_error`: `run_flow("does_not_exist")` levanta exceção mapeada para `error.code="configuration"`.

**Critério de conclusão:**
- [ ] 3 testes presentes; todos falham

---

### T007 — Teste falhando: `tail_events` e `cancel_run`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | T002  |

**Descrição:** Criar `tests/mcp/test_tail_and_cancel.py`. Use `pytest-anyio`. Cenários:
1. `test_tail_events_paginates`: rodar `hello`; `tail_events(run_id, since_seq=0, limit=2)` retorna 2 eventos + `next_seq=2`; chamada seguinte com `since_seq=2` continua.
2. `test_tail_events_unknown_run_returns_state_error`: `run_id` inválido → exceção mapeada para `state_consistency`.
3. `test_cancel_run_propagates_to_anyio`: flow com agent que dorme 5s; chamar `cancel_run` em outra task; assertar evento `RUN_CANCELLED` na sequência e payload `{"cancelled": true}`.
4. `test_cancel_finished_run_is_idempotent`: cancelar run já completado retorna `{"cancelled": false, "reason": "run already finished"}` sem exceção.

**Critério de conclusão:**
- [ ] 4 testes presentes; todos falham

---

### T008 — Teste falhando: mapeamento de erros

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Criar `tests/mcp/test_error_mapping.py`. Cenários (usar mocks/stubs de exceções):
1. `test_classify_configuration`: `FileNotFoundError` em `miniautogen.yaml` → `code="configuration"`.
2. `test_classify_timeout`: `TimeoutError` → `code="timeout"`.
3. `test_classify_adapter_failure`: exceção custom marcada como adapter → `code="adapter"`.
4. `test_classify_unknown_returns_permanent`: exceção desconhecida → `code="permanent"` (fallback explícito).

**Critério de conclusão:**
- [ ] 4 testes presentes; todos falham por `ImportError` em `miniautogen.mcp.errors`

---

### T009 — Teste arquitetural: isolamento de `mcp.*`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Criar `tests/architecture/test_mcp_isolation.py`. Varrer recursivamente todos os `.py` em `miniautogen/core/` e `miniautogen/pipeline/` procurando padrões `^import mcp(\.|$)` e `^from mcp(\.| )`. O teste falha se qualquer match for encontrado. Lista de exceções: vazia (zero tolerância).

**Critério de conclusão:**
- [ ] 1 teste presente; passa atualmente (estado inicial limpo)
- [ ] Smoke: criar `miniautogen/core/_smoke.py` com `import mcp` localmente, rodar o teste, confirmar que falha; reverter.

---

### T010 — Implementar `errors.py`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T008  |

**Descrição:** Criar `miniautogen/mcp/errors.py` com:
- Dict `ERROR_CODE_BY_CATEGORY` (8 entradas, alinhado com `ErrorCategory`).
- `to_mcp_error(exc: Exception) -> dict` que chama `classify_error` (já em `miniautogen.api`) e retorna `{"code", "message", "category"}`.

**Critério de conclusão:**
- [ ] `tests/mcp/test_error_mapping.py` → 4/4 verdes
- [ ] `mypy` limpo

---

### T011 — Implementar `tools.py` + `resources.py` + `_workspace.py`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T002, T004, T005, T006, T007, T010 |

**Descrição:** Implementar os 7 handlers de tools e 4 de resources conforme `plan-mcp-server.md`. Pontos críticos:

1. `_workspace.py`: carrega workspace via `cli/config.require_project_config` (chdir contextual). Cacheia config por path durante o ciclo de vida do server.
2. `tools.py`: mantém `_active_runs: dict[str, anyio.CancelScope]` para suporte a `cancel_run`. Cada `run_flow` registra e remove ao terminar. Reusa `cli/services/run_pipeline.execute_pipeline` para preservar paridade.
3. `tools.py`: `tail_events` lê de um `InMemoryEventSink` que o handler instala antes de rodar o flow; chave é o `run_id`.
4. `resources.py`: `workspace://config` retorna YAML como JSON; `flow://{name}`, `run://{run_id}/result`, `run://{run_id}/events` retornam payloads alinhados aos contratos.
5. Toda exceção é encapsulada via `to_mcp_error` e propagada como `mcp.ErrorData`.

**Critério de conclusão:**
- [ ] `tests/mcp/test_tools_listing.py` → 3/3 verdes
- [ ] `tests/mcp/test_resources_listing.py` → 4/4 verdes
- [ ] `tests/mcp/test_run_flow_e2e.py` → 3/3 verdes
- [ ] `tests/mcp/test_tail_and_cancel.py` → 4/4 verdes
- [ ] Nenhum `time.sleep`, `threading.*` ou wrapper síncrono em paths async
- [ ] Logs estruturados (structlog) em cada handler

---

### T012 — Implementar `server.py` + `transport.py`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T003, T011 |

**Descrição:**
1. `server.py`: `build_server(workspace_path: Path) -> Server` instancia `mcp.server.Server("miniautogen")`, registra todos os tools e resources via decorators do SDK, e retorna a instância.
2. `transport.py`:
   - `async def run_stdio(workspace_path: Path) -> None` — usa `mcp.server.stdio.stdio_server()` como async context manager; entrega `(read_stream, write_stream)` ao `server.run(...)`.
   - `run_sse(workspace_path: Path) -> NoReturn` — levanta `NotImplementedError("SSE transport is phase 2; use stdio")`. Mensagem clara e exit code apropriado.
3. Teardown limpo: ao receber SIGTERM/EOF, fechar `EventBus` e cancelar runs órfãos.

**Critério de conclusão:**
- [ ] `tests/mcp/test_server_handshake.py` → 2/2 verdes
- [ ] `tests/architecture/test_mcp_isolation.py` continua verde
- [ ] Smoke local: `python -m miniautogen mcp serve` (em workspace exemplo) responde a handshake do `mcp inspector` sem stack trace

---

### T013 — CLI `miniautogen mcp serve`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T012  |

**Descrição:**
1. Criar `miniautogen/cli/commands/mcp.py` com grupo `mcp` e subcomando `serve` (opções `--transport`, `--workspace`).
2. Registrar em `cli/main.py` via `cli.add_command(mcp_group)`.
3. `serve` chama `anyio.run(run_stdio, workspace_path)` para o caminho stdio; para `sse`, levanta `click.ClickException` com mensagem clara.
4. Pré-validar workspace via `require_project_config` antes de iniciar transport; falha fast com mensagem amigável se o cwd não for um workspace válido.

**Critério de conclusão:**
- [ ] `miniautogen --help` mostra o grupo `mcp`
- [ ] `miniautogen mcp serve --help` lista as opções
- [ ] Smoke: `miniautogen mcp serve --workspace tests/mcp/fixtures/sample_workspace` (em pipe) responde JSON-RPC válido a um `initialize` request manual

---

### T014 — Docs, exemplo Claude config, README, smoke E2E

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | T013  |

**Descrição:**
1. Criar `docs/pt/guides/mcp-server.md` com:
   - O que é, quando usar.
   - Passo-a-passo `claude mcp add miniautogen -- miniautogen mcp serve`.
   - Tabela das 7 tools + 4 resources.
   - Tabela do mapeamento de erros (copiada da spec).
   - Limitações da v1 (sem streaming, sem auth em stdio) + roteiro de fase 2.
2. Criar `examples/mcp/claude-config-snippet.json` com configuração pronta para `~/.claude.json`.
3. Atualizar `README.md` (seção "MCP server" após "Web Console") com 5 linhas + link para o guia.
4. Smoke manual completo: registrar via `claude mcp add`, abrir Claude Code, pedir "liste meus flows" → confirmar tool call → pedir "rode o flow hello" → confirmar `run_id` e resultado. Documentar no PR (screenshot ou transcript).
5. Rodar `skills/run_anyio_tests.sh` + `ruff check` + `mypy` em todo o projeto.

**Critério de conclusão:**
- [ ] Guia renderiza no GitHub e tem todas as seções acima
- [ ] `pytest` 100% verde no projeto
- [ ] `ruff` + `mypy` limpos
- [ ] Smoke E2E com Claude Code documentado no PR

---

## Grafo de Dependências

```
T001 ┐
T002 ┤        ┌─> T003 ┐
T003 ┤        │        │
T004 ┤        ├─> T004 │
T005 ┤        │        │
T006 ┤        ├─> T005 ├──> T012 ──> T013 ──> T014
T007 ┤        │        │
T008 ┤        ├─> T006 │
T009 ┘        │        │
              ├─> T007 │
T008 ──> T010 ┤        │
              └─> T011 ┘
T009 ────────────────────────────────^ (regressão durante T011/T012)
```

(Leitura: T001/T002 desbloqueiam o bloco de testes T003–T009 em paralelo. T010 depende só de T008. T011 só pode iniciar quando os testes que ele torna verdes existirem. T012 fecha o servidor; T013 expõe via CLI; T014 documenta e valida E2E.)

---

## Resumo

| Paralelizáveis | Sequenciais | Bloqueadas | Total |
|----------------|-------------|------------|-------|
| 9              | 5           | 0          | 14    |
