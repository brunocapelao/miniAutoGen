# Plano Técnico: MCP Server (mcp-out)

| Campo         | Valor       |
|---------------|-------------|
| Spec ID       | 014         |
| Data          | 2026-05-16  |
| Complexidade  | Medium      |

---

## Arquitetura Proposta

### Módulos Afetados

| Módulo / Caminho                                   | Tipo de Alteração            |
|----------------------------------------------------|------------------------------|
| `miniautogen/mcp/__init__.py`                      | Novo (módulo adapter)        |
| `miniautogen/mcp/server.py`                        | Novo                         |
| `miniautogen/mcp/tools.py`                         | Novo                         |
| `miniautogen/mcp/resources.py`                     | Novo                         |
| `miniautogen/mcp/errors.py`                        | Novo                         |
| `miniautogen/mcp/transport.py`                     | Novo                         |
| `miniautogen/mcp/_workspace.py`                    | Novo (helpers de discovery)  |
| `miniautogen/cli/commands/mcp.py`                  | Novo (subcomando `mcp serve`)|
| `miniautogen/cli/main.py`                          | Alterado (registrar grupo `mcp`) |
| `pyproject.toml`                                   | Alterado (+`mcp>=1.0`)       |
| `tests/mcp/test_server_handshake.py`               | Novo                         |
| `tests/mcp/test_tools_listing.py`                  | Novo                         |
| `tests/mcp/test_resources_listing.py`              | Novo                         |
| `tests/mcp/test_run_flow_e2e.py`                   | Novo                         |
| `tests/mcp/test_tail_and_cancel.py`                | Novo                         |
| `tests/mcp/test_error_mapping.py`                  | Novo                         |
| `tests/architecture/test_mcp_isolation.py`         | Novo (linter arquitetural)   |
| `tests/mcp/fixtures/sample_workspace/`             | Novo (yaml + flow stubs)     |
| `examples/mcp/claude-config-snippet.json`          | Novo                         |
| `docs/pt/guides/mcp-server.md`                     | Novo                         |
| `README.md`                                        | Alterado (seção MCP)         |
| `miniautogen/core/**`                              | **INTOCADO**                 |
| `miniautogen/pipeline/**`                          | **INTOCADO**                 |

### Diagrama de fluxo

```
Cliente MCP (Claude Code, Cursor, mcp inspector)
        │  JSON-RPC sobre stdio
        ▼
┌──────────────────────────────────┐
│  miniautogen/mcp/transport.py    │  stdio_server() do SDK
│         └─ stdio | sse (fase 2)  │
└──────────────┬───────────────────┘
               ▼
┌──────────────────────────────────┐
│  miniautogen/mcp/server.py       │  registra tools+resources
│  ──────────────────────────────  │
│  call_tool(name, args)           │──┐
│  read_resource(uri)              │  │
└──────────────┬───────────────────┘  │
               ▼                      │
┌──────────────────────────────────┐  │
│  tools.py / resources.py         │  │ handlers async
│  (consomem miniautogen.api)      │  │
└──────────────┬───────────────────┘  │
               ▼                      │
┌──────────────────────────────────┐  │
│  miniautogen.api  (facade)       │  │
│  + cli/services/run_pipeline     │  │
└──────────────┬───────────────────┘  │
               ▼                      │
┌──────────────────────────────────┐  │
│  core/runtime/PipelineRunner     │◄─┘ (canônico, sem fork)
└──────────────────────────────────┘
```

---

## Contratos e Interfaces

### Schema das tools MCP (descobríveis via `tools/list`)

Todas as tools devolvem JSON serializável. Schemas declarados via `inputSchema` (JSON Schema, conforme MCP spec). Aqui em forma resumida:

```python
# miniautogen/mcp/tools.py

# 1. Discovery / leitura
async def list_flows() -> list[dict]:
    """Retorna lista de flows do workspace."""
    # → [{"name": str, "kind": str, "agents": [str], "description": str|None}]

async def list_agents() -> list[dict]:
    """Retorna agentes do workspace."""

async def list_engines() -> list[dict]:
    """Retorna engines do workspace."""

# 2. Execução
async def run_flow(
    flow_name: str,
    input: str | None = None,
    timeout_seconds: float | None = None,
) -> dict:
    """Executa um flow (síncrono nesta fase).

    Returns:
        {"run_id": str, "status": "completed"|"failed"|"timed_out", "result": Any|None, "error": dict|None}
    """

# 3. Inspeção
async def get_run(run_id: str) -> dict:
    """Estado e resultado de um run."""
    # → {"run_id", "flow_name", "status", "started_at", "finished_at", "result", "error"}

async def tail_events(
    run_id: str,
    since_seq: int = 0,
    limit: int = 200,
) -> dict:
    """Eventos de execução paginados por seq."""
    # → {"events": [ExecutionEvent.model_dump(), ...], "next_seq": int}

# 4. Controle
async def cancel_run(run_id: str) -> dict:
    """Cancela run em andamento (AnyIO cancellation)."""
    # → {"cancelled": bool, "reason": str|None}
```

Cada handler é registado no servidor MCP via:

```python
# miniautogen/mcp/server.py
from mcp.server import Server
from mcp.types import Tool, TextContent

server = Server("miniautogen")

@server.list_tools()
async def _list_tools() -> list[Tool]:
    return [
        Tool(name="list_flows", description="...", inputSchema={...}),
        # ...
    ]

@server.call_tool()
async def _call_tool(name: str, arguments: dict) -> list[TextContent]:
    handler = TOOL_HANDLERS[name]
    payload = await handler(**arguments)
    return [TextContent(type="text", text=json.dumps(payload))]
```

### Schema dos resources MCP

```
workspace://config           → conteúdo de miniautogen.yaml (parsed YAML como JSON)
flow://{name}                → definição declarativa do flow (igual ao item em list_flows)
run://{run_id}/result        → resultado final do run (404 se ainda em execução)
run://{run_id}/events        → array completo de ExecutionEvents do run (ND-JSON)
```

Resources são **read-only**; mutação acontece apenas via tools.

### Mapeamento canônico de erros

```python
# miniautogen/mcp/errors.py
from miniautogen.api import ErrorCategory

# Cada handler captura exceções e mapeia:
ERROR_CODE_BY_CATEGORY: dict[ErrorCategory, str] = {
    ErrorCategory.CONFIGURATION: "configuration",
    ErrorCategory.VALIDATION: "validation",
    ErrorCategory.TIMEOUT: "timeout",
    ErrorCategory.CANCELLATION: "cancellation",
    ErrorCategory.ADAPTER: "adapter",
    ErrorCategory.TRANSIENT: "transient",
    ErrorCategory.STATE_CONSISTENCY: "state_consistency",
    ErrorCategory.PERMANENT: "permanent",
}

def to_mcp_error(exc: Exception) -> dict:
    """Converte exceção interna em error payload MCP-friendly."""
    category = classify_error(exc)  # já existe em miniautogen.api
    return {
        "code": ERROR_CODE_BY_CATEGORY.get(category, "permanent"),
        "message": str(exc),
        "category": category.value,
    }
```

A propagação para o cliente MCP usa `mcp.ErrorData` (do SDK) com `code` = string canônico acima e `data.category` para introspecção.

### CLI

```python
# miniautogen/cli/commands/mcp.py
import click

@click.group("mcp")
def mcp_group() -> None:
    """MCP server commands."""

@mcp_group.command("serve")
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio")
@click.option("--workspace", type=click.Path(exists=True, file_okay=False), default=".")
def serve(transport: str, workspace: str) -> None:
    """Run the MiniAutoGen MCP server."""
    from miniautogen.mcp.transport import run_stdio, run_sse
    if transport == "sse":
        run_sse(workspace_path=workspace)
    else:
        run_stdio(workspace_path=workspace)
```

Registro em `cli/main.py`: `cli.add_command(mcp_group)`.

### Contratos alterados

Nenhum contrato existente é alterado. `McpServerBinding` (mcp-in) permanece intocado.

---

## Riscos e Mitigações

| Risco                                                                  | Impacto | Mitigação                                                                                          |
|------------------------------------------------------------------------|---------|----------------------------------------------------------------------------------------------------|
| SDK `mcp` ainda jovem (breaking changes possíveis)                     | Médio   | Pin maior `mcp>=1.0,<2.0`; isolar imports em `transport.py` e `server.py` (boundary fino)         |
| Paridade de eventos com `miniautogen run` quebra silenciosamente       | Alto    | Test `test_run_flow_e2e.py` compara sequência de `EventType` lado a lado                          |
| Servidor stdio em background nunca limpa workspace                     | Médio   | `run_stdio` usa `anyio.run` e finally explícito; closes do `EventBus` no teardown                 |
| Cancel via MCP não propaga para AnyIO                                  | Alto    | `cancel_run` mantém handle de `CancelScope` por `run_id` em dict in-memory; teste cobre           |
| Vazamento de `mcp.*` em `core/`                                        | Alto    | Teste arquitetural com `grep`/AST que falha CI se houver import                                   |
| Streaming long-running mascara timeout                                 | Médio   | Versão 1 é síncrona (polling via `tail_events`); streaming nativo é fase 2                        |
| Authn em stdio confiando no processo pai                               | Baixo   | Documentado; SSE só desbloqueado com `MINIAUTOGEN_API_KEY` no header (fase 2)                     |
| Run muito grande satura `tail_events`                                  | Médio   | Paginação obrigatória (`since_seq`, `limit≤500`); resource `run://{id}/events` para fetch total   |

---

## Estimativa de Complexidade

| Aspecto              | Estimativa |
|----------------------|------------|
| Ficheiros novos      | 16 (7 código + 7 testes + 2 exemplos/docs) |
| Ficheiros alterados  | 3 (`pyproject.toml`, `cli/main.py`, `README.md`) |
| Testes novos         | ~22 (handshake 2, tools 6, resources 4, e2e 3, tail/cancel 4, errors 3) |
| Esforço estimado     | Medium (3-5 dias) |

---

## Sequência de Implementação

Test-First. As tarefas T001–T007 são todas testes falhando que escrevem o contrato esperado antes da implementação aparecer.

1. **Dependência:** adicionar `mcp>=1.0,<2.0` em `pyproject.toml` (`[project] dependencies`). Sem isso, `pytest` falha por `ModuleNotFoundError` antes mesmo de chegar aos testes.
2. **Test-first:** `tests/mcp/test_server_handshake.py` — instanciar `Server("miniautogen")` e validar capabilities anunciadas (`tools`, `resources`).
3. **Test-first:** `tests/mcp/test_tools_listing.py` — `tools/list` retorna os 7 nomes esperados com `inputSchema` válido (jsonschema).
4. **Test-first:** `tests/mcp/test_resources_listing.py` — `resources/list` retorna `workspace://config` + templates para `flow://`, `run://{id}/result`, `run://{id}/events`.
5. **Test-first:** `tests/mcp/test_run_flow_e2e.py` — fixture `tests/mcp/fixtures/sample_workspace/` (yaml + flow stub) executa via `run_flow` MCP e compara `EventType[]` com run direto via `cli/services/run_pipeline.execute_pipeline`. **Esta é a guarda de paridade.**
6. **Test-first:** `tests/mcp/test_tail_and_cancel.py` — flow long-running (sleep agent), `tail_events` paginado retorna mesma sequência; `cancel_run` propaga `Cancelled` e gera `RUN_CANCELLED`.
7. **Test-first:** `tests/mcp/test_error_mapping.py` — 4 casos: flow inexistente → `configuration`; timeout → `timeout`; agente quebrado → `adapter`; run_id desconhecido → `state_consistency`.
8. **Test-first arquitetural:** `tests/architecture/test_mcp_isolation.py` — varre `miniautogen/core/` e `miniautogen/pipeline/` procurando `import mcp` / `from mcp`. Falha se encontrar.
9. **Implementação:** `miniautogen/mcp/errors.py` (mapeamento + `to_mcp_error`).
10. **Implementação:** `miniautogen/mcp/_workspace.py` (loaders que delegam para `cli/config.require_project_config`).
11. **Implementação:** `miniautogen/mcp/tools.py` — 7 handlers async; cada um delega para `miniautogen.api` ou `cli/services/run_pipeline`. Mantém dict in-memory `{run_id → CancelScope}` para suporte a `cancel_run`.
12. **Implementação:** `miniautogen/mcp/resources.py` — 4 resource handlers.
13. **Implementação:** `miniautogen/mcp/server.py` — `build_server(workspace_path) -> Server` registra tools+resources, monta logging structlog.
14. **Implementação:** `miniautogen/mcp/transport.py` — `run_stdio(workspace_path)` usa `mcp.server.stdio.stdio_server`; `run_sse(...)` levanta `NotImplementedError` com mensagem clara (fase 2).
15. **CLI:** `miniautogen/cli/commands/mcp.py` + registro em `cli/main.py`.
16. Rodar `skills/run_anyio_tests.sh` → verde. Rodar `ruff` + `mypy`.
17. **Smoke manual:** rodar `mcp inspector` apontando para `python -m miniautogen mcp serve` num workspace de exemplo. Documentar resultado no PR.
18. **Docs:** `docs/pt/guides/mcp-server.md` (passo-a-passo `claude mcp add`); `examples/mcp/claude-config-snippet.json`; seção curta no `README.md` linkando para o guia.

---

## Notas

- **Por que síncrono em `run_flow` v1?** Porque o protocolo MCP `notifications/progress` ainda tem implementação imatura no SDK Python (1.x). Polling via `tail_events` é suficiente para o caso headless/CI e mantém o servidor stateless o suficiente para múltiplos clientes.
- **Por que reusar `cli/services/run_pipeline.execute_pipeline`?** É o mesmo caminho que `miniautogen run`, garantindo paridade observacional automaticamente — qualquer melhoria futura no runner (e.g. event sinks novos) propaga para o MCP server sem código duplicado.
- **`cancel_run` e ciclo de vida de `CancelScope`:** o handle só vive enquanto o run está executando. Após terminal state, o entry é removido do dict; chamadas posteriores retornam `{"cancelled": false, "reason": "run already finished"}`.
- **Future Work explícito:** habilitar `notifications/progress` em `run_flow` (streaming nativo MCP), implementar `--transport sse` com auth via `MINIAUTOGEN_API_KEY`, e — fechando o loop com o objetivo de longo prazo do operador — construir um agente meta interno que consome este MCP server localmente para tornar o workspace conversacional (depende desta spec mas não bloqueia este ciclo).
- **Interação com `McpServerBinding` (mcp-in):** zero. Os dois lados são independentes e podem coexistir no mesmo processo (o miniautogen pode ser MCP server e MCP client simultaneamente, com adapters separados).
- **Por que `miniautogen/mcp/` e não `miniautogen/server/mcp/`?** Para deixar visualmente óbvio que MCP é um adapter de entrada de mesmo nível que `server/` (HTTP) e `tui/`. Misturar com `server/` causaria confusão entre os dois transports HTTP e o transport JSON-RPC MCP.
