from __future__ import annotations

from miniautogen.adapters.llm import LiteLLMProvider, OpenAICompatibleProvider
from miniautogen.app.settings import MiniAutoGenSettings
from miniautogen.policies import RetryPolicy


def build_provider(settings: MiniAutoGenSettings):
    if settings.default_provider == "gemini-cli-gateway":
        if not settings.gateway_base_url:
            raise ValueError("gateway_base_url is required when using gemini-cli-gateway")
        return OpenAICompatibleProvider(
            base_url=settings.gateway_base_url,
            api_key=settings.gateway_api_key,
            timeout_seconds=settings.default_timeout_seconds,
        )

    return LiteLLMProvider(
        default_model=settings.default_model,
        retry_policy=RetryPolicy(max_attempts=settings.default_retry_attempts),
    )
