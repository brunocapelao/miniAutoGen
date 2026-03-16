from __future__ import annotations

from typing import Any
from uuid import uuid4

from gemini_cli_gateway.config import GatewaySettings
from gemini_cli_gateway.models import ChatCompletionRequest
from gemini_cli_gateway.prompt_builder import build_prompt
from gemini_cli_gateway.runner import run_gemini_command


async def complete_chat(
    request: ChatCompletionRequest,
    *,
    settings: GatewaySettings,
) -> dict[str, Any]:
    prompt = build_prompt(request.messages)
    command = [
        settings.binary,
        "-m",
        request.model,
        "--output-format",
        "json",
    ]
    result = await run_gemini_command(
        command,
        prompt,
        timeout_seconds=settings.command_timeout_seconds,
    )
    return {
        "id": f"chatcmpl-gemini-cli-{uuid4().hex[:12]}",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result.text},
                "finish_reason": "stop",
            }
        ],
        "model": request.model,
        "usage": None,
    }
