from miniautogen.schemas import ChatState, Message


def test_legacy_schema_module_still_exports_message_and_chat_state():
    message = Message(sender_id="user", content="hello")
    state = ChatState(messages=[message])

    assert state.messages[0].content == "hello"
