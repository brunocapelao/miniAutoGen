from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionPolicy:
    timeout_seconds: float | None = None
