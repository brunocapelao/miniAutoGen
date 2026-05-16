# Plano Técnico: Local Endpoint Credentials

| Campo         | Valor       |
|---------------|-------------|
| Spec ID       | 010         |
| Data          | 2026-05-16  |
| Complexidade  | Quick       |

---

## Arquitetura Proposta

### Módulos Afetados

| Módulo / Caminho                                            | Tipo de Alteração       |
|-------------------------------------------------------------|-------------------------|
| `miniautogen/backends/openai_sdk/factory.py`                | Alterado                |
| `miniautogen/backends/errors.py`                            | Alterado (novo erro)    |
| `tests/backends/openai_sdk/test_factory.py`                 | Novo (ou alterado se existir) |

### Tabela de Decisão (host × api_key)

| `config.endpoint`                       | `api_key` resolvido | Comportamento                                                                 |
|-----------------------------------------|---------------------|-------------------------------------------------------------------------------|
| `None` / `""`                           | `None`              | `BackendConfigurationError("api_key required for default OpenAI endpoint")` |
| `None` / `""`                           | string              | Normal (api.openai.com com a chave fornecida)                                |
| `https://api.openai.com/v1`             | `None`              | `BackendConfigurationError` (mesma mensagem)                                 |
| `https://api.openai.com/v1`             | string              | Normal                                                                       |
| `https://eu.api.openai.com/v1`          | `None`              | `BackendConfigurationError` (qualquer host `*.openai.com`)                    |
| `http://localhost:11434/v1` (Ollama)    | `None`              | Inject `sk-noauth-local` + warning estruturado                                |
| `http://localhost:11434/v1`             | string              | Usa string fornecida (sem sentinela)                                          |
| `https://gateway.internal/v1`           | `None`              | Inject `sk-noauth-local` + warning                                            |

---

## Contratos e Interfaces

### Função auxiliar nova (privada, no factory)

```python
from urllib.parse import urlparse

_LOCAL_SENTINEL = "sk-noauth-local"
_OPENAI_HOSTS = ("api.openai.com",)


def _is_openai_host(endpoint: str | None) -> bool:
    """Return True if endpoint targets OpenAI's official hosts."""
    if not endpoint:
        return True  # endpoint omitido == default OpenAI
    host = (urlparse(endpoint).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in _OPENAI_HOSTS)
```

### Erro novo

```python
# miniautogen/backends/errors.py
class BackendConfigurationError(BackendError):
    """Raised when backend configuration is invalid or incomplete."""
    error_category = "configuration"  # taxonomia canônica
```

(Se `BackendError` ou taxonomia já existir, apenas reusar.)

### Factory ajustado

```python
def openai_sdk_factory(config: BackendConfig) -> OpenAISDKDriver:
    from openai import AsyncOpenAI
    import structlog

    api_key: str | None = None
    if config.auth and config.auth.type == "bearer" and config.auth.token_env:
        api_key = os.environ.get(config.auth.token_env)

    if api_key is None:
        if _is_openai_host(config.endpoint):
            raise BackendConfigurationError(
                "OpenAI endpoint requires an api_key. "
                f"Set the environment variable referenced by auth.token_env "
                f"(currently '{config.auth.token_env if config.auth else 'unset'}')."
            )
        # Endpoint local/custom — injeta sentinela
        api_key = _LOCAL_SENTINEL
        structlog.get_logger().warning(
            "openai_sdk.using_local_sentinel",
            endpoint=config.endpoint,
            reason="custom_endpoint_no_api_key",
        )

    metadata = config.metadata
    client_kwargs: dict = {"api_key": api_key}
    if config.endpoint:
        client_kwargs["base_url"] = config.endpoint
    client = AsyncOpenAI(**client_kwargs)
    return OpenAISDKDriver(
        client=client,
        model=metadata.get("model", "gpt-4o"),
        temperature=metadata.get("temperature", 0.2),
        max_tokens=metadata.get("max_tokens"),
        timeout_seconds=config.timeout_seconds,
    )
```

---

## Riscos e Mitigações

| Risco                                                              | Impacto | Mitigação                                                            |
|--------------------------------------------------------------------|---------|----------------------------------------------------------------------|
| Usuário aponta endpoint local que **exige** auth (ex: vLLM seguro) | Médio   | Sentinela ainda permite que o usuário passe `auth.token_env` real    |
| Usuário aponta `api.openai.com` por engano com sentinela           | Alto    | Heurística rejeita `*.openai.com` — falha cedo                       |
| Subdomínio inesperado da OpenAI (ex: `*.openai.com` regional)      | Médio   | `endswith(".openai.com")` cobre subdomínios                          |
| Sentinela aparece em logs de billing dos usuários                  | Baixo   | Warning estruturado dedicado permite filtrar/observar                |

---

## Estimativa de Complexidade

| Aspecto              | Estimativa |
|----------------------|------------|
| Ficheiros novos      | 0 (ou 1 teste)   |
| Ficheiros alterados  | 2 (factory + errors) |
| Testes novos         | 6+ casos   |
| Esforço estimado     | Quick (½ dia) |

---

## Sequência de Implementação

1. **Test-first:** escrever 6 testes em `tests/backends/openai_sdk/test_factory.py` cobrindo a tabela de decisão. Todos devem falhar inicialmente.
2. Adicionar `BackendConfigurationError` em `miniautogen/backends/errors.py` (se ausente).
3. Implementar `_is_openai_host` e refatorar `openai_sdk_factory` conforme tabela.
4. Verificar `pytest tests/backends/openai_sdk/test_factory.py` → 6/6 verdes.
5. Rodar `ruff check && mypy miniautogen/backends/openai_sdk/`.
6. Rodar suite completa para regressão.
7. Atualizar `docs/getting-started.md` ou `README.md` com nota: "Endpoints locais agora dispensam `OPENAI_API_KEY=dummy`".

---

## Notas

- A heurística por host é **branca-explícita** (denylist de `*.openai.com`), não blacklist genérico. Isso protege contra subdomínios futuros que a OpenAI possa registrar.
- O sentinela poderia ser configurável via env (`MINIAUTOGEN_LOCAL_SENTINEL`), mas isso é over-engineering — manter literal e auditável.
- Caso o spec `agent-driver-protocol.md` (010) saia primeiro, esta mudança continua válida pois opera dentro do adapter.
