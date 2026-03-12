from miniautogen.pipeline.pipeline import ChatPipelineState


def test_chat_pipeline_state_exposes_mutable_mapping_state():
    state = ChatPipelineState(group_chat="chat", chat_admin="admin")
    state.update_state(selected_agent="assistant")

    assert state.get_state()["group_chat"] == "chat"
    assert state.get_state()["selected_agent"] == "assistant"
