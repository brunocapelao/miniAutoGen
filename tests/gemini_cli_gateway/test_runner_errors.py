import pytest

from gemini_cli_gateway.runner import (
    GeminiCLIExecutionError,
    parse_gemini_output,
    run_gemini_command,
)


class NonZeroProcessResult:
    def __init__(self) -> None:
        self.returncode = 2
        self.stdout = b""
        self.stderr = b"boom"


@pytest.mark.asyncio
async def test_run_gemini_command_raises_on_non_zero_exit(monkeypatch) -> None:
    async def fake_run_process(command, input=None):
        return NonZeroProcessResult()

    monkeypatch.setattr("gemini_cli_gateway.runner.anyio.run_process", fake_run_process)

    with pytest.raises(GeminiCLIExecutionError):
        await run_gemini_command(["gemini"], "hello")



def test_parse_gemini_output_raises_on_invalid_json() -> None:
    with pytest.raises(GeminiCLIExecutionError):
        parse_gemini_output("not-json", "")



def test_parse_gemini_output_raises_on_empty_stdout() -> None:
    with pytest.raises(GeminiCLIExecutionError):
        parse_gemini_output("", "warning")
