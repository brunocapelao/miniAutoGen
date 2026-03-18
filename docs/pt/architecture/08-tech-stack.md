# Stack Tecnológica do MiniAutoGen

**Versão:** 1.0.0
**Data:** 2025-06-18
**Python:** >=3.10, <3.12

---

## 1. Visão Geral

O MiniAutoGen é construído sobre uma stack Python async-first, com ênfase em type safety, observabilidade e isolamento de providers. A escolha de cada tecnologia segue os princípios arquiteturais do microkernel: o core não depende de nenhum provider específico, e toda integração externa é isolada em adapters.

```
┌──────────────────────────────────────────────────────────────────┐
│                        MiniAutoGen                                │
├──────────────┬───────────────┬──────────────┬────────────────────┤
│ CLI (Click)  │ TUI (Textual) │ API (FastAPI)│ Server (Uvicorn)   │
├──────────────┴───────────────┴──────────────┴────────────────────┤
│                    Core / Kernel                                  │
│  Contracts (Pydantic) · Events (structlog) · Runtime (AnyIO)     │
├──────────────────────────────────────────────────────────────────┤
│                    Policies & Stores                              │
│  Retry (tenacity) · Persistence (SQLAlchemy + aiosqlite)         │
├──────────────────────────────────────────────────────────────────┤
│                    Adapters / Drivers                             │
│  OpenAI SDK · Anthropic SDK · Google GenAI · LiteLLM · CLI Agent │
├──────────────────────────────────────────────────────────────────┤
│                    Infrastructure                                 │
│  httpx · YAML (ruamel/pyyaml) · Jinja2 · python-dotenv          │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Dependências Principais

### 2.1 Runtime Assíncrono

| Pacote | Versão | Papel no MiniAutoGen |
|---|---|---|
| **anyio** | >=4.0.0 | **Fundação do runtime.** Concorrência estruturada, cancelamento, timeouts. Abstrai asyncio/trio. Usado em todos os runtimes (Workflow, AgenticLoop, Deliberation). `anyio.create_task_group()` para fan-out paralelo, `anyio.fail_after()` para timeouts. |
| **aiosqlite** | >=0.19.0 | Backend async para SQLite. Permite operações de banco sem bloquear o event loop. |

**Por que AnyIO (e não asyncio puro):** AnyIO fornece cancelamento estruturado nativo (`TaskGroup`), timeouts composáveis, e compatibilidade com trio. O CLAUDE.md define como invariante: "Código bloqueante no fluxo principal é terminantemente proibido."

### 2.2 Contratos e Validação

| Pacote | Versão | Papel no MiniAutoGen |
|---|---|---|
| **pydantic** | >=2.5.0 | **Espinha dorsal dos contratos.** Todos os modelos do sistema (AgentSpec, RunContext, ExecutionEvent, RouterDecision, CoordinationPlan, etc.) são BaseModel Pydantic. Validação de schemas, serialização JSON, validators customizados. |
| **pydantic-settings** | 2.x | Configuração via environment variables (`MiniAutoGenSettings`). |
| **typing-extensions** | >=4.9.0 | `Protocol`, `runtime_checkable`, `TypeVar` para contratos tipados. |

**Por que Pydantic v2 (e não dataclasses):** Validação em runtime, serialização JSON nativa, `model_validator` para regras cross-field (ex: `RouterDecision` valida que `terminate XOR next_agent`), e `Field` com defaults e constraints.

### 2.3 Persistência

| Pacote | Versão | Papel no MiniAutoGen |
|---|---|---|
| **sqlalchemy** | >=2.0.23 | ORM + SQL toolkit. `async_sessionmaker` para sessões async. `DeclarativeBase` para modelos. JSON payload columns para schema flexível. Usado em RunStore, CheckpointStore, MessageStore. |
| **aiosqlite** | >=0.19.0 | Driver SQLite async para SQLAlchemy. Default para desenvolvimento local. |

**Pattern:** Minimal schema (id + timestamps + JSON payload). Sem migrations complexas — o payload JSON absorve evolução de schema.

### 2.4 Observabilidade

| Pacote | Versão | Papel no MiniAutoGen |
|---|---|---|
| **structlog** | >=24.0.0 | **Logging estruturado.** Bound loggers com contexto (run_id, correlation_id, scope). Output JSON para produção, output humano para dev. Integrado com o EventSink — cada ExecutionEvent é logado com contexto completo. |

**Por que structlog (e não logging stdlib):** Context binding (adiciona run_id/correlation_id automaticamente), processadores composáveis (filtros, formatadores), output JSON-serializable para ingestão por Datadog/ELK/etc.

### 2.5 Resiliência

| Pacote | Versão | Papel no MiniAutoGen |
|---|---|---|
| **tenacity** | >=8.2.0 | Retry com backoff exponencial, selective exception types, stop conditions. `build_retrying_call()` wrapa async functions com `AsyncRetrying`. Usado em RetryPolicy e nos LLM providers. |

### 2.6 HTTP & Networking

| Pacote | Versão | Papel no MiniAutoGen |
|---|---|---|
| **httpx** | >=0.28.0 | Cliente HTTP async. Usado em AgentAPIDriver para endpoints OpenAI-compatible, e em backends que comunicam via HTTP. |
| **fastapi** | >=0.115.0 | Framework web async. Servidor do Workspace — expõe Flows e Agents como API REST. |
| **uvicorn** | >=0.32.0 | Servidor ASGI. Executa o FastAPI em produção. |

### 2.7 CLI & TUI

| Pacote | Versão | Papel no MiniAutoGen | Extra |
|---|---|---|---|
| **click** | >=8.0 | Framework CLI. 12+ comandos: init, check, run, sessions, engine, agent, flow, server, doctor, dash, completions. | Obrigatório |
| **textual** | >=1.0.0 | Framework TUI. MiniAutoGen Dash — "Your AI Team at Work". Views para agents, events, flows, runs, engines, config. | `tui` |
| **rich** | (via textual) | Formatação terminal. Tabelas, cores, markdown rendering, progress bars. | Transitivo |

### 2.8 Providers LLM

| Pacote | Versão | Driver MiniAutoGen | Extra |
|---|---|---|---|
| **openai** | >=1.3.9 | OpenAISDKDriver | Obrigatório |
| **litellm** | >=1.16.12 | LiteLLMDriver (100+ providers) | Obrigatório |
| **anthropic** | >=0.40.0 | AnthropicSDKDriver | `anthropic` |
| **google-genai** | >=1.0.0 | GoogleGenAIDriver | `google` |

**Estratégia multi-provider:** LiteLLM é o provider default (abstrai 100+ modelos). SDKs nativos (OpenAI, Anthropic, Google) são opcionais para quem precisa de features específicas do provider (streaming, tool calling nativo, etc.).

### 2.9 Configuração & Templating

| Pacote | Versão | Papel no MiniAutoGen |
|---|---|---|
| **pyyaml** | >=6.0 | Parsing de `miniautogen.yml` e configs YAML. |
| **ruamel-yaml** | >=0.18.0 | YAML com preservação de comentários. Round-trip editing de configs. |
| **jinja2** | >=3.1.0 | Template rendering. Prompts, geração de YAML no `init`, formatação de outputs. |
| **python-dotenv** | 1.0.0 | Carregamento de `.env` para environment variables. |

---

## 3. Dependências de Desenvolvimento

### 3.1 Testes

| Pacote | Versão | Papel |
|---|---|---|
| **pytest** | ^7.4.0 | Framework de testes. 336+ testes cobrindo unit, integration e E2E. |
| **pytest-asyncio** | ^0.23.0 | Suporte a testes async. Todos os testes de runtime são async. |
| **hypothesis** | ^6.130.0 | Property-based testing. Testes de propriedades para contratos Pydantic. |

### 3.2 Qualidade de Código

| Pacote | Versão | Papel | Configuração |
|---|---|---|---|
| **ruff** | ^0.15.0 | Linter + formatter. Substitui flake8, isort, black. | `line-length=100`, `select=["E","F","I"]`, `target-version="py310"` |
| **mypy** | ^1.9.0 | Type checker estático. | `check_untyped_defs=true`, `warn_unused_configs=true` |

### 3.3 Desenvolvimento

| Pacote | Versão | Papel |
|---|---|---|
| **ipykernel** | 6.28.0 | Jupyter kernel para notebooks de experimentação. |

---

## 4. Arquitetura de Drivers (Engines)

O `EngineResolver` mapeia engine names para drivers concretos:

| Engine Name | DriverType | Pacote Usado | Categoria |
|---|---|---|---|
| `openai` | OPENAI_SDK | `openai` (AsyncOpenAI) | API Provider |
| `anthropic` | ANTHROPIC_SDK | `anthropic` (AsyncAnthropic) | API Provider |
| `google` | GOOGLE_GENAI | `google-genai` | API Provider |
| `litellm` | LITELLM | `litellm` | API Provider (multi) |
| `openai-compat` | AGENT_API | `httpx` | API Provider (genérico) |
| `claude-code` | CLI | `anyio.open_process` | CLI Agent |
| `gemini-cli` | CLI | `anyio.open_process` | CLI Agent |
| `codex-cli` | CLI | `anyio.open_process` | CLI Agent |

**CLIAgentDriver** usa `anyio.open_process()` para spawnar subprocessos. Comunicação via JSON no stdin/stdout (NDJSON). Sem dependência adicional — apenas AnyIO.

---

## 5. Configuração do Projeto

### 5.1 Build System

```toml
[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

- **Poetry** como gerenciador de dependências e build
- Virtual environment in-project (`.venv/`)

### 5.2 Entry Point

```toml
[tool.poetry.scripts]
miniautogen = "miniautogen.cli.main:cli"
```

### 5.3 Extras (Optional Groups)

```toml
[tool.poetry.extras]
tui = ["textual"]        # Dashboard TUI
anthropic = ["anthropic"] # Anthropic Claude SDK
google = ["google-genai"]  # Google Gemini SDK
```

### 5.4 Environment Variables

| Variável | Default | Propósito |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///miniautogen.db` | URL do banco de dados |
| `MINIAUTOGEN_DEFAULT_PROVIDER` | `litellm` | Provider LLM default |
| `MINIAUTOGEN_DEFAULT_MODEL` | `gpt-4o-mini` | Modelo default |
| `MINIAUTOGEN_DEFAULT_TIMEOUT_SECONDS` | `30.0` | Timeout de requests |
| `MINIAUTOGEN_DEFAULT_RETRY_ATTEMPTS` | `1` | Tentativas de retry |
| `MINIAUTOGEN_GATEWAY_BASE_URL` | — | URL do AgentAPI gateway |
| `MINIAUTOGEN_GATEWAY_API_KEY` | — | Chave de autenticação |

---

## 6. Decisões Técnicas e Justificativas

### Por que estas escolhas (e não as alternativas)

| Decisão | Escolha | Alternativas Rejeitadas | Justificativa |
|---|---|---|---|
| Async framework | **AnyIO** | asyncio puro, trio | Cancelamento estruturado, compatibility layer, task groups nativos |
| Validação | **Pydantic v2** | dataclasses, attrs, msgspec | Runtime validation, JSON schema, validators cross-field, BaseSettings |
| ORM | **SQLAlchemy 2.0 async** | Tortoise, Prisma, raw SQL | Maturidade, async nativo, JSON columns, ecosystem |
| HTTP client | **httpx** | aiohttp, requests | Async nativo, typing, HTTP/2, compatível com sync/async |
| Web framework | **FastAPI** | Flask, Starlette, Litestar | Pydantic nativo, async, OpenAPI auto, dependency injection |
| CLI | **Click** | argparse, typer, fire | Composição de commands, groups, extensibilidade, maturidade |
| TUI | **Textual** | curses, blessed, urwid | CSS-like styling, reactive widgets, async-first, Rich integration |
| Logging | **structlog** | logging stdlib, loguru | Context binding, structured output, processadores composáveis |
| LLM abstraction | **LiteLLM** | LangChain, custom | 100+ providers, drop-in replacement, sem lock-in |
| Retry | **tenacity** | stamina, backoff, custom | Async support, composable strategies, selective exceptions |
| YAML | **ruamel-yaml** | pyyaml, strictyaml | Round-trip (preserva comentários), YAML 1.2 |
| Linter | **ruff** | flake8 + isort + black | 100x mais rápido, substitui 3 ferramentas, configuração única |
| Type checker | **mypy** | pyright, pytype | Maturidade, ecosystem, strict mode |
| Testing | **pytest + hypothesis** | unittest, ward | Fixtures, parametrize, property-based, asyncio plugin |

---

## 7. Métricas do Projeto

| Métrica | Valor |
|---|---|
| **Dependências diretas** | 15 (obrigatórias) + 3 (opcionais) |
| **Dependências totais** (incluindo transitivas) | ~85 pacotes |
| **Módulos top-level** | 22 (`miniautogen/`) |
| **Testes** | 336+ (unit + integration + E2E) |
| **Event Types** | 47+ em 12 categorias |
| **Drivers implementados** | 7 (OpenAI, Anthropic, Google, LiteLLM, AgentAPI, CLI, Base) |
| **Coordination Modes** | 4 (Workflow, AgenticLoop, Deliberation, Composite) |
| **CLI Commands** | 12+ |
| **Python** | >=3.10, <3.12 |

---

## 8. Diagrama de Dependências

```
                          miniautogen
                              │
              ┌───────────────┼───────────────┐
              │               │               │
         core/kernel      adapters         shell
              │               │               │
    ┌─────────┤         ┌─────┤         ┌─────┤
    │         │         │     │         │     │
 pydantic   anyio    httpx  openai   click  textual
    │         │         │     │         │     │
 typing-  aiosqlite  fastapi litellm  rich  prompt-
 extensions    │      uvicorn  │             toolkit
              │         │   anthropic
          sqlalchemy    │   google-genai
              │         │
          structlog  tenacity
              │
           jinja2
           pyyaml
           ruamel-yaml
           python-dotenv
```

---

*Documento gerado em 2025-06-18 | Baseado em análise do `pyproject.toml`, `poetry.lock` e imports do codebase*
