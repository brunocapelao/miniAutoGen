# Especificação: MCP Server (mcp-out) — expor MiniAutoGen via Model Context Protocol

| Campo      | Valor                          |
|------------|--------------------------------|
| Data       | 2026-05-16                     |
| Autor      | Bruno Capelão                  |
| Status     | Rascunho                       |
| Spec ID    | 014                            |

---

## Contrato de Prompt (G/C/FC)

### 🎯 Goal (Objetivo)

Expor o workspace MiniAutoGen como um **servidor MCP** (Model Context Protocol) consumível por clientes externos (Claude Code, Cursor, Codex CLI, etc.). O agente externo passa a orquestrar `flows`, inspecionar `runs` e ouvir `events` através das primitivas nativas do MCP (`tools` + `resources`), sem precisar conhecer o HTTP/CLI do projeto.

**Não-objetivo deste ciclo:** consumir MCP externo *dentro* dos agentes do MiniAutoGen (`mcp-in`) — isso é o domínio do contrato existente `McpServerBinding` (`miniautogen/core/contracts/mcp_binding.py`) e pertence a uma spec separada.

### 🚧 Constraint (Restrição)

1. **Isolamento de adapters preservado.** O servidor MCP vive em `miniautogen/mcp/` (módulo novo, sibling de `server/`) e **consome apenas** o facade público `miniautogen.api`. Nada do SDK MCP (`mcp` PyPI) pode vazar para `miniautogen/core/`.
2. **Reutiliza o PipelineRunner canônico.** Não introduz executor próprio. `run_flow` invoca o mesmo caminho que `miniautogen run` (`cli/services/run_pipeline.execute_pipeline`).
3. **AnyIO end-to-end.** Handlers MCP são `async`; nada de `threading.Lock` ou IO bloqueante no event loop.
4. **Eventos canônicos.** Streaming de progresso usa `ExecutionEvent` (`core/contracts/events.py`) serializado via `model_dump()`. Nenhum schema de evento paralelo.
5. **Erros taxonomizados.** Falhas mapeiam para `ErrorCategory` canônico → MCP `error.code` (string estável).

### 🛑 Failure Condition (Condição de Falha)

A implementação **falhou** se, no fim do ciclo, qualquer um destes for verdadeiro:

1. Um cliente MCP de referência (`claude` CLI ou `mcp inspector`) **não consegue** completar este fluxo de aceitação contra um workspace de exemplo:
   - listar flows → escolher um → invocar `run_flow` → receber `run_id` → ler resource `run://{id}/events` → resultado final coerente com `miniautogen run <flow>`.
2. Existe alguma import de `mcp.*` (SDK) dentro de `miniautogen/core/` ou `miniautogen/pipeline/`.
3. Executar um flow via MCP produz `ExecutionEvent`s diferentes (em tipo ou ordem) dos emitidos por `miniautogen run` para o mesmo input — quebra de paridade observacional.
4. `pytest tests/mcp/` falha em qualquer ambiente CI suportado, ou a cobertura do módulo `miniautogen/mcp/` cai abaixo de 85%.
5. O servidor MCP bloqueia o event loop por >100ms em qualquer handler durante o teste de carga leve (10 runs concorrentes em workspace InMemory).

---

## User Stories

- Como **dev usando Claude Code**, quero registrar o miniautogen como MCP server no meu `~/.claude.json`, para que eu peça em linguagem natural "rode o flow de pesquisa em paralelo" e o agente externo invoque `run_flow` sem aprender a CLI.
- Como **operador de CI**, quero invocar `miniautogen mcp serve --transport stdio` num job para que um agente downstream (Codex/Claude) execute pipelines do repo e leia eventos sem ter que parsear JSON-Lines de stdout.
- Como **autor de spec do MiniAutoGen**, quero que o servidor MCP exponha o `miniautogen.yaml` e cada flow como resources MCP `workspace://`, `flow://{name}`, `run://{id}`, para que o agente externo descubra a estrutura do workspace via discovery padrão (sem ler diretório manualmente).
- Como **mantenedor**, quero que cada tool MCP delegue a `miniautogen.api`, para que o servidor MCP herde gratuitamente futuras features (novos runtimes de coordenação, novos stores) sem reescrita.

---

## Critérios de Aceitação

### Superfície MCP exposta

- [ ] **Tools** registradas e descobríveis via `tools/list`:
  - [ ] `list_flows()` → `[{name, kind, agents, description}]`
  - [ ] `list_agents()` → `[{name, engine, role}]`
  - [ ] `list_engines()` → `[{name, kind, provider, model}]`
  - [ ] `run_flow(flow_name, input?, timeout_seconds?, stream?: bool=false)` → `{run_id, status, result?}` (sync; `stream=true` reservado para fase 2)
  - [ ] `get_run(run_id)` → `{run_id, status, started_at, finished_at, result?, error?}`
  - [ ] `tail_events(run_id, since_seq?: int, limit?: int=200)` → `{events: [...], next_seq}`
  - [ ] `cancel_run(run_id)` → `{cancelled: bool, reason?}`
- [ ] **Resources** registrados e descobríveis via `resources/list`:
  - [ ] `workspace://config` (read-only, `miniautogen.yaml` parsed)
  - [ ] `flow://{name}` (definição declarativa do flow)
  - [ ] `run://{run_id}/result` (resultado final, se disponível)
  - [ ] `run://{run_id}/events` (event log JSON, ND-JSON)

### CLI

- [ ] Novo subcomando: `miniautogen mcp serve [--transport stdio|sse] [--workspace .] [--api-key ENV]`
  - [ ] `--transport stdio` é o default e funciona com `claude mcp add`/`mcp inspector` sem flags extras.
  - [ ] `--transport sse` (fase 2, marcar `--help` como experimental se não implementado neste ciclo).
- [ ] Subcomando aparece em `miniautogen --help` e `miniautogen mcp --help`.

### Configuração / Discovery

- [ ] README ganha seção "MCP server" com snippet pronto para `~/.claude.json` (ou `claude mcp add`) e link para a spec.
- [ ] `miniautogen mcp serve` falha rápido com mensagem clara se o cwd não for um workspace válido (reusa `require_project_config`).

### Erros e observabilidade

- [ ] Qualquer exceção em handler MCP é mapeada para `ErrorCategory` → string estável no campo `error.code` MCP. Lista canônica documentada na spec.
- [ ] Cada chamada MCP emite log estruturado (structlog) com `mcp.tool`, `mcp.request_id`, `run_id?`, `duration_ms`.

### Testes (Test-First, AnyIO)

- [ ] `tests/mcp/test_server_handshake.py` — initialize/capabilities exchange.
- [ ] `tests/mcp/test_tools_listing.py` — toda tool acima aparece em `tools/list` com schema válido.
- [ ] `tests/mcp/test_run_flow_e2e.py` — `run_flow` num workspace de fixture produz mesmo resultado que `miniautogen run`; eventos coletados via `tail_events` batem com os do `PipelineRunner` direto (paridade observacional).
- [ ] `tests/mcp/test_resources.py` — `workspace://config` e `flow://{name}` retornam payload coerente com YAML.
- [ ] `tests/mcp/test_cancel.py` — `cancel_run` num flow long-running propaga cancelamento estruturado AnyIO e o evento `RUN_CANCELLED` é emitido.
- [ ] `tests/mcp/test_error_mapping.py` — flow inexistente → `error.code="configuration"`; timeout → `error.code="timeout"`; exceção dentro do agent → `error.code="adapter"` (ou apropriado).
- [ ] Linter arquitetural: `tests/architecture/test_no_mcp_sdk_in_core.py` (ou regra existente) impede imports de `mcp.*` em `core/` e `pipeline/`.
- [ ] `skills/run_anyio_tests.sh` continua verde após introdução do módulo.

---

## Invariantes Afetadas

- [x] **Isolamento de Adapters** — Adapters não vazam para `core/`
- [x] **Microkernel / PipelineRunner** — Executor único, sem loops paralelos
- [x] **Assincronismo Canônico (AnyIO)** — Sem código bloqueante no fluxo principal
- [ ] **Policies Event-Driven** — Não introduz novas policies; reutiliza emissão atual

Notas sobre invariantes:

> O servidor MCP é tratado como **adapter de entrada** — mesmo nível conceitual do `server/` FastAPI. Vive em `miniautogen/mcp/` e depende apenas de `miniautogen.api`. Qualquer extensão futura (novas tools/resources) deve adicionar handler sem tocar em `core/`. Para preservar `Microkernel`, `run_flow` reusa `cli/services/run_pipeline.execute_pipeline` (mesmo `PipelineRunner` que o CLI), não invoca runtimes diretamente. Para preservar `AnyIO`, handlers são `async def` e qualquer IO sincrônico passa por `anyio.to_thread.run_sync`.

---

## Dependências

| Dependência                       | Tipo           | Estado                |
|-----------------------------------|----------------|-----------------------|
| `mcp` (SDK Python oficial)        | Externa (pip)  | ≥1.0 (a adicionar)    |
| `miniautogen.api` (facade Python) | Interna        | Pronta                |
| `cli/services/run_pipeline`       | Interna        | Pronta                |
| `core/contracts/events.ExecutionEvent` | Interna   | Pronta                |
| `ErrorCategory` taxonomy          | Interna        | Pronta                |
| `core/contracts/mcp_binding`      | Interna        | Pronta (mcp-in, não usado aqui) |

---

## Arquitetura proposta (alto nível)

```
miniautogen/
├── api.py                       # facade público (já existe — não muda)
├── mcp/                         # NOVO — adapter de entrada MCP
│   ├── __init__.py
│   ├── server.py                # MCPServer (instancia mcp.server.Server, registra tools/resources)
│   ├── tools.py                 # handlers async: list_flows, run_flow, etc.
│   ├── resources.py             # handlers de resources URI workspace://, flow://, run://
│   ├── errors.py                # mapeamento ErrorCategory → MCP error code
│   └── transport.py             # wrappers stdio/SSE (chamam mcp.server.stdio.stdio_server etc.)
├── cli/commands/mcp.py          # NOVO — subcomando `miniautogen mcp serve`
└── core/                        # INTOCADO
```

**Boundary contract:** `miniautogen/mcp/*.py` só pode importar de `miniautogen.api`, `mcp` (SDK externo), stdlib, e `miniautogen/cli/services/*` (para reaproveitar `execute_pipeline`). Não importa de `miniautogen.core.*` direto.

---

## Mapeamento canônico de erros

| Excepção interna / situação                    | `ErrorCategory`     | `error.code` MCP   |
|------------------------------------------------|---------------------|--------------------|
| Flow inexistente                               | `configuration`     | `configuration`    |
| YAML inválido                                  | `validation`        | `validation`       |
| Timeout do runner                              | `timeout`           | `timeout`          |
| Cancelamento (AnyIO `Cancelled`)               | `cancellation`      | `cancellation`     |
| Adapter LLM externo falhou (HTTP/CLI)          | `adapter`           | `adapter`          |
| Erro transiente (rate limit, etc.)             | `transient`         | `transient`        |
| Estado inválido (run já finalizado)            | `state_consistency` | `state_consistency`|
| Bug interno não classificado                   | `permanent`         | `permanent`        |

---

## Notas Adicionais

### Streaming de eventos

Versão 1: `tail_events(run_id, since_seq?)` por polling (paginado por `seq`). É suficiente para o caso headless/CI. **Streaming nativo MCP** (`server-sent updates` via SSE/notifications) fica como fase 2 — depende de validação do SDK Python para `notifications/progress`.

### Autenticação

`stdio` herda confiança do processo pai (sem auth). Para `sse` (fase 2): reusar `MINIAUTOGEN_API_KEY` (mesma env var do FastAPI server) via header `Authorization: Bearer`.

### Paridade com `miniautogen run`

A regra é: **se passar via MCP, deve passar via CLI** e vice-versa, para o mesmo input. O teste de aceitação `test_run_flow_e2e.py` é a guarda dessa paridade.

### Future Work (fora deste ciclo, mas decidido)

- **`mcp-in` runtime**: ativar `McpServerBinding` em runtime, permitindo que agentes do MiniAutoGen consumam MCP servers externos como tools. Spec separada.
- **Motor LLM/CLI-LLM orquestrador embutido**: tornar o próprio workspace MiniAutoGen conversacional via um agente meta que recebe linguagem natural e chama as tools MCP locais (`run_flow`, etc.). Habilitado naturalmente após esta spec — o LLM apenas consome o servidor MCP que vamos construir aqui.
- **Streaming MCP nativo** (`notifications/progress`) para `run_flow` long-running.
- **`mcp serve --transport sse`** para deploy multi-cliente.
