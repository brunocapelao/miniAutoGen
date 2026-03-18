"""Tests for the context-aware hint bar."""

from __future__ import annotations

from textual.widget import Widget

from miniautogen.tui.widgets.hint_bar import HintBar


def test_hint_bar_is_widget() -> None:
    assert issubclass(HintBar, Widget)


def test_hint_bar_default_hints() -> None:
    bar = HintBar()
    text = bar.get_hint_text()
    assert "[Enter]" in text
    assert "[/]" in text or "search" in text.lower()
    assert "[:]" in text or "commands" in text.lower()
    assert "[?]" in text or "help" in text.lower()


def test_hint_bar_default_context_is_workspace() -> None:
    bar = HintBar()
    assert bar.context == "workspace"


def test_hint_bar_agent_detail_hints() -> None:
    bar = HintBar(context="agent_detail")
    text = bar.get_hint_text()
    assert "[Esc]" in text
    assert "[e]" in text or "edit" in text.lower()


def test_hint_bar_approval_hints() -> None:
    bar = HintBar(context="approval")
    text = bar.get_hint_text()
    assert "[A]" in text or "approve" in text.lower()
    assert "[D]" in text or "deny" in text.lower()


def test_hint_bar_set_context() -> None:
    bar = HintBar()
    assert bar.context == "workspace"
    bar.set_context("approval")
    assert bar.context == "approval"
    text = bar.get_hint_text()
    assert "[A]" in text or "approve" in text.lower()


def test_hint_bar_unknown_context_falls_back_to_default() -> None:
    bar = HintBar(context="unknown_context")
    text = bar.get_hint_text()
    # Should fall back to default hints
    assert "[Enter]" in text
