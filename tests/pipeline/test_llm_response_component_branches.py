import pytest

from miniautogen.pipeline.components.components import LLMResponseComponent
from miniautogen.pipeline.pipeline import ChatPipelineState


class LegacyClient:
    async def get_model_response(
        self,
        prompt: list[dict[str, str]],
        model_name: str | None = None,
        temperature: float = 1.0,
    ) -> str:
        return "legacy-response"


class EmptyClient:
    async def generate_response(
        self,
        prompt: list[dict[str, str]],
        model_name: str | None = None,
        temperature: float = 1.0,
    ) -> str:
        return ""


@pytest.mark.asyncio
async def test_llm_response_component_supports_legacy_client_fallback() -> None:
    component = LLMResponseComponent(LegacyClient(), model_name="gpt-4o-mini")
    state = ChatPipelineState(prompt=[{"role": "user", "content": "hello"}])

    result = await component.process(state)

    assert result is state
    assert state.get_state()["reply"] == "legacy-response"


@pytest.mark.asyncio
async def test_llm_response_component_returns_state_when_prompt_missing() -> None:
    component = LLMResponseComponent(LegacyClient(), model_name="gpt-4o-mini")
    state = ChatPipelineState()

    result = await component.process(state)

    assert result is state
    assert "reply" not in state.get_state()


@pytest.mark.asyncio
async def test_llm_response_component_raises_when_llm_returns_empty_text() -> None:
    component = LLMResponseComponent(EmptyClient(), model_name="gpt-4o-mini")
    state = ChatPipelineState(prompt=[{"role": "user", "content": "hello"}])

    with pytest.raises(RuntimeError, match="Failed to get response from LLM."):
        await component.process(state)
