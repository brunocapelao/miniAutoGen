"""Memory profile specification for the MiniAutoGen SDK.

Memory is a runtime-resolved capability, not a magic attribute.
The agent declares a profile; the runtime resolves it into
concrete retrieval, persistence, compaction, and injection.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MemoryProfile(BaseModel):
    """Concrete memory configuration.

    Defines how session memory, retrieval, compaction, and
    summaries work for agents that reference this profile.
    """

    session: bool = True
    retrieval: dict[str, Any] = Field(default_factory=dict)
    compaction: dict[str, Any] = Field(default_factory=dict)
    summaries: dict[str, Any] = Field(default_factory=dict)
    retention: dict[str, Any] = Field(default_factory=dict)
