import pytest

from gemini_cli_gateway.runner import parse_gemini_output, run_gemini_command


class FakeProcessResult:
    def __init__(self) -> None:
        self.returncode = 0
        self.stdout = b'{"response":"hello"}'
        self.stderr = b''


@pytest.mark.asyncio
async def test_run_gemini_command_parses_successful_output(monkeypatch) -> None:
    async def fake_run_process(command, input=None):
        assert command == ["gemini", "-m", "gemini-2.5-pro", "--output-format", "json"]
        assert input == b"hello"
        return FakeProcessResult()

    monkeypatch.setattr("gemini_cli_gateway.runner.anyio.run_process", fake_run_process)
    result = await run_gemini_command(
        ["gemini", "-m", "gemini-2.5-pro", "--output-format", "json"],
        "hello",
    )
    assert result.text == "hello"
    assert result.returncode == 0
    assert result.duration_ms >= 0



def test_parse_gemini_output_falls_back_to_first_valid_json_object() -> None:
    stdout = 'warning line\n{"response":"hello"}\nextra line'
    assert parse_gemini_output(stdout, "") == "hello"
