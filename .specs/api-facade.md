# Spec: API Facade — CLI Access via miniautogen.api

> **Data:** 2026-05-15
> **Status:** Draft
> **Scope:** miniautogen/api/ + CLI services refactor + import boundary test pass
> **Invariantes respeitados:** Isolamento de adapters (CLI nao importa core/backends/stores/server diretamente)

---

## Contrato de Prompt

- 🎯 **Goal:** Eliminar a violação D3 — CLI importa módulos internos (`server.*`, `stores.*`, `core.runtime.*`, `core.events.*`, `core.contracts.*`, `backends.*`). Criar `miniautogen.api` como facade pública e refatorar os 4 ficheiros violadores. O `test_import_boundary.py` passa a verde.
- 🚧 **Constraint:** Zero breaking changes no comportamento da CLI. Todas as refatorações usam lazy imports (padrão já existente). A API facade re-exporta símbolos sem modificar lógica interna.
- 🛑 **Failure Condition:** `test_cli_does_not_import_internal_modules` falha (D3 continua violado). Testes CLI existentes quebram. Comando `send`, `chat`, `run --console`, `console` deixam de funcionar.

---

## User Stories

- Como **engenheiro do core**, quero que a CLI respeite a segregação D3 importando apenas de `miniautogen.api`, para que a arquitetura de camadas seja enforced.
- Como **developer da CLI**, quero uma função `create_runtime()` que abstraia o pattern repetitivo de criar AgentRuntime (EngineResolver → driver → run_context → initialize), para eliminar duplicação entre chat_service e send_service.

---

## Criterios de Aceitacao

- [ ] `miniautogen/api/__init__.py` existe com re-exportações e função `create_runtime()`
- [ ] `cli/services/chat_service.py` — imports forbidden substituídos por `from miniautogen.api import create_runtime, RunContext, NullEventSink`
- [ ] `cli/services/send_service.py` — imports forbidden substituídos por `from miniautogen.api import create_runtime, RunContext, NullEventSink`
- [ ] `cli/commands/console.py` — lazy imports forbidden substituídos por `from miniautogen.api import ...`
- [ ] `cli/commands/run.py` — lazy import forbidden substituído por `from miniautogen.api import create_app`
- [ ] `ruff` passa sem erros nos ficheiros alterados
- [ ] `mypy` passa sem erros nos ficheiros alterados
- [ ] `test_cli_does_not_import_internal_modules` passa (D3 OK)
- [ ] Todos os testes CLI existentes continuam a passar

---

## Invariantes Afetadas

- [x] **Isolamento de Adapters** — CLI só comunica com o core via miniautogen.api
- [ ] **Microkernel / PipelineRunner** — Nao afetado
- [ ] **Assincronismo Canónico (AnyIO)** — Nao afetado
- [ ] **Policies Laterais** — Nao afetado

---

## Dependencias

| Dependencia | Tipo | Status |
|-------------|------|--------|
| `chat_service.py`, `send_service.py` | Clientes da api | Refatorar imports |
| `console.py`, `run.py` | Clientes da api | Refatorar imports |
| `backends/engine_resolver.py` | Re-exportado | Nao alterado |
| `core/runtime/agent_runtime.py` | Re-exportado + usado em create_runtime | Nao alterado |
| `core/contracts/run_context.py` | Re-exportado | Nao alterado |
| `core/events/event_sink.py` | Re-exportado | Nao alterado |
| `server/app.py` | Re-exportado | Nao alterado |
| `tui/data_provider.py` | Re-exportado | Nao alterado |
| Stores (4 módulos) | Re-exportados | Nao alterado |
| `cli/config.py`, `cli/services/agent_ops.py` | Usados internamente por create_runtime | Nao alterados |

---

## Design

### Ficheiro: `miniautogen/api/__init__.py`

```python
"""Public API facade for CLI and external consumers.

All SDK interaction from CLI must go through this module.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from miniautogen.backends.engine_resolver import EngineResolver
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import NullEventSink
from miniautogen.core.runtime.agent_runtime import AgentRuntime
from miniautogen.server.app import create_app
from miniautogen.server.standalone_provider import StandaloneProvider
from miniautogen.stores.in_memory_event_store import InMemoryEventStore
from miniautogen.stores.in_memory_run_store import InMemoryRunStore
from miniautogen.stores.sqlalchemy_event_store import SQLAlchemyEventStore
from miniautogen.stores.sqlalchemy_run_store import SQLAlchemyRunStore
from miniautogen.tui.data_provider import DashDataProvider


async def create_runtime(
    project_root: Path,
    agent_name: str,
    run_id_prefix: str = "run",
    system_prompt: str = "",
) -> tuple[AgentRuntime, str]:
    """Load agent config, create driver, build and initialize AgentRuntime.

    Args:
        project_root: Path to the workspace root.
        agent_name: Name of the agent to use.
        run_id_prefix: Prefix for the auto-generated run ID.
        system_prompt: Optional override. Falls back to agent spec goal.

    Returns:
        Tuple of (initialized AgentRuntime, run_id).

    Raises:
        ValueError: If agent not found.
    """
    from miniautogen.cli.config import load_config, CONFIG_FILENAME
    from miniautogen.cli.services.agent_ops import load_agent_specs

    config = load_config(project_root / CONFIG_FILENAME)
    agent_specs = load_agent_specs(project_root)
    spec = agent_specs[agent_name]
    run_id = f"{run_id_prefix}-{uuid.uuid4().hex[:8]}"

    engine_resolver = EngineResolver()
    engine_name = getattr(spec, "engine_profile", None) or config.defaults.engine
    driver = engine_resolver.create_fresh_driver(engine_name, config)

    run_context = RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id=run_id,
    )

    runtime = AgentRuntime(
        agent_id=agent_name,
        driver=driver,
        run_context=run_context,
        event_sink=NullEventSink(),
        system_prompt=system_prompt or getattr(spec, "goal", None) or "",
    )
    await runtime.initialize()
    return runtime, run_id
```

### Alteração: `cli/services/chat_service.py`

Antes (linhas 15-16 + 71-72):
```python
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import NullEventSink
# ...
        from miniautogen.backends.engine_resolver import EngineResolver
        from miniautogen.core.runtime.agent_runtime import AgentRuntime
```

Depois:
```python
from miniautogen.api import create_runtime
```

E substituir o corpo de `ChatSession.create()`:
```python
    @classmethod
    async def create(
        cls,
        project_root: Path,
        agent_name: str | None = None,
    ) -> ChatSession:
        from miniautogen.cli.services.agent_ops import load_agent_specs

        config = load_config(project_root / CONFIG_FILENAME)
        agent_specs = load_agent_specs(project_root)
        if not agent_specs:
            raise ValueError(...)

        if agent_name is None:
            agent_name = next(iter(agent_specs))
        elif agent_name not in agent_specs:
            ...

        spec = agent_specs[agent_name]
        runtime, run_id = await create_runtime(
            project_root, agent_name, "chat",
            system_prompt=getattr(spec, "goal", None) or "",
        )
        return cls(agent_name=agent_name, runtime=runtime, run_id=run_id)
```

### Alteração: `cli/services/send_service.py`

Antes (linhas 15-17 + 42-43):
```python
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import NullEventSink
# ...
    from miniautogen.backends.engine_resolver import EngineResolver
    from miniautogen.core.runtime.agent_runtime import AgentRuntime
```

Depois:
```python
from miniautogen.api import create_runtime
```

E substituir corpo de `send_message()`:
```python
    runtime, run_id = await create_runtime(
        project_root, agent_name, "send",
        system_prompt="",
    )
    try:
        await runtime.initialize()
        response = await runtime.process(message)
    finally:
        await runtime.close()
```

### Alteração: `cli/commands/console.py`

Substituir todos os lazy imports por `from miniautogen.api import ...`.

Antes:
```python
    from miniautogen.server.app import create_app
    from miniautogen.server.standalone_provider import StandaloneProvider
    from miniautogen.stores.sqlalchemy_event_store import SQLAlchemyEventStore
    from miniautogen.stores.sqlalchemy_run_store import SQLAlchemyRunStore
    from miniautogen.stores.in_memory_event_store import InMemoryEventStore
    from miniautogen.stores.in_memory_run_store import InMemoryRunStore
```

Depois:
```python
    from miniautogen.api import (
        create_app,
        StandaloneProvider,
        SQLAlchemyEventStore,
        SQLAlchemyRunStore,
        InMemoryEventStore,
        InMemoryRunStore,
    )
```

### Alteração: `cli/commands/run.py`

Antes (linha 166):
```python
        from miniautogen.server.app import create_app
```

Depois:
```python
        from miniautogen.api import create_app
```

---

## Plano de Testes

| Teste | Tipo | O Que Verifica |
|-------|------|----------------|
| `test_cli_does_not_import_internal_modules` | Arquitetural | D3 — CLI nao importa módulos internos |
| Testes CLI existentes (167 tests) | Regressão | Comandos send, chat, run, console continuam a funcionar |
| `ruff check miniautogen/api/ miniautogen/cli/` | Estilo | Código formatado |
| `mypy miniautogen/api/ miniautogen/cli/` | Tipos | Tipagem correta |
