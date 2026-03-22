"""Tests for HumanAgent and InputChannel implementations."""

from __future__ import annotations

import pytest

from miniautogen.core.contracts.agentic_loop import RouterDecision
from miniautogen.core.contracts.deliberation import Contribution, Review
from miniautogen.core.runtime.human_agent import (
    HumanAgent,
    InputChannel,
    QueueInputChannel,
)


class TestQueueInputChannel:
    @pytest.mark.anyio
    async def test_send_prompt(self) -> None:
        channel = QueueInputChannel()
        await channel.send_prompt("Hello?", {"agent_id": "human"})
        assert channel.last_prompt == "Hello?"
        assert channel.last_context["agent_id"] == "human"

    @pytest.mark.anyio
    async def test_push_and_receive(self) -> None:
        channel = QueueInputChannel()
        channel.push_response("yes")
        result = await channel.receive()
        assert result == "yes"

    @pytest.mark.anyio
    async def test_receive_timeout(self) -> None:
        channel = QueueInputChannel()
        with pytest.raises(TimeoutError):
            await channel.receive(timeout_seconds=0.01)

    @pytest.mark.anyio
    async def test_satisfies_protocol(self) -> None:
        channel = QueueInputChannel()
        assert isinstance(channel, InputChannel)


class TestHumanAgent:
    def _make_agent(self) -> tuple[HumanAgent, QueueInputChannel]:
        channel = QueueInputChannel()
        agent = HumanAgent(agent_id="human", channel=channel)
        return agent, channel

    @pytest.mark.anyio
    async def test_process(self) -> None:
        agent, channel = self._make_agent()
        channel.push_response("human output")
        result = await agent.process("analyze this")
        assert result == "human output"
        assert "process" in channel.last_context["action"]

    @pytest.mark.anyio
    async def test_reply(self) -> None:
        agent, channel = self._make_agent()
        channel.push_response("hello back")
        result = await agent.reply("hello", {"turn": 1})
        assert result == "hello back"

    @pytest.mark.anyio
    async def test_route_next_agent(self) -> None:
        agent, channel = self._make_agent()
        channel.push_response("analyst")
        decision = await agent.route(["msg1", "msg2"])
        assert isinstance(decision, RouterDecision)
        assert decision.next_agent == "analyst"
        assert decision.terminate is False

    @pytest.mark.anyio
    async def test_route_terminate(self) -> None:
        agent, channel = self._make_agent()
        channel.push_response("done")
        decision = await agent.route([])
        assert decision.terminate is True

    @pytest.mark.anyio
    async def test_route_terminate_variants(self) -> None:
        for word in ("Done", "finish", "END", "terminate"):
            agent, channel = self._make_agent()
            channel.push_response(word)
            decision = await agent.route([])
            assert decision.terminate is True, f"'{word}' should terminate"

    @pytest.mark.anyio
    async def test_route_empty_input(self) -> None:
        """Empty or whitespace-only input produces termination."""
        for empty_input in ("", "   ", "\n", "\t"):
            agent, channel = self._make_agent()
            channel.push_response(empty_input)
            decision = await agent.route([])
            assert decision.terminate is True, (
                f"Empty input {empty_input!r} should terminate"
            )
            assert "empty input" in decision.current_state_summary.lower()

    @pytest.mark.anyio
    async def test_contribute(self) -> None:
        agent, channel = self._make_agent()
        channel.push_response("My analysis of the topic")
        contrib = await agent.contribute("API design")
        assert isinstance(contrib, Contribution)
        assert contrib.participant_id == "human"
        assert contrib.content["text"] == "My analysis of the topic"

    @pytest.mark.anyio
    async def test_review(self) -> None:
        agent, channel = self._make_agent()
        contrib = Contribution(
            participant_id="other", title="Design", content={"text": "proposal"},
        )
        channel.push_response("Looks good but needs more detail")
        review = await agent.review("other", contrib)
        assert isinstance(review, Review)
        assert review.reviewer_id == "human"
        assert review.target_id == "other"
        assert len(review.concerns) == 1

    @pytest.mark.anyio
    async def test_review_empty(self) -> None:
        agent, channel = self._make_agent()
        contrib = Contribution(participant_id="other", title="T", content={})
        channel.push_response("")
        review = await agent.review("other", contrib)
        assert review.concerns == []

    @pytest.mark.anyio
    async def test_consolidate_sufficient(self) -> None:
        agent, channel = self._make_agent()
        contribs = [Contribution(participant_id="a", title="t", content={})]
        reviews: list[Review] = []
        channel.push_response("yes")
        state = await agent.consolidate("topic", contribs, reviews)
        assert state.is_sufficient is True

    @pytest.mark.anyio
    async def test_consolidate_insufficient(self) -> None:
        agent, channel = self._make_agent()
        channel.push_response("no, needs more work")
        state = await agent.consolidate("topic", [], [])
        assert state.is_sufficient is False

    @pytest.mark.anyio
    async def test_produce_final_document(self) -> None:
        from miniautogen.core.contracts.deliberation import DeliberationState

        agent, channel = self._make_agent()
        state = DeliberationState(is_sufficient=True, leader_decision="Approved")
        channel.push_response("Final summary here")
        doc = await agent.produce_final_document(state, [])
        assert doc.executive_summary == "Final summary here"
        assert doc.decision_summary == "Approved"

    @pytest.mark.anyio
    async def test_lifecycle(self) -> None:
        agent, _ = self._make_agent()
        await agent.initialize()
        await agent.close()

    def test_agent_id(self) -> None:
        agent, _ = self._make_agent()
        assert agent.agent_id == "human"

    @pytest.mark.anyio
    async def test_timeout(self) -> None:
        channel = QueueInputChannel()
        agent = HumanAgent(
            agent_id="human", channel=channel, timeout_seconds=0.01,
        )
        with pytest.raises(TimeoutError):
            await agent.process("test")

    @pytest.mark.anyio
    async def test_workflow_integration(self) -> None:
        """Test HumanAgent in a WorkflowRuntime."""
        from datetime import datetime, timezone

        from miniautogen.core.contracts.coordination import WorkflowPlan, WorkflowStep
        from miniautogen.core.contracts.enums import RunStatus
        from miniautogen.core.contracts.run_context import RunContext
        from miniautogen.core.runtime.pipeline_runner import PipelineRunner
        from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime
        from miniautogen.testing.mock_engine import MockEngine

        # AI agent + Human agent
        engine = MockEngine()
        engine.script("analyst", [{"response": "AI analysis"}])

        channel = QueueInputChannel()
        human = HumanAgent(agent_id="reviewer", channel=channel)

        registry: dict = {**engine.registry(), "reviewer": human}

        runner = PipelineRunner()
        wf = WorkflowRuntime(runner=runner, agent_registry=registry)

        plan = WorkflowPlan(steps=[
            WorkflowStep(component_name="analyst", agent_id="analyst"),
            WorkflowStep(component_name="reviewer", agent_id="reviewer"),
        ])
        ctx = RunContext(
            run_id="test-1",
            started_at=datetime.now(timezone.utc),
            correlation_id="test-1",
            input_payload="initial data",
        )

        # Pre-load human response
        channel.push_response("human approved")

        result = await wf.run([], ctx, plan)
        assert result.status == RunStatus.FINISHED
        assert result.output == "human approved"
