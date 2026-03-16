import asyncio

import anyio
import pytest
from httpx import ASGITransport, AsyncClient

import gemini_cli_gateway.app as gateway_app


@pytest.mark.asyncio
async def test_chat_completions_respects_semaphore(monkeypatch) -> None:
    active = 0
    max_active = 0
    lock = asyncio.Lock()

    async def fake_complete(request):
        nonlocal active, max_active
        async with lock:
            active += 1
            max_active = max(max_active, active)
        await anyio.sleep(0.05)
        async with lock:
            active -= 1
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
            "model": request.model,
        }

    monkeypatch.setattr(gateway_app, "complete_chat", fake_complete)
    monkeypatch.setattr(gateway_app, "semaphore", anyio.Semaphore(1))

    async with AsyncClient(
        transport=ASGITransport(app=gateway_app.app),
        base_url="http://test",
    ) as client:
        await asyncio.gather(
            client.post(
                "/v1/chat/completions",
                json={
                    "model": "gemini-2.5-pro",
                    "messages": [{"role": "user", "content": "one"}],
                    "temperature": 0.0,
                },
            ),
            client.post(
                "/v1/chat/completions",
                json={
                    "model": "gemini-2.5-pro",
                    "messages": [{"role": "user", "content": "two"}],
                    "temperature": 0.0,
                },
            ),
        )

    assert max_active == 1
