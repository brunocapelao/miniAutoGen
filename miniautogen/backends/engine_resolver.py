"""EngineResolver — bridge between EngineProfileConfig and AgentDriver.

Converts user-facing engine profiles (from YAML) into BackendConfig objects,
registers them with BackendResolver, and returns cached driver instances.
This is the "Config -> Resolve -> Drive" glue layer.
"""

from __future__ import annotations

import os
import re
from typing import Any

from miniautogen.backends.agentapi.factory import agentapi_factory
from miniautogen.backends.config import AuthConfig, BackendConfig, DriverType
from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.errors import BackendUnavailableError
from miniautogen.backends.resolver import BackendResolver
from miniautogen.cli.config import EngineProfileConfig, ProjectConfig
from miniautogen.observability.logging import get_logger

logger = get_logger(__name__)

# Provider string -> DriverType mapping
_PROVIDER_TO_DRIVER: dict[str, DriverType] = {
    "openai-compat": DriverType.AGENT_API,
    "openai": DriverType.OPENAI_SDK,
    "anthropic": DriverType.ANTHROPIC_SDK,
    "google": DriverType.GOOGLE_GENAI,
    "litellm": DriverType.LITELLM,
    "claude-code": DriverType.CLI,
    "gemini-cli": DriverType.CLI,
    "codex-cli": DriverType.CLI,
}

# CLI provider -> default command mapping
_CLI_COMMANDS: dict[str, list[str]] = {
    "claude-code": ["claude", "--agent"],
    "gemini-cli": ["gemini"],
    "codex-cli": ["codex"],
}

# Pattern for environment variable references: ${VAR_NAME}
_ENV_VAR_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


class EngineResolver:
    """Converts EngineProfileConfig -> AgentDriver (instantiated, cached).

    Uses BackendResolver internally for factory registration and caching.
    """

    def __init__(self) -> None:
        self._resolver = BackendResolver()
        self._registered_profiles: set[str] = set()
        self._register_default_factories()

    def resolve_with_discovery(
        self, config: ProjectConfig,
    ) -> dict[str, EngineProfileConfig]:
        """Merge explicit config with auto-discovered engines.

        Priority: explicit YAML engines always override discovered engines.
        Discovered engines fill in the gaps (env vars, local servers).

        Returns:
            Merged dict of engine name -> EngineProfileConfig.
        """
        from miniautogen.backends.discovery import EngineDiscovery

        discovery = EngineDiscovery()
        discovered = discovery.discover_all()

        # Start with discovered, then overlay explicit (explicit wins)
        merged = dict(discovered)
        merged.update(config.engine_profiles)
        return merged

    def list_available_engines(
        self, config: ProjectConfig,
    ) -> list[dict[str, str]]:
        """List all available engines with source information.

        Returns a list of dicts with keys: name, source, provider, model.
        Source is one of: "yaml", "env", "local".
        """
        from miniautogen.backends.discovery import EngineDiscovery

        discovery = EngineDiscovery()
        env_engines = discovery.discover_from_env()
        local_engines = discovery.discover_local_servers()

        result: list[dict[str, str]] = []

        # Collect all unique engine names preserving priority order
        all_names: dict[str, str] = {}

        # Local has lowest priority
        for name in local_engines:
            all_names[name] = "local"

        # Env overrides local
        for name in env_engines:
            all_names[name] = "env"

        # YAML overrides everything
        for name in config.engine_profiles:
            all_names[name] = "yaml"

        # Build result list
        for name, source in sorted(all_names.items()):
            if source == "yaml":
                profile = config.engine_profiles[name]
            elif source == "env":
                profile = env_engines[name]
            else:
                profile = local_engines[name]

            result.append({
                "name": name,
                "source": source,
                "provider": profile.provider,
                "model": profile.model or "(default)",
            })

        return result

    def resolve(self, profile_name: str, config: ProjectConfig) -> AgentDriver:
        """Resolve an engine profile name to a cached driver instance.

        Args:
            profile_name: Name of the engine profile (e.g., "fast-cheap").
            config: The full project configuration containing engine_profiles.

        Returns:
            An instantiated AgentDriver ready for use.

        Raises:
            BackendUnavailableError: If profile not found or driver can't be created.
        """
        engine = config.engine_profiles.get(profile_name)
        if engine is None:
            msg = f"Engine profile '{profile_name}' not found in project config"
            raise BackendUnavailableError(msg)

        # Only register the backend config once
        if profile_name not in self._registered_profiles:
            backend_config = self._engine_to_backend(profile_name, engine)
            self._resolver.add_backend(backend_config)
            self._registered_profiles.add(profile_name)

        return self._resolver.get_driver(profile_name)

    def create_fresh_driver(
        self, profile_name: str, config: ProjectConfig,
    ) -> AgentDriver:
        """Create a NEW driver instance (not cached). For per-agent sessions.

        Each call creates a distinct driver with a unique backend_id so it
        is never shared with (or stored in) the resolver cache.  This is
        required when multiple agents need independent sessions against the
        same engine profile.

        Args:
            profile_name: Name of the engine profile (e.g., "fast-cheap").
            config: The full project configuration containing engine_profiles.

        Returns:
            A freshly instantiated AgentDriver, not shared with any cache.

        Raises:
            BackendUnavailableError: If profile not found or driver can't be
                created.
        """
        from uuid import uuid4

        engine = config.engine_profiles.get(profile_name)
        if engine is None:
            msg = f"Engine profile '{profile_name}' not found"
            raise BackendUnavailableError(msg)

        backend_config = self._engine_to_backend(
            f"{profile_name}_{uuid4().hex[:8]}", engine,
        )
        return self._resolver.create_driver(backend_config)

    def resolve_with_fallbacks(
        self, profile_name: str, config: ProjectConfig,
    ) -> AgentDriver:
        """Try primary engine, fall back to alternatives on failure.

        Args:
            profile_name: Primary engine profile name.
            config: Full project config.

        Returns:
            First successfully resolved driver.

        Raises:
            BackendUnavailableError: If all options (primary + fallbacks) fail.
        """
        engine = config.engine_profiles.get(profile_name)
        if engine is None:
            msg = f"Engine profile '{profile_name}' not found in project config"
            raise BackendUnavailableError(msg)

        # Build the chain: primary + fallbacks
        chain = [profile_name, *engine.fallbacks]
        errors: list[str] = []

        for name in chain:
            try:
                driver = self.resolve(name, config)
                if name != profile_name:
                    logger.info(
                        "fallback_resolved",
                        primary=profile_name,
                        resolved=name,
                    )
                return driver
            except (BackendUnavailableError, Exception) as exc:
                errors.append(f"{name}: {exc}")
                logger.warning(
                    "engine_resolution_failed",
                    profile=name,
                    error=str(exc),
                )

        msg = (
            f"All engines failed for '{profile_name}'. "
            f"Tried: {', '.join(chain)}. Errors: {'; '.join(errors)}"
        )
        raise BackendUnavailableError(msg)

    def _engine_to_backend(
        self, name: str, engine: EngineProfileConfig,
    ) -> BackendConfig:
        """Map an EngineProfileConfig to a BackendConfig.

        This is the core translation layer. It converts user-facing
        config (provider, model, api_key) into the internal BackendConfig
        format (driver type, endpoint, auth, metadata).
        """
        driver_type = _PROVIDER_TO_DRIVER.get(engine.provider)
        if driver_type is None:
            msg = f"Unknown provider '{engine.provider}' in engine profile '{name}'"
            raise BackendUnavailableError(msg)

        # Resolve API key (handles ${ENV_VAR} references)
        resolved_key = self._resolve_api_key(engine.api_key)

        # Build auth config if we have a key
        auth: AuthConfig | None = None
        if resolved_key:
            # Store the resolved key in env for the auth system
            env_var_name = f"_MINIAUTOGEN_{name.upper().replace('-', '_')}_KEY"
            os.environ[env_var_name] = resolved_key
            auth = AuthConfig(type="bearer", token_env=env_var_name)

        # Build metadata with model and engine-specific params
        metadata: dict[str, Any] = dict(engine.metadata)
        if engine.model:
            metadata["model"] = engine.model
        metadata["temperature"] = engine.temperature
        metadata["max_retries"] = engine.max_retries
        metadata["retry_delay"] = engine.retry_delay
        if engine.max_tokens is not None:
            metadata["max_tokens"] = engine.max_tokens
        # Disable health check for SDK drivers (they handle it internally)
        if driver_type != DriverType.AGENT_API:
            metadata.setdefault("health_endpoint", None)

        # Determine command for CLI drivers
        command: list[str] | None = None
        if driver_type == DriverType.CLI:
            command = _CLI_COMMANDS.get(engine.provider, [engine.provider])

        # Determine endpoint for API drivers
        endpoint = engine.endpoint
        if driver_type == DriverType.AGENT_API and not endpoint:
            # Default OpenAI-compat endpoint
            endpoint = "https://api.openai.com/v1"

        return BackendConfig(
            backend_id=name,
            driver=driver_type,
            command=command,
            endpoint=endpoint,
            timeout_seconds=engine.timeout_seconds,
            auth=auth,
            metadata=metadata,
        )

    def _resolve_api_key(self, api_key: str | None) -> str | None:
        """Resolve ${ENV_VAR} references to actual values.

        If the key looks like ${VAR_NAME}, reads from environment.
        Otherwise returns the literal value.
        Returns None if the env var is not set.
        """
        if api_key is None:
            return None

        match = _ENV_VAR_PATTERN.match(api_key)
        if match:
            var_name = match.group(1)
            value = os.environ.get(var_name)
            if value is None:
                logger.warning("env_var_not_set", var_name=var_name)
            return value

        return api_key

    def register_factory(
        self, driver_type: DriverType, factory: Any,
    ) -> None:
        """Register a driver factory. Delegates to internal BackendResolver."""
        self._resolver.register_factory(driver_type, factory)

    def _register_default_factories(self) -> None:
        """Register factories for all built-in driver types."""
        from miniautogen.backends.anthropic_sdk.factory import (
            anthropic_sdk_factory,
        )
        from miniautogen.backends.cli.factory import cli_factory
        from miniautogen.backends.google_genai.factory import (
            google_genai_factory,
        )
        from miniautogen.backends.openai_sdk.factory import (
            openai_sdk_factory,
        )

        self._resolver.register_factory(DriverType.AGENT_API, agentapi_factory)
        self._resolver.register_factory(DriverType.OPENAI_SDK, openai_sdk_factory)
        self._resolver.register_factory(
            DriverType.ANTHROPIC_SDK, anthropic_sdk_factory,
        )
        self._resolver.register_factory(
            DriverType.GOOGLE_GENAI, google_genai_factory,
        )
        self._resolver.register_factory(DriverType.CLI, cli_factory)
