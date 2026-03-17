"""Tests for CLI error hierarchy."""

from miniautogen.cli.errors import (
    CLIError,
    ConfigurationError,
    ExecutionError,
    IOError,
    PipelineNotFoundError,
    ProjectNotFoundError,
    ValidationError,
)


def test_cli_error_exit_code() -> None:
    err = CLIError("test")
    assert err.exit_code == 1


def test_validation_error_exit_code() -> None:
    assert ValidationError.exit_code == 1


def test_configuration_error_exit_code() -> None:
    assert ConfigurationError.exit_code == 2


def test_project_not_found_exit_code() -> None:
    assert ProjectNotFoundError.exit_code == 2


def test_execution_error_exit_code() -> None:
    assert ExecutionError.exit_code == 3


def test_pipeline_not_found_exit_code() -> None:
    assert PipelineNotFoundError.exit_code == 3


def test_io_error_exit_code() -> None:
    assert IOError.exit_code == 4


def test_cli_error_message() -> None:
    err = CLIError("something broke")
    assert err.format_message() == "Error: something broke"


def test_cli_error_message_with_hint() -> None:
    err = CLIError("something broke", hint="Try running 'miniautogen check'")
    assert "Error: something broke" in err.format_message()
    assert "Hint: Try running 'miniautogen check'" in err.format_message()


def test_all_errors_inherit_from_cli_error() -> None:
    for cls in [ProjectNotFoundError, ConfigurationError,
                PipelineNotFoundError, ValidationError,
                ExecutionError, IOError]:
        assert issubclass(cls, CLIError)
