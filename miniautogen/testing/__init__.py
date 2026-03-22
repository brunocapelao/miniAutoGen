"""Testing utilities for MiniAutoGen — deterministic simulation without LLM calls.

Provides MockEngine and RecordReplayEngine for unit testing multi-agent
coordination logic without spending tokens or depending on the network.

Usage::

    from miniautogen.testing import MockEngine, RecordReplayEngine

    # Script deterministic agent decisions
    engine = MockEngine()
    engine.script("analyst", [
        {"action": "contribute", "response": {"title": "Analysis", "content": {"key": "value"}}},
        {"action": "review", "response": {"strengths": ["good"], "concerns": []}},
    ])

    # Record and replay real sessions
    recorder = RecordReplayEngine(real_driver)
    # ... run real flow, then save
    recorder.save("session.json")
    # Later: replay deterministically
    replayer = RecordReplayEngine.from_recording("session.json")

.. stability:: experimental
"""

from miniautogen.testing.mock_engine import MockEngine
from miniautogen.testing.record_replay import RecordReplayEngine

__all__ = [
    "MockEngine",
    "RecordReplayEngine",
]
