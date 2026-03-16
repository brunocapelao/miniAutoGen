import pytest

from gemini_cli_gateway.runner import parse_gemini_output, run_gemini_command


class FakeProcessResult:
    def __init__(self) -> None:
        self.returncode = 0
        self.stdout = b'{"response":"hello"}'
        self.stderr = b''


@pytest.mark.asyncio
async def test_run_gemini_command_parses_successful_output(monkeypatch) -> None:
    async def fake_run_process(command, input=None, check=True):
        assert command == ["gemini", "-m", "gemini-2.5-pro", "--output-format", "json"]
        assert input == b"hello"
        assert check is False
        return FakeProcessResult()

    monkeypatch.setattr("gemini_cli_gateway.runner.anyio.run_process", fake_run_process)
    result = await run_gemini_command(
        ["gemini", "-m", "gemini-2.5-pro", "--output-format", "json"],
        "hello",
    )
    assert result.text == "hello"
    assert result.returncode == 0
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_run_gemini_command_retries_transient_non_zero_exit(monkeypatch) -> None:
    calls = {"count": 0}

    async def fake_run_process(command, input=None, check=True):
        calls["count"] += 1
        assert check is False
        if calls["count"] == 1:
            class FailedResult:
                returncode = 1
                stdout = b""
                stderr = b"temporary failure"

            return FailedResult()
        return FakeProcessResult()

    async def fake_sleep(delay: float) -> None:
        assert delay == 0.01

    monkeypatch.setattr("gemini_cli_gateway.runner.anyio.run_process", fake_run_process)
    monkeypatch.setattr("gemini_cli_gateway.runner.anyio.sleep", fake_sleep)

    result = await run_gemini_command(
        ["gemini", "-m", "gemini-2.5-pro", "--output-format", "json"],
        "hello",
        max_attempts=2,
        retry_delay_seconds=0.01,
    )

    assert result.text == "hello"
    assert calls["count"] == 2



def test_parse_gemini_output_falls_back_to_first_valid_json_object() -> None:
    stdout = 'warning line\n{"response":"hello"}\nextra line'
    assert parse_gemini_output(stdout, "") == "hello"
