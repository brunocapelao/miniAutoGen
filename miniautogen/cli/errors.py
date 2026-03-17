"""CLI-specific exception hierarchy and exit code mapping."""

from __future__ import annotations

import click


class CLIError(click.ClickException):
    """Base CLI error with configurable exit code."""

    exit_code: int = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)

    def format_message(self) -> str:
        return f"Error: {self.message}"


class ProjectNotFoundError(CLIError):
    """No miniautogen.yaml found in directory tree."""
    exit_code = 2


class ConfigurationError(CLIError):
    """Invalid or unparseable project configuration."""
    exit_code = 3


class PipelineNotFoundError(CLIError):
    """Referenced pipeline does not exist."""
    exit_code = 4


class ValidationError(CLIError):
    """Project validation failed."""
    exit_code = 5
