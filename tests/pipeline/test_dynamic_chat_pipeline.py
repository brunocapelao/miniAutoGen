from miniautogen.core.contracts.agentic_loop import ConversationPolicy
from miniautogen.pipeline.dynamic_chat_pipeline import DynamicChatPipeline


def test_dynamic_chat_pipeline_holds_router_agents_and_policy() -> None:
    pipeline = DynamicChatPipeline(
        router_agent="Router",
        agent_registry={"Planner": object(), "QA_Agent": object()},
        policy=ConversationPolicy(max_turns=4),
    )
    assert pipeline.router_agent == "Router"
    assert "Planner" in pipeline.agent_registry
    assert pipeline.policy.max_turns == 4
