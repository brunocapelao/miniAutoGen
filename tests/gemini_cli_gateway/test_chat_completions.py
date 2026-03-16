import pytest
from httpx import ASGITransport, AsyncClient

from gemini_cli_gateway.app import app


@pytest.mark.asyncio
async def test_chat_completions_returns_openai_like_payload(monkeypatch) -> None:
    async def fake_complete(request):
        return {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
            "model": "gemini-2.5-pro",
        }

    monkeypatch.setattr("gemini_cli_gateway.app.complete_chat", fake_complete)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gemini-2.5-pro",
                "messages": [{"role": "user", "content": "hello"}],
                "temperature": 0.1,
            },
        )
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "ok"
