"""Factory for creating AnthropicSDKDriver from BackendConfig."""

from __future__ import annotations

import os

from miniautogen.backends.anthropic_sdk.driver import AnthropicSDKDriver
from miniautogen.backends.config import BackendConfig


def anthropic_sdk_factory(config: BackendConfig) -> AnthropicSDKDriver:
    """Create an AnthropicSDKDriver from declarative config.

    Requires the `anthropic` package to be installed.
    """
    try:
        from anthropic import AsyncAnthropic
    except ImportError as exc:
        msg = (
            "anthropic package not installed. "
            "Install with: pip install miniautogen[anthropic]"
        )
        raise ImportError(msg) from exc

    api_key: str | None = None
    if config.auth and config.auth.type == "bearer" and config.auth.token_env:
        api_key = os.environ.get(config.auth.token_env)

    metadata = config.metadata
    model = metadata.get("model", "claude-sonnet-4-20250514")
    temperature = metadata.get("temperature", 0.2)
    max_tokens = metadata.get("max_tokens", 4096)

    client = AsyncAnthropic(api_key=api_key)

    return AnthropicSDKDriver(
        client=client,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=config.timeout_seconds,
    )
