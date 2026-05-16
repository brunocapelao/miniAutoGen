"""Tests for UI sink selection gating logic.

These tests verify that _select_ui_sink returns the correct sink
implementation based on output_format, TTY availability, and --verbose flag.
All must fail initially because _select_ui_sink does not exist yet.
"""

from __future__ import annotations

from miniautogen.cli.services.event_sinks import _select_ui_sink


def test_text_tty_not_verbose_returns_rich_live_sink(
    monkeypatch,
) -> None:
    """output_format=text + isatty() + not verbose -> RichLiveEventSink."""
    from miniautogen.cli.services.rich_live_sink import RichLiveEventSink

    monkeypatch.setattr("sys.stderr.isatty", lambda: True)
    sink = _select_ui_sink(output_format="text", verbose=False)
    assert isinstance(sink, RichLiveEventSink)


def test_text_tty_verbose_returns_verbose_sink(monkeypatch) -> None:
    """output_format=text + isatty() + verbose -> _VerboseEventSink."""
    from miniautogen.cli.services.event_sinks import _VerboseEventSink

    monkeypatch.setattr("sys.stderr.isatty", lambda: True)
    sink = _select_ui_sink(output_format="text", verbose=True)
    assert isinstance(sink, _VerboseEventSink)


def test_json_returns_none(monkeypatch) -> None:
    """output_format=json -> sink is None (no visual UI)."""
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)
    sink = _select_ui_sink(output_format="json", verbose=False)
    assert sink is None


def test_notty_text_returns_verbose_sink(monkeypatch) -> None:
    """Not a TTY + text format -> _VerboseEventSink fallback."""
    from miniautogen.cli.services.event_sinks import _VerboseEventSink

    monkeypatch.setattr("sys.stderr.isatty", lambda: False)
    sink = _select_ui_sink(output_format="text", verbose=False)
    assert isinstance(sink, _VerboseEventSink)


def test_miniautogen_no_tty_forces_fallback(monkeypatch) -> None:
    """MINIAUTOGEN_NO_TTY=1 forces non-rich sink even when isatty()."""
    from miniautogen.cli.services.event_sinks import _VerboseEventSink

    monkeypatch.setattr("sys.stderr.isatty", lambda: True)
    monkeypatch.setenv("MINIAUTOGEN_NO_TTY", "1")
    sink = _select_ui_sink(output_format="text", verbose=False)
    assert isinstance(sink, _VerboseEventSink)
