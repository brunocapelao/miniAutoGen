from datetime import UTC, datetime

from miniautogen.core.contracts.run_context import RunContext
from miniautogen.pipeline.pipeline import ChatPipelineState


def test_bridge_chat_pipeline_state_to_run_context():
    from miniautogen.compat.state_bridge import bridge_chat_pipeline_state_to_run_context

    legacy = ChatPipelineState(group_chat="chat", chat_admin="admin")

    context = bridge_chat_pipeline_state_to_run_context(
        legacy,
        run_id="run-1",
        started_at=datetime.now(UTC),
        correlation_id="corr-1",
    )

    assert isinstance(context, RunContext)
    assert context.run_id == "run-1"
    assert context.execution_state["group_chat"] == "chat"
