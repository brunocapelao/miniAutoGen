"""Tests for the Message contract."""

from datetime import datetime

from miniautogen.core.contracts.message import Message


def test_message_creation() -> None:
    msg = Message(sender_id="agent-1", content="Hello")
    assert msg.sender_id == "agent-1"
    assert msg.content == "Hello"


def test_message_has_timestamp() -> None:
    msg = Message(sender_id="agent-1", content="test")
    assert isinstance(msg.timestamp, datetime)


def test_message_additional_info_default() -> None:
    msg = Message(sender_id="agent-1", content="test")
    assert msg.additional_info == {}


def test_message_with_additional_info() -> None:
    msg = Message(
        sender_id="agent-1",
        content="test",
        additional_info={"role": "system"},
    )
    assert msg.additional_info["role"] == "system"


def test_message_serialization_roundtrip() -> None:
    msg = Message(sender_id="agent-1", content="test data")
    data = msg.model_dump()
    restored = Message.model_validate(data)
    assert restored.sender_id == msg.sender_id
    assert restored.content == msg.content
