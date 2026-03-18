"""Tests for the 7-state status vocabulary."""

from __future__ import annotations

from miniautogen.tui.status import AgentStatus, StatusVocab


def test_status_vocab_has_seven_states() -> None:
    assert len(AgentStatus) == 7


def test_status_done() -> None:
    info = StatusVocab.get(AgentStatus.DONE)
    assert info.symbol == "\u2713"  # checkmark
    assert info.color == "dim green"
    assert info.label == "Done"


def test_status_active() -> None:
    info = StatusVocab.get(AgentStatus.ACTIVE)
    assert info.symbol == "\u25cf"  # filled circle
    assert info.color == "bright_green"
    assert info.label == "Active"


def test_status_working() -> None:
    info = StatusVocab.get(AgentStatus.WORKING)
    assert info.symbol == "\u25d0"  # half circle
    assert info.color == "yellow"
    assert info.label == "Working"


def test_status_waiting() -> None:
    info = StatusVocab.get(AgentStatus.WAITING)
    assert info.symbol == "\u231b"  # hourglass
    assert info.color == "dark_orange"
    assert info.label == "Waiting"


def test_status_pending() -> None:
    info = StatusVocab.get(AgentStatus.PENDING)
    assert info.symbol == "\u25cb"  # open circle
    assert info.color == "grey50"
    assert info.label == "Pending"


def test_status_failed() -> None:
    info = StatusVocab.get(AgentStatus.FAILED)
    assert info.symbol == "\u2715"  # multiplication x
    assert info.color == "red"
    assert info.label == "Failed"


def test_status_cancelled() -> None:
    info = StatusVocab.get(AgentStatus.CANCELLED)
    assert info.symbol == "\u2298"  # circled division slash
    assert info.color == "dark_red"
    assert info.label == "Cancelled"


def test_all_symbols_are_unique() -> None:
    symbols = [StatusVocab.get(s).symbol for s in AgentStatus]
    assert len(symbols) == len(set(symbols))


def test_rich_markup() -> None:
    info = StatusVocab.get(AgentStatus.ACTIVE)
    markup = info.rich_markup()
    assert "bright_green" in markup
    assert "\u25cf" in markup
