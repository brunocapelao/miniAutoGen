import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from miniautogen.adapters.llm.openai_compatible_provider import OpenAICompatibleProvider
from miniautogen.core.runtime import PipelineRunner
from miniautogen.stores import InMemoryCheckpointStore, InMemoryRunStore


class GatewayBackedPipeline:
    def __init__(self, provider):
        self.provider = provider

    async def run(self, state):
        reply = await self.provider.generate_response(
            [{"role": "user", "content": state["prompt"]}],
            model_name="gemini-2.5-pro",
        )
        return {"reply": reply}


@pytest.mark.asyncio
async def test_pipeline_runner_works_with_openai_compatible_gateway() -> None:
    app = FastAPI()

    @app.post("/v1/chat/completions")
    async def chat_completions():
        return JSONResponse(
            {
                "id": "chatcmpl-fake",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "gateway-ok"},
                        "finish_reason": "stop",
                    }
                ],
                "model": "gemini-2.5-pro",
            }
        )

    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    provider = OpenAICompatibleProvider(base_url="http://test", client=client)
    runner = PipelineRunner(
        run_store=InMemoryRunStore(),
        checkpoint_store=InMemoryCheckpointStore(),
    )
    result = await runner.run_pipeline(GatewayBackedPipeline(provider), {"prompt": "hello"})
    await client.aclose()

    assert result == {"reply": "gateway-ok"}
