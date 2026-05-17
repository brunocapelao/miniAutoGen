# MiniAutoGen

Biblioteca Python de microkernel para orquestração de pipelines e coordenação multi-agente assíncrona.

## Getting Started

```bash
pip install miniautogen
miniautogen init hello --template quickstart
cd hello
miniautogen send "Hello!" --agent assistant
```

See the [Quickstart Guide](docs/quickstart.md) for install -> first run in 5 minutes.

O MiniAutoGen fornece contratos tipados, runtimes de coordenação e policies transversais para construir sistemas multi-agente. A arquitetura separa rigorosamente o núcleo dos adapters externos, permitindo trocar providers LLM, stores e backends sem alterar lógica de domínio. Todo o fluxo de execução é assíncrono via AnyIO.

---

## Modos de coordenação

- **Workflow** -- execução sequencial de steps com agentes atribuídos
- **Deliberation** -- ciclos de contribuição e revisão entre pares
- **Agentic loop** -- loop conversacional com roteamento dinâmico
- **Team** -- orquestração hierárquica com Lead e colaboradores (Spec 015)
- **Composite** -- composição de subruns heterogêneos num único run

---

## Estado atual

- `PipelineRunner` como runtime oficial com timeout, checkpoint e lifecycle de eventos
- Contratos tipados em `core/contracts/` (Pydantic models e Protocol definitions)
- 5 stores especializados (messages, runs, checkpoints, effects, events) com backends InMemory e SQLAlchemy
- 11 policies transversais: budget, approval, retry, timeout, validation, permission, execution, chain, reactive, effect, semantic_cache
- 72 tipos de evento em 13 categorias para observabilidade via structlog
- Abstração de backend drivers com `AgentAPIDriver` para endpoints OpenAI-compatible
- CLI com 16 comandos e grupos: `init`, `check`, `run`, `send`, `chat`, `status`, `agent`, `engine`, `flow`, `sessions`, `server`, `console`, `daemon`, `dash`, `doctor`, `completions`
- Taxonomia canónica de erros com 8 categorias e `classify_error()` extensível
- Effect Engine com idempotência via `EffectInterceptor` e `EffectJournal`
- Supervisão hierárquica (StepSupervisor + FlowSupervisor) em todos os runtimes
- `RunStateMachine` com transições formais de estado (PENDING→RUNNING→terminal)
- `EventBus` assíncrono com subscrições tipadas e `ReactivePolicy`
- `CheckpointManager` para coordenação de checkpoint + eventos
- `HeartbeatToken` para detecção de agentes zombie
- `CircuitBreakerRegistry` global para circuit breaking partilhado

---

## Gemini CLI Integration

O MiniAutoGen suporta o uso do [Gemini CLI](https://github.com/google/gemini-cli) como motor LLM para agentes headless através de um gateway local compatível com a API da OpenAI.

### 1. Iniciar o Gateway
O gateway atua como uma ponte HTTP para o binário do Gemini.

```bash
# Instale as dependências e inicie o gateway
uvicorn gemini_cli_gateway.app:app --host 127.0.0.1 --port 8000
```

### 2. Configurar o Engine
No seu `miniautogen.yaml`, vincule o engine ao gateway:

```yaml
engines:
  gemini:
    kind: api
    provider: openai-compat
    endpoint: http://127.0.0.1:8000/v1
    model: gemini-2.0-flash
    timeout_seconds: 120

defaults:
  engine: gemini
```

### 3. Vincular Agentes
Os agentes podem agora usar o Gemini CLI de forma transparente:

```yaml
# agents/assistant.yaml
name: assistant
role: "Assistente útil"
goal: "Responder perguntas de forma concisa"
engine: gemini
```

Guia detalhado: [Gemini CLI Gateway](docs/pt/guides/gemini-cli-gateway.md)

---

## Backend drivers

Camada unificada de drivers para agentes externos:

- `AgentDriver` -- interface abstrata (start_session, send_turn, cancel_turn, close_session, capabilities)
- `AgentAPIDriver` -- driver HTTP para endpoints OpenAI-compatible (Gemini CLI gateway, LiteLLM, vLLM, Ollama)
- `BackendResolver` -- resolução config-driven com factory registry

Documentação: [Arquitetura](docs/pt/architecture/README.md)

---

## Web Console

Dashboard web para observação e controle de flows em tempo real.

```bash
# Modo produção (single port)
miniautogen console --port 8080

# Modo dev (API + frontend com hot reload)
miniautogen console --dev

# Com persistência
miniautogen console --db sqlite:///runs.db
```

Funcionalidades:
- Dashboard com contadores de agents, flows e runs
- CRUD completo de agents, flows e engines via interface web
- Settings editor e log viewer integrados
- Visualização de flows com React Flow (workflow e deliberation graphs)
- Trigger de runs via interface web com run tracking
- Event feed em tempo real (WebSocket com fallback para polling)
- Human-in-the-loop (approval list e modal)
- Standalone mode com store-backed data (SQLAlchemy ou in-memory)
- 134 frontend tests

---

## CLI reference

| Comando | Descrição |
|---------|-----------|
| `miniautogen init` | Criar novo workspace (templates: quickstart, minimal, advanced) |
| `miniautogen check` | Validar configuração |
| `miniautogen run` | Executar um flow |
| `miniautogen send` | Enviar mensagem a um agente |
| `miniautogen chat` | Chat interativo com um agente |
| `miniautogen status` | Estado atual do workspace e runs |
| `miniautogen agent` | Gerenciar agentes (create, list, show) |
| `miniautogen engine` | Gerenciar engines (create, list, show) |
| `miniautogen flow` | Gerenciar flows (create, list, show) |
| `miniautogen sessions` | Gerenciar sessões de execução |
| `miniautogen server` | Lançar API server |
| `miniautogen console` | Lançar web dashboard |
| `miniautogen daemon` | Executar em modo daemon |
| `miniautogen dash` | Lançar TUI dashboard |
| `miniautogen doctor` | Diagnóstico do ambiente |
| `miniautogen completions` | Shell completions |

---

## Documentação

- [Documentação em português](docs/pt/README.md)
- [Arquitetura atual (C4)](docs/pt/architecture/README.md)
- [Referência rápida dos módulos](docs/pt/quick-reference.md)

---

## Docker

```bash
docker-compose up
```

Dockerfile e docker-compose.yml incluídos para deploy containerizado.

---

## Testes

- 2,457+ testes Python (pytest + AnyIO)
- 134 testes frontend (Vitest)

---

## Exemplos executáveis

- [Tutorial da nova arquitetura](output/jupyter-notebook/miniautogen-nova-arquitetura-tutorial.ipynb)
- [Mini app com Gemini CLI](output/jupyter-notebook/miniautogen-mini-app-exemplo.ipynb)
- [Agentic loop com debate](output/jupyter-notebook/miniautogen-agentic-loop-debate.ipynb)
