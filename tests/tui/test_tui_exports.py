"""Tests for TUI package public API exports."""

from __future__ import annotations


def test_tui_exports_app() -> None:
    from miniautogen.tui import MiniAutoGenDash

    assert MiniAutoGenDash is not None


def test_tui_exports_event_sink() -> None:
    from miniautogen.tui import TuiEventSink

    assert TuiEventSink is not None


def test_tui_exports_tui_event() -> None:
    from miniautogen.tui import TuiEvent

    assert TuiEvent is not None


def test_tui_exports_status() -> None:
    from miniautogen.tui import AgentStatus, StatusVocab

    assert AgentStatus is not None
    assert StatusVocab is not None


def test_all_exports_in_dunder_all() -> None:
    import miniautogen.tui as tui_mod

    assert hasattr(tui_mod, "__all__")
    expected = {"MiniAutoGenDash", "TuiEventSink", "TuiEvent", "AgentStatus", "StatusVocab"}
    assert set(tui_mod.__all__) == expected
