import logging
from typing import Optional

import openai
from litellm import acompletion

from miniautogen.adapters.llm.protocol import LLMProvider


class OpenAIProvider(LLMProvider):
    """Adapter around the OpenAI async chat completion API."""

    def __init__(self, api_key: str | None = None, client: object | None = None):
        self.client = client or openai.AsyncOpenAI(api_key=api_key)
        self.logger = logging.getLogger(__name__)

    async def generate_response(
        self,
        prompt: list[dict[str, str]],
        model_name: Optional[str] = None,
        temperature: float = 1.0,
    ) -> str:
        if hasattr(self.client, "get_model_response"):
            return await self.client.get_model_response(prompt, model_name, temperature)

        model = model_name or "gpt-3.5-turbo"
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=prompt,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as exc:
            self.logger.error("Error calling the OpenAI API: %s", exc)
            raise


class LiteLLMProvider(LLMProvider):
    """Adapter around LiteLLM for provider-agnostic model calls."""

    def __init__(self, default_model: str = "gpt-4o-mini", client: object | None = None):
        self.default_model = default_model
        self.client = client
        self.logger = logging.getLogger(__name__)

    async def generate_response(
        self,
        prompt: list[dict[str, str]],
        model_name: Optional[str] = None,
        temperature: float = 1.0,
    ) -> str:
        model = model_name or self.default_model

        if self.client and hasattr(self.client, "get_model_response"):
            return await self.client.get_model_response(prompt, model, temperature)

        try:
            response = await acompletion(
                model=model,
                messages=prompt,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as exc:
            self.logger.error("Error calling the LiteLLM API: %s", exc)
            raise
