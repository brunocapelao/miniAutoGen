import pytest

from miniautogen.adapters.llm import LiteLLMProvider, OpenAIProvider


class DummyClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[list[dict[str, str]], str | None, float]] = []

    async def get_model_response(
        self,
        prompt: list[dict[str, str]],
        model_name: str | None = None,
        temperature: float = 1.0,
    ) -> str:
        self.calls.append((prompt, model_name, temperature))
        return self.response


@pytest.mark.asyncio
async def test_litellm_provider_delegates_to_client() -> None:
    prompt = [{"role": "user", "content": "hello"}]
    client = DummyClient("world")

    provider = LiteLLMProvider(client=client)
    result = await provider.generate_response(prompt, model_name="gpt-4o-mini")

    assert result == "world"
    assert client.calls == [(prompt, "gpt-4o-mini", 1.0)]


@pytest.mark.asyncio
async def test_openai_provider_delegates_to_client() -> None:
    prompt = [{"role": "user", "content": "hello"}]
    client = DummyClient("world")

    provider = OpenAIProvider(client=client)
    result = await provider.generate_response(prompt)

    assert result == "world"
    assert client.calls == [(prompt, None, 1.0)]
