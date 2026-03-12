# MiniAutoGen Wave 3 Adapters and Stores Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the third wave of the MiniAutoGen architecture migration by formalizing adapter protocols and introducing the first real store family without breaking current behavior.

**Architecture:** This wave assumes the safety-net, core contracts, and initial runner compatibility already exist. It adds provider-neutral adapters around LLM, HTTP, and template concerns, then introduces explicit message, run, and checkpoint store contracts with initial in-memory and SQLite-backed implementations, while keeping the current repository abstraction alive as a compatibility bridge.

**Tech Stack:** Python 3.10+, Pydantic v2, pytest, pytest-asyncio, HTTPX, LiteLLM, Jinja, SQLAlchemy 2.x, aiosqlite

---

## Wave Scope

This wave covers:

- `adapters/http`
- `adapters/llm`
- `adapters/templates`
- `stores/message`
- `stores/run`
- `stores/checkpoint`
- compatibility bridges from `storage/*` to the new store family

This wave does not cover:

- full policy integration;
- OpenTelemetry exporters;
- MCP;
- final removal of `ChatRepository`;
- Postgres production adapter completion.

## Preconditions

- Regression suite from Wave 1 exists and passes.
- Core contracts from Wave 1 exist for `Message`, `RunContext`, `RunResult`, and `ExecutionEvent`.
- `PipelineRunner` and compatibility bridge from Wave 2 exist and keep the current runtime behavior stable.

## Definition of Done for the Wave

- HTTP adapters use `HTTPX` via a reusable client abstraction.
- LiteLLM is hidden behind a provider-neutral protocol.
- Jinja is hidden behind a template renderer protocol.
- `MessageStore`, `RunStore`, and `CheckpointStore` exist as explicit contracts.
- At least one in-memory implementation exists for all three stores.
- Initial SQLite-backed persistence exists for messages and runs, with checkpoint persistence scaffolded.
- Current repository-based flows still pass their regression tests.

### Task 1: Create Adapter Package Skeleton

**Files:**
- Create: `miniautogen/adapters/__init__.py`
- Create: `miniautogen/adapters/http/__init__.py`
- Create: `miniautogen/adapters/http/client.py`
- Create: `miniautogen/adapters/llm/__init__.py`
- Create: `miniautogen/adapters/llm/protocol.py`
- Create: `miniautogen/adapters/templates/__init__.py`
- Create: `miniautogen/adapters/templates/protocol.py`
- Create: `tests/adapters/test_adapter_package_layout.py`

**Step 1: Write the failing test**

```python
from miniautogen.adapters.http.client import HTTPClientAdapter
from miniautogen.adapters.llm.protocol import LLMProviderProtocol
from miniautogen.adapters.templates.protocol import TemplateRenderer


def test_adapter_protocols_and_clients_are_importable():
    assert HTTPClientAdapter.__name__ == "HTTPClientAdapter"
    assert LLMProviderProtocol.__name__ == "LLMProviderProtocol"
    assert TemplateRenderer.__name__ == "TemplateRenderer"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/adapters/test_adapter_package_layout.py -q`
Expected: FAIL with import errors for missing adapter modules.

**Step 3: Write minimal implementation**

```python
from typing import Any, Protocol


class LLMProviderProtocol(Protocol):
    async def complete(self, prompt: Any, *, model: str | None = None) -> str:
        ...


class TemplateRenderer(Protocol):
    async def render(self, template: str, context: dict[str, Any]) -> Any:
        ...


class HTTPClientAdapter:
    pass
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/adapters/test_adapter_package_layout.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/adapters tests/adapters/test_adapter_package_layout.py
git commit -m "feat: scaffold adapter package for wave 3"
```

### Task 2: Introduce Reusable HTTPX Client Adapter

**Files:**
- Modify: `miniautogen/adapters/http/client.py`
- Create: `tests/adapters/http/test_http_client_adapter.py`

**Step 1: Write the failing test**

```python
import pytest

from miniautogen.adapters.http.client import HTTPClientAdapter


@pytest.mark.asyncio
async def test_http_client_adapter_exposes_async_request_method():
    client = HTTPClientAdapter(base_url="https://example.com")
    assert hasattr(client, "request")
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/adapters/http/test_http_client_adapter.py -q`
Expected: FAIL because the adapter has no real constructor or request method.

**Step 3: Write minimal implementation**

```python
import httpx


class HTTPClientAdapter:
    def __init__(self, base_url: str | None = None, timeout_seconds: float = 10.0):
        self._client = httpx.AsyncClient(base_url=base_url or "", timeout=timeout_seconds)

    async def request(self, method: str, url: str, **kwargs):
        return await self._client.request(method, url, **kwargs)

    async def aclose(self):
        await self._client.aclose()
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/adapters/http/test_http_client_adapter.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/adapters/http/client.py tests/adapters/http/test_http_client_adapter.py
git commit -m "feat: add reusable HTTPX adapter"
```

### Task 3: Wrap LiteLLM Behind Provider-Neutral Adapter

**Files:**
- Modify: `miniautogen/llms/llm_client.py`
- Create: `miniautogen/adapters/llm/litellm_provider.py`
- Create: `tests/adapters/llm/test_litellm_provider.py`

**Step 1: Write the failing test**

```python
import pytest

from miniautogen.adapters.llm.litellm_provider import LiteLLMProvider


class FakeLiteLLMClient:
    async def get_model_response(self, prompt, model_name=None, temperature=1.0):
        return "ok"


@pytest.mark.asyncio
async def test_litellm_provider_hides_legacy_client_shape():
    provider = LiteLLMProvider(FakeLiteLLMClient())
    result = await provider.complete([{"role": "user", "content": "hello"}], model="demo")

    assert result == "ok"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/adapters/llm/test_litellm_provider.py -q`
Expected: FAIL because the wrapper does not exist.

**Step 3: Write minimal implementation**

```python
class LiteLLMProvider:
    def __init__(self, client):
        self._client = client

    async def complete(self, prompt, *, model=None):
        return await self._client.get_model_response(prompt, model_name=model)
```

Update `miniautogen/llms/llm_client.py` only as needed to keep the current client intact and compatible with the wrapper.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/adapters/llm/test_litellm_provider.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/adapters/llm/litellm_provider.py miniautogen/llms/llm_client.py tests/adapters/llm/test_litellm_provider.py
git commit -m "feat: wrap LiteLLM client in provider-neutral adapter"
```

### Task 4: Extract Jinja Template Renderer Adapter

**Files:**
- Create: `miniautogen/adapters/templates/jinja_renderer.py`
- Modify: `miniautogen/pipeline/components/components.py`
- Create: `tests/adapters/templates/test_jinja_renderer.py`

**Step 1: Write the failing test**

```python
import pytest

from miniautogen.adapters.templates.jinja_renderer import JinjaTemplateRenderer


@pytest.mark.asyncio
async def test_jinja_template_renderer_renders_context():
    renderer = JinjaTemplateRenderer()
    rendered = await renderer.render("Hello {{ name }}", {"name": "Bruno"})

    assert rendered == "Hello Bruno"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/adapters/templates/test_jinja_renderer.py -q`
Expected: FAIL because the renderer does not exist.

**Step 3: Write minimal implementation**

```python
from jinja2 import Environment, select_autoescape


class JinjaTemplateRenderer:
    def __init__(self):
        self._env = Environment(autoescape=select_autoescape())

    async def render(self, template: str, context: dict[str, object]) -> str:
        return self._env.from_string(template).render(context)
```

Update `Jinja2SingleTemplateComponent` to delegate rendering to this adapter without changing its public behavior.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/adapters/templates/test_jinja_renderer.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/adapters/templates/jinja_renderer.py miniautogen/pipeline/components/components.py tests/adapters/templates/test_jinja_renderer.py
git commit -m "feat: extract Jinja template adapter"
```

### Task 5: Create Message Store Contract and In-Memory Implementation

**Files:**
- Create: `miniautogen/stores/__init__.py`
- Create: `miniautogen/stores/message_store.py`
- Create: `miniautogen/stores/memory/__init__.py`
- Create: `miniautogen/stores/memory/message_store.py`
- Create: `tests/stores/test_message_store_contract.py`

**Step 1: Write the failing test**

```python
import pytest

from miniautogen.core.contracts.message import Message
from miniautogen.stores.memory.message_store import InMemoryMessageStore


@pytest.mark.asyncio
async def test_in_memory_message_store_is_append_only():
    store = InMemoryMessageStore()
    await store.append(Message(sender_id="user", content="hello"))
    await store.append(Message(sender_id="assistant", content="world"))

    items = await store.list_messages()
    assert [item.content for item in items] == ["hello", "world"]
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/stores/test_message_store_contract.py -q`
Expected: FAIL because the store package does not exist.

**Step 3: Write minimal implementation**

```python
class InMemoryMessageStore:
    def __init__(self):
        self._items = []

    async def append(self, message):
        self._items.append(message)

    async def list_messages(self):
        return list(self._items)
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/stores/test_message_store_contract.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/stores tests/stores/test_message_store_contract.py
git commit -m "feat: add append-only message store contract"
```

### Task 6: Add Run Store Contract and In-Memory Implementation

**Files:**
- Create: `miniautogen/stores/run_store.py`
- Create: `miniautogen/stores/memory/run_store.py`
- Create: `tests/stores/test_run_store_contract.py`

**Step 1: Write the failing test**

```python
import pytest

from miniautogen.stores.memory.run_store import InMemoryRunStore


@pytest.mark.asyncio
async def test_run_store_persists_and_updates_terminal_status():
    store = InMemoryRunStore()
    await store.create_run("run-1")
    await store.finish_run("run-1", status="succeeded")

    run = await store.get_run("run-1")
    assert run["status"] == "succeeded"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/stores/test_run_store_contract.py -q`
Expected: FAIL because the run store modules are missing.

**Step 3: Write minimal implementation**

```python
class InMemoryRunStore:
    def __init__(self):
        self._runs = {}

    async def create_run(self, run_id: str):
        self._runs[run_id] = {"run_id": run_id, "status": "running"}

    async def finish_run(self, run_id: str, *, status: str):
        self._runs[run_id]["status"] = status

    async def get_run(self, run_id: str):
        return self._runs[run_id]
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/stores/test_run_store_contract.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/stores/run_store.py miniautogen/stores/memory/run_store.py tests/stores/test_run_store_contract.py
git commit -m "feat: add run store contract and memory implementation"
```

### Task 7: Add Checkpoint Store Contract and In-Memory Implementation

**Files:**
- Create: `miniautogen/stores/checkpoint_store.py`
- Create: `miniautogen/stores/memory/checkpoint_store.py`
- Create: `tests/stores/test_checkpoint_store_contract.py`

**Step 1: Write the failing test**

```python
import pytest

from miniautogen.stores.memory.checkpoint_store import InMemoryCheckpointStore


@pytest.mark.asyncio
async def test_checkpoint_store_saves_and_reads_versioned_snapshot():
    store = InMemoryCheckpointStore()
    await store.save_checkpoint("run-1", "cp-1", {"value": 1}, schema_version="v1")

    checkpoint = await store.get_checkpoint("run-1", "cp-1")
    assert checkpoint["schema_version"] == "v1"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/stores/test_checkpoint_store_contract.py -q`
Expected: FAIL because checkpoint store modules are missing.

**Step 3: Write minimal implementation**

```python
class InMemoryCheckpointStore:
    def __init__(self):
        self._items = {}

    async def save_checkpoint(self, run_id, checkpoint_id, snapshot, *, schema_version):
        self._items[(run_id, checkpoint_id)] = {
            "run_id": run_id,
            "checkpoint_id": checkpoint_id,
            "snapshot": snapshot,
            "schema_version": schema_version,
        }

    async def get_checkpoint(self, run_id, checkpoint_id):
        return self._items[(run_id, checkpoint_id)]
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/stores/test_checkpoint_store_contract.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/stores/checkpoint_store.py miniautogen/stores/memory/checkpoint_store.py tests/stores/test_checkpoint_store_contract.py
git commit -m "feat: add checkpoint store contract and memory implementation"
```

### Task 8: Add SQLite Message Store and Run Store

**Files:**
- Create: `miniautogen/stores/sqlite/__init__.py`
- Create: `miniautogen/stores/sqlite/message_store.py`
- Create: `miniautogen/stores/sqlite/run_store.py`
- Create: `tests/stores/sqlite/test_sqlite_message_store.py`
- Create: `tests/stores/sqlite/test_sqlite_run_store.py`

**Step 1: Write the failing tests**

```python
import pytest

from miniautogen.core.contracts.message import Message
from miniautogen.stores.sqlite.message_store import SQLiteMessageStore


@pytest.mark.asyncio
async def test_sqlite_message_store_persists_messages(tmp_path):
    db_path = tmp_path / "messages.db"
    store = SQLiteMessageStore(f"sqlite+aiosqlite:///{db_path}")
    await store.init_db()
    await store.append(Message(sender_id="user", content="hello"))

    items = await store.list_messages()
    assert len(items) == 1
```

**Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/stores/sqlite -q`
Expected: FAIL because SQLite-backed stores do not exist.

**Step 3: Write minimal implementation**

Implement SQLite-backed stores using SQLAlchemy async with explicit tables for messages and runs. Keep checkpoint persistence scaffolded for the next task.

```python
async def init_db(self):
    async with self.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

**Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/stores/sqlite -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/stores/sqlite tests/stores/sqlite
git commit -m "feat: add initial SQLite-backed message and run stores"
```

### Task 9: Bridge `ChatRepository` to `MessageStore`

**Files:**
- Modify: `miniautogen/storage/repository.py`
- Modify: `miniautogen/storage/in_memory_repository.py`
- Modify: `miniautogen/storage/sql_repository.py`
- Create: `tests/compat/test_chat_repository_store_bridge.py`

**Step 1: Write the failing test**

```python
import pytest

from miniautogen.storage.in_memory_repository import InMemoryChatRepository


@pytest.mark.asyncio
async def test_chat_repository_bridge_preserves_list_order():
    repo = InMemoryChatRepository()
    await repo.add_message_from_content("user", "hello")
    await repo.add_message_from_content("assistant", "world")

    items = await repo.get_messages()
    assert [item.content for item in items] == ["hello", "world"]
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/compat/test_chat_repository_store_bridge.py -q`
Expected: FAIL because the compatibility helper does not exist.

**Step 3: Write minimal implementation**

Add compatibility helpers so repository implementations can internally delegate to `MessageStore` while preserving the current repository API.

```python
async def add_message_from_content(self, sender_id: str, content: str):
    message = Message(sender_id=sender_id, content=content)
    await self.add_message(message)
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/compat/test_chat_repository_store_bridge.py tests/regression -q`
Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/storage tests/compat/test_chat_repository_store_bridge.py
git commit -m "feat: bridge legacy chat repository to message store contract"
```

### Task 10: Add Wave-Level Integration Backlog and Acceptance Notes

**Files:**
- Create: `docs/plans/backlog/wave-3-adapters-stores.md`

**Step 1: Create the backlog note**

```md
# Wave 3 Adapters and Stores

- Packages:
  - `miniautogen/adapters/http`
  - `miniautogen/adapters/llm`
  - `miniautogen/adapters/templates`
  - `miniautogen/stores`
  - `miniautogen/storage`
- Done when:
  - adapters are protocol-driven
  - LiteLLM is wrapped
  - message/run/checkpoint stores exist
  - repository compatibility remains green
```

**Step 2: Run documentation grep**

Run: `rg -n "Done when|Packages:" docs/plans/backlog/wave-3-adapters-stores.md`
Expected: PASS

**Step 3: Commit**

```bash
git add docs/plans/backlog/wave-3-adapters-stores.md
git commit -m "docs: add wave 3 backlog acceptance notes"
```

## Wave Verification Sweep

After completing this wave, run:

```bash
PYTHONPATH=. pytest tests/adapters tests/stores tests/compat tests/regression -q
PYTHONPATH=. pytest tests/stores/sqlite -q
```

Expected:

- adapters are importable and protocol-driven;
- LiteLLM and Jinja are hidden behind explicit adapters;
- message, run, and checkpoint store contracts pass their tests;
- SQLite persistence works for messages and runs;
- current repository-based behavior still passes the regression suite.
