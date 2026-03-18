# Engine Architecture v2.1 — Design Specification

**Date:** 2026-03-18
**Status:** Approved
**Concept:** "Config → Resolve → Drive"

## Vision

Transform the engine from configuration storage into an execution binding layer. When an agent with `engine_profile: "gpt4o"` runs, the system automatically resolves the correct driver and calls the LLM.

## Research Summary

### Benchmarks Analyzed

| Product | Language | Key Pattern Adopted |
|---------|----------|-------------------|
| **OpenCode** | Go | 2-layer Provider/ProviderClient + baseProvider wrapper + message transformation |
| **OpenClaw** | Node.js | Fallback chains, model catalog as allowlist |
| **AWS CAO** | Python | CLI agent process isolation via tmux/subprocess |
| **AionUI** | — | Capability normalization ("same capabilities regardless of model") |

### LLM Library Decision

**Decision:** Replace LiteLLM dependency with direct provider SDKs.

**Rationale:**
- LiteLLM has 800+ open GitHub issues, dependency bloat (grpcio, mlflow, polars), OOM incidents
- Direct SDKs (openai, anthropic, google-genai) are lighter, more stable, async-native
- The `openai` SDK with `base_url` covers ALL OpenAI-compatible servers (Ollama, vLLM, LMStudio, OpenClaw)
- LiteLLM kept as OPTIONAL Tier 3 for users wanting 100+ providers

## Architecture

### Flow: Config → Resolve → Drive

```
EngineProfileConfig (YAML)
        │
        ▼
EngineResolver.resolve(profile_name, config)
        │
        ├── Maps provider → DriverType
        ├── Resolves ${ENV_VAR} → actual API key
        ├── Converts EngineProfileConfig → BackendConfig
        ├── Handles fallback chain resolution
        │
        ▼
BackendResolver.get_driver(backend_id)
        │
        ├── Looks up factory for DriverType
        ├── Instantiates driver (cached)
        │
        ▼
BaseDriver (wrapper)
        │
        ├── Sanitizes messages
        ├── Validates capabilities
        ├── Normalizes errors
        │
        ▼
Concrete AgentDriver
        │
        ├── OpenAISDKDriver (openai SDK)
        ├── AnthropicSDKDriver (anthropic SDK)
        ├── GoogleGenAIDriver (google-genai SDK)
        ├── AgentAPIDriver (httpx, OpenAI-compat — EXISTING)
        ├── LiteLLMDriver (litellm — optional)
        └── CLIAgentDriver (subprocess — Claude Code, Gemini CLI, Codex)
```

### Driver Taxonomy

```
kind: "api"
├── provider: "openai"         → OpenAISDKDriver
├── provider: "anthropic"      → AnthropicSDKDriver
├── provider: "google"         → GoogleGenAIDriver
├── provider: "openai-compat"  → AgentAPIDriver (EXISTING)
│   (covers: Ollama, vLLM, LMStudio, OpenClaw, any OpenAI-compat)
└── provider: "litellm"        → LiteLLMDriver (OPTIONAL)

kind: "cli"
├── provider: "claude-code"    → CLIAgentDriver + claude-agent-sdk
├── provider: "gemini-cli"     → CLIAgentDriver + subprocess
└── provider: "codex-cli"      → CLIAgentDriver + codex-python-sdk
```

### Provider → DriverType Mapping

```python
class DriverType(str, Enum):
    AGENT_API = "agentapi"          # Existing
    OPENAI_SDK = "openai_sdk"       # New
    ANTHROPIC_SDK = "anthropic_sdk" # New
    GOOGLE_GENAI = "google_genai"   # New
    LITELLM = "litellm"            # New
    CLI = "cli"                     # New (replaces ACP/PTY)

_PROVIDER_TO_DRIVER: dict[str, DriverType] = {
    "openai-compat": DriverType.AGENT_API,
    "openai": DriverType.OPENAI_SDK,
    "anthropic": DriverType.ANTHROPIC_SDK,
    "google": DriverType.GOOGLE_GENAI,
    "litellm": DriverType.LITELLM,
    "claude-code": DriverType.CLI,
    "gemini-cli": DriverType.CLI,
    "codex-cli": DriverType.CLI,
}
```

## Key Components

### 1. EngineProfileConfig v2.1

```python
class EngineProfileConfig(BaseModel):
    kind: Literal["api", "cli"] = "api"
    provider: str = "openai-compat"
    model: str | None = None
    endpoint: str | None = None
    api_key: str | None = None
    temperature: float = 0.2
    max_tokens: int | None = None
    timeout_seconds: float = 120.0
    fallbacks: list[str] = Field(default_factory=list)
    max_retries: int = 3
    retry_delay: float = 1.0
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### 2. EngineResolver

```python
class EngineResolver:
    """Converts EngineProfileConfig → AgentDriver (instantiated, cached)."""

    def __init__(self) -> None:
        self._resolver = BackendResolver()
        self._register_default_factories()

    def resolve(self, profile_name: str, config: ProjectConfig) -> AgentDriver:
        """Resolve engine profile to cached driver instance."""

    def resolve_with_fallbacks(
        self, profile_name: str, config: ProjectConfig
    ) -> AgentDriver:
        """Try primary engine, fall back to alternatives on failure."""

    def _engine_to_backend(
        self, name: str, engine: EngineProfileConfig
    ) -> BackendConfig:
        """Map EngineProfileConfig → BackendConfig."""

    def _resolve_api_key(self, api_key: str | None) -> str | None:
        """Resolve ${ENV_VAR} references to actual values."""
```

### 3. BaseDriver (Wrapper — inspired by OpenCode)

```python
class BaseDriver(AgentDriver):
    """Wraps any driver with sanitization, validation, error normalization."""

    def __init__(
        self, inner: AgentDriver, capabilities: BackendCapabilities
    ) -> None:
        self._inner = inner
        self._capabilities = capabilities

    async def send_turn(self, request: SendTurnRequest) -> AsyncIterator[AgentEvent]:
        sanitized = self._sanitize_messages(request.messages)
        request = request.model_copy(update={"messages": sanitized})
        try:
            async for event in self._inner.send_turn(request):
                yield self._normalize_event(event)
        except Exception as exc:
            yield self._error_event(exc, request.session_id)

    def _sanitize_messages(self, messages: list[dict]) -> list[dict]:
        """Remove empty messages, normalize roles, strip control chars."""

    def _normalize_event(self, event: AgentEvent) -> AgentEvent:
        """Ensure consistent event format regardless of provider."""

    def _error_event(self, exc: Exception, session_id: str) -> AgentEvent:
        """Convert any exception to a BACKEND_ERROR AgentEvent."""
```

### 4. MessageTransformer Protocol

```python
class MessageTransformer(Protocol):
    """Converts between internal format and provider-specific format."""

    def to_provider(self, messages: list[dict[str, Any]]) -> Any:
        """Internal messages → provider format."""
        ...

    def from_provider(self, response: Any, session_id: str, turn_id: str) -> list[AgentEvent]:
        """Provider response → AgentEvents."""
        ...
```

Each SDK driver implements its own transformer internally.

### 5. New Drivers

#### OpenAISDKDriver

```python
class OpenAISDKDriver(AgentDriver):
    """Direct OpenAI SDK driver. Async (httpx). Lightweight."""

    def __init__(self, api_key: str, model: str, **kwargs) -> None:
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key, **kwargs)
        self._model = model

    async def send_turn(self, request: SendTurnRequest) -> AsyncIterator[AgentEvent]:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=request.messages,
        )
        # Transform and yield AgentEvents

    async def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            streaming=True, tools=True, sessions=False,
        )
```

#### AnthropicSDKDriver

```python
class AnthropicSDKDriver(AgentDriver):
    """Direct Anthropic SDK driver. Async (httpx)."""

    def __init__(self, api_key: str, model: str, **kwargs) -> None:
        from anthropic import AsyncAnthropic
        self._client = AsyncAnthropic(api_key=api_key, **kwargs)
        self._model = model

    async def send_turn(self, request: SendTurnRequest) -> AsyncIterator[AgentEvent]:
        response = await self._client.messages.create(
            model=self._model,
            messages=self._transform_messages(request.messages),
            max_tokens=4096,
        )
        # Transform Anthropic response → AgentEvents
```

#### CLIAgentDriver

```python
class CLIAgentDriver(AgentDriver):
    """Runs CLI agent as subprocess with async IO."""

    def __init__(self, command: list[str], **kwargs) -> None:
        self._command = command

    async def send_turn(self, request: SendTurnRequest) -> AsyncIterator[AgentEvent]:
        async with await anyio.open_process(self._command) as proc:
            # Send messages via stdin (JSON)
            # Read responses via stdout (JSON lines)
            # Yield AgentEvents as they arrive

    async def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            streaming=True, tools=True, sessions=True, artifacts=True,
        )
```

## Packaging (Optional Extras)

```toml
[tool.poetry.extras]
tui = ["textual"]
openai = ["openai"]
anthropic = ["anthropic"]
google = ["google-genai"]
litellm = ["litellm"]
claude-code = ["claude-agent-sdk-python"]
all-providers = ["openai", "anthropic", "google-genai"]
all = ["textual", "openai", "anthropic", "google-genai"]
```

Tier 1 (always available): AgentAPIDriver via httpx (zero extra deps)
Tier 2 (recommended): openai, anthropic, google-genai SDKs
Tier 3 (optional): litellm, claude-agent-sdk

## Example YAML

```yaml
project:
  name: my-agents

defaults:
  engine_profile: fast-cheap

engine_profiles:
  # Tier 1: Any OpenAI-compatible server (zero extra deps)
  local-ollama:
    kind: api
    provider: openai-compat
    endpoint: http://localhost:11434/v1
    model: llama3.2

  # Tier 2: Direct SDK (best performance)
  fast-cheap:
    kind: api
    provider: openai
    model: gpt-4o-mini
    api_key: ${OPENAI_API_KEY}

  smart-premium:
    kind: api
    provider: anthropic
    model: claude-sonnet-4-20250514
    api_key: ${ANTHROPIC_API_KEY}
    capabilities: [streaming, tools]
    fallbacks: [fast-cheap, local-ollama]

  vision:
    kind: api
    provider: google
    model: gemini-2.5-pro
    api_key: ${GOOGLE_API_KEY}
    capabilities: [streaming, tools, multimodal]

  # Tier 3: CLI agent as engine
  claude-agent:
    kind: cli
    provider: claude-code
    model: claude-sonnet-4-20250514
    capabilities: [streaming, tools, artifacts]

agents:
  planner:
    engine_profile: smart-premium
    role: Architect

  writer:
    engine_profile: fast-cheap
    role: Developer

  reviewer:
    engine_profile: smart-premium
    role: QA Lead

  editor:
    engine_profile: local-ollama
    role: Refiner
```

## Deprecation Plan

| Component | Action | Timeline |
|-----------|--------|----------|
| `LLMProvider` (adapters/llm/protocol.py) | Deprecated, add DeprecationWarning | This release |
| `OpenAIProvider` | Replaced by OpenAISDKDriver | This release |
| `LiteLLMProvider` | Replaced by LiteLLMDriver (optional) | This release |
| `OpenAICompatibleProvider` | Absorbed by AgentAPIDriver | This release |
| `DriverType.ACP` | Replaced by DriverType.CLI | This release |
| `DriverType.PTY` | Replaced by DriverType.CLI | This release |

## What Does NOT Change

- `AgentDriver` ABC — unchanged
- `BackendResolver` — reused inside EngineResolver
- `SessionManager` + state machine — unchanged
- `AgentAPIClient` — unchanged (httpx + retry)
- `BackendConfig` — unchanged (extended with new DriverTypes)
- `AgentEvent`, `BackendCapabilities` — unchanged
- `ExecutionEvent` system — unchanged
- Microkernel invariants — preserved (no provider leaks into core)

## Build Order

Phase 0: Foundation (EngineResolver + BaseDriver + config updates)
Phase 1: Tier 1 driver (AgentAPIDriver already exists — wire it)
Phase 2: Tier 2 drivers (OpenAISDK, Anthropic, Google)
Phase 3: CLI drivers (CLIAgentDriver)
Phase 4: Fallback chains + capability enforcement
Phase 5: Deprecation of LLMProvider layer
Phase 6: Tests + integration verification
