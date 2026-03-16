import pytest

from miniautogen.adapters.llm.openai_compatible_provider import OpenAICompatibleProvider


class FakeHTTPClient:
    async def post(self, url, json, headers=None, timeout=None):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "choices": [
                        {"message": {"content": "gateway-response"}}
                    ]
                }

        return Response()


@pytest.mark.asyncio
async def test_openai_compatible_provider_extracts_assistant_content() -> None:
    provider = OpenAICompatibleProvider(
        base_url="http://gateway.local",
        client=FakeHTTPClient(),
    )
    response = await provider.generate_response(
        [{"role": "user", "content": "hello"}],
        model_name="gemini-2.5-pro",
    )
    assert response == "gateway-response"
