"""Tests for the Conversation model."""

from miniautogen.core.contracts.conversation import Conversation
from miniautogen.core.contracts.message import Message


def _make_message(sender_id: str = "agent_1", content: str = "hello") -> Message:
    return Message(sender_id=sender_id, content=content)


class TestConversationInit:
    def test_empty_conversation(self):
        conv = Conversation()
        assert conv.id == ""
        assert conv.messages == []
        assert conv.metadata == {}

    def test_conversation_with_id(self):
        conv = Conversation(id="conv-1")
        assert conv.id == "conv-1"

    def test_conversation_with_messages(self):
        msgs = [_make_message(), _make_message(sender_id="agent_2", content="world")]
        conv = Conversation(id="conv-1", messages=msgs)
        assert len(conv.messages) == 2
        assert conv.messages[0].content == "hello"
        assert conv.messages[1].content == "world"

    def test_conversation_with_metadata(self):
        conv = Conversation(metadata={"topic": "test"})
        assert conv.metadata == {"topic": "test"}


class TestAddMessage:
    def test_add_message_returns_new_conversation(self):
        conv = Conversation(id="conv-1")
        msg = _make_message()
        new_conv = conv.add_message(msg)
        assert new_conv is not conv
        assert len(new_conv.messages) == 1
        assert new_conv.messages[0] is msg

    def test_add_message_does_not_mutate_original(self):
        conv = Conversation(id="conv-1")
        msg = _make_message()
        conv.add_message(msg)
        assert len(conv.messages) == 0

    def test_add_message_preserves_existing(self):
        msg1 = _make_message(content="first")
        conv = Conversation(id="conv-1", messages=[msg1])
        msg2 = _make_message(content="second")
        new_conv = conv.add_message(msg2)
        assert len(new_conv.messages) == 2
        assert new_conv.messages[0].content == "first"
        assert new_conv.messages[1].content == "second"

    def test_add_message_preserves_id_and_metadata(self):
        conv = Conversation(id="conv-1", metadata={"key": "val"})
        new_conv = conv.add_message(_make_message())
        assert new_conv.id == "conv-1"
        assert new_conv.metadata == {"key": "val"}


class TestLastN:
    def test_last_n_returns_last_messages(self):
        msgs = [_make_message(content=str(i)) for i in range(5)]
        conv = Conversation(messages=msgs)
        result = conv.last_n(2)
        assert len(result) == 2
        assert result[0].content == "3"
        assert result[1].content == "4"

    def test_last_n_with_n_larger_than_length(self):
        msgs = [_make_message(content=str(i)) for i in range(3)]
        conv = Conversation(messages=msgs)
        result = conv.last_n(10)
        assert len(result) == 3

    def test_last_n_zero_returns_empty(self):
        msgs = [_make_message()]
        conv = Conversation(messages=msgs)
        assert conv.last_n(0) == []

    def test_last_n_negative_returns_empty(self):
        msgs = [_make_message()]
        conv = Conversation(messages=msgs)
        assert conv.last_n(-1) == []

    def test_last_n_on_empty_conversation(self):
        conv = Conversation()
        assert conv.last_n(5) == []


class TestBySender:
    def test_by_sender_filters_correctly(self):
        msgs = [
            _make_message(sender_id="a", content="1"),
            _make_message(sender_id="b", content="2"),
            _make_message(sender_id="a", content="3"),
        ]
        conv = Conversation(messages=msgs)
        result = conv.by_sender("a")
        assert len(result) == 2
        assert result[0].content == "1"
        assert result[1].content == "3"

    def test_by_sender_no_match(self):
        msgs = [_make_message(sender_id="a")]
        conv = Conversation(messages=msgs)
        assert conv.by_sender("nonexistent") == []

    def test_by_sender_empty_conversation(self):
        conv = Conversation()
        assert conv.by_sender("a") == []


class TestConversationExport:
    def test_importable_from_contracts(self):
        from miniautogen.core.contracts import Conversation as ConvFromInit
        assert ConvFromInit is Conversation
