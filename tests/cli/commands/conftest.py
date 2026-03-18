"""Shared fixtures for CLI command tests."""

import pytest
from click.testing import CliRunner

from miniautogen.cli.main import cli


@pytest.fixture
def init_project(tmp_path, monkeypatch):
    """Initialize a MiniAutoGen project in tmp_path and return a CliRunner."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["init", "proj"])
    monkeypatch.chdir(tmp_path / "proj")
    return runner
