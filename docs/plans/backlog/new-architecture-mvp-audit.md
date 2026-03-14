# New Architecture MVP Audit

## Uso interno de `miniautogen.storage`

### Não bloqueia o MVP

- `tests/stores/test_repository_compat.py`
- `tests/test_core.py`
- `tests/regression/test_repository_regression.py`
- `tests/runtime/test_chatadmin_runner_delegation.py`
- `tests/regression/test_chatadmin_regression.py`
- `tests/regression/test_chat_regression.py`
- `tests/runtime/test_chatadmin_runtime_regression.py`

### Compat apenas

- todos os usos encontrados de `miniautogen.storage.*` estão em testes de compatibilidade ou regressão

## Uso interno de `miniautogen.llms`

### Bloqueia o MVP

- `miniautogen/pipeline/components/components.py`
  - `LLMResponseComponent` ainda usa `get_model_response(...)` como caminho principal

### Não bloqueia o MVP

- `miniautogen/llms/llm_client.py`
  - módulo legado de fachada; deve continuar importável

### Compat apenas

- `tests/adapters/llm/test_legacy_llm_client_compat.py`

## Leitura atual

- `storage/*` já não bloqueia o MVP novo no runtime principal; está basicamente restrito a compatibilidade e testes
- o bloqueador real imediato é `LLMResponseComponent`, que ainda trata a API legada como contrato primário
- os próximos cortes devem priorizar:
  - provider contract no runtime
  - stores mínimos de `run` e `checkpoint`
  - persistência mínima integrada ao `PipelineRunner`

## Status após a rodada atual

### Removido do caminho principal

- `Chat()` usa `InMemoryMessageStore` como default
- `LLMResponseComponent` aceita `generate_response(...)` como caminho primário
- `PipelineRunner` já conhece `RunStore`, `CheckpointStore` e `ExecutionPolicy`

### Ainda exposto apenas por compatibilidade

- `miniautogen/llms/llm_client.py`
- `miniautogen/storage/repository.py`
- `miniautogen/storage/in_memory_repository.py`
- `miniautogen/storage/sql_repository.py`

### Pendente para remoção futura

- fallback legado para `get_model_response(...)` dentro do adapter/component
- facades legadas ainda importáveis por uma janela de compatibilidade
