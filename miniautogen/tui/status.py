"""7-state status vocabulary for agent and step visualization.

Each status has a unique symbol (distinguishable without color for
accessibility), a color, and a human-readable label.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AgentStatus(str, Enum):
    """The 7 possible states for an agent or pipeline step."""

    DONE = "done"
    ACTIVE = "active"
    WORKING = "working"
    WAITING = "waiting"
    PENDING = "pending"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class StatusInfo:
    """Display metadata for a status state."""

    symbol: str
    color: str
    label: str

    def rich_markup(self) -> str:
        """Return a Rich markup string for this status."""
        return f"[{self.color}]{self.symbol} {self.label}[/{self.color}]"


class StatusVocab:
    """Maps AgentStatus to display information."""

    _LOOKUP: dict[AgentStatus, StatusInfo] = {
        AgentStatus.DONE: StatusInfo(
            symbol="\u2713",
            color="dim green",
            label="Done",
        ),
        AgentStatus.ACTIVE: StatusInfo(
            symbol="\u25cf",
            color="bright_green",
            label="Active",
        ),
        AgentStatus.WORKING: StatusInfo(
            symbol="\u25d0",
            color="yellow",
            label="Working",
        ),
        AgentStatus.WAITING: StatusInfo(
            symbol="\u231b",
            color="dark_orange",
            label="Waiting",
        ),
        AgentStatus.PENDING: StatusInfo(
            symbol="\u25cb",
            color="grey50",
            label="Pending",
        ),
        AgentStatus.FAILED: StatusInfo(
            symbol="\u2715",
            color="red",
            label="Failed",
        ),
        AgentStatus.CANCELLED: StatusInfo(
            symbol="\u2298",
            color="dark_red",
            label="Cancelled",
        ),
    }

    @classmethod
    def get(cls, status: AgentStatus) -> StatusInfo:
        """Get display info for a status."""
        return cls._LOOKUP[status]
