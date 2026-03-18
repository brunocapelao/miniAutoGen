"""Factory for creating CLIAgentDriver from BackendConfig."""

from __future__ import annotations

from miniautogen.backends.cli.driver import CLIAgentDriver
from miniautogen.backends.config import BackendConfig


def cli_factory(config: BackendConfig) -> CLIAgentDriver:
    """Create a CLIAgentDriver from declarative config."""
    if not config.command:
        msg = f"command is required for CLI driver '{config.backend_id}'"
        raise ValueError(msg)

    return CLIAgentDriver(
        command=config.command,
        provider=config.backend_id,
        timeout_seconds=config.timeout_seconds,
        env=config.env or {},
    )
