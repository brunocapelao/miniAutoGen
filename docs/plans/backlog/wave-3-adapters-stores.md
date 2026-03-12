# Wave 3: Adapters + Stores

## Entregas

- Introduzir `miniautogen.adapters.llm` com `LLMProvider`, `OpenAIProvider` e `LiteLLMProvider`.
- Introduzir `miniautogen.adapters.templates` com `TemplateRenderer` e `JinjaTemplateRenderer`.
- Introduzir `miniautogen.stores` com `MessageStore`, `InMemoryMessageStore`, `SQLAlchemyMessageStore`, `RunStore` e `CheckpointStore`.
- Manter `miniautogen.storage.*` como fachadas legadas de compatibilidade.
- Manter `miniautogen.llms.llm_client` como fachada legada sobre a nova camada de adapters.

## Arquivos centrais

- `miniautogen/adapters/llm/*`
- `miniautogen/adapters/templates/*`
- `miniautogen/stores/*`
- `miniautogen/storage/*`
- `miniautogen/llms/llm_client.py`
- `miniautogen/chat/chat.py`

## Verificação

- `ruff check miniautogen tests/adapters tests/stores`
- `PYTHONPATH=. pytest tests/adapters tests/stores -q`
- `PYTHONPATH=. pytest tests/test_core.py tests/regression tests/core/contracts tests/runtime tests/core/runtime tests/compat tests/adapters tests/stores -q`
- `mypy` focado na superfície nova, sem expandir para integrações ainda não estabilizadas
