from __future__ import annotations

from typing import Any, Optional

import httpx

from miniautogen.adapters.llm.protocol import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        client: Any | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = client
        self.timeout_seconds = timeout_seconds

    async def generate_response(
        self,
        prompt: list[dict[str, str]],
        model_name: Optional[str] = None,
        temperature: float = 1.0,
    ) -> str:
        payload = {
            "model": model_name or "gemini-2.5-pro",
            "messages": prompt,
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else None

        if self.client is not None:
            response = await self.client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
        else:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )

        response.raise_for_status()
        body = response.json()
        return body["choices"][0]["message"]["content"]
