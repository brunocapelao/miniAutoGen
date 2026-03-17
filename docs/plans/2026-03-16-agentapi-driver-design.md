# AgentAPIDriver — Design Document

**Data:** 2026-03-16
**Status:** Aprovado
**Fase do spec:** Phase 3 — `AgentAPIDriver` (HTTP bridge)
**Dependência:** Phase 1 — Backend Driver Abstraction (commit `3df504e`)

---

## Objetivo

Implementar o `AgentAPIDriver`, um cliente HTTP que implementa a interface `AgentDriver` e se conecta a qualquer endpoint OpenAI-compatible (como o `gemini_cli_gateway` existente). Este é o primeiro driver concreto sobre a abstração construída na Phase 1.

## Princípios

- **Thin HTTP Client** — o driver não sabe que backend está por trás. Fala OpenAI-compatible.
- **Sem acoplamento** — funciona com `gemini_cli_gateway`, mas também com qualquer outro bridge (LiteLLM proxy, vLLM, Ollama, etc.).
- **Sem streaming na V1** — request/response síncrono. O mapper é estruturado para facilitar adição futura de SSE.
- **Sessões lógicas** — o gateway não tem sessões nativas; o `SessionManager` do Phase 1 gere o lifecycle internamente.

---

## Arquitetura de Módulos

```
miniautogen/backends/agentapi/
  __init__.py          - exports AgentAPIDriver
  driver.py            - AgentAPIDriver (orquestra client + mapper)
  client.py            - AgentAPIClient (httpx wrapper com retry, auth, health check)
  mapper.py            - Conversão de response JSON → AgentEvent canônicos
```

### `client.py` — AgentAPIClient

Responsabilidades:
- Wrapper sobre `httpx.AsyncClient` com config de timeout, auth, e retry
- Health check configurável (endpoint, habilitado/desabilitado)
- POST para `/v1/chat/completions` com payload OpenAI-compatible
- Extração padronizada de mensagens de erro em respostas 4xx/5xx

```python
class AgentAPIClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
        connect_timeout: float = 10.0,
        health_endpoint: str | None = "/health",
        max_retry_attempts: int = 3,
        retry_delay: float = 1.0,
    ) -> None: ...

    async def health_check(self) -> bool: ...
    async def chat_completion(
        self, messages: list[dict[str, Any]], model: str | None = None,
    ) -> dict[str, Any]: ...
    async def close(self) -> None: ...
```

**Timeout strategy:**
- `httpx.Timeout(timeout_seconds, connect=connect_timeout)` no client
- `anyio.fail_after(timeout_seconds)` como camada extra no `send_turn`

**Retry:**
- Usa `tenacity` (padrão do codebase) para retries em erros transitórios (5xx, connection errors)
- Não retenta 4xx (erros do cliente)

**Health check:**
- Configurável via `health_endpoint` (default: `/health`)
- Se `None`, health check é desabilitado — o `start_session` assume disponibilidade
- Se falha, levanta `BackendUnavailableError`

**Extração de erros:**
- Tenta `response.json()` → procura `error.message`, `detail`, `message` (nesta ordem)
- Fallback: `response.text[:500]`

### `mapper.py` — ResponseMapper

Responsabilidades:
- Converter response JSON do gateway em sequência de `AgentEvent`
- Estruturado com funções separadas para facilitar extensão futura

```python
def map_completion_response(
    response_data: dict[str, Any],
    session_id: str,
    turn_id: str,
) -> list[AgentEvent]:
    """Converte uma response completa (não-streaming) em eventos canônicos.

    Retorna: [turn_started, message_completed, turn_completed]
    """

# Reservado para Phase futura:
# def map_streaming_chunk(chunk: dict, session_id, turn_id) -> AgentEvent | None
```

**Eventos emitidos (V1):**
1. `turn_started` — antes da request HTTP
2. `message_completed` — com `payload.text` extraído da response
3. `turn_completed` — após processamento completo

### `driver.py` — AgentAPIDriver

Responsabilidades:
- Implementa `AgentDriver` ABC
- Orquestra `AgentAPIClient` e `ResponseMapper`
- Gera `turn_id` (formato: `turn_{uuid4_short}`)
- Usa `anyio.fail_after` para timeout total no `send_turn`

```python
class AgentAPIDriver(AgentDriver):
    def __init__(self, client: AgentAPIClient, model: str | None = None) -> None: ...

    async def start_session(self, request) -> StartSessionResponse:
        # health check (se habilitado) → gerar session_id → retornar capabilities
        ...

    def send_turn(self, request) -> AsyncIterator[AgentEvent]:
        # yield turn_started → POST chat_completion → yield message_completed → yield turn_completed
        ...

    async def cancel_turn(self, request) -> None:
        raise CancelNotSupportedError("AgentAPIDriver does not support cancellation")

    async def list_artifacts(self, session_id) -> list[ArtifactRef]:
        return []

    async def close_session(self, session_id) -> None:
        pass  # sessão lógica, sem estado no backend

    async def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(sessions=False, streaming=False)
```

**Nota sobre `send_turn`:** Declarado como `def` (não `async def`) conforme D1. Implementado como `async def` + `yield` (async generator), que satisfaz o contrato `AsyncIterator`.

**Lifecycle do httpx client:** O `AgentAPIClient` mantém um `httpx.AsyncClient` interno que é reutilizado entre sessões. O `close()` do client fecha a conexão. O driver pode ser usado com context manager ou o `BackendResolver` pode chamar `close()` no shutdown.

---

## Configuração

### BackendConfig

```yaml
agent_backends:
  gemini_gateway:
    driver: agentapi
    endpoint: "http://127.0.0.1:8000"
    auth:
      type: bearer
      token_env: "GATEWAY_API_KEY"
    timeout_seconds: 60
    metadata:
      model: "gemini-2.5-pro"
      health_endpoint: "/health"
      connect_timeout: 10.0
      max_retry_attempts: 3
      retry_delay: 1.0
```

### Factory Registration

```python
def agentapi_factory(config: BackendConfig) -> AgentAPIDriver:
    client = AgentAPIClient(
        base_url=config.endpoint,
        api_key=_resolve_api_key(config.auth),
        timeout_seconds=config.timeout_seconds,
        health_endpoint=config.metadata.get("health_endpoint", "/health"),
        connect_timeout=config.metadata.get("connect_timeout", 10.0),
        max_retry_attempts=config.metadata.get("max_retry_attempts", 3),
        retry_delay=config.metadata.get("retry_delay", 1.0),
    )
    return AgentAPIDriver(client=client, model=config.metadata.get("model"))

resolver.register_factory(DriverType.AGENT_API, agentapi_factory)
```

---

## Tratamento de Erros

| Cenário | Erro | Retryable? |
|---------|------|-----------|
| Connection refused / DNS failure | `BackendUnavailableError` | Sim |
| Connection timeout | `BackendUnavailableError` | Sim |
| Read timeout | `TurnExecutionError` | Sim |
| HTTP 4xx | `TurnExecutionError` (detalhes no msg) | Não |
| HTTP 5xx | `TurnExecutionError` (transient) | Sim |
| Health check falha | `BackendUnavailableError` | — |
| Response JSON inválido | `EventMappingError` | Não |
| Campo `choices` ausente | `EventMappingError` | Não |
| `anyio.fail_after` timeout | `TurnExecutionError` | Não |

---

## Testes

| Ficheiro | Cobertura |
|----------|----------|
| `tests/backends/agentapi/test_client.py` | HTTP client: request/response, auth, retry, health check, error extraction |
| `tests/backends/agentapi/test_mapper.py` | Conversão JSON → AgentEvent, edge cases (missing fields, empty choices) |
| `tests/backends/agentapi/test_driver.py` | Driver completo com client mockado, sequência de eventos, timeouts |
| `tests/backends/agentapi/test_driver_contract.py` | Contract test suite parametrizada (mesmo suite do FakeDriver) |
| `tests/backends/agentapi/test_factory.py` | Factory + resolver + config integration |

**Mock strategy:** Usar `httpx.MockTransport` para simular respostas HTTP sem servidor real. Isso é mais rápido e determinístico que um fake server.

---

## Decisões Arquiteturais

1. **O driver é genérico** — funciona com qualquer endpoint OpenAI-compatible, não apenas Gemini.
2. **Health check é opcional** — `health_endpoint=None` desabilita. Nem todos os gateways têm `/health`.
3. **Retry vive no client, não no driver** — separação de concerns. O driver orquestra; o client lida com resiliência HTTP.
4. **Mapper preparado para streaming** — funções separadas para response completa vs. chunks SSE.
5. **httpx.AsyncClient é reutilizado** — connection pooling entre sessões. Fechado explicitamente via `close()`.
6. **Parâmetros extras via `metadata`** — `health_endpoint`, `connect_timeout`, `retry_*` vêm de `BackendConfig.metadata` para não poluir o modelo base.

---

## Fora de Escopo (V1)

- Streaming SSE (`text/event-stream`)
- Cancelamento de requests em andamento
- Coleta de artefatos
- Sessões persistentes no backend
- Autenticação OAuth/mTLS
- Rate limiting / circuit breaker
