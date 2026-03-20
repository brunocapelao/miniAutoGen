"""Config-driven backend resolution and driver instantiation.

The resolver holds backend configs and a registry of driver factories.
When a driver is requested, it looks up the config, finds the matching
factory, creates the driver (once), and caches it.
"""

from __future__ import annotations

from typing import Callable

from miniautogen.backends.config import BackendConfig, DriverType
from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.errors import BackendUnavailableError

DriverFactory = Callable[[BackendConfig], AgentDriver]


class BackendResolver:
    """Resolves backend IDs to configured AgentDriver instances."""

    def __init__(self) -> None:
        self._configs: dict[str, BackendConfig] = {}
        self._factories: dict[DriverType, DriverFactory] = {}
        self._cache: dict[str, AgentDriver] = {}

    def register_factory(
        self,
        driver_type: DriverType,
        factory: DriverFactory,
    ) -> None:
        """Register a factory function for a driver type."""
        self._factories[driver_type] = factory

    def add_backend(self, config: BackendConfig) -> None:
        """Add a backend configuration."""
        if config.backend_id in self._configs:
            msg = f"Backend '{config.backend_id}' already configured"
            raise ValueError(msg)
        self._configs[config.backend_id] = config

    def get_driver(self, backend_id: str) -> AgentDriver:
        """Get or create the driver for a backend.

        Raises BackendUnavailableError if the backend is not configured
        or no factory is registered for its driver type.
        """
        if backend_id in self._cache:
            return self._cache[backend_id]

        config = self._configs.get(backend_id)
        if config is None:
            msg = f"Backend '{backend_id}' not configured"
            raise BackendUnavailableError(msg)

        factory = self._factories.get(config.driver)
        if factory is None:
            msg = f"No factory registered for driver type '{config.driver.value}'"
            raise BackendUnavailableError(msg)

        driver = factory(config)
        self._cache[backend_id] = driver
        return driver

    def create_driver(self, config: BackendConfig) -> AgentDriver:
        """Create a NEW driver instance (not cached). Public factory method.

        Unlike get_driver(), this always creates a fresh instance and does
        not store it in the cache. Useful for per-agent sessions where each
        agent needs its own driver.

        Raises BackendUnavailableError if no factory is registered for the
        driver type in config.
        """
        factory = self._factories.get(config.driver)
        if factory is None:
            msg = f"No factory for driver type '{config.driver.value}'"
            raise BackendUnavailableError(msg)
        return factory(config)

    def get_config(self, backend_id: str) -> BackendConfig | None:
        """Get the config for a backend, or None if not found."""
        return self._configs.get(backend_id)

    def list_backends(self) -> list[str]:
        """List all configured backend IDs."""
        return list(self._configs.keys())
