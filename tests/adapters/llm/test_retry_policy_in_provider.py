import pytest

from miniautogen.adapters.llm import LiteLLMProvider
from miniautogen.policies import RetryPolicy


class FlakyClient:
    def __init__(self) -> None:
        self.calls = 0

    async def get_model_response(
        self,
        prompt,
        model_name=None,
        temperature=1.0,
    ) -> str:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient")
        return "ok"


@pytest.mark.asyncio
async def test_provider_applies_retry_policy() -> None:
    client = FlakyClient()
    provider = LiteLLMProvider(client=client, retry_policy=RetryPolicy(max_attempts=2))

    result = await provider.generate_response([{"role": "user", "content": "hello"}])

    assert result == "ok"
    assert client.calls == 2


class PermanentFailureClient:
    def __init__(self) -> None:
        self.calls = 0

    async def get_model_response(
        self,
        prompt,
        model_name=None,
        temperature=1.0,
    ) -> str:
        self.calls += 1
        raise ValueError("bad-request")


@pytest.mark.asyncio
async def test_provider_does_not_retry_exceptions_outside_policy_scope() -> None:
    client = PermanentFailureClient()
    provider = LiteLLMProvider(client=client, retry_policy=RetryPolicy(max_attempts=2))

    with pytest.raises(ValueError, match="bad-request"):
        await provider.generate_response([{"role": "user", "content": "hello"}])

    assert client.calls == 1
