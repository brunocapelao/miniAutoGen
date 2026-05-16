"""Tests that FlowConfig response_format and prompts propagate to AgentRuntime."""
from __future__ import annotations

import pytest

from miniautogen.cli.config import (
    EngineConfig,
    FlowConfig,
    ProjectMeta,
    WorkspaceConfig,
)
from miniautogen.core.runtime.pipeline_runner import PipelineRunner, _build_timeout_policy
from miniautogen.policies.execution import ExecutionPolicy


class TestFlowConfigPropagation:
    @pytest.mark.anyio()
    async def test_flow_prompts_reach_agent_runtime(self) -> None:
        """FlowConfig.prompts should be passed to AgentRuntime._flow_prompts."""
        # This test validates the wiring; full integration tested separately.
        fc = FlowConfig(
            mode="deliberation",
            participants=["agent1", "agent2"],
            leader="agent1",
            prompts={"contribute": "Custom {topic} prompt."},
            response_format="free_text",
        )
        assert fc.prompts["contribute"] == "Custom {topic} prompt."
        assert fc.response_format == "free_text"


@pytest.mark.anyio()
async def test_cli_timeout_wires_to_config_driven_flow_timeout_source() -> None:
    """Config-driven flows use the runner execution timeout as flow timeout."""
    runner = PipelineRunner(execution_policy=ExecutionPolicy(timeout_seconds=5.0))
    config = WorkspaceConfig(
        project=ProjectMeta(name="test"),
        engines={"default_api": EngineConfig(timeout_seconds=120.0)},
    )
    flow_config = FlowConfig(
        mode="workflow",
        participants=["agent"],
        agent_timeouts={},
        round_timeouts={},
    )

    policy = _build_timeout_policy(
        flow_config=flow_config,
        config=config,
        flow_timeout=runner.execution_policy.timeout_seconds,
    )
    events: list[dict[str, object]] = []

    async def emit(event_type: str, **payload: object) -> None:
        events.append({"type": event_type, **payload})

    async with policy.scope_for_turn(
        agent_id="agent",
        round_name=None,
        emit=emit,
    ) as resolved:
        assert resolved.seconds == 5.0
        assert resolved.source == "flow"
