"""Configuration models for backend drivers.

Supports declarative backend config as described in the spec (section 9).
Each backend has a driver type, optional command/endpoint, auth, and
capability overrides.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class DriverType(str, Enum):
    ACP = "acp"             # Deprecated: use CLI
    AGENT_API = "agentapi"
    PTY = "pty"             # Deprecated: use CLI
    OPENAI_SDK = "openai_sdk"
    ANTHROPIC_SDK = "anthropic_sdk"
    GOOGLE_GENAI = "google_genai"
    LITELLM = "litellm"
    CLI = "cli"


class AuthConfig(BaseModel):
    """Authentication configuration for HTTP-based drivers."""

    type: str = "none"
    token_env: str | None = None

    @model_validator(mode="after")
    def validate_bearer_has_token(self) -> "AuthConfig":
        if self.type == "bearer" and not self.token_env:
            msg = "token_env is required when auth type is 'bearer'"
            raise ValueError(msg)
        return self


class BackendConfig(BaseModel):
    """Declarative configuration for a single backend.

    Validates semantic constraints per driver type so invalid config
    fails at parse time, not at runtime (see D3).
    """

    backend_id: str
    driver: DriverType
    command: list[str] | None = None
    endpoint: str | None = None
    agent: str | None = None
    auth: AuthConfig | None = None
    parse_mode: str | None = None
    timeout_seconds: float = 120.0
    capabilities_override: dict[str, bool] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_driver_requirements(self) -> "BackendConfig":
        if self.driver in (DriverType.ACP, DriverType.PTY, DriverType.CLI) and not self.command:
            msg = f"command is required for driver type '{self.driver.value}'"
            raise ValueError(msg)
        if self.driver == DriverType.AGENT_API and not self.endpoint:
            msg = "endpoint is required for driver type 'agentapi'"
            raise ValueError(msg)
        if self.auth and self.auth.type == "bearer" and not self.auth.token_env:
            msg = "token_env is required when auth type is 'bearer'"
            raise ValueError(msg)
        return self
