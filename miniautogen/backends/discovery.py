"""Engine auto-discovery from environment variables and local servers.

Priority: Explicit YAML > Environment variables > Local server detection.
Discovered engines never override explicitly configured engines.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from miniautogen.cli.config import EngineProfileConfig
from miniautogen.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class _EnvMapping:
    """Maps an environment variable to an engine profile."""

    env_var: str
    engine_name: str
    provider: str
    model: str | None
    endpoint: str | None = None


# Known API key environment variables and their corresponding engine profiles.
_ENV_MAPPINGS: list[_EnvMapping] = [
    _EnvMapping(
        env_var="OPENAI_API_KEY",
        engine_name="openai",
        provider="openai",
        model="gpt-4o-mini",
    ),
    _EnvMapping(
        env_var="ANTHROPIC_API_KEY",
        engine_name="anthropic",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
    ),
    _EnvMapping(
        env_var="GOOGLE_API_KEY",
        engine_name="google",
        provider="google",
        model="gemini-2.5-flash",
    ),
    _EnvMapping(
        env_var="GEMINI_API_KEY",
        engine_name="google",
        provider="google",
        model="gemini-2.5-flash",
    ),
    _EnvMapping(
        env_var="GROQ_API_KEY",
        engine_name="groq",
        provider="openai-compat",
        model="llama-3.3-70b-versatile",
        endpoint="https://api.groq.com/openai/v1",
    ),
    _EnvMapping(
        env_var="DEEPSEEK_API_KEY",
        engine_name="deepseek",
        provider="openai-compat",
        model="deepseek-chat",
        endpoint="https://api.deepseek.com/v1",
    ),
    _EnvMapping(
        env_var="OPENROUTER_API_KEY",
        engine_name="openrouter",
        provider="openai-compat",
        model="auto",
        endpoint="https://openrouter.ai/api/v1",
    ),
    _EnvMapping(
        env_var="TOGETHER_API_KEY",
        engine_name="together",
        provider="openai-compat",
        model=None,
        endpoint="https://api.together.xyz/v1",
    ),
    _EnvMapping(
        env_var="MISTRAL_API_KEY",
        engine_name="mistral",
        provider="openai-compat",
        model="mistral-large-latest",
        endpoint="https://api.mistral.ai/v1",
    ),
]


@dataclass(frozen=True)
class _LocalServer:
    """Known local LLM server signatures."""

    host: str
    port: int
    engine_name: str
    health_path: str
    models_path: str


_LOCAL_SERVERS: list[_LocalServer] = [
    _LocalServer(
        host="localhost",
        port=11434,
        engine_name="ollama",
        health_path="/",
        models_path="/v1/models",
    ),
    _LocalServer(
        host="localhost",
        port=1234,
        engine_name="lmstudio",
        health_path="/v1/models",
        models_path="/v1/models",
    ),
    _LocalServer(
        host="localhost",
        port=8080,
        engine_name="local-server",
        health_path="/v1/models",
        models_path="/v1/models",
    ),
]

# Very short timeout for local server probes (seconds).
_PROBE_TIMEOUT = 0.5


class EngineDiscovery:
    """Discovers available engines from environment and local servers."""

    def discover_all(self) -> dict[str, EngineProfileConfig]:
        """Return all discovered engines (env + local).

        Never overrides explicit config — merging is the caller's job.
        """
        engines: dict[str, EngineProfileConfig] = {}

        # Local servers first (lower priority)
        local = self.discover_local_servers()
        engines.update(local)

        # Env vars override local (higher priority)
        env = self.discover_from_env()
        engines.update(env)

        return engines

    def discover_from_env(self) -> dict[str, EngineProfileConfig]:
        """Detect API keys in env vars and create engine profiles.

        The api_key field stores the env var NAME (e.g., "${OPENAI_API_KEY}"),
        not the actual value.
        """
        engines: dict[str, EngineProfileConfig] = {}

        for mapping in _ENV_MAPPINGS:
            value = os.environ.get(mapping.env_var)
            if not value:
                continue

            # Skip if we already discovered this engine name
            # (e.g., GOOGLE_API_KEY and GEMINI_API_KEY both map to "google")
            if mapping.engine_name in engines:
                continue

            kwargs: dict[str, Any] = {
                "provider": mapping.provider,
                "api_key": f"${{{mapping.env_var}}}",
            }
            if mapping.model is not None:
                kwargs["model"] = mapping.model
            if mapping.endpoint is not None:
                kwargs["endpoint"] = mapping.endpoint

            engines[mapping.engine_name] = EngineProfileConfig(**kwargs)
            logger.debug(
                "engine_discovered_from_env",
                engine=mapping.engine_name,
                env_var=mapping.env_var,
            )

        return engines

    def discover_local_servers(self) -> dict[str, EngineProfileConfig]:
        """Detect local LLM servers by pinging known ports.

        Uses httpx with a very short timeout (0.5s) to avoid blocking.
        Sync-safe: called during config loading, not in async context.
        """
        engines: dict[str, EngineProfileConfig] = {}

        for server in _LOCAL_SERVERS:
            if self._probe_server(server.host, server.port, server.health_path):
                endpoint = f"http://{server.host}:{server.port}/v1"
                engines[server.engine_name] = EngineProfileConfig(
                    provider="openai-compat",
                    endpoint=endpoint,
                    model="auto",
                )
                logger.debug(
                    "engine_discovered_local",
                    engine=server.engine_name,
                    port=server.port,
                )

        return engines

    @staticmethod
    def _probe_server(host: str, port: int, path: str) -> bool:
        """Probe a local server with a GET request.

        Returns True if the server responds (any 2xx/3xx/4xx),
        False on connection error or timeout.
        """
        try:
            url = f"http://{host}:{port}{path}"
            resp = httpx.get(url, timeout=_PROBE_TIMEOUT)
            # Any HTTP response means the server is running
            return resp.status_code < 500
        except Exception:  # noqa: BLE001 — network errors are expected
            return False
