"""Factory for creating OpenAISDKDriver from BackendConfig."""

from __future__ import annotations

import os

from miniautogen.backends.config import BackendConfig
from miniautogen.backends.openai_sdk.driver import OpenAISDKDriver


def openai_sdk_factory(config: BackendConfig) -> OpenAISDKDriver:
    """Create an OpenAISDKDriver from declarative config.

    Reads api_key from auth config or environment, model from metadata.
    """
    from openai import AsyncOpenAI

    api_key: str | None = None
    if config.auth and config.auth.type == "bearer" and config.auth.token_env:
        api_key = os.environ.get(config.auth.token_env)

    metadata = config.metadata
    model = metadata.get("model", "gpt-4o")
    temperature = metadata.get("temperature", 0.2)
    max_tokens = metadata.get("max_tokens")

    client_kwargs: dict = {"api_key": api_key}
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
