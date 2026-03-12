import pytest

from miniautogen.llms.llm_client import LiteLLMClient, OpenAIClient


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
async def test_legacy_openai_client_delegates_to_provider_adapter() -> None:
    prompt = [{"role": "user", "content": "hello"}]
    client = DummyClient("world")

    llm_client = OpenAIClient(client=client)
    result = await llm_client.get_model_response(prompt, model_name="gpt-4.1-mini")

    assert result == "world"
    assert client.calls == [(prompt, "gpt-4.1-mini", 1.0)]


@pytest.mark.asyncio
async def test_legacy_litellm_client_delegates_to_provider_adapter() -> None:
    prompt = [{"role": "user", "content": "hello"}]
    client = DummyClient("world")

    llm_client = LiteLLMClient(default_model="gpt-4o-mini", client=client)
    result = await llm_client.get_model_response(prompt)

    assert result == "world"
    assert client.calls == [(prompt, "gpt-4o-mini", 1.0)]
