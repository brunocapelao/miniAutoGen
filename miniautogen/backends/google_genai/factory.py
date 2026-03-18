"""Factory for creating GoogleGenAIDriver from BackendConfig."""

from __future__ import annotations

import os

from miniautogen.backends.config import BackendConfig
from miniautogen.backends.google_genai.driver import GoogleGenAIDriver


def google_genai_factory(config: BackendConfig) -> GoogleGenAIDriver:
    """Create a GoogleGenAIDriver from declarative config.

    Requires the `google-genai` package to be installed.
    """
    try:
        from google import genai
    except ImportError as exc:
        msg = (
            "google-genai package not installed. "
            "Install with: pip install miniautogen[google]"
        )
        raise ImportError(msg) from exc

    api_key: str | None = None
    if config.auth and config.auth.type == "bearer" and config.auth.token_env:
        api_key = os.environ.get(config.auth.token_env)

    metadata = config.metadata
    model = metadata.get("model", "gemini-2.5-pro")
    temperature = metadata.get("temperature", 0.2)
    max_tokens = metadata.get("max_tokens")

    client = genai.Client(api_key=api_key)

    return GoogleGenAIDriver(
        client=client,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=config.timeout_seconds,
    )
