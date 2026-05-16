from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

CheckpointReason = Literal["cancelled", "timed_out", "completed", "failed"]
OnCancelCallback = Callable[[CheckpointReason, dict], Awaitable[None]] | None


@dataclass(frozen=True)
class ExecutionPolicy:
    timeout_seconds: float | None = None
    graceful_save_timeout: float = 5.0
    on_cancel: OnCancelCallback = None
