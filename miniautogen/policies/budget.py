from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetPolicy:
    max_cost: float | None = None
