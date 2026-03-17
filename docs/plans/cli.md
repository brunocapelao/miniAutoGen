# Tech Spec — Suporte a Backends de Agentes via ACP / Bridge / PTY no MiniAutoGen

**Projeto:** MiniAutoGen
**Tema:** Camada de integração unificada para agentes externos e CLIs de IA
**Status:** Proposta de implementação
**Objetivo:** permitir que o MiniAutoGen orquestre agentes externos de forma elegante, extensível e resiliente, priorizando protocolos estruturados e reduzindo ao mínimo a dependência de scraping de terminal.

---

## 1. Contexto

Hoje, o ecossistema de agentes de código e CLIs de IA está fragmentado. Existem três formas principais de integração:

1. **Protocolos estruturados**, como ACP, que padronizam a comunicação.
2. **Bridges/gateways**, que encapsulam CLIs e expõem uma interface mais limpa.
3. **Integrações de subprocesso/PTY**, para casos legados ou não padronizados.

O MiniAutoGen não deve acoplar seu core à implementação específica de um CLI, nem assumir que todos os backends falam o mesmo protocolo. O sistema deve:

* manter o core de orquestração independente dos detalhes do backend;
* adotar **ACP como caminho preferencial**;
* suportar bridges HTTP e integrações PTY como fallback;
* expor uma interface interna única de sessão, eventos e artefatos.

---

## 2. Objetivos

### 2.1 Objetivos principais

* Criar uma **camada unificada de drivers** para agentes externos.
* Permitir que o MiniAutoGen trate diferentes backends por uma interface comum.
* Priorizar **comunicação estruturada** sobre parsing frágil de terminal.
* Suportar **streaming de eventos**, sessões persistentes, cancelamento e coleta de artefatos.
* Permitir fallback progressivo:

  * ACP primeiro
  * bridge HTTP depois
  * PTY por último

### 2.2 Não objetivos

* Não transformar o MiniAutoGen em um clone de ACP.
* Não implementar um runtime de agente completo alternativo ao backend.
* Não suportar todos os CLIs do mercado na primeira versão.
* Não embutir lógica específica de fornecedor dentro do core.

---

## 3. Princípios de arquitetura

1. **Core-first**
   O centro do sistema é o runtime/orquestrador do MiniAutoGen, não o protocolo externo.

2. **Protocol agnostic core**
   ACP, HTTP bridge e PTY devem existir como drivers, não como forma dominante do domínio interno.

3. **Capability-driven design**
   Cada backend declara o que suporta:

   * sessões persistentes
   * streaming
   * cancelamento
   * tools
   * artefatos
   * retomada
   * multimodalidade

4. **Structured-first**
   Sempre preferir eventos estruturados e serializáveis.

5. **Fallback explícito**
   Se um backend depende de PTY/parsing, isso deve ser visível como limitação do driver.

---

## 4. Visão geral da solução

```text
+------------------------------------------------------+
|                  MiniAutoGen Core                    |
|------------------------------------------------------|
| Orchestrator | Policies | Memory | Scheduler | Trace |
+-------------------------+----------------------------+
                          |
                          v
+------------------------------------------------------+
|                Agent Driver Abstraction              |
|------------------------------------------------------|
| start_session | send_turn | stream_events | cancel   |
| resume        | get_artifacts | list_tools | close    |
+-------------------------+----------------------------+
                          |
        +-----------------+------------------+
        |                 |                  |
        v                 v                  v
+---------------+ +----------------+ +------------------+
| ACPDriver     | | AgentAPIDriver | | PTYDriver        |
| (preferred)   | | (bridge)       | | (fallback)       |
+---------------+ +----------------+ +------------------+
        |                 |                  |
        v                 v                  v
   ACP-compatible      HTTP bridge      CLI / subprocess /
      agents             service            interactive PTY
```

---

## 5. Arquitetura lógica

### 5.1 Camadas

#### A. Core Layer

Responsável por:

* execução de workflows multiagente;
* composição entre agentes;
* políticas de roteamento;
* gestão de memória;
* observabilidade;
* retries, timeouts e backpressure.

#### B. Contract Layer

Define a interface comum entre o core e qualquer backend.

#### C. Driver Layer

Implementações concretas:

* `ACPDriver`
* `AgentAPIDriver`
* `PTYDriver`

#### D. Backend Layer

Executáveis, serviços ou agentes externos.

---

## 6. Modelo de domínio

## 6.1 Entidades principais

### `AgentBackend`

Representa uma fonte de execução de agente.

Campos principais:

* `backend_id`
* `driver_type`
* `command` ou `endpoint`
* `capabilities`
* `config`
* `env`
* `metadata`

### `AgentSession`

Representa uma sessão de conversa/execução com um backend.

Campos:

* `session_id`
* `backend_id`
* `created_at`
* `status`
* `external_session_ref`
* `capabilities_snapshot`
* `context`

### `AgentTurn`

Uma interação unitária com o backend.

Campos:

* `turn_id`
* `session_id`
* `input_messages`
* `requested_tools`
* `attachments`
* `deadline`
* `metadata`

### `AgentEvent`

Evento emitido pelo backend durante execução.

Tipos esperados:

* `session_started`
* `message_delta`
* `message_completed`
* `tool_call_requested`
* `tool_call_result`
* `artifact_emitted`
* `warning`
* `error`
* `turn_completed`
* `session_closed`

### `Artifact`

Saída materializada gerada pelo backend.

Exemplos:

* arquivo
* patch
* plano
* JSON estruturado
* diff
* imagem
* log

---

## 7. Contrato interno do MiniAutoGen

A interface interna deve ser independente do protocolo externo.

## 7.1 Interface base

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal

CapabilityName = Literal[
    "sessions",
    "streaming",
    "cancel",
    "resume",
    "tools",
    "artifacts",
    "multimodal",
]

@dataclass(slots=True)
class BackendCapabilities:
    sessions: bool = False
    streaming: bool = False
    cancel: bool = False
    resume: bool = False
    tools: bool = False
    artifacts: bool = False
    multimodal: bool = False

@dataclass(slots=True)
class StartSessionRequest:
    backend_id: str
    system_prompt: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class StartSessionResponse:
    session_id: str
    external_session_ref: str | None
    capabilities: BackendCapabilities

@dataclass(slots=True)
class SendTurnRequest:
    session_id: str
    messages: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class CancelTurnRequest:
    session_id: str
    reason: str | None = None

@dataclass(slots=True)
class ArtifactRef:
    artifact_id: str
    kind: str
    name: str | None = None
    uri: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class AgentEvent:
    type: str
    session_id: str
    turn_id: str | None
    payload: dict[str, Any] = field(default_factory=dict)

class AgentDriver(ABC):
    @abstractmethod
    async def start_session(
        self,
        request: StartSessionRequest,
    ) -> StartSessionResponse: ...

    @abstractmethod
    async def send_turn(
        self,
        request: SendTurnRequest,
    ) -> AsyncIterator[AgentEvent]: ...

    @abstractmethod
    async def cancel_turn(
        self,
        request: CancelTurnRequest,
    ) -> None: ...

    @abstractmethod
    async def list_artifacts(
        self,
        session_id: str,
    ) -> list[ArtifactRef]: ...

    @abstractmethod
    async def close_session(
        self,
        session_id: str,
    ) -> None: ...

    @abstractmethod
    async def capabilities(self) -> BackendCapabilities: ...
```

---

## 8. Estratégia de drivers

## 8.1 `ACPDriver` — driver preferencial

### Responsabilidade

Integrar agentes compatíveis com ACP, direta ou indiretamente, usando uma superfície estruturada.

### Estratégia recomendada

Na V1, implementar o `ACPDriver` usando um cliente externo como backend operacional, por exemplo um executável headless ACP.

### Responsabilidades do driver

* iniciar sessão ACP;
* enviar turns;
* consumir stream de eventos;
* mapear eventos ACP para `AgentEvent`;
* encerrar sessão;
* detectar capabilities reais do backend.

### Vantagens

* comunicação estruturada;
* menor fragilidade;
* melhor alinhamento com futuro ecossistema;
* menor custo de manutenção.

### Limitações

* o backend precisa falar ACP, ou ser mediado por ferramenta compatível;
* nem todos os agentes terão o mesmo nível de suporte.

## 8.2 `AgentAPIDriver` — bridge HTTP

### Responsabilidade

Consumir serviços locais/remotos que encapsulam CLIs via API.

### Responsabilidades

* criar sessão HTTP lógica;
* enviar prompt/mensagens;
* consumir streaming HTTP/SSE/WebSocket quando suportado;
* mapear resposta para `AgentEvent`;
* lidar com autenticação e reconnect.

### Vantagens

* baixo esforço de integração;
* útil para CLIs que não falam ACP;
* simples de operar em ambientes distribuídos.

### Limitações

* ainda pode depender de emulação de terminal do outro lado;
* semântica de sessão pode variar;
* nem sempre há forte padronização de eventos.

## 8.3 `PTYDriver` — fallback de último recurso

### Responsabilidade

Executar CLIs interativos ou batch via subprocesso/PTY.

### Submodos

* `subprocess-batch`
* `subprocess-stream`
* `pty-interactive`

### Responsabilidades

* spawn de processo;
* envio de stdin;
* leitura incremental de stdout/stderr;
* timeouts;
* cancelamento;
* heurísticas mínimas de parsing;
* captura de artefatos em disco.

### Vantagens

* máxima compatibilidade;
* funciona com ferramentas legadas ou pouco padronizadas.

### Limitações

* alto custo de manutenção;
* parsing frágil;
* difícil garantir robustez.

---

## 9. Resolução de backend e seleção de driver

O MiniAutoGen deve suportar configuração declarativa de backends.

## 9.1 Exemplo de configuração

```yaml
agent_backends:
  claude_code:
    driver: acp
    launcher:
      command: ["acpx"]
    agent: "claude-code"
    capabilities:
      sessions: true
      streaming: true

  gemini_bridge:
    driver: agentapi
    endpoint: "http://127.0.0.1:8090"
    auth:
      type: bearer
      token_env: "AGENTAPI_TOKEN"

  legacy_cli:
    driver: pty
    command: ["legacy-agent", "--interactive"]
    parse_mode: "line"
    timeout_seconds: 180
```

## 9.2 Resolver

O sistema deve ter um `BackendResolver` responsável por:

* validar config;
* instanciar o driver correto;
* aplicar defaults;
* expor capabilities;
* testar disponibilidade do backend.

---

## 10. Detecção de capabilities

Capabilities não devem ser assumidas apenas pela configuração. Devem ser:

1. inferidas por tipo de driver;
2. enriquecidas por metadata/config;
3. confirmadas por handshake quando possível.

Exemplo:

* `ACPDriver` pode descobrir suporte a sessões e tools no handshake;
* `AgentAPIDriver` pode descobrir suporte a streaming por endpoint;
* `PTYDriver` em geral expõe somente `streaming` parcial e artefatos limitados.

---

## 11. Mapeamento de eventos

O core precisa de um formato consistente de eventos.

## 11.1 Eventos canônicos

```python
AGENT_EVENT_TYPES = {
    "session_started",
    "turn_started",
    "message_delta",
    "message_completed",
    "tool_call_requested",
    "tool_call_executed",
    "artifact_emitted",
    "warning",
    "error",
    "turn_completed",
    "session_closed",
}
```

## 11.2 Regras

* Eventos externos devem ser convertidos para o modelo canônico.
* Eventos desconhecidos podem ser emitidos como `warning` com payload bruto.
* Payload bruto pode ser armazenado em `raw_event` para debug.

## 11.3 Exemplo de conversão

Um chunk de texto vindo por stream do backend:

```python
AgentEvent(
    type="message_delta",
    session_id="sess_123",
    turn_id="turn_456",
    payload={"delta": "continuando a resposta..."},
)
```

---

## 12. Sessões

## 12.1 Objetivo

Padronizar o conceito de sessão mesmo quando o backend não a suporta nativamente.

## 12.2 Estratégia

* Se o backend suporta sessão real: usar `external_session_ref`.
* Se o backend não suporta: o MiniAutoGen simula sessão localmente e cada turn é independente.

## 12.3 Estados de sessão

* `created`
* `active`
* `busy`
* `interrupted`
* `completed`
* `failed`
* `closed`

---

## 13. Cancelamento e interrupção

Cancelamento deve ser suportado em diferentes níveis:

1. **Nativo**: backend/protocolo possui cancelamento.
2. **Best effort**: cancelar request HTTP ou matar processo.
3. **Cooperativo**: sinalizar interrupção e esperar encerramento.

O core deve sempre expor `cancel_turn()`, mesmo que internamente o driver faça apenas best effort.

---

## 14. Artefatos

## 14.1 Requisito

O MiniAutoGen deve tratar artefatos como entidade de primeira classe.

## 14.2 Tipos

* `file`
* `diff`
* `json`
* `image`
* `code`
* `transcript`
* `log`

## 14.3 Estratégia

* ACP/bridge: consumir artefatos estruturados quando existirem.
* PTY: descobrir artefatos por diretório de trabalho monitorado, padrões de output ou configuração explícita.

---

## 15. Observabilidade

## 15.1 Logging

Cada driver deve produzir logs estruturados:

* início e fim de sessão;
* backend selecionado;
* latência;
* bytes recebidos;
* erros;
* retries;
* cancelamentos.

## 15.2 Tracing

O core deve conseguir correlacionar:

* workflow id
* agent id
* backend id
* session id
* turn id

## 15.3 Debug raw

Modo opcional para guardar eventos crus do backend.

---

## 16. Tratamento de erro

## 16.1 Classes de erro sugeridas

```python
class AgentDriverError(Exception): ...
class BackendUnavailableError(AgentDriverError): ...
class SessionStartError(AgentDriverError): ...
class TurnExecutionError(AgentDriverError): ...
class EventMappingError(AgentDriverError): ...
class CancelNotSupportedError(AgentDriverError): ...
class ArtifactCollectionError(AgentDriverError): ...
```

## 16.2 Estratégia

* erros transitórios podem virar retry em drivers HTTP;
* erros de parsing em PTY devem gerar warning + raw capture;
* falhas no driver não devem corromper o core.

---

## 17. Segurança

### Requisitos

* isolamento de variáveis de ambiente por backend;
* allowlist de comandos para drivers PTY;
* diretório de trabalho controlado;
* timeouts configuráveis;
* limites de saída;
* sanitização de logs sensíveis.

### Riscos específicos

* execução arbitrária de comandos;
* vazamento de segredos em stdout/stderr;
* lock de processo interativo;
* crescimento indefinido de memória por stream.

---

## 18. Estrutura de módulos sugerida

```text
miniautogen/
  backends/
    __init__.py
    base.py
    resolver.py
    registry.py
    models.py

    acp/
      __init__.py
      driver.py
      mapper.py
      client.py
      handshake.py

    agentapi/
      __init__.py
      driver.py
      client.py
      mapper.py

    pty/
      __init__.py
      driver.py
      process.py
      parser.py
      artifact_discovery.py

  runtime/
    sessions.py
    events.py
    artifacts.py
    orchestration.py

  observability/
    logging.py
    tracing.py

  config/
    backend_schema.py
```

---

## 19. Roadmap de implementação

## Fase 1 — Fundamentos

### Entregas

* interface `AgentDriver`
* modelos base
* `BackendResolver`
* eventos canônicos
* persistência local de sessão
* testes de contrato

### Critério de pronto

* core consegue iniciar backend, enviar turn, consumir eventos e fechar sessão por interface única.

---

## Fase 2 — `ACPDriver`

### Entregas

* implementação inicial do `ACPDriver`
* handshake e descoberta de capabilities
* mapper ACP → `AgentEvent`
* suporte a streaming
* suporte a artefatos básicos

### Critério de pronto

* pelo menos um backend ACP funcional em fluxo ponta a ponta.

---

## Fase 3 — `AgentAPIDriver`

### Entregas

* cliente HTTP assíncrono
* suporte a request/response e streaming
* autenticação
* mapper bridge → `AgentEvent`

### Critério de pronto

* um backend HTTP bridge operacional com sessões e streaming.

---

## Fase 4 — `PTYDriver`

### Entregas

* subprocesso assíncrono
* modo PTY interativo
* timeout/cancelamento
* parser mínimo por linha/bloco
* descoberta básica de artefatos

### Critério de pronto

* um CLI legado integrado com comportamento estável suficiente.

---

## Fase 5 — Políticas avançadas

### Entregas

* roteamento por capability
* fallback automático entre drivers
* seleção por custo/latência
* retries e circuit breaker por backend

### Critério de pronto

* core escolhe backend de forma inteligente conforme perfil do agente.

---

## 20. Estratégia de testes

## 20.1 Testes de contrato

Todos os drivers devem passar pela mesma suíte:

* start session
* send turn
* stream events
* cancel
* list artifacts
* close session

## 20.2 Testes fake/mock

Criar backend fake com eventos previsíveis.

## 20.3 Testes de integração

* backend ACP real
* serviço bridge real
* CLI PTY real

## 20.4 Testes de resiliência

* timeout
* stream truncado
* evento inválido
* processo travado
* cancelamento em corrida
* reconexão HTTP

---

## 21. Decisões arquiteturais

## 21.1 Decisão

**ACP é o protocolo preferencial externo.**
**Não é o contrato interno do core.**

## 21.2 Decisão

**Drivers são plugins internos.**
O core não conhece detalhes de CLI, HTTP ou ACP.

## 21.3 Decisão

**PTY é fallback, não padrão.**

## 21.4 Decisão

**Sessão é conceito interno obrigatório**, ainda que simulada para alguns backends.

---

## 22. Exemplo de uso esperado

```python
resolver = BackendResolver(config)
driver = await resolver.get_driver("claude_code")

session = await driver.start_session(
    StartSessionRequest(
        backend_id="claude_code",
        system_prompt="Você é um engenheiro de software pragmático."
    )
)

async for event in driver.send_turn(
    SendTurnRequest(
        session_id=session.session_id,
        messages=[{"role": "user", "content": "Escreva um parser TOML mínimo."}],
    )
):
    print(event.type, event.payload)

artifacts = await driver.list_artifacts(session.session_id)
await driver.close_session(session.session_id)
```

---

## 23. Resultado esperado

Ao final dessa implementação, o MiniAutoGen terá:

* uma **camada unificada de integração de agentes**;
* suporte progressivo a múltiplos backends;
* menor acoplamento com CLIs específicos;
* um caminho elegante para crescer com o ecossistema ACP;
* fallback pragmático para casos legados;
* base sólida para recursos futuros como:

  * multiagente heterogêneo
  * replay de sessões
  * tracing entre agentes
  * cache e memória por backend
  * políticas de escalonamento

---

## 24. Resumo executivo

A implementação proposta adiciona ao MiniAutoGen uma arquitetura de backends baseada em **contrato interno estável + drivers pluggáveis**, com prioridade para **ACP**, suporte secundário a **HTTP bridges** e fallback por **PTY/subprocesso**.

Isso preserva a filosofia do MiniAutoGen:

* minimalista
* elegante
* modular
* extensível
* pragmático

sem transformá-lo em uma coleção de adapters frágeis e específicos por fornecedor.

Se você quiser, no próximo passo eu posso converter isso em uma **issue técnica real de GitHub**, já com:

* checklist de tarefas
* critérios de aceite
* estrutura de arquivos
* milestones de implementação.
