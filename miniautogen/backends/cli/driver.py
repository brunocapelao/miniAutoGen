"""CLIAgentDriver — runs CLI agent tools as subprocess.

Supports Claude Code, Gemini CLI, Codex CLI, and any CLI tool
that accepts JSON on stdin and outputs JSON on stdout.

Uses anyio.open_process for async subprocess management.
"""

from __future__ import annotations

import uuid

from miniautogen._json import dumps
from typing import Any, AsyncIterator

from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.errors import CancelNotSupportedError, TurnExecutionError
from miniautogen.backends.models import (
    AgentEvent,
    ArtifactRef,
    BackendCapabilities,
    CancelTurnRequest,
    SendTurnRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from miniautogen.observability.logging import get_logger

logger = get_logger(__name__)


class CLIAgentDriver(AgentDriver):
    """Driver that runs CLI agent tools as subprocess.

    Communication protocol:
    - Send: JSON object on stdin (one per line)
    - Receive: JSON lines on stdout (one event per line)

    Args:
        command: Command and arguments to run (e.g., ["claude", "--agent"]).
        provider: Provider identifier for logging.
        timeout_seconds: Maximum time for a single turn.
        env: Additional environment variables for the subprocess.
    """

    def __init__(
        self,
        command: list[str],
        provider: str = "cli",
        timeout_seconds: float = 300.0,
        env: dict[str, str] | None = None,
    ) -> None:
        self._command = command
        self._provider = provider
        self._timeout_seconds = timeout_seconds
        self._env = env or {}
        self._caps = BackendCapabilities(
            sessions=True,
            streaming=True,
            cancel=False,
            resume=False,
            tools=True,
            artifacts=True,
            multimodal=False,
        )

    async def start_session(
        self,
        request: StartSessionRequest,
    ) -> StartSessionResponse:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        logger.info(
            "session_started",
            session_id=session_id,
            backend_id=request.backend_id,
            provider=self._provider,
            command=self._command,
        )
        return StartSessionResponse(
            session_id=session_id,
            capabilities=self._caps,
        )

    async def send_turn(
        self,
        request: SendTurnRequest,
    ) -> AsyncIterator[AgentEvent]:
        import subprocess

        import anyio

        turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        logger.debug(
            "send_turn_cli",
            session_id=request.session_id,
            turn_id=turn_id,
            command=self._command,
        )

        yield AgentEvent(
            type="turn_started",
            session_id=request.session_id,
            turn_id=turn_id,
        )

        try:
            # Extract the last user message as the prompt text
            prompt_text = self._extract_prompt(request.messages)

            # Build command with prompt flag for CLI tools that support it
            cmd = list(self._command)
            if prompt_text and self._supports_prompt_flag():
                if prompt_text.startswith("-"):
                    # Prompt starts with dash — fall back to stdin to avoid
                    # the CLI tool interpreting it as a flag/option
                    logger.debug("prompt_starts_with_dash_using_stdin")
                    stdin_data = (dumps({
                        "session_id": request.session_id,
                        "messages": request.messages,
                        "metadata": request.metadata,
                    }) + "\n").encode()
                else:
                    cmd.extend(["-p", prompt_text])
                    stdin_data = None
            else:
                # Fallback: send JSON on stdin for tools that expect it
                stdin_data = (dumps({
                    "session_id": request.session_id,
                    "messages": request.messages,
                    "metadata": request.metadata,
                }) + "\n").encode()

            async with await anyio.open_process(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as proc:
                # Send input if needed
                if proc.stdin:
                    if stdin_data:
                        await proc.stdin.send(stdin_data)
                    await proc.stdin.aclose()

                # Read output
                output = b""
                if proc.stdout:
                    async for chunk in proc.stdout:
                        output += chunk

                await proc.wait()

                if proc.returncode != 0:
                    stderr_output = b""
                    if proc.stderr:
                        async for chunk in proc.stderr:
                            stderr_output += chunk
                    msg = (
                        f"CLI process exited with code {proc.returncode}: "
                        f"{stderr_output.decode(errors='replace')[:500]}"
                    )
                    raise TurnExecutionError(msg)

                # Parse output as text response
                content = output.decode(errors="replace").strip()

                yield AgentEvent(
                    type="message_completed",
                    session_id=request.session_id,
                    turn_id=turn_id,
                    payload={"text": content, "role": "assistant"},
                )

        except TurnExecutionError:
            raise
        except Exception as exc:
            logger.error("cli_driver_error", error=str(exc), command=self._command)
            msg = f"CLI driver error: {exc}"
            raise TurnExecutionError(msg) from exc

        yield AgentEvent(
            type="turn_completed",
            session_id=request.session_id,
            turn_id=turn_id,
        )

    async def cancel_turn(
        self,
        request: CancelTurnRequest,
    ) -> None:
        raise CancelNotSupportedError(
            "CLIAgentDriver does not support cancellation yet",
        )

    async def list_artifacts(self, session_id: str) -> list[ArtifactRef]:
        return []

    async def close_session(self, session_id: str) -> None:
        pass

    async def capabilities(self) -> BackendCapabilities:
        return self._caps

    def _supports_prompt_flag(self) -> bool:
        """Check if the CLI tool supports -p/--prompt flag for headless mode."""
        # Known CLI tools that accept -p for non-interactive prompts
        base_cmd = self._command[0] if self._command else ""
        return base_cmd in ("gemini", "claude", "codex")

    @staticmethod
    def _extract_prompt(messages: list[dict[str, Any]]) -> str | None:
        """Extract the text content from the last user message.

        For CLI tools that accept a prompt string rather than a full
        chat history, we extract just the last user message content.
        """
        if not messages:
            return None
        # Find the last user message
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                # Handle structured content (list of parts)
                if isinstance(content, list):
                    texts = [
                        p.get("text", "") for p in content
                        if isinstance(p, dict) and p.get("type") == "text"
                    ]
                    return "\n".join(texts) if texts else None
        return None
