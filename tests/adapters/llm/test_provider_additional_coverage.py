from types import SimpleNamespace

import pytest

from miniautogen.adapters.llm import LiteLLMProvider, OpenAIProvider
from miniautogen.adapters.llm import providers as provider_module


class RecordingCompletions:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls: list[tuple[str, list[dict[str, str]], float]] = []

    async def create(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> SimpleNamespace:
        self.calls.append((model, messages, temperature))
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.response_text))]
        )


@pytest.mark.asyncio
async def test_openai_provider_uses_native_client_shape_when_no_legacy_method() -> None:
    completions = RecordingCompletions("native-response")
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAIProvider(client=client)

    result = await provider.generate_response([{"role": "user", "content": "hello"}])

    assert result == "native-response"
    assert completions.calls == [
        ("gpt-3.5-turbo", [{"role": "user", "content": "hello"}], 1.0)
    ]


@pytest.mark.asyncio
async def test_openai_provider_logs_and_raises_when_native_client_fails() -> None:
    class BrokenCompletions:
        async def create(self, model: str, messages, temperature: float):
            raise RuntimeError("boom")

    client = SimpleNamespace(chat=SimpleNamespace(completions=BrokenCompletions()))
    provider = OpenAIProvider(client=client)

    with pytest.raises(RuntimeError, match="boom"):
        await provider.generate_response([{"role": "user", "content": "hello"}])


@pytest.mark.asyncio
async def test_litellm_provider_uses_native_completion_when_no_legacy_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_completion(model: str, messages, temperature: float):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="native-lite"))]
        )

    monkeypatch.setattr(provider_module, "acompletion", fake_completion)
    provider = LiteLLMProvider(default_model="gpt-4o-mini")

    result = await provider.generate_response([{"role": "user", "content": "hello"}])

    assert result == "native-lite"


@pytest.mark.asyncio
async def test_litellm_provider_logs_and_raises_when_native_completion_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing_completion(model: str, messages, temperature: float):
        raise RuntimeError("litellm-boom")

    monkeypatch.setattr(provider_module, "acompletion", failing_completion)
    provider = LiteLLMProvider(default_model="gpt-4o-mini")

    with pytest.raises(RuntimeError, match="litellm-boom"):
        await provider.generate_response([{"role": "user", "content": "hello"}])
