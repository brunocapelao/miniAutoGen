# Referência Rápida dos Módulos

Este documento resume os módulos vivos mais importantes do MiniAutoGen e substitui antigos guias dispersos por arquivo.

## Núcleo

### `miniautogen/core/contracts`

Contratos tipados para execução e integração:
- `Message`
- `RunContext`
- `RunResult`
- `ExecutionEvent`
- `RouterDecision`
- `ConversationPolicy`
- `AgenticLoopState`
- `ResearchOutput`
- `PeerReview`
- `DeliberationState`
- `FinalDocument`

### `miniautogen/core/runtime`

Runtime oficial da biblioteca.

Principal elemento:
- `PipelineRunner`: centraliza execução, timeout, run lifecycle, checkpoint e publicação de eventos.

Helpers deliberativos:
- `summarize_peer_reviews`
- `build_follow_up_tasks`
- `apply_leader_review`
- `render_final_document_markdown`
- `detect_stagnation`
- `should_stop_loop`

### `miniautogen/core/events`

Taxonomia e sinks de eventos do runtime.

## Composição

### `miniautogen/pipeline`

Mecanismo de composição por pipeline.

Elementos principais:
- `Pipeline`
- `PipelineComponent`
- `DynamicChatPipeline`
- componentes prontos em `pipeline/components/components.py`

## Domínio conversacional

### `miniautogen/chat`

Camada de chat e histórico de mensagens.

### `miniautogen/agent`

Representação de agentes e pipelines associados.

### `miniautogen/chat/chatadmin.py`

Coordenação de rodadas e execução do pipeline administrativo.

## Persistência

### `miniautogen/stores`

Stores especializados por responsabilidade:
- mensagens
- runs
- checkpoints

Inclui implementações em memória e com SQLAlchemy.

## Adapters

### `miniautogen/adapters/llm`

Integrações de motores LLM.

Principais adapters:
- `LiteLLMProvider`
- `OpenAIProvider`
- `OpenAICompatibleProvider`

## Aplicação

### `miniautogen/app`

Configuração, settings e factory de providers.

## Gemini CLI

### `gemini_cli_gateway`

Gateway local compatível com `/v1/chat/completions` para usar Gemini CLI sem acoplar subprocessos ao core do framework.

### `miniautogen/app/notebook_cache.py`

Cache simples para notebooks e demos longas com Gemini CLI real. Permite reexecução mais estável sem esconder o motor real.

## Onde aprofundar

- [Arquitetura atual](architecture/README.md)
- [Arquitetura alvo](target-architecture/README.md)
- [Guia do Gemini CLI Gateway](guides/gemini-cli-gateway.md)
