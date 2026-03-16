from miniautogen.core.contracts.agentic_loop import ConversationPolicy
from miniautogen.pipeline.components.agentic_loop import AgenticLoopComponent


def test_agentic_loop_component_exposes_policy() -> None:
    component = AgenticLoopComponent(policy=ConversationPolicy(max_turns=5))
    assert component.policy.max_turns == 5
