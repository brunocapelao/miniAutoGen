# Plano Técnico: Rich Live CLI Runner

| Campo         | Valor       |
|---------------|-------------|
| Spec ID       | 012         |
| Data          | 2026-05-16  |
| Complexidade  | Medium      |

---

## Arquitetura Proposta

### Módulos Afetados

| Módulo / Caminho                                              | Tipo de Alteração       |
|---------------------------------------------------------------|-------------------------|
| `pyproject.toml`                                              | Alterado (dep `rich`)   |
| `miniautogen/cli/services/rich_live_sink.py`                  | Novo                    |
| `miniautogen/cli/commands/run.py`                             | Alterado (gating + sink wiring) |
| `miniautogen/cli/services/run_pipeline.py`                    | Alterado (aceita sink já wired) |
| `tests/cli/test_rich_live_sink.py`                            | Novo                    |
| `tests/cli/test_run_ui_gating.py`                             | Novo                    |
| `docs/getting-started.md`                                     | Alterado (screenshot/gif) |

### Layout do Live

```
┌─ miniautogen run · main · run_id=abc12345 · elapsed=02:14 ─┐
│                                                             │
│  ▶ Engenheiro de Dados  · Contribute · Round 2/5            │
│                                                             │
│  └─ "Proponho um pipeline streaming via Kafka particionado  │
│      por hash de CPF para isolar consumo PII..."            │
│                                                             │
│  Events: 47  ·  Press Ctrl+C to cancel & save               │
└─────────────────────────────────────────────────────────────┘
```

### Diagrama de fluxo

```
ExecutionEvent ──> CompositeEventSink ──┬──> InMemoryEventSink (always)
                                        ├──> _VerboseEventSink (if --verbose)
                                        ├──> RichLiveEventSink (if TTY + text + !verbose)
                                        └──> console_event_sink (if --console)
```

---

## Contratos e Interfaces

### `RichLiveEventSink`

```python
# miniautogen/cli/services/rich_live_sink.py
from __future__ import annotations

import time
from collections import deque
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text

from miniautogen.api import ExecutionEvent


class RichLiveEventSink:
    """Event sink that renders a live inline UI via Rich.

    Subscribes to canonical events and updates 3 zones:
    header, activity panel, last thoughts. Safe in non-TTY (no-op).
    """

    def __init__(
        self,
        *,
        console: Console | None = None,
        refresh_per_second: int = 8,
        thought_lines: int = 3,
    ) -> None:
        self._console = console or Console(stderr=True)
        self._refresh = refresh_per_second
        self._thoughts: deque[str] = deque(maxlen=thought_lines)
        self._flow: str = ""
        self._run_id: str = ""
        self._agent: str = ""
        self._action: str = ""
        self._round: str = ""
        self._events_total: int = 0
        self._started_at: float = 0.0
        self._live: Live | None = None

    def __enter__(self) -> "RichLiveEventSink":
        self._started_at = time.monotonic()
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=self._refresh,
            transient=False,
        )
        self._live.__enter__()
        return self

    def __exit__(self, *exc) -> None:
        if self._live is not None:
            self._live.__exit__(*exc)
            self._live = None

    async def publish(self, event: ExecutionEvent) -> None:
        self._events_total += 1
        self._update_from_event(event)
        if self._live is not None:
            self._live.update(self._render())

    def _update_from_event(self, event: ExecutionEvent) -> None:
        et = event.type
        payload = event.payload or {}
        if et == "run_started":
            self._flow = payload.get("flow_name", "")
            self._run_id = (payload.get("run_id") or event.run_id or "")[:8]
        elif et == "agent_turn_started":
            self._agent = payload.get("agent_id", "")
            self._action = payload.get("action", "Contribute")
            self._round = f"Round {payload.get('round', '?')}/{payload.get('max_rounds', '?')}"
            self._thoughts.clear()
        elif et == "agent_thought" or et == "agent_chunk":
            text = payload.get("text", "").strip()
            if text:
                self._thoughts.append(text[:80])
        elif et == "run_cancelled":
            self._action = "Saving checkpoint..."
        elif et == "run_timed_out":
            self._action = "Timeout — saving checkpoint..."
        elif et == "run_completed":
            self._action = "Done"

    def _render(self) -> Panel:
        elapsed = time.monotonic() - self._started_at
        elapsed_str = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
        header = f"miniautogen run · {self._flow} · run_id={self._run_id} · elapsed={elapsed_str}"

        body = Text()
        body.append("▶ ", style="bold cyan")
        body.append(self._agent or "(waiting)", style="bold")
        body.append(f"  · {self._action}", style="dim")
        if self._round:
            body.append(f"  · {self._round}", style="dim")
        body.append("\n\n")
        for line in self._thoughts:
            body.append(f"  └─ ", style="dim")
            body.append(f"{line}\n")

        footer = Text(f"\nEvents: {self._events_total}  ·  Press Ctrl+C to cancel & save", style="dim")
        body.append(footer)
        return Panel(body, title=header, border_style="cyan", padding=(0, 1))
```

### Gating na CLI (`cli/commands/run.py`)

```python
import os
import sys

def _select_ui_sink(
    *,
    output_format: str,
    verbose: bool,
) -> "RichLiveEventSink | _VerboseEventSink | None":
    """Decide which UI sink to use based on env, format, and TTY."""
    if output_format == "json":
        return None
    if os.environ.get("MINIAUTOGEN_NO_TTY") == "1":
        return _VerboseEventSink() if verbose else None
    if verbose:
        return _VerboseEventSink()
    if sys.stderr.isatty():
        from miniautogen.cli.services.rich_live_sink import RichLiveEventSink
        return RichLiveEventSink()
    return _VerboseEventSink()
```

E na chamada principal:

```python
ui_sink = _select_ui_sink(output_format=output_format, verbose=verbose)

# Remover o _Spinner antigo
spinner = None  # deprecated, kept only for non-TTY fallback if needed

cm = ui_sink if isinstance(ui_sink, RichLiveEventSink) else nullcontext()
with cm:
    result = run_async(
        execute_pipeline,
        config, pipeline_name, root,
        timeout=timeout,
        verbose=False,  # já injetado via ui_sink
        pipeline_input=pipeline_input,
        resume_run_id=resume,
        event_sink=ui_sink,
        console_event_sink=console_event_sink,
    )
```

### Ajuste em `execute_pipeline`

```python
async def execute_pipeline(
    ...,
    event_sink: Any = None,           # passa a aceitar o sink unificado
    console_event_sink: Any = None,
) -> dict[str, Any]:
    ...
    sinks: list[Any] = [internal_sink]
    if event_sink is not None:
        sinks.append(event_sink)
    if console_event_sink is not None:
        sinks.append(console_event_sink)
    effective_sink = CompositeEventSink(sinks=sinks) if len(sinks) > 1 else internal_sink
```

(O `_VerboseEventSink` original passa a ser construído pelo `_select_ui_sink`; deixa de ser instanciado dentro do `execute_pipeline`. O parâmetro `verbose: bool` continua existindo para retrocompat de chamadores não-CLI.)

---

## Riscos e Mitigações

| Risco                                                                | Impacto | Mitigação                                                                 |
|----------------------------------------------------------------------|---------|---------------------------------------------------------------------------|
| `Rich.Live` em terminais antigos (Windows Terminal pre-2021) quebra  | Médio   | `Console(stderr=True, force_terminal=False)` deixa Rich detectar; fallback automático |
| Eventos chegam mais rápido que 8 FPS → backlog                       | Baixo   | `Live` agrega; o sink só atualiza estado, o render acontece no tick fixo  |
| `Ctrl+C` durante render deixa cursor escondido                       | Médio   | `Live` tem `__exit__` que restaura cursor; usar `with`                    |
| Concorrência com `--console` (dois sinks ativos)                     | Baixo   | Composite suporta ambos; testar ordem de emit/update                      |
| Peso adicional do `rich` no install                                  | Baixo   | ~250 KB; aceitável para uma CLI                                           |
| Saída JSON contaminada com bytes ANSI                                | Alto    | `_select_ui_sink` retorna `None` para JSON → testado                      |

---

## Estimativa de Complexidade

| Aspecto              | Estimativa |
|----------------------|------------|
| Ficheiros novos      | 3 (sink + 2 testes) |
| Ficheiros alterados  | 3          |
| Testes novos         | ~6         |
| Esforço estimado     | Medium (3-5 dias) |

---

## Sequência de Implementação

1. Adicionar `rich>=13.0` em `pyproject.toml` → `uv sync` (ou `pip install -e .`).
2. **Test-first:** `tests/cli/test_run_ui_gating.py` com matrizes:
   - TTY + text + !verbose → `RichLiveEventSink`
   - TTY + text + verbose → `_VerboseEventSink`
   - TTY + json → `None`
   - !TTY + text → `_VerboseEventSink`
   - env `MINIAUTOGEN_NO_TTY=1` → fallback
3. **Test-first:** `tests/cli/test_rich_live_sink.py` — instanciar sink, alimentar 5 eventos sintéticos, verificar estado interno (`_agent`, `_thoughts`, `_events_total`).
4. Implementar `RichLiveEventSink` em `cli/services/rich_live_sink.py`.
5. Implementar `_select_ui_sink` e ajustar `cli/commands/run.py` (remover `_Spinner` ou manter como código morto comentado).
6. Ajustar `execute_pipeline` para aceitar o sink unificado.
7. Rodar testes → 6/6 verdes.
8. Smoke visual: gravar GIF de uma deliberação 3-agentes mostrando UI; salvar em `docs/assets/rich-live-demo.gif`.
9. Atualizar `docs/getting-started.md` com a GIF e nota sobre `MINIAUTOGEN_NO_TTY=1`.

---

## Notas

- **Coordenação com Item 2:** quando `graceful-cancel-checkpoint` lança o save shielded, o evento `run_cancelled` chega ao sink e atualiza `_action = "Saving checkpoint..."`. O `__exit__` do `Live` é acionado em seguida pelo `with` da CLI. Ordem importa: o save acontece **antes** do `Live` sair, garantindo que a mensagem fique visível.
- **Coordenação com Item 4:** se per-agent-timeouts disparar, o evento `agent_turn_timed_out` (a definir lá) atualiza o sink com `_action = "Timeout on this agent"`.
- **Acessibilidade:** logs estruturados continuam disponíveis via structlog. UI é puramente visual; nada de lógica passa por ela.
