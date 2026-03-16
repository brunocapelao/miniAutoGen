from __future__ import annotations

from dataclasses import dataclass
from json import JSONDecodeError, JSONDecoder, loads
from time import perf_counter
from typing import Any

import anyio


class GeminiCLIExecutionError(RuntimeError):
    """Raised when the Gemini CLI gateway cannot obtain a valid model response."""


@dataclass(frozen=True)
class GeminiCLIResult:
    text: str
    raw_stdout: str
    raw_stderr: str
    returncode: int
    duration_ms: float



def _extract_first_json_object(stdout: str) -> dict[str, Any]:
    decoder = JSONDecoder()
    for index, char in enumerate(stdout):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(stdout[index:])
        except JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise GeminiCLIExecutionError("Gemini CLI output did not contain a valid JSON object.")



def parse_gemini_output(stdout: str, stderr: str) -> str:
    stripped = stdout.strip()
    if not stripped:
        raise GeminiCLIExecutionError(f"Gemini CLI returned empty stdout. stderr={stderr!r}")

    try:
        payload = loads(stripped)
    except JSONDecodeError:
        payload = _extract_first_json_object(stripped)

    if not isinstance(payload, dict):
        raise GeminiCLIExecutionError("Gemini CLI JSON payload must be an object.")

    for key in ("response", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value

    raise GeminiCLIExecutionError(
        f"Gemini CLI JSON payload did not contain text. payload={payload!r}"
    )


async def run_gemini_command(
    command: list[str],
    prompt: str,
    *,
    timeout_seconds: float = 60.0,
) -> GeminiCLIResult:
    started = perf_counter()
    try:
        with anyio.fail_after(timeout_seconds):
            result = await anyio.run_process(command, input=prompt.encode("utf-8"))
    except TimeoutError as exc:
        raise GeminiCLIExecutionError(
            f"Gemini CLI timed out after {timeout_seconds} seconds."
        ) from exc
    except FileNotFoundError as exc:
        raise GeminiCLIExecutionError("Gemini CLI binary was not found.") from exc

    duration_ms = (perf_counter() - started) * 1000.0
    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")

    if result.returncode != 0:
        raise GeminiCLIExecutionError(
            f"Gemini CLI failed with exit code {result.returncode}. stderr={stderr!r}"
        )

    text = parse_gemini_output(stdout, stderr)
    return GeminiCLIResult(
        text=text,
        raw_stdout=stdout,
        raw_stderr=stderr,
        returncode=result.returncode,
        duration_ms=duration_ms,
    )
