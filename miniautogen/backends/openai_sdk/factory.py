"""Factory for creating OpenAISDKDriver from BackendConfig."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

import structlog

from miniautogen.backends.config import BackendConfig
from miniautogen.backends.errors import BackendConfigurationError
from miniautogen.backends.openai_sdk.driver import OpenAISDKDriver

_LOCAL_SENTINEL = "sk-noauth-local"
_OPENAI_HOSTS = ("api.openai.com",)


def _is_openai_host(endpoint: str | None) -> bool:
    """Return True if endpoint targets OpenAI's official hosts."""
    if not endpoint:
        return True
    host = (urlparse(endpoint).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in _OPENAI_HOSTS)


def openai_sdk_factory(config: BackendConfig) -> OpenAISDKDriver:
    """Create an OpenAISDKDriver from declarative config.

    Reads api_key from auth config or environment, model from metadata.
    Injects a sentinel token for custom endpoints without explicit auth.
    """
    from openai import AsyncOpenAI

    api_key: str | None = None
    if config.auth and config.auth.type == "bearer" and config.auth.token_env:
        api_key = os.environ.get(config.auth.token_env)

    if api_key is None:
        api_key = os.environ.get("OPENAI_API_KEY")

    if api_key is None:
        if _is_openai_host(config.endpoint):
            token_env = config.auth.token_env if config.auth else None
            host_desc = "api.openai.com" if config.endpoint is None else config.endpoint
            raise BackendConfigurationError(
                f"Endpoint '{host_desc}' requires an api_key. "
                "Omitting 'endpoint' defaults to OpenAI. "
                f"Set the environment variable referenced by auth.token_env "
                f"(currently '{token_env}')."
            )
        api_key = _LOCAL_SENTINEL
        structlog.get_logger().warning(
            "openai_sdk.using_local_sentinel",
            endpoint=config.endpoint,
            reason="custom_endpoint_no_api_key",
        )

    metadata = config.metadata
    model = metadata.get("model", "gpt-4o")
    temperature = metadata.get("temperature", 0.2)
    max_tokens = metadata.get("max_tokens")

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if config.endpoint:
        client_kwargs["base_url"] = config.endpoint

    client = AsyncOpenAI(**client_kwargs)

    return OpenAISDKDriver(
        client=client,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=config.timeout_seconds,
    )
