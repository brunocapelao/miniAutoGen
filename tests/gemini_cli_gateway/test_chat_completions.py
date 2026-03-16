import pytest
from httpx import ASGITransport, AsyncClient

from gemini_cli_gateway.app import app
from gemini_cli_gateway.config import GatewaySettings


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


@pytest.mark.asyncio
async def test_chat_completion_passes_retry_settings_to_service(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_run_gemini_command(
        command,
        prompt,
        *,
        timeout_seconds,
        max_attempts,
        retry_delay_seconds,
    ):
        captured["command"] = command
        captured["prompt"] = prompt
        captured["timeout_seconds"] = timeout_seconds
        captured["max_attempts"] = max_attempts
        captured["retry_delay_seconds"] = retry_delay_seconds
        return type(
            "Result",
            (),
            {
                "text": "ok",
                "raw_stdout": '{"response":"ok"}',
                "raw_stderr": "",
                "returncode": 0,
                "duration_ms": 1.0,
            },
        )()

    monkeypatch.setattr("gemini_cli_gateway.service.run_gemini_command", fake_run_gemini_command)

    from gemini_cli_gateway.models import ChatCompletionRequest
    from gemini_cli_gateway.service import complete_chat

    settings = GatewaySettings(
        GEMINI_GATEWAY_TIMEOUT_SECONDS=91,
        GEMINI_GATEWAY_RETRY_MAX_ATTEMPTS=4,
        GEMINI_GATEWAY_RETRY_DELAY_SECONDS=0.25,
    )
    request = ChatCompletionRequest(
        model="gemini-2.5-pro",
        messages=[{"role": "user", "content": "hello"}],
    )

    response = await complete_chat(request, settings=settings)

    assert response["choices"][0]["message"]["content"] == "ok"
    assert captured["timeout_seconds"] == 91
    assert captured["max_attempts"] == 4
    assert captured["retry_delay_seconds"] == 0.25
