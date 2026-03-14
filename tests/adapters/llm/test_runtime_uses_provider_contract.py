import pytest

from miniautogen.pipeline.components.components import LLMResponseComponent
from miniautogen.pipeline.pipeline import ChatPipelineState


class DummyProvider:
    async def generate_response(
        self,
        prompt: list[dict[str, str]],
        model_name: str | None = None,
        temperature: float = 1.0,
    ) -> str:
        return "provider-response"


@pytest.mark.asyncio
async def test_llm_response_component_accepts_provider_contract() -> None:
    component = LLMResponseComponent(DummyProvider(), model_name="gpt-4o-mini")
    state = ChatPipelineState(prompt=[{"role": "user", "content": "hello"}])

    result = await component.process(state)

    assert result is state
    assert state.get_state()["reply"] == "provider-response"
