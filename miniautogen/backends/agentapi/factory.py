# miniautogen/backends/agentapi/factory.py
"""Factory function for creating AgentAPIDriver from BackendConfig.

Resolves auth, extracts metadata params, and constructs the client.
Register with BackendResolver via:
    resolver.register_factory(DriverType.AGENT_API, agentapi_factory)
"""

from __future__ import annotations

import os

from miniautogen.backends.agentapi.client import AgentAPIClient
from miniautogen.backends.agentapi.driver import AgentAPIDriver
from miniautogen.backends.config import BackendConfig


def agentapi_factory(config: BackendConfig) -> AgentAPIDriver:
    """Create an AgentAPIDriver from declarative config."""
    api_key: str | None = None
    if config.auth and config.auth.type == "bearer" and config.auth.token_env:
        api_key = os.environ.get(config.auth.token_env)

    metadata = config.metadata
    health_ep = metadata.get("health_endpoint", "/health")

    client = AgentAPIClient(
        base_url=config.endpoint,  # type: ignore[arg-type]
        api_key=api_key,
        timeout_seconds=config.timeout_seconds,
        connect_timeout=metadata.get("connect_timeout", 10.0),
        health_endpoint=health_ep,
        max_retry_attempts=metadata.get("max_retry_attempts", 3),
        retry_delay=metadata.get("retry_delay", 1.0),
    )

    return AgentAPIDriver(
        client=client,
        model=metadata.get("model"),
        timeout_seconds=config.timeout_seconds,
    )
