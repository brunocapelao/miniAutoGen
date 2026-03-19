"""Tests for CLI deprecation warning utilities."""

from __future__ import annotations

import warnings

from miniautogen.cli.deprecation import emit_deprecation


def test_emit_deprecation_emits_warning() -> None:
    """emit_deprecation should emit a DeprecationWarning with the given message."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        emit_deprecation("old_name", "new_name", since="0.5.0")
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "old_name" in str(w[0].message)
        assert "new_name" in str(w[0].message)
        assert "0.5.0" in str(w[0].message)


def test_emit_deprecation_message_format() -> None:
    """The deprecation message should include old name, new name, and version."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        emit_deprecation("pipelines", "flows", since="0.5.0")
        msg = str(w[0].message)
        assert "pipelines" in msg
        assert "flows" in msg
        assert "deprecated" in msg.lower()
