import logging
from typing import Any, Optional, cast

import openai
from litellm import acompletion

from miniautogen.adapters.llm.protocol import LLMProvider
from miniautogen.policies.retry import RetryPolicy, build_retrying_call


class OpenAIProvider(LLMProvider):
    """Adapter around the OpenAI async chat completion API."""

    def __init__(
        self,
        api_key: str | None = None,
        client: object | None = None,
        retry_policy: RetryPolicy | None = None,
    ):
        self.client = client or openai.AsyncOpenAI(api_key=api_key)
        self.logger = logging.getLogger(__name__)
        self.retry_policy = retry_policy or RetryPolicy()

    async def generate_response(
        self,
        prompt: list[dict[str, str]],
        model_name: Optional[str] = None,
        temperature: float = 1.0,
    ) -> str:
        async def operation() -> str:
            if hasattr(self.client, "get_model_response"):
                return await self.client.get_model_response(prompt, model_name, temperature)

            model = model_name or "gpt-3.5-turbo"
            client = cast(Any, self.client)
            response = await client.chat.completions.create(
                model=model,
                messages=prompt,
                temperature=temperature,
            )
            return response.choices[0].message.content

        try:
            retry_call = build_retrying_call(self.retry_policy)
            return await retry_call(operation)
        except Exception as exc:
            self.logger.error("Error calling the OpenAI API: %s", exc)
            raise


class LiteLLMProvider(LLMProvider):
    """Adapter around LiteLLM for provider-agnostic model calls."""

    def __init__(
        self,
        default_model: str = "gpt-4o-mini",
        client: object | None = None,
        retry_policy: RetryPolicy | None = None,
    ):
        self.default_model = default_model
        self.client = client
        self.logger = logging.getLogger(__name__)
        self.retry_policy = retry_policy or RetryPolicy()

    async def generate_response(
        self,
        prompt: list[dict[str, str]],
        model_name: Optional[str] = None,
        temperature: float = 1.0,
    ) -> str:
        model = model_name or self.default_model

        async def operation() -> str:
            if self.client and hasattr(self.client, "get_model_response"):
                return await self.client.get_model_response(prompt, model, temperature)

            response = await acompletion(
                model=model,
                messages=prompt,
                temperature=temperature,
            )
            return response.choices[0].message.content

        try:
            retry_call = build_retrying_call(self.retry_policy)
            return await retry_call(operation)
        except Exception as exc:
            self.logger.error("Error calling the LiteLLM API: %s", exc)
            raise
