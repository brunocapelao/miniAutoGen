"""RecordReplayEngine — record real agent interactions and replay deterministically.

Records the *semantic behavior* (input → decision/output) of agents during
a real run, then replays those exact decisions in subsequent test runs.
Unlike VCR-style HTTP recording, this is robust to prompt changes.

Usage::

    # Record mode: wrap real agents
    recorder = RecordReplayEngine()
    recorder.wrap("analyst", real_analyst_agent)
    # ... run the flow normally ...
    recorder.save("recordings/session_001.json")

    # Replay mode: load and use as mock agents
    replayer = RecordReplayEngine.from_recording("recordings/session_001.json")
    analyst = replayer.agent("analyst")
    # ... run tests deterministically ...
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from miniautogen.testing.mock_engine import MockAgent, _CallRecord


class _RecordingProxy:
    """Proxy that records calls to a real agent while passing through."""

    def __init__(self, agent_id: str, real_agent: Any) -> None:
        self._agent_id = agent_id
        self._real = real_agent
        self._records: list[dict[str, Any]] = []

    @property
    def agent_id(self) -> str:
        return self._agent_id

    async def _record_call(self, action: str, input_data: Any, coro: Any) -> Any:
        result = await coro
        self._records.append({
            "action": action,
            "input": _serialize(input_data),
            "response": _serialize(result),
        })
        return result

    async def process(self, input: Any) -> Any:
        return await self._record_call("process", input, self._real.process(input))

    async def reply(self, message: str, context: dict[str, Any]) -> str:
        return await self._record_call("reply", message, self._real.reply(message, context))

    async def route(self, conversation_history: list[Any]) -> Any:
        return await self._record_call("route", conversation_history, self._real.route(conversation_history))

    async def contribute(self, topic: str) -> Any:
        return await self._record_call("contribute", topic, self._real.contribute(topic))

    async def review(self, target_id: str, contribution: Any) -> Any:
        return await self._record_call("review", target_id, self._real.review(target_id, contribution))

    async def consolidate(self, topic: str, contributions: list, reviews: list) -> Any:
        return await self._record_call(
            "consolidate", topic,
            self._real.consolidate(topic, contributions, reviews),
        )

    async def produce_final_document(self, state: Any, contributions: list) -> Any:
        return await self._record_call(
            "produce_final_document", None,
            self._real.produce_final_document(state, contributions),
        )

    async def execute(self, prompt: str) -> str:
        return await self._record_call("execute", prompt, self._real.execute(prompt))

    async def initialize(self) -> None:
        if hasattr(self._real, "initialize"):
            await self._real.initialize()

    async def close(self) -> None:
        if hasattr(self._real, "close"):
            await self._real.close()


def _serialize(obj: Any) -> Any:
    """Best-effort serialization of objects to JSON-safe dicts."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return str(obj)


class RecordReplayEngine:
    """Records real agent interactions and replays them deterministically.

    Two modes:
    1. **Record mode**: Wrap real agents with `wrap()`, run the flow,
       then `save()` the recording.
    2. **Replay mode**: Load a recording with `from_recording()`, get
       deterministic mock agents with `agent()`.
    """

    def __init__(self) -> None:
        self._proxies: dict[str, _RecordingProxy] = {}
        self._recordings: dict[str, list[dict[str, Any]]] = {}
        self._mock_agents: dict[str, MockAgent] = {}

    # -- Record mode --

    def wrap(self, agent_id: str, real_agent: Any) -> _RecordingProxy:
        """Wrap a real agent with a recording proxy.

        Args:
            agent_id: Agent identifier.
            real_agent: The real agent to wrap.

        Returns:
            A recording proxy that acts like the real agent.
        """
        proxy = _RecordingProxy(agent_id, real_agent)
        self._proxies[agent_id] = proxy
        return proxy

    def save(self, path: str | Path) -> None:
        """Save all recorded interactions to a JSON file.

        Args:
            path: File path to save the recording.
        """
        data: dict[str, Any] = {
            "version": "1.0",
            "agents": {},
        }
        for agent_id, proxy in self._proxies.items():
            data["agents"][agent_id] = proxy._records

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str))

    # -- Replay mode --

    @classmethod
    def from_recording(cls, path: str | Path) -> "RecordReplayEngine":
        """Load a recording and create a replay engine.

        Args:
            path: Path to the JSON recording file.

        Returns:
            A RecordReplayEngine in replay mode.
        """
        path = Path(path)
        data = json.loads(path.read_text())
        engine = cls()
        engine._recordings = data.get("agents", {})

        for agent_id, records in engine._recordings.items():
            engine._mock_agents[agent_id] = MockAgent(
                agent_id,
                responses=records,
            )

        return engine

    def agent(self, agent_id: str) -> MockAgent:
        """Get a replay agent for the given ID.

        Raises:
            KeyError: If agent was not in the recording.
        """
        if agent_id not in self._mock_agents:
            raise KeyError(
                f"No recording found for agent '{agent_id}'. "
                f"Available: {', '.join(self._mock_agents.keys()) or 'none'}"
            )
        return self._mock_agents[agent_id]

    def registry(self) -> dict[str, MockAgent]:
        """Get all replay agents as a registry dict."""
        return dict(self._mock_agents)

    def recorded_agents(self) -> list[str]:
        """List all agent IDs that have recordings."""
        return list(self._recordings.keys())
