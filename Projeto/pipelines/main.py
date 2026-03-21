"""Main pipeline for Projeto.

This is the default pipeline executed by `miniautogen run main`.
"""

from __future__ import annotations

from typing import Any


class MainPipeline:
    """Pipeline that sends input to the configured engine and returns its response."""

    def __init__(self, engine_config: dict[str, Any] | None = None) -> None:
        self._engine_config = engine_config

    async def run(self, state: dict) -> dict:
        """Execute the pipeline.

        If an engine is configured, sends the input message to the LLM
        and returns the response. Otherwise, returns a placeholder.
        """
        user_input = state.get("input", "Hello!")
        engine_config = state.get("engine_config", self._engine_config)

        if engine_config is None:
            return {**state, "status": "completed", "output": "(no engine configured)"}

        # Lazy imports to avoid circular dependencies at scaffold time
        from miniautogen.backends.engine_resolver import EngineResolver
        from miniautogen.backends.models import SendTurnRequest, StartSessionRequest
        from miniautogen.cli.config import require_project_config

        _project_root, config = require_project_config()
        resolver = EngineResolver()

        engine_name = engine_config.get("engine_name", config.defaults.engine)
        driver = resolver.resolve(engine_name, config)

        session = await driver.start_session(
            StartSessionRequest(backend_id=engine_name),
        )
        turn_request = SendTurnRequest(
            session_id=session.session_id,
            messages=[{"role": "user", "content": user_input}],
        )

        # Collect streamed events into a final response
        response_parts: list[str] = []
        async for event in driver.send_turn(turn_request):
            if event.payload:
                text = event.payload.get("text", "")
                if text:
                    response_parts.append(text)

        response_text = "".join(response_parts) if response_parts else "(empty response)"

        return {
            **state,
            "status": "completed",
            "output": response_text,
            "engine": engine_name,
        }


def build_pipeline(engine_config: dict[str, Any] | None = None) -> MainPipeline:
    """Factory function referenced by miniautogen.yaml."""
    return MainPipeline(engine_config=engine_config)
