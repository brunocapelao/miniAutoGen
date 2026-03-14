import pytest

from miniautogen.adapters.llm import LiteLLMProvider
from miniautogen.chat.chat import Chat
from miniautogen.core.events import InMemoryEventSink
from miniautogen.core.runtime import PipelineRunner
from miniautogen.pipeline.components.components import LLMResponseComponent
from miniautogen.pipeline.pipeline import ChatPipelineState
from miniautogen.stores import (
    InMemoryCheckpointStore,
    InMemoryMessageStore,
    InMemoryRunStore,
)


class DummyProvider(LiteLLMProvider):
    def __init__(self) -> None:
        pass

    async def generate_response(
        self,
        prompt: list[dict[str, str]],
        model_name: str | None = None,
        temperature: float = 1.0,
    ) -> str:
        return "provider-response"


class DummyPipeline:
    async def run(self, state):
        return {"ok": True}


@pytest.mark.asyncio
async def test_chat_defaults_to_new_message_store_for_mvp() -> None:
    chat = Chat()

    assert isinstance(chat.repository, InMemoryMessageStore)


@pytest.mark.asyncio
async def test_llm_response_component_accepts_new_provider_default_path() -> None:
    component = LLMResponseComponent(DummyProvider(), model_name="gpt-4o-mini")
    state = ChatPipelineState(prompt=[{"role": "user", "content": "hello"}])

    result = await component.process(state)

    assert result is state
    assert state.get_state()["reply"] == "provider-response"


@pytest.mark.asyncio
async def test_pipeline_runner_persists_and_emits_events_on_official_path() -> None:
    sink = InMemoryEventSink()
    run_store = InMemoryRunStore()
    checkpoint_store = InMemoryCheckpointStore()
    runner = PipelineRunner(
        event_sink=sink,
        run_store=run_store,
        checkpoint_store=checkpoint_store,
    )

    result = await runner.run_pipeline(DummyPipeline(), {"ok": True})

    assert result == {"ok": True}
    assert runner.last_run_id is not None
    assert await run_store.get_run(runner.last_run_id) is not None
    assert await checkpoint_store.get_checkpoint(runner.last_run_id) == {"ok": True}
    assert len(sink.events) == 2
