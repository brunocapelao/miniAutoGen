from __future__ import annotations

import time
from collections import deque

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from miniautogen.api import ExecutionEvent


class RichLiveEventSink:
    """Event sink that renders a live inline UI via Rich.

    Subscribes to canonical events and updates 3 zones:
    header, activity panel, last thoughts.
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

    def __enter__(self) -> RichLiveEventSink:
        self._started_at = time.monotonic()
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=self._refresh,
            transient=False,
        )
        self._live.__enter__()
        return self

    def __exit__(self, *exc: object) -> None:
        if self._live is not None:
            self._live.__exit__(*exc)
            self._live = None

    async def publish(self, event: ExecutionEvent) -> None:
        self._events_total += 1
        self._update_from_event(event)
        if self._live is not None:
            self._live.update(self._render())

    def _update_from_event(self, event: ExecutionEvent) -> None:
        payload = event.payload_dict()
        et = event.type
        if et == "run_started":
            self._flow = payload.get("flow_name", "")
            self._run_id = (payload.get("run_id") or event.run_id or "")[:8]
        elif et == "agent_turn_started":
            self._agent = payload.get("agent_id", "")
            self._action = payload.get("action", "Contribute")
            self._round = f"Round {payload.get('round', '?')}/{payload.get('max_rounds', '?')}"
            self._thoughts.clear()
        elif et in ("agent_thought", "agent_chunk"):
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
        body.append("\n")
        body.append("▶ ", style="bold cyan")
        body.append(self._agent or "(waiting)", style="bold")
        body.append(f"  · {self._action}", style="dim")
        if self._round:
            body.append(f"  · {self._round}", style="dim")
        body.append("\n\n")
        for line in self._thoughts:
            body.append("  └─ ", style="dim")
            body.append(f"{line}\n")

        footer = Text(
            f"\nEvents: {self._events_total}  ·  Press Ctrl+C to cancel & save",
            style="dim",
        )
        body.append(footer)
        return Panel(body, title=header, border_style="cyan", padding=(0, 1))
