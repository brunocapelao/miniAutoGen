"""Test that execute_pipeline accepts an optional event_sink parameter."""
from __future__ import annotations

import inspect

from miniautogen.cli.services.run_pipeline import execute_pipeline


def test_execute_pipeline_accepts_event_sink_param() -> None:
    """execute_pipeline must accept an optional event_sink keyword argument."""
    sig = inspect.signature(execute_pipeline)
    assert "event_sink" in sig.parameters, (
        "execute_pipeline must accept an 'event_sink' keyword argument"
    )
    param = sig.parameters["event_sink"]
    assert param.default is None, (
        "event_sink parameter should default to None"
    )
