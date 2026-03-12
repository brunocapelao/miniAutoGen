from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationPolicy:
    enabled: bool = True
