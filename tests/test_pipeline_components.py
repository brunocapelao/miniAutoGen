"""Comprehensive tests for pipeline components, Pipeline, and PipelineComponent."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miniautogen.core.contracts.message import Message
from miniautogen.pipeline.components.components import (
    AgentReplyComponent,
    Jinja2SingleTemplateComponent,
    LLMResponseComponent,
    NextAgentSelectorComponent,
    TerminateChatComponent,
    UserExitException,
    UserResponseComponent,
)
from miniautogen.pipeline.components.pipelinecomponent import PipelineComponent
from miniautogen.pipeline.pipeline import ChatPipelineState, Pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _ConcreteComponent(PipelineComponent):
    """Minimal concrete subclass for testing the ABC."""

    async def process(self, state: Any) -> Any:
        return state


class _FailingComponent(PipelineComponent):
    async def process(self, state: Any) -> Any:
        raise RuntimeError("boom")


class _AppendComponent(PipelineComponent):
    """Appends a marker to state to verify ordering."""

    def __init__(self, marker: str):
        self.marker = marker

    async def process(self, state: Any) -> Any:
        state.update_state(
            trail=state.get_state().get("trail", "") + self.marker,
        )
        return state


def _make_chat_state(**kwargs) -> ChatPipelineState:
    return ChatPipelineState(**kwargs)


def _make_group_chat(agents=None, messages=None):
    """Return a mock group-chat with async helpers."""
    gc = MagicMock()
    gc.agents = agents or []
    gc.get_messages = AsyncMock(return_value=messages or [])
    gc.add_message = AsyncMock()
    return gc


def _make_agent(agent_id="a1", name="Agent1"):
    agent = MagicMock()
    agent.agent_id = agent_id
    agent.name = name
    agent.generate_reply = AsyncMock(return_value="reply text")
    return agent


def _make_message(sender_id="a1", content="hello"):
    return Message(sender_id=sender_id, content=content)


# ===================================================================
# PipelineComponent (abstract base)
# ===================================================================


class TestPipelineComponent:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            PipelineComponent()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_concrete_subclass_works(self):
        comp = _ConcreteComponent()
        result = await comp.process("data")
        assert result == "data"


# ===================================================================
# Pipeline
# ===================================================================


class TestPipeline:
    def test_init_empty(self):
        p = Pipeline()
        assert p.components == []

    def test_init_with_components(self):
        c = _ConcreteComponent()
        p = Pipeline(components=[c])
        assert p.components == [c]

    def test_add_component_valid(self):
        p = Pipeline()
        c = _ConcreteComponent()
        p.add_component(c)
        assert len(p.components) == 1

    def test_add_component_rejects_non_subclass(self):
        p = Pipeline()
        with pytest.raises(TypeError, match="subclass of PipelineComponent"):
            p.add_component("not a component")  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_run_empty_pipeline(self):
        p = Pipeline()
        state = _make_chat_state(x=1)
        with pytest.warns(DeprecationWarning):
            result = await p.run(state)
        assert result is state

    @pytest.mark.asyncio
    async def test_run_chains_components(self):
        p = Pipeline(
            components=[_AppendComponent("A"), _AppendComponent("B")]
        )
        state = _make_chat_state()
        with pytest.warns(DeprecationWarning):
            result = await p.run(state)
        assert result.get_state()["trail"] == "AB"

    @pytest.mark.asyncio
    async def test_run_propagates_error(self):
        p = Pipeline(components=[_FailingComponent()])
        state = _make_chat_state()
        with pytest.raises(RuntimeError, match="boom"):
            with pytest.warns(DeprecationWarning):
                await p.run(state)


# ===================================================================
# UserResponseComponent
# ===================================================================


class TestUserResponseComponent:
    @pytest.mark.asyncio
    async def test_process_captures_input(self):
        comp = UserResponseComponent()
        state = _make_chat_state()
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value="user said hi"
            )
            result = await comp.process(state)

        assert result == "user said hi"
        assert state.get_state()["reply"] == "user said hi"

    @pytest.mark.asyncio
    async def test_process_raises_on_error(self):
        comp = UserResponseComponent()
        state = _make_chat_state()
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                side_effect=EOFError("no input")
            )
            with pytest.raises(EOFError):
                await comp.process(state)


# ===================================================================
# NextAgentSelectorComponent
# ===================================================================


class TestNextAgentSelectorComponent:
    @pytest.mark.asyncio
    async def test_raises_when_no_group_chat(self):
        comp = NextAgentSelectorComponent()
        state = _make_chat_state()
        with pytest.raises(ValueError, match="Invalid GroupChat"):
            await comp.process(state)

    @pytest.mark.asyncio
    async def test_raises_when_group_chat_has_no_agents_attr(self):
        comp = NextAgentSelectorComponent()
        gc = object()  # no .agents attribute
        state = _make_chat_state(group_chat=gc)
        with pytest.raises(ValueError, match="Invalid GroupChat"):
            await comp.process(state)

    @pytest.mark.asyncio
    async def test_selects_first_agent_when_no_messages(self):
        a1 = _make_agent("a1", "First")
        a2 = _make_agent("a2", "Second")
        gc = _make_group_chat(agents=[a1, a2], messages=[])
        state = _make_chat_state(group_chat=gc)

        comp = NextAgentSelectorComponent()
        result = await comp.process(state)

        assert state.get_state()["selected_agent"] is a1

    @pytest.mark.asyncio
    async def test_selects_next_agent_round_robin(self):
        a1 = _make_agent("a1", "First")
        a2 = _make_agent("a2", "Second")
        msg = _make_message(sender_id="a1", content="hi")
        gc = _make_group_chat(agents=[a1, a2], messages=[msg])
        state = _make_chat_state(group_chat=gc)

        comp = NextAgentSelectorComponent()
        await comp.process(state)

        assert state.get_state()["selected_agent"] is a2

    @pytest.mark.asyncio
    async def test_wraps_around_to_first_agent(self):
        a1 = _make_agent("a1", "First")
        a2 = _make_agent("a2", "Second")
        msg = _make_message(sender_id="a2", content="hi")
        gc = _make_group_chat(agents=[a1, a2], messages=[msg])
        state = _make_chat_state(group_chat=gc)

        comp = NextAgentSelectorComponent()
        await comp.process(state)

        assert state.get_state()["selected_agent"] is a1

    @pytest.mark.asyncio
    async def test_raises_when_select_next_agent_fails(self):
        gc = _make_group_chat(agents=[])
        gc.get_messages = AsyncMock(side_effect=RuntimeError("db error"))
        state = _make_chat_state(group_chat=gc)

        comp = NextAgentSelectorComponent()
        with pytest.raises(RuntimeError, match="db error"):
            await comp.process(state)


# ===================================================================
# AgentReplyComponent
# ===================================================================


class TestAgentReplyComponent:
    @pytest.mark.asyncio
    async def test_raises_without_agent(self):
        gc = _make_group_chat()
        state = _make_chat_state(group_chat=gc)
        comp = AgentReplyComponent()
        with pytest.raises(ValueError, match="Agent and GroupChat are required"):
            await comp.process(state)

    @pytest.mark.asyncio
    async def test_raises_without_group_chat(self):
        agent = _make_agent()
        state = _make_chat_state(selected_agent=agent)
        comp = AgentReplyComponent()
        with pytest.raises(ValueError, match="Agent and GroupChat are required"):
            await comp.process(state)

    @pytest.mark.asyncio
    async def test_generates_reply_and_adds_message(self):
        agent = _make_agent("a1", "Bot")
        gc = _make_group_chat()
        state = _make_chat_state(selected_agent=agent, group_chat=gc)

        comp = AgentReplyComponent()
        result = await comp.process(state)

        agent.generate_reply.assert_awaited_once_with(state)
        gc.add_message.assert_awaited_once_with(
            sender_id="a1", content="reply text"
        )
        assert result is state

    @pytest.mark.asyncio
    async def test_raises_on_generate_reply_error(self):
        agent = _make_agent()
        agent.generate_reply = AsyncMock(side_effect=RuntimeError("llm down"))
        gc = _make_group_chat()
        state = _make_chat_state(selected_agent=agent, group_chat=gc)

        comp = AgentReplyComponent()
        with pytest.raises(RuntimeError, match="llm down"):
            await comp.process(state)


# ===================================================================
# TerminateChatComponent
# ===================================================================


class TestTerminateChatComponent:
    @pytest.mark.asyncio
    async def test_raises_without_chat(self):
        state = _make_chat_state()
        comp = TerminateChatComponent()
        with pytest.raises(ValueError, match="Chat is required"):
            await comp.process(state)

    @pytest.mark.asyncio
    async def test_returns_state_when_no_messages(self):
        gc = _make_group_chat(messages=[])
        state = _make_chat_state(group_chat=gc)
        comp = TerminateChatComponent()
        result = await comp.process(state)
        assert result is state

    @pytest.mark.asyncio
    async def test_returns_state_when_no_terminate(self):
        msg = _make_message(content="keep going")
        gc = _make_group_chat(messages=[msg])
        state = _make_chat_state(group_chat=gc)

        comp = TerminateChatComponent()
        result = await comp.process(state)
        assert result is state

    @pytest.mark.asyncio
    async def test_detects_terminate_keyword(self):
        msg = _make_message(content="ok TERMINATE now")
        gc = _make_group_chat(messages=[msg])
        state = _make_chat_state(group_chat=gc)

        comp = TerminateChatComponent()
        result = await comp.process(state)
        assert result == "TERMINATE"

    @pytest.mark.asyncio
    async def test_detects_terminate_case_insensitive(self):
        msg = _make_message(content="terminate")
        gc = _make_group_chat(messages=[msg])
        state = _make_chat_state(group_chat=gc)

        comp = TerminateChatComponent()
        result = await comp.process(state)
        assert result == "TERMINATE"

    @pytest.mark.asyncio
    async def test_calls_chat_admin_stop(self):
        msg = _make_message(content="TERMINATE")
        gc = _make_group_chat(messages=[msg])
        admin = MagicMock()
        admin.stop = MagicMock()
        state = _make_chat_state(group_chat=gc, chat_admin=admin)

        comp = TerminateChatComponent()
        result = await comp.process(state)

        assert result == "TERMINATE"
        admin.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_terminate_without_chat_admin(self):
        msg = _make_message(content="TERMINATE")
        gc = _make_group_chat(messages=[msg])
        state = _make_chat_state(group_chat=gc)

        comp = TerminateChatComponent()
        result = await comp.process(state)
        assert result == "TERMINATE"


# ===================================================================
# LLMResponseComponent
# ===================================================================


class TestLLMResponseComponent:
    @pytest.mark.asyncio
    async def test_returns_state_when_no_prompt(self):
        llm = MagicMock()
        comp = LLMResponseComponent(llm_client=llm, model_name="gpt-4")
        state = _make_chat_state()
        result = await comp.process(state)
        assert result is state

    @pytest.mark.asyncio
    async def test_uses_generate_response(self):
        llm = MagicMock()
        llm.generate_response = AsyncMock(return_value="llm reply")
        comp = LLMResponseComponent(llm_client=llm, model_name="gpt-4")
        state = _make_chat_state(prompt="tell me a joke")

        result = await comp.process(state)

        llm.generate_response.assert_awaited_once_with("tell me a joke", "gpt-4")
        assert result.get_state()["reply"] == "llm reply"

    @pytest.mark.asyncio
    async def test_falls_back_to_get_model_response(self):
        llm = MagicMock(spec=[])  # no generate_response attribute
        llm.get_model_response = AsyncMock(return_value="fallback reply")
        comp = LLMResponseComponent(llm_client=llm, model_name="gpt-3.5")
        state = _make_chat_state(prompt="hi")

        result = await comp.process(state)

        llm.get_model_response.assert_awaited_once_with("hi", "gpt-3.5")
        assert result.get_state()["reply"] == "fallback reply"

    @pytest.mark.asyncio
    async def test_raises_when_response_is_empty(self):
        llm = MagicMock()
        llm.generate_response = AsyncMock(return_value="")
        comp = LLMResponseComponent(llm_client=llm)
        state = _make_chat_state(prompt="hi")

        with pytest.raises(RuntimeError, match="Failed to get response"):
            await comp.process(state)

    @pytest.mark.asyncio
    async def test_raises_when_response_is_none(self):
        llm = MagicMock()
        llm.generate_response = AsyncMock(return_value=None)
        comp = LLMResponseComponent(llm_client=llm)
        state = _make_chat_state(prompt="hi")

        with pytest.raises(RuntimeError, match="Failed to get response"):
            await comp.process(state)


# ===================================================================
# Jinja2SingleTemplateComponent
# ===================================================================


class TestJinja2SingleTemplateComponent:
    @pytest.mark.asyncio
    async def test_raises_without_template(self):
        comp = Jinja2SingleTemplateComponent()
        gc = _make_group_chat()
        state = _make_chat_state(group_chat=gc)
        with pytest.raises(ValueError, match="Template string not set"):
            await comp.process(state)

    @pytest.mark.asyncio
    async def test_init_defaults(self):
        comp = Jinja2SingleTemplateComponent()
        assert comp.template_str is None
        assert comp.variables is None
        assert comp.env is not None

    @pytest.mark.asyncio
    async def test_set_template_str(self):
        comp = Jinja2SingleTemplateComponent()
        comp.set_template_str("Hello {{ name }}")
        assert comp.template_str == "Hello {{ name }}"

    @pytest.mark.asyncio
    async def test_set_variables(self):
        comp = Jinja2SingleTemplateComponent()
        comp.set_variables({"name": "world"})
        assert comp.variables == {"name": "world"}

    @pytest.mark.asyncio
    async def test_renders_string_prompt(self):
        comp = Jinja2SingleTemplateComponent()
        comp.set_template_str("Hello {{ agent.name }}")

        agent = _make_agent("a1", "TestBot")
        msg = _make_message(sender_id="a1", content="hi there")
        gc = _make_group_chat(messages=[msg])
        state = _make_chat_state(group_chat=gc, selected_agent=agent)

        result = await comp.process(state)

        prompt = result.get_state()["prompt"]
        assert prompt == "Hello TestBot"

    @pytest.mark.asyncio
    async def test_renders_json_prompt(self):
        template = '{"role": "user", "content": "{{ agent.name }}"}'
        comp = Jinja2SingleTemplateComponent()
        comp.set_template_str(template)

        agent = _make_agent("a1", "Bot")
        gc = _make_group_chat(messages=[])
        state = _make_chat_state(group_chat=gc, selected_agent=agent)

        result = await comp.process(state)

        prompt = result.get_state()["prompt"]
        assert isinstance(prompt, dict)
        assert prompt["role"] == "user"
        assert prompt["content"] == "Bot"

    @pytest.mark.asyncio
    async def test_uses_messages_in_template(self):
        template = "{% for m in messages %}{{ m.message }};{% endfor %}"
        comp = Jinja2SingleTemplateComponent()
        comp.set_template_str(template)

        msgs = [
            _make_message("a1", "first"),
            _make_message("a2", "second"),
        ]
        gc = _make_group_chat(messages=msgs)
        agent = _make_agent()
        state = _make_chat_state(group_chat=gc, selected_agent=agent)

        result = await comp.process(state)

        prompt = result.get_state()["prompt"]
        assert "first" in prompt
        assert "second" in prompt

    @pytest.mark.asyncio
    async def test_variables_from_state_when_none(self):
        """When self.variables is None, should pull from state['variables']."""
        comp = Jinja2SingleTemplateComponent()
        comp.set_template_str("{{ custom_var }}")

        gc = _make_group_chat(messages=[])
        agent = _make_agent()
        state = _make_chat_state(
            group_chat=gc,
            selected_agent=agent,
            variables={"custom_var": "from_state"},
        )

        result = await comp.process(state)

        prompt = result.get_state()["prompt"]
        assert prompt == "from_state"

    @pytest.mark.asyncio
    async def test_explicit_variables_override(self):
        comp = Jinja2SingleTemplateComponent()
        comp.set_template_str("{{ custom_var }}")
        comp.set_variables({"custom_var": "explicit"})

        gc = _make_group_chat(messages=[])
        agent = _make_agent()
        state = _make_chat_state(group_chat=gc, selected_agent=agent)

        result = await comp.process(state)

        prompt = result.get_state()["prompt"]
        assert prompt == "explicit"


# ===================================================================
# ChatPipelineState
# ===================================================================


class TestChatPipelineState:
    def test_get_state(self):
        s = ChatPipelineState(a=1, b=2)
        assert s.get_state() == {"a": 1, "b": 2}

    def test_update_state(self):
        s = ChatPipelineState(a=1)
        s.update_state(b=2)
        assert s.get_state() == {"a": 1, "b": 2}

    def test_update_state_overwrites(self):
        s = ChatPipelineState(a=1)
        s.update_state(a=99)
        assert s.get_state()["a"] == 99
