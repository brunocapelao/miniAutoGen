# MiniAutoGen

Biblioteca Python de microkernel para orquestração de pipelines e coordenação multi-agente assíncrona.

## Getting Started

See the [Quickstart Guide](docs/quickstart.md) for install -> first run in 5 minutes.

O MiniAutoGen fornece contratos tipados, runtimes de coordenação e policies transversais para construir sistemas multi-agente. A arquitetura separa rigorosamente o núcleo dos adapters externos, permitindo trocar providers LLM, stores e backends sem alterar lógica de domínio. Todo o fluxo de execução é assíncrono via AnyIO.

---

## Modos de coordenação

- **Workflow** -- execução sequencial de steps com agentes atribuídos
- **Deliberation** -- ciclos de contribuição e revisão entre pares
- **Agentic loop** -- loop conversacional com roteamento dinâmico
- **Composite** -- composição de subruns heterogêneos num único run

---

## Estado atual

- `PipelineRunner` como runtime oficial com timeout, checkpoint e lifecycle de eventos
- Contratos tipados em `core/contracts/` (Pydantic models e Protocol definitions)
- 5 stores especializados (messages, runs, checkpoints, effects, events) com backends InMemory e SQLAlchemy
- 10 policies transversais: budget, approval, retry, timeout, validation, permission, execution, chain
- 72 tipos de evento em 13 categorias para observabilidade via structlog
- Abstração de backend drivers com `AgentAPIDriver` para endpoints OpenAI-compatible
- CLI com comandos `init`, `check`, `run`, `sessions` e `console`
- Taxonomia canónica de erros com 8 categorias e `classify_error()` extensível
- Effect Engine com idempotência via `EffectInterceptor` e `EffectJournal`
- Supervisão hierárquica (StepSupervisor + FlowSupervisor) em todos os 3 runtimes
- `RunStateMachine` com transições formais de estado (PENDING→RUNNING→terminal)
- `EventBus` assíncrono com subscrições tipadas e `ReactivePolicy`
- `CheckpointManager` para coordenação de checkpoint + eventos
- `HeartbeatToken` para detecção de agentes zombie
- `CircuitBreakerRegistry` global para circuit breaking partilhado

---

## Gemini CLI

Caminho suportado para usar Gemini CLI como motor LLM:

- `gemini_cli_gateway/` como gateway local compatível com `/v1/chat/completions`
- `OpenAICompatibleProvider` como adapter HTTP

Guia: [Gemini CLI Gateway](docs/pt/guides/gemini-cli-gateway.md)

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
- Visualização de flows com React Flow (workflow e deliberation graphs)
- Trigger de runs via interface web
- Event feed em tempo real (WebSocket com fallback para polling)
- Human-in-the-loop (approval list e modal)
- Standalone mode com store-backed data (SQLAlchemy ou in-memory)

---

## CLI reference

| Comando | Descrição |
|---------|-----------|
| `miniautogen init` | Criar novo workspace |
| `miniautogen check` | Validar configuração |
| `miniautogen run` | Executar um flow |
| `miniautogen sessions` | Gerenciar sessões de execução |
| `miniautogen dash` | Lançar TUI dashboard |
| `miniautogen console` | Lançar web dashboard |

---

## Documentação

- [Documentação em português](docs/pt/README.md)
- [Arquitetura atual (C4)](docs/pt/architecture/README.md)
- [Referência rápida dos módulos](docs/pt/quick-reference.md)

---

## Exemplos executáveis

- [Tutorial da nova arquitetura](output/jupyter-notebook/miniautogen-nova-arquitetura-tutorial.ipynb)
- [Mini app com Gemini CLI](output/jupyter-notebook/miniautogen-mini-app-exemplo.ipynb)
- [Agentic loop com debate](output/jupyter-notebook/miniautogen-agentic-loop-debate.ipynb)
