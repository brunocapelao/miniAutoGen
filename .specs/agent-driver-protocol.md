# Spec: AgentDriverProtocol — Isolar Core de Backends

> **Data:** 2026-05-15
> **Status:** Draft
> **Scope:** core/contracts/agent_driver.py + backends/driver.py + agent_runtime.py type annotation + architecture test
> **Invariantes respeitados:** Isolamento de adapters (core nao importa classes concretas de backends)

---

## Contrato de Prompt

- 🎯 **Goal:** Eliminar a violação arquitetural P0.1 — o core (`agent_runtime.py`) importa `AgentDriver` concreto de `backends/driver.py`. Criar `AgentDriverProtocol` em `core/contracts/` e fazer o runtime depender do Protocol, nao da classe concreta.
- 🚧 **Constraint:** Zero breaking changes nas implementações concretas de driver (Anthropic, OpenAI, GenAI, CLI). A interface do Protocol espelha exatamente a ABC existente. Nao mover modelos (`backends/models.py`) para core/contracts/ — fora de scope.
- 🛑 **Failure Condition:** mypy ou pytest falham na branch; `AgentDriver` nao satisfaz `isinstance(driver, AgentDriverProtocol)`; qualquer teste existente quebra.

---

## User Stories

- Como **engenheiro do core**, quero que o runtime dependa de um Protocol (nao de uma classe concreta de adapter), para que a regra de ouro "Adapters nao vazam para core" seja enforced pelo type system.
- Como **developer de backend**, quero que os meus drivers concretos continuem a funcionar sem alterações, para que esta refatoraçao seja segura e incremental.

---

## Criterios de Aceitacao

- [ ] `core/contracts/agent_driver.py` existe com `AgentDriverProtocol` (Protocol + runtime_checkable), espelhando os 6 metodos de AgentDriver
- [ ] `backends/driver.py`: `AgentDriver` herda de `(ABC, AgentDriverProtocol)` — Duck typing válido, ABC continua funcional
- [ ] `agent_runtime.py:71`: o parametro `driver` muda de `AgentDriver` para `AgentDriverProtocol`
- [ ] `agent_runtime.py:27`: o import muda de `from miniautogen.backends.driver import AgentDriver` para `from miniautogen.core.contracts.agent_driver import AgentDriverProtocol`
- [ ] `ruff` passa sem erros
- [ ] `mypy` passa sem erros
- [ ] `pytest` — todos os testes existentes passam (0 regressoes)
- [ ] `tests/architecture/test_core_does_not_import_backends.py` — novo teste arquitetural que verifica que `core/runtime/` nao importa de `backends/` (AST scan)
- [ ] `isinstance(AgentDriver(...), AgentDriverProtocol)` retorna `True`

---

## Invariantes Afetadas

- [x] **Isolamento de Adapters** — AgentDriverProtocol implementa a barreira: core depende do tipo abstrato, backends fornecem a implementação concreta
- [ ] **Microkernel / PipelineRunner** — Nao afetado
- [ ] **Assincronismo Canónico (AnyIO)** — Nao afetado
- [ ] **Policies Laterais** — Nao afetado

---

## Dependencias

| Dependencia | Tipo | Status |
|-------------|------|--------|
| `backends/driver.py` (AgentDriver ABC) | Existente, vai herdar Protocol | Sem alteração de interface |
| `backends/models.py` (request/response models) | Importado pelo Protocol (residual) | Aceite — fora de scope mover modelos |
| `core/runtime/agent_runtime.py` | Cliente do Protocol | So muda anotação de tipo |
| Implementações concretas (Anthropic, OpenAI, GenAI, CLI drivers) | Clientes de AgentDriver ABC | Zero alterações necessárias |

---

## Design

### Ficheiro: `core/contracts/agent_driver.py`

```python
from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)


@runtime_checkable
class AgentDriverProtocol(Protocol):
    async def start_session(
        self, request: StartSessionRequest
    ) -> StartSessionResponse: ...

    def send_turn(
        self, request: SendTurnRequest
    ) -> AsyncIterator[AgentEvent]: ...

    async def cancel_turn(
        self, request: CancelTurnRequest
    ) -> None: ...

    async def list_artifacts(
        self, session_id: str
    ) -> list[ArtifactRef]: ...

    async def close_session(
        self, session_id: str
    ) -> None: ...

    async def capabilities(self) -> BackendCapabilities: ...
```

### Alteração em `backends/driver.py`

```python
from miniautogen.core.contracts.agent_driver import AgentDriverProtocol

class AgentDriver(ABC, AgentDriverProtocol):
    # corpo existente, sem alterações
    ...
```

### Alteração em `core/runtime/agent_runtime.py`

```python
# linha 27: antes
# from miniautogen.backends.driver import AgentDriver
# depois
from miniautogen.core.contracts.agent_driver import AgentDriverProtocol

# linha 71: antes
# driver: AgentDriver,
# depois
driver: AgentDriverProtocol,
```

### Teste arquitetural: `tests/architecture/test_core_does_not_import_backends.py`

```python
"""Architectural test: core must not import anything from backends/ or policies/.

Enforces §3 of CLAUDE.md: adapters and policies must not leak into core.
Uses AST scan, same pattern as tests/cli/test_import_boundary.py.
"""

from __future__ import annotations

import ast
from pathlib import Path

_CORE_DIR = Path(__file__).parent.parent.parent / "miniautogen" / "core"

_FORBIDDEN_IMPORTS = (
    "miniautogen.backends",
)

_ALLOWED_IMPORTS = (
    "miniautogen.backends.models",
)


def _collect_imports(filepath: Path) -> list[str]:
    source = filepath.read_text()
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def test_core_does_not_import_backends() -> None:
    """Scan all .py files in miniautogen/core/ for forbidden imports."""
    violations: list[str] = []
    for py_file in sorted(_CORE_DIR.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        imports = _collect_imports(py_file)
        for imp in imports:
            if not imp.startswith("miniautogen"):
                continue
            if any(imp.startswith(a) for a in _ALLOWED_IMPORTS):
                continue
    if any(imp.startswith(f) for f in _FORBIDDEN_IMPORTS):
        rel = py_file.relative_to(_CORE_DIR)
        violations.append(f"{rel}: imports {imp}")
    assert not violations, (
        "Core code imports from backends/ (invariant violation):\n"
        + "\n".join(f"  - {v}" for v in violations)
    )
```

---

## Notas de Implementação

- `send_turn` usa `def` (nao `async def`) porque retorna `AsyncIterator` — a convenção de `AgentDriver` é mantida no Protocol
- Os modelos (`backends/models.py`) continuam a ser importados pelo Protocol — isto é uma dependência residual aceite. Mover os modelos para `core/contracts/` seria um refactor separado que duplica o scope deste spec
- Nao há necessidade de tocar nas implementações concretas (drivers Anthropic, OpenAI, GenAI, CLI) — todas herdam de `AgentDriver` que por sua vez implementa `AgentDriverProtocol`

## Plano de Testes

| Teste | Tipo | O Que Verifica |
|-------|------|----------------|
| Testes existentes (pytest) | Regressão | Nada quebrou |
| `tests/architecture/test_core_does_not_import_backends.py` | Arquitetural | Core nao importa backends/ (gating regressao P0.1) |
| `isinstance(AgentDriver(...), AgentDriverProtocol)` | Runtime | Duck typing funcional |
| mypy —strict | Tipos | Protocol compatível com ABC |
