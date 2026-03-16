from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BudgetPolicy:
    """Policy for cost budget limits."""

    max_cost: float | None = None


class BudgetExceededError(Exception):
    """Raised when budget is exceeded."""


@dataclass
class BudgetTracker:
    """Tracks cost against a BudgetPolicy.

    Thread-safe for single-event-loop async usage.
    """

    policy: BudgetPolicy
    _spent: float = field(default=0.0, init=False)

    @property
    def spent(self) -> float:
        return self._spent

    @property
    def remaining(self) -> float | None:
        if self.policy.max_cost is None:
            return None
        return max(0.0, self.policy.max_cost - self._spent)

    def record(self, cost: float) -> None:
        """Record a cost. Raises BudgetExceededError if budget exceeded."""
        if cost < 0:
            raise ValueError("Cost cannot be negative")
        self._spent += cost
        if self.policy.max_cost is not None and self._spent > self.policy.max_cost:
            raise BudgetExceededError(
                f"Budget exceeded: spent {self._spent:.4f}, limit {self.policy.max_cost:.4f}"
            )

    def check(self) -> bool:
        """Return True if within budget, False if exceeded."""
        if self.policy.max_cost is None:
            return True
        return self._spent <= self.policy.max_cost
