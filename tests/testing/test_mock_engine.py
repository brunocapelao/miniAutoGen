"""Tests for MockEngine and MockAgent."""

from __future__ import annotations

import pytest

from miniautogen.core.contracts.agentic_loop import RouterDecision
from miniautogen.core.contracts.deliberation import (
    Contribution,
    DeliberationState,
    FinalDocument,
    Review,
)
from miniautogen.testing.mock_engine import MockAgent, MockEngine


class TestMockAgent:
    @pytest.mark.anyio
    async def test_process(self) -> None:
        agent = MockAgent("test", responses=[{"response": "done"}])
        result = await agent.process("do something")
        assert result == "done"

    @pytest.mark.anyio
    async def test_reply(self) -> None:
        agent = MockAgent("test", responses=[{"response": "hello back"}])
        result = await agent.reply("hello", {})
        assert result == "hello back"

    @pytest.mark.anyio
    async def test_contribute_dict(self) -> None:
        agent = MockAgent("test", responses=[
            {"response": {"title": "My Analysis", "content": {"key": "val"}}},
        ])
        contrib = await agent.contribute("topic")
        assert isinstance(contrib, Contribution)
        assert contrib.title == "My Analysis"
        assert contrib.participant_id == "test"

    @pytest.mark.anyio
    async def test_contribute_string(self) -> None:
        agent = MockAgent("test", responses=[{"response": "plain text"}])
        contrib = await agent.contribute("topic")
        assert contrib.content == {"text": "plain text"}

    @pytest.mark.anyio
    async def test_review_dict(self) -> None:
        contrib = Contribution(participant_id="other", title="Test", content={})
        agent = MockAgent("test", responses=[
            {"response": {"strengths": ["good"], "concerns": ["bad"], "questions": []}},
        ])
        review = await agent.review("other", contrib)
        assert isinstance(review, Review)
        assert review.strengths == ["good"]
        assert review.reviewer_id == "test"

    @pytest.mark.anyio
    async def test_review_string_fallback(self) -> None:
        contrib = Contribution(participant_id="other", title="Test", content={})
        agent = MockAgent("test", responses=[
            {"response": "needs work"},
        ])
        review = await agent.review("other", contrib)
        assert isinstance(review, Review)
        assert review.concerns == ["needs work"]
        assert review.reviewer_id == "test"

    @pytest.mark.anyio
    async def test_route_dict(self) -> None:
        agent = MockAgent("test", responses=[
            {"response": {
                "current_state_summary": "s",
                "missing_information": "m",
                "next_agent": "agent_b",
            }},
        ])
        decision = await agent.route([])
        assert isinstance(decision, RouterDecision)
        assert decision.next_agent == "agent_b"

    @pytest.mark.anyio
    async def test_route_router_decision(self) -> None:
        rd = RouterDecision(
            current_state_summary="s",
            missing_information="m",
            terminate=True,
        )
        agent = MockAgent("test", responses=[{"response": rd}])
        result = await agent.route([])
        assert result.terminate is True

    @pytest.mark.anyio
    async def test_exhausted_responses_raises(self) -> None:
        agent = MockAgent("test", responses=[{"response": "one"}])
        await agent.process("first")
        with pytest.raises(IndexError, match="ran out of scripted responses"):
            await agent.process("second")

    @pytest.mark.anyio
    async def test_response_fn(self) -> None:
        def fn(action: str, input_data: object) -> str:
            return f"handled {action}"

        agent = MockAgent("test", response_fn=fn)
        r1 = await agent.process("a")
        r2 = await agent.reply("b", {})
        assert r1 == "handled process"
        assert r2 == "handled reply"

    @pytest.mark.anyio
    async def test_lifecycle_noop(self) -> None:
        agent = MockAgent("test")
        await agent.initialize()
        await agent.close()

    @pytest.mark.anyio
    async def test_consolidate_dict(self) -> None:
        agent = MockAgent("test", responses=[
            {"response": {"review_cycle": 2, "is_sufficient": True}},
        ])
        result = await agent.consolidate("topic", [], [])
        assert isinstance(result, DeliberationState)
        assert result.is_sufficient is True
        assert result.review_cycle == 2

    @pytest.mark.anyio
    async def test_consolidate_default(self) -> None:
        agent = MockAgent("test", responses=[
            {"response": "anything"},
        ])
        result = await agent.consolidate("topic", [], [])
        assert isinstance(result, DeliberationState)
        assert result.is_sufficient is True

    @pytest.mark.anyio
    async def test_produce_final_document_dict(self) -> None:
        agent = MockAgent("test", responses=[
            {"response": {
                "executive_summary": "sum",
                "decision_summary": "dec",
                "body_markdown": "body",
            }},
        ])
        state = DeliberationState(is_sufficient=True)
        result = await agent.produce_final_document(state, [])
        assert isinstance(result, FinalDocument)
        assert result.executive_summary == "sum"

    @pytest.mark.anyio
    async def test_produce_final_document_default(self) -> None:
        agent = MockAgent("test", responses=[
            {"response": "custom summary"},
        ])
        state = DeliberationState(is_sufficient=True)
        result = await agent.produce_final_document(state, [])
        assert isinstance(result, FinalDocument)
        assert result.executive_summary == "custom summary"

    @pytest.mark.anyio
    async def test_execute(self) -> None:
        agent = MockAgent("test", responses=[
            {"response": "executed result"},
        ])
        result = await agent.execute("do this")
        assert result == "executed result"


class TestMockEngine:
    def test_script_and_agent(self) -> None:
        engine = MockEngine()
        engine.script("a", [{"response": "r"}])
        agent = engine.agent("a")
        assert agent.agent_id == "a"

    def test_agent_missing_raises(self) -> None:
        engine = MockEngine()
        with pytest.raises(KeyError, match="No mock agent"):
            engine.agent("missing")

    @pytest.mark.anyio
    async def test_call_count_and_calls(self) -> None:
        engine = MockEngine()
        engine.script("a", [{"response": "r1"}, {"response": "r2"}])
        agent = engine.agent("a")
        await agent.process("input1")
        await agent.process("input2")
        assert engine.call_count("a") == 2
        assert engine.calls("a")[0].action == "process"
        assert engine.calls("a")[0].input == "input1"

    def test_registry(self) -> None:
        engine = MockEngine()
        engine.script("a", []).script("b", [])
        reg = engine.registry()
        assert "a" in reg
        assert "b" in reg

    @pytest.mark.anyio
    async def test_reset(self) -> None:
        engine = MockEngine()
        engine.script("a", [{"response": "r1"}, {"response": "r2"}])
        await engine.agent("a").process("x")
        assert engine.call_count("a") == 1
        engine.reset()
        assert engine.call_count("a") == 0
        # Can replay from start
        await engine.agent("a").process("y")
        assert engine.call_count("a") == 1

    def test_script_fn(self) -> None:
        engine = MockEngine()
        engine.script_fn("a", lambda action, inp: "dynamic")
        agent = engine.agent("a")
        assert agent._response_fn is not None

    @pytest.mark.anyio
    async def test_chaining(self) -> None:
        engine = MockEngine()
        result = engine.script("a", []).script("b", [])
        assert result is engine

    @pytest.mark.anyio
    async def test_workflow_integration(self) -> None:
        """Test MockEngine with WorkflowRuntime (the core use case)."""
        from datetime import datetime, timezone
        from miniautogen.core.contracts.coordination import WorkflowPlan, WorkflowStep
        from miniautogen.core.contracts.run_context import RunContext
        from miniautogen.core.contracts.enums import RunStatus
        from miniautogen.core.runtime.pipeline_runner import PipelineRunner
        from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime

        engine = MockEngine()
        engine.script("analyst", [{"response": "analysis done"}])
        engine.script("reviewer", [{"response": "review complete"}])

        runner = PipelineRunner()
        wf = WorkflowRuntime(runner=runner, agent_registry=engine.registry())

        plan = WorkflowPlan(steps=[
            WorkflowStep(component_name="analyst", agent_id="analyst"),
            WorkflowStep(component_name="reviewer", agent_id="reviewer"),
        ])
        ctx = RunContext(
            run_id="test-1",
            started_at=datetime.now(timezone.utc),
            correlation_id="test-1",
            input_payload="test data",
        )

        result = await wf.run([], ctx, plan)
        assert result.status == RunStatus.FINISHED
        assert engine.call_count("analyst") == 1
        assert engine.call_count("reviewer") == 1
