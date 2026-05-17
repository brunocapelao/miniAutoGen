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
        protocol: str | None = None,
    ) -> None:
        self._command = command
        self._provider = provider
        self._timeout_seconds = timeout_seconds
        self._env = env or {}
        self._protocol: str = protocol or self._detect_protocol(command)
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
            cmd = list(self._command)
            stdin_data: bytes | None = None

            if self._protocol == "gemini":
                if "--skip-trust" not in cmd[1:]:
                    cmd.insert(1, "--skip-trust")
                stdin_data = self._build_gemini_prompt(request.messages)
            elif self._protocol == "prompt-flag":
                prompt_text = self._extract_prompt(request.messages)
                if prompt_text:
                    if prompt_text.startswith("-"):
                        logger.debug("prompt_starts_with_dash_using_stdin")
                        stdin_data = (dumps({
                            "session_id": request.session_id,
                            "messages": request.messages,
                            "metadata": request.metadata,
                        }) + "\n").encode()
                    else:
                        cmd.extend(["-p", prompt_text])
                else:
                    stdin_data = (dumps({
                        "session_id": request.session_id,
                        "messages": request.messages,
                        "metadata": request.metadata,
                    }) + "\n").encode()
            else:
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

    @staticmethod
    def _build_gemini_prompt(messages: list[dict[str, Any]]) -> bytes:
        """Build a plain-text prompt for gemini CLI from message list."""
        blocks: list[str] = []
        for msg in messages:
            role = msg.get("role", "user").upper()
            content = ""
            raw = msg.get("content", "")
            if isinstance(raw, str):
                content = raw
            elif isinstance(raw, list):
                texts = [
                    p.get("text", "") for p in raw
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                content = "\n".join(texts)
            blocks.append(f"{role}\n{content}")
        return "\n\n".join(blocks).encode("utf-8")

    @staticmethod
    def _detect_protocol(command: list[str]) -> str:
        """Auto-detect the communication protocol from the CLI command name."""
        base_cmd = command[0] if command else ""
        KNOWN_MAP: dict[str, str] = {
            "gemini": "gemini",
            "claude": "prompt-flag",
            "codex": "prompt-flag",
        }
        return KNOWN_MAP.get(base_cmd, "json")

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
