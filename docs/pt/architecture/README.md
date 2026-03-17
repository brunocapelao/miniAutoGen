# Arquitetura do MiniAutoGen

## Posicionamento

MiniAutoGen é um microkernel Python para coordenação multi-agente que oferece três modos de coordenação nativos -- workflow, deliberation e agentic loop -- composíveis via composite runtime. O kernel centraliza a gestão de contexto de execução (RunContext), emissão de eventos (42 tipos em 10 categorias), enforcement de políticas transversais e propagação de resultados (RunResult). Toda concorrência é estruturada via AnyIO, garantindo cancelamento determinístico e isolamento de falhas.

---

## Camadas da arquitetura

| Camada | Nome | Descrição |
|--------|------|-----------|
| 4 | API Pública | `miniautogen/api.py` -- ponto de entrada único, exporta 54 tipos |
| 3 | Padrões Canônicos | Reservada para padrões de composição reutilizáveis (não implementada) |
| 2 | Modos de Coordenação | WorkflowRuntime, DeliberationRuntime, AgenticLoopRuntime, CompositeRuntime -- implementam o protocolo CoordinationMode |
| 1 | Kernel | PipelineRunner, RunContext, RunResult, stores, eventos, políticas, adapters |

A comunicação entre camadas é estritamente descendente: a camada superior depende da inferior, nunca o inverso. A Camada 3 está reservada e não contém implementação no estado atual do código.

---

## Mapa de módulos

| Diretório | Responsabilidade |
|-----------|------------------|
| `core/contracts/` | Modelos Pydantic (30+) e definições de Protocol (WorkflowAgent, DeliberationAgent, ConversationalAgent) |
| `core/runtime/` | Implementações dos 4 modos de coordenação e PipelineRunner |
| `core/events/` | Constantes de tipos de evento e infraestrutura de event sinks |
| `pipeline/` | Abstrações Pipeline e PipelineComponent |
| `policies/` | 8 políticas transversais: budget, approval, retry, timeout, validation, permission, execution, chain |
| `adapters/` | Integração com provedores LLM (OpenAICompatibleProvider, LiteLLMProvider, OpenAIProvider) e templates Jinja2 |
| `stores/` | Camada de persistência: MessageStore, RunStore, CheckpointStore com backends InMemory e SQLAlchemy |
| `backends/` | Abstração unificada de drivers para agentes externos (AgentDriver ABC, AgentAPIDriver) |
| `observability/` | Infraestrutura de logging e LoggingEventSink |
| `cli/` | Interface de linha de comando: init, check, run, sessions (list/clean) |
| `chat/`, `agent/`, `compat/` | Módulos legados mantidos para compatibilidade retroativa |

---

## Diagrama de dependências

```mermaid
flowchart TB
    App["Aplicação Hospedeira"] --> API["API Pública (api.py)"]
    API --> Modes["Modos de Coordenação"]
    API --> Kernel["Microkernel (PipelineRunner)"]
    Modes --> WF["WorkflowRuntime"]
    Modes --> DL["DeliberationRuntime"]
    Modes --> AL["AgenticLoopRuntime"]
    Modes --> CR["CompositeRuntime"]
    Kernel --> Policies["Policies"]
    Kernel --> Events["Eventos (42 tipos)"]
    Kernel --> Stores["Stores"]
    Kernel --> Adapters["Adapters"]
    Adapters --> LLM["Provedores LLM"]
    Adapters --> Backends["Backend Drivers"]
```

---

## Leitura recomendada

1. [Contexto do sistema](01-contexto.md) -- fronteiras externas e atores que interagem com o MiniAutoGen
2. [Camadas e containers](02-containers.md) -- decomposição lógica detalhada de cada camada
3. [Componentes internos](03-componentes.md) -- contratos, protocolos e classes de cada módulo
4. [Fluxos de execução](04-fluxos.md) -- sequências de execução para cada modo de coordenação
5. [Invariantes e taxonomias](05-invariantes.md) -- regras arquiteturais invioláveis e taxonomia canônica de erros
6. [Decisões arquiteturais](06-decisoes.md) -- ADRs com contexto, decisão e consequências

---

## Escopo desta trilha

Esta trilha descreve:

- a biblioteca Python `miniautogen` como produto principal;
- a arquitetura microkernel com modos de coordenação composíveis;
- o mecanismo de eventos, políticas e persistência;
- a abstração de backend drivers para agentes externos;
- a integração com provedores de LLM via adapters tipados.

Esta trilha não cobre:

- documentação de contribuição ou versionamento;
- detalhamento da CLI ou guias de uso (consulte [guides/](../guides/)).
