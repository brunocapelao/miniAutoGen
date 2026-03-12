from miniautogen.pipeline.pipeline import ChatPipelineState


def test_bridge_chat_pipeline_state_returns_mutable_runtime_mapping():
    from miniautogen.compat.state_bridge import bridge_chat_pipeline_state

    state = ChatPipelineState(group_chat="chat", chat_admin="admin")
    result = bridge_chat_pipeline_state(state)

    assert result["group_chat"] == "chat"
    assert result["chat_admin"] == "admin"
