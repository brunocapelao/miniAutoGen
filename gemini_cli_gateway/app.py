from __future__ import annotations

import anyio
from fastapi import FastAPI

from gemini_cli_gateway.config import GatewaySettings
from gemini_cli_gateway.models import ChatCompletionRequest
from gemini_cli_gateway.service import complete_chat as service_complete_chat

app = FastAPI()
settings = GatewaySettings()  # type: ignore[call-arg]
semaphore = anyio.Semaphore(settings.max_concurrent_processes)


async def complete_chat(request: ChatCompletionRequest) -> dict[str, object]:
    return await service_complete_chat(request, settings=settings)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> dict[str, object]:
    async with semaphore:
        return await complete_chat(request)
