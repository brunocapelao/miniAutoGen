"""Engine profile specification for the MiniAutoGen SDK.

Defines HOW an agent runs — the inference engine binding.
Separates capability (AgentSpec) from execution (EngineProfile).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class EngineProfile(BaseModel):
    """Execution engine binding.

    Defines the provider, model, and parameters for agent
    inference. Multiple profiles can coexist in a project,
    allowing the same agent to run on different engines.
    """

    kind: Literal["api", "cli"] = "api"
    provider: str = "litellm"
    model: str | None = None
    command: str | None = None
    temperature: float = 0.2
