# MiniAutoGen New Architecture MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** levar o MiniAutoGen a um MVP funcional em que o caminho oficial de execução, persistência e integração use apenas a nova estrutura arquitetural, deixando o legado restrito a facades de compatibilidade.

**Architecture:** o corte final do MVP deve consolidar `PipelineRunner` como runtime oficial, completar a persistência mínima da nova arquitetura com `RunStore` e `CheckpointStore`, e remover o uso interno de `llms/` e `storage/` como caminhos primários. O legado continua importável, mas deixa de ser a rota principal do framework.

**Tech Stack:** Python 3.10+, Pydantic v2, AnyIO, SQLAlchemy 2.x, pytest, pytest-asyncio, Ruff, MyPy

---

## Definição de MVP

O projeto só pode ser considerado “100% funcional na nova estrutura” quando todas as condições abaixo forem verdadeiras:

- toda execução oficial passa por `miniautogen/core/runtime/pipeline_runner.py`
- `Chat`, `ChatAdmin` e os componentes principais dependem de `miniautogen.adapters.*` e `miniautogen.stores.*`
- `MessageStore`, `RunStore` e `CheckpointStore` possuem implementação em memória funcional
- existe ao menos um backend persistente simples para `RunStore` e `CheckpointStore`
- o legado em `miniautogen/llms` e `miniautogen/storage` não é mais usado internamente
- os testes provam que o caminho novo é o default

## Fora do Escopo Deste MVP

- instrumentação OpenTelemetry completa
- MCP
- `Instructor`
- `msgspec`
- migração para `uv`
- remoção física imediata das facades legadas

## Critério de Saída do Plano

- o caminho primário do framework usa apenas a nova arquitetura
- a compatibilidade legada fica restrita a facades finas
- a persistência mínima nova sustenta execução e checkpoint
- os testes de regressão, runtime, stores e compatibilidade passam com o caminho novo como padrão

### Task 1: Auditar o uso interno de APIs legadas

**Files:**
- Create: `docs/plans/backlog/new-architecture-mvp-audit.md`
- Modify: `docs/plans/2026-03-12-miniautogen-new-architecture-mvp.md`

**Step 1: Mapear usos internos de `miniautogen.storage`**

Run:

```bash
rg -n "miniautogen\\.storage|from miniautogen\\.storage|import miniautogen\\.storage" miniautogen tests
```

Expected: lista exata dos pontos que ainda dependem da camada legada.

**Step 2: Mapear usos internos de `miniautogen.llms`**

Run:

```bash
rg -n "miniautogen\\.llms|from miniautogen\\.llms|import miniautogen\\.llms|get_model_response" miniautogen tests
```

Expected: lista exata dos pontos que ainda dependem da fachada legada.

**Step 3: Registrar o inventário**

Criar `docs/plans/backlog/new-architecture-mvp-audit.md` com:

- arquivos que ainda usam `storage/*`
- arquivos que ainda usam `llms/*`
- classificação por prioridade: `bloqueia MVP`, `não bloqueia`, `compat apenas`

**Step 4: Commit**

```bash
git add docs/plans/backlog/new-architecture-mvp-audit.md docs/plans/2026-03-12-miniautogen-new-architecture-mvp.md
git commit -m "docs: audit legacy internal usage for new architecture mvp"
```

### Task 2: Tornar `LLMProvider` o contrato oficial do runtime

**Files:**
- Modify: `miniautogen/pipeline/components/components.py`
- Modify: `miniautogen/agent/agent.py`
- Modify: `miniautogen/chat/chatadmin.py`
- Create: `tests/adapters/llm/test_runtime_uses_provider_contract.py`

**Step 1: Escrever o teste que falha para o runtime novo**

```python
import pytest

from miniautogen.adapters.llm import LiteLLMProvider
from miniautogen.pipeline.components.components import LLMResponseComponent


class DummyProvider:
    async def generate_response(self, prompt, model_name=None, temperature=1.0):
        return "ok"


@pytest.mark.asyncio
async def test_llm_response_component_accepts_provider_contract():
    component = LLMResponseComponent(DummyProvider(), model_name="gpt-4o-mini")
    ...
```

**Step 2: Rodar o teste para garantir falha**

Run:

```bash
PYTHONPATH=. pytest tests/adapters/llm/test_runtime_uses_provider_contract.py -q
```

Expected: FAIL se o componente ainda depender exclusivamente de `get_model_response`.

**Step 3: Implementar a menor adaptação possível**

Atualizar `LLMResponseComponent` para:

- preferir `generate_response(...)` quando disponível
- cair para `get_model_response(...)` só como compatibilidade

Não alterar a semântica externa de resposta.

**Step 4: Rodar testes focados**

Run:

```bash
PYTHONPATH=. pytest tests/adapters/llm/test_provider_contract.py tests/adapters/llm/test_legacy_llm_client_compat.py tests/adapters/llm/test_runtime_uses_provider_contract.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/pipeline/components/components.py miniautogen/agent/agent.py miniautogen/chat/chatadmin.py tests/adapters/llm/test_runtime_uses_provider_contract.py
git commit -m "refactor: make llm provider the official runtime contract"
```

### Task 3: Tornar `MessageStore` o contrato oficial do chat

**Files:**
- Modify: `miniautogen/chat/chat.py`
- Modify: `miniautogen/chat/chatadmin.py`
- Modify: `miniautogen/pipeline/components/components.py`
- Create: `tests/stores/test_runtime_uses_message_store.py`

**Step 1: Escrever o teste que falha para o caminho oficial**

```python
import pytest

from miniautogen.chat.chat import Chat
from miniautogen.stores import InMemoryMessageStore


@pytest.mark.asyncio
async def test_chat_defaults_to_new_message_store():
    chat = Chat()
    assert isinstance(chat.repository, InMemoryMessageStore)
```

**Step 2: Rodar teste focado**

Run:

```bash
PYTHONPATH=. pytest tests/stores/test_runtime_uses_message_store.py -q
```

Expected: FAIL se o default ainda apontar para a fachada legada.

**Step 3: Ajustar o runtime e componentes**

Garantir que:

- `Chat()` usa `InMemoryMessageStore` como default real
- componentes e orchestration paths tratam `MessageStore` como contrato primário
- imports internos não referenciam `storage/*` como caminho principal

**Step 4: Rodar testes de stores e runtime**

Run:

```bash
PYTHONPATH=. pytest tests/stores tests/runtime tests/regression/test_chat_regression.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/chat/chat.py miniautogen/chat/chatadmin.py miniautogen/pipeline/components/components.py tests/stores/test_runtime_uses_message_store.py
git commit -m "refactor: make message store the official chat contract"
```

### Task 4: Implementar `InMemoryRunStore`

**Files:**
- Modify: `miniautogen/stores/run_store.py`
- Create: `miniautogen/stores/in_memory_run_store.py`
- Modify: `miniautogen/stores/__init__.py`
- Create: `tests/stores/test_in_memory_run_store.py`

**Step 1: Escrever o teste que falha**

```python
import pytest

from miniautogen.stores import InMemoryRunStore


@pytest.mark.asyncio
async def test_in_memory_run_store_roundtrip():
    store = InMemoryRunStore()
    await store.save_run("run-1", {"status": "started"})

    assert await store.get_run("run-1") == {"status": "started"}
```

**Step 2: Rodar o teste**

Run:

```bash
PYTHONPATH=. pytest tests/stores/test_in_memory_run_store.py -q
```

Expected: FAIL porque a implementação ainda não existe.

**Step 3: Implementar o mínimo**

Criar `InMemoryRunStore` usando `dict[str, dict[str, Any]]`.

**Step 4: Rodar teste focado**

Run:

```bash
PYTHONPATH=. pytest tests/stores/test_in_memory_run_store.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/stores/run_store.py miniautogen/stores/in_memory_run_store.py miniautogen/stores/__init__.py tests/stores/test_in_memory_run_store.py
git commit -m "feat: add in-memory run store for new runtime"
```

### Task 5: Implementar `InMemoryCheckpointStore`

**Files:**
- Modify: `miniautogen/stores/checkpoint_store.py`
- Create: `miniautogen/stores/in_memory_checkpoint_store.py`
- Modify: `miniautogen/stores/__init__.py`
- Create: `tests/stores/test_in_memory_checkpoint_store.py`

**Step 1: Escrever o teste que falha**

```python
import pytest

from miniautogen.stores import InMemoryCheckpointStore


@pytest.mark.asyncio
async def test_in_memory_checkpoint_store_roundtrip():
    store = InMemoryCheckpointStore()
    await store.save_checkpoint("run-1", {"step": "llm"})

    assert await store.get_checkpoint("run-1") == {"step": "llm"}
```

**Step 2: Rodar o teste**

Run:

```bash
PYTHONPATH=. pytest tests/stores/test_in_memory_checkpoint_store.py -q
```

Expected: FAIL porque a implementação ainda não existe.

**Step 3: Implementar o mínimo**

Criar `InMemoryCheckpointStore` com armazenamento por `run_id`.

**Step 4: Rodar teste focado**

Run:

```bash
PYTHONPATH=. pytest tests/stores/test_in_memory_checkpoint_store.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/stores/checkpoint_store.py miniautogen/stores/in_memory_checkpoint_store.py miniautogen/stores/__init__.py tests/stores/test_in_memory_checkpoint_store.py
git commit -m "feat: add in-memory checkpoint store for new runtime"
```

### Task 6: Adicionar backend persistente mínimo para runs

**Files:**
- Create: `miniautogen/stores/sqlalchemy_run_store.py`
- Modify: `miniautogen/stores/__init__.py`
- Create: `tests/stores/test_sqlalchemy_run_store.py`

**Step 1: Escrever o teste que falha**

```python
import pytest

from miniautogen.stores import SQLAlchemyRunStore


@pytest.mark.asyncio
async def test_sqlalchemy_run_store_roundtrip(tmp_path):
    store = SQLAlchemyRunStore(db_url=f"sqlite+aiosqlite:///{tmp_path / 'runs.db'}")
    await store.init_db()
    await store.save_run("run-1", {"status": "finished"})

    assert await store.get_run("run-1") == {"status": "finished"}
```

**Step 2: Rodar o teste**

Run:

```bash
PYTHONPATH=. pytest tests/stores/test_sqlalchemy_run_store.py -q
```

Expected: FAIL porque a store ainda não existe.

**Step 3: Implementar o mínimo**

Criar tabela simples com:

- `run_id`
- `payload_json`
- `updated_at`

**Step 4: Rodar teste focado**

Run:

```bash
PYTHONPATH=. pytest tests/stores/test_sqlalchemy_run_store.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/stores/sqlalchemy_run_store.py miniautogen/stores/__init__.py tests/stores/test_sqlalchemy_run_store.py
git commit -m "feat: add sqlalchemy run store for new architecture mvp"
```

### Task 7: Adicionar backend persistente mínimo para checkpoints

**Files:**
- Create: `miniautogen/stores/sqlalchemy_checkpoint_store.py`
- Modify: `miniautogen/stores/__init__.py`
- Create: `tests/stores/test_sqlalchemy_checkpoint_store.py`

**Step 1: Escrever o teste que falha**

```python
import pytest

from miniautogen.stores import SQLAlchemyCheckpointStore


@pytest.mark.asyncio
async def test_sqlalchemy_checkpoint_store_roundtrip(tmp_path):
    store = SQLAlchemyCheckpointStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'checkpoints.db'}"
    )
    await store.init_db()
    await store.save_checkpoint("run-1", {"step": "checkpoint"})

    assert await store.get_checkpoint("run-1") == {"step": "checkpoint"}
```

**Step 2: Rodar o teste**

Run:

```bash
PYTHONPATH=. pytest tests/stores/test_sqlalchemy_checkpoint_store.py -q
```

Expected: FAIL porque a store ainda não existe.

**Step 3: Implementar o mínimo**

Criar tabela simples com:

- `run_id`
- `payload_json`
- `updated_at`

**Step 4: Rodar teste focado**

Run:

```bash
PYTHONPATH=. pytest tests/stores/test_sqlalchemy_checkpoint_store.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/stores/sqlalchemy_checkpoint_store.py miniautogen/stores/__init__.py tests/stores/test_sqlalchemy_checkpoint_store.py
git commit -m "feat: add sqlalchemy checkpoint store for new architecture mvp"
```

### Task 8: Integrar `RunStore` e `CheckpointStore` ao `PipelineRunner`

**Files:**
- Modify: `miniautogen/core/runtime/pipeline_runner.py`
- Modify: `miniautogen/policies/execution.py`
- Create: `tests/core/runtime/test_runner_persists_run_lifecycle.py`

**Step 1: Escrever o teste que falha**

```python
import pytest

from miniautogen.core.runtime import PipelineRunner
from miniautogen.stores import InMemoryCheckpointStore, InMemoryRunStore


class DummyPipeline:
    async def run(self, state):
        return {"ok": True}


@pytest.mark.asyncio
async def test_runner_persists_run_lifecycle():
    run_store = InMemoryRunStore()
    checkpoint_store = InMemoryCheckpointStore()
    runner = PipelineRunner(run_store=run_store, checkpoint_store=checkpoint_store)

    await runner.run_pipeline(DummyPipeline(), {"ok": True})

    ...
```

**Step 2: Rodar o teste**

Run:

```bash
PYTHONPATH=. pytest tests/core/runtime/test_runner_persists_run_lifecycle.py -q
```

Expected: FAIL porque o runner ainda não persiste lifecycle.

**Step 3: Implementar a persistência mínima**

Persistir ao menos:

- criação de run com status inicial
- atualização de status final
- checkpoint final opcional do estado retornado

Não inventar replay completo nesta etapa.

**Step 4: Rodar testes do runtime**

Run:

```bash
PYTHONPATH=. pytest tests/core/runtime -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/core/runtime/pipeline_runner.py miniautogen/policies/execution.py tests/core/runtime/test_runner_persists_run_lifecycle.py
git commit -m "feat: persist run lifecycle in pipeline runner"
```

### Task 9: Aplicar `ExecutionPolicy` no caminho oficial do runner

**Files:**
- Modify: `miniautogen/core/runtime/pipeline_runner.py`
- Modify: `miniautogen/policies/execution.py`
- Create: `tests/core/runtime/test_runner_execution_policy.py`

**Step 1: Escrever o teste que falha**

```python
import anyio
import pytest

from miniautogen.core.runtime import PipelineRunner
from miniautogen.policies import ExecutionPolicy


class SlowPipeline:
    async def run(self, state):
        await anyio.sleep(0.2)
        return state


@pytest.mark.asyncio
async def test_runner_applies_execution_policy_timeout():
    runner = PipelineRunner(execution_policy=ExecutionPolicy(timeout_seconds=0.01))
    with pytest.raises(TimeoutError):
        await runner.run_pipeline(SlowPipeline(), {})
```

**Step 2: Rodar o teste**

Run:

```bash
PYTHONPATH=. pytest tests/core/runtime/test_runner_execution_policy.py -q
```

Expected: FAIL se o runner ainda ignorar a policy.

**Step 3: Implementar**

Fazer o runner:

- preferir `execution_policy.timeout_seconds` quando presente
- manter `timeout_seconds` explícito como override transitório

**Step 4: Rodar testes do runtime**

Run:

```bash
PYTHONPATH=. pytest tests/core/runtime -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/core/runtime/pipeline_runner.py miniautogen/policies/execution.py tests/core/runtime/test_runner_execution_policy.py
git commit -m "feat: apply execution policy in official runtime path"
```

### Task 10: Aplicar `RetryPolicy` só nos adapters

**Files:**
- Modify: `miniautogen/adapters/llm/providers.py`
- Modify: `miniautogen/policies/retry.py`
- Create: `tests/adapters/llm/test_retry_policy_in_provider.py`

**Step 1: Escrever o teste que falha**

```python
import pytest

from miniautogen.adapters.llm import LiteLLMProvider
from miniautogen.policies import RetryPolicy


class FlakyClient:
    def __init__(self):
        self.calls = 0

    async def get_model_response(self, prompt, model_name=None, temperature=1.0):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient")
        return "ok"


@pytest.mark.asyncio
async def test_provider_applies_retry_policy():
    provider = LiteLLMProvider(client=FlakyClient(), retry_policy=RetryPolicy(max_attempts=2))
    result = await provider.generate_response([{"role": "user", "content": "hello"}])

    assert result == "ok"
```

**Step 2: Rodar o teste**

Run:

```bash
PYTHONPATH=. pytest tests/adapters/llm/test_retry_policy_in_provider.py -q
```

Expected: FAIL porque a provider ainda não aplica policy.

**Step 3: Implementar o mínimo**

Aplicar retry apenas dentro dos adapters, sem colocar retry no core.

**Step 4: Rodar testes de adapters**

Run:

```bash
PYTHONPATH=. pytest tests/adapters/llm -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/adapters/llm/providers.py miniautogen/policies/retry.py tests/adapters/llm/test_retry_policy_in_provider.py
git commit -m "feat: apply retry policy at llm adapter boundary"
```

### Task 11: Parar de usar internamente `miniautogen.llms` e `miniautogen.storage`

**Files:**
- Modify: arquivos listados no inventário de `docs/plans/backlog/new-architecture-mvp-audit.md`
- Create: `tests/compat/test_legacy_modules_are_facades_only.py`

**Step 1: Escrever o teste que falha**

Criar teste que assegura duas coisas:

- o caminho primário usa `adapters/*` e `stores/*`
- os módulos legados continuam importáveis

**Step 2: Rodar o teste**

Run:

```bash
PYTHONPATH=. pytest tests/compat/test_legacy_modules_are_facades_only.py -q
```

Expected: FAIL até o corte interno estar completo.

**Step 3: Executar o corte**

Remover imports internos de:

- `miniautogen.storage.*`
- `miniautogen.llms.*`

Substituir por:

- `miniautogen.stores.*`
- `miniautogen.adapters.llm.*`

**Step 4: Rodar regressão completa**

Run:

```bash
PYTHONPATH=. pytest tests/regression tests/runtime tests/adapters tests/stores tests/compat -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen tests/compat/test_legacy_modules_are_facades_only.py
git commit -m "refactor: stop internal runtime usage of legacy modules"
```

### Task 12: Tornar o caminho novo o default comprovado

**Files:**
- Create: `tests/runtime/test_new_architecture_mvp_defaults.py`
- Modify: `tests/test_core.py`

**Step 1: Escrever os testes que falham**

Cobrir explicitamente:

- `Chat()` usa `InMemoryMessageStore`
- `PipelineRunner` é o runtime oficial
- `LLMResponseComponent` aceita provider novo
- eventos e persistência mínima são emitidos no caminho oficial

**Step 2: Rodar os testes**

Run:

```bash
PYTHONPATH=. pytest tests/runtime/test_new_architecture_mvp_defaults.py tests/test_core.py -q
```

Expected: FAIL até o default ficar 100% consistente.

**Step 3: Ajustar o que faltar**

Fazer apenas os ajustes mínimos para que o default real seja o caminho novo.

**Step 4: Rodar os testes focados**

Run:

```bash
PYTHONPATH=. pytest tests/runtime/test_new_architecture_mvp_defaults.py tests/test_core.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add tests/runtime/test_new_architecture_mvp_defaults.py tests/test_core.py miniautogen
git commit -m "test: prove new architecture defaults for mvp"
```

### Task 13: Hardening final do MVP

**Files:**
- Modify: `pyproject.toml`
- Modify: `docs/plans/backlog/new-architecture-mvp-audit.md`
- Create: `docs/plans/backlog/new-architecture-mvp-exit-checklist.md`

**Step 1: Atualizar a checklist de saída**

Registrar em `docs/plans/backlog/new-architecture-mvp-exit-checklist.md`:

- contratos oficiais
- stores mínimos
- runtime oficial
- policies mínimas aplicadas
- compatibilidade legada restante
- itens fora do MVP

**Step 2: Rodar as verificações finais**

Run:

```bash
ruff check miniautogen tests
PYTHONPATH=. pytest tests/test_core.py tests/regression tests/core tests/runtime tests/adapters tests/stores tests/compat tests/observability tests/policies tests/properties -q
python -m mypy miniautogen/core miniautogen/adapters miniautogen/stores miniautogen/compat miniautogen/policies miniautogen/observability
```

Expected:

- `ruff`: PASS
- `pytest`: PASS
- `mypy`: PASS ou baseline documentado com escopo residual explícito

**Step 3: Registrar o status do legado**

Atualizar `docs/plans/backlog/new-architecture-mvp-audit.md` com:

- removido do caminho principal
- ainda exposto apenas por compatibilidade
- pendente para remoção futura

**Step 4: Commit**

```bash
git add pyproject.toml docs/plans/backlog/new-architecture-mvp-audit.md docs/plans/backlog/new-architecture-mvp-exit-checklist.md
git commit -m "chore: finalize new architecture mvp hardening checklist"
```

## Verificação Final do MVP

Run:

```bash
ruff check miniautogen tests
PYTHONPATH=. pytest tests/test_core.py tests/regression tests/core tests/runtime tests/adapters tests/stores tests/compat tests/observability tests/policies tests/properties -q
python -m mypy miniautogen/core miniautogen/adapters miniautogen/stores miniautogen/compat miniautogen/policies miniautogen/observability
```

## Resultado Esperado

- o caminho principal do framework roda na nova arquitetura
- o legado permanece só como compatibilidade de import e API
- execução, stores e integração LLM usam contratos novos
- o projeto fica pronto para decidir depois entre remover o legado ou mantê-lo deprecado por mais uma versão
