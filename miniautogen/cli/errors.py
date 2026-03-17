"""CLI-specific exception hierarchy and exit code mapping.

Exit codes follow the spec:
  0 = success
  1 = validation error
  2 = configuration error
  3 = execution/runtime error
  4 = I/O error
"""

from __future__ import annotations

import click


class CLIError(click.ClickException):
    """Base CLI error with configurable exit code and optional hint."""

    exit_code: int = 1
    hint: str | None = None

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        if hint is not None:
            self.hint = hint

    def format_message(self) -> str:
        lines = [f"Error: {self.message}"]
        if self.hint:
            lines.append(f"Hint: {self.hint}")
        return "\n".join(lines)


class ValidationError(CLIError):
    """Project or resource validation failed."""
    exit_code = 1


class ConfigurationError(CLIError):
    """Invalid or unparseable project configuration."""
    exit_code = 2


class ProjectNotFoundError(CLIError):
    """No miniautogen.yaml found in directory tree."""
    exit_code = 2


class ExecutionError(CLIError):
    """Pipeline execution or runtime error."""
    exit_code = 3


class PipelineNotFoundError(CLIError):
    """Referenced pipeline does not exist."""
    exit_code = 3


class IOError(CLIError):
    """File or network I/O error."""
    exit_code = 4
