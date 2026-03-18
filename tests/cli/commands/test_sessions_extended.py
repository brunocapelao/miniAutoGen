"""Extended tests for sessions CLI command — show, list filters, clean variants."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import yaml
from click.testing import CliRunner

from miniautogen.cli.config import CONFIG_FILENAME
from miniautogen.cli.main import cli


def _make_project(tmp_path: Path) -> Path:
    config = {
        "project": {"name": "test"},
        "defaults": {"engine_profile": "default_api"},
        "engine_profiles": {
            "default_api": {"kind": "api", "provider": "litellm"},
        },
        "pipelines": {"main": {"target": "pipelines.main:build"}},
    }
    (tmp_path / CONFIG_FILENAME).write_text(yaml.dump(config))
    return tmp_path


# ---------------------------------------------------------------------------
# sessions show
# ---------------------------------------------------------------------------


def test_sessions_show_found(tmp_path, monkeypatch) -> None:
    """Show a run that exists returns its details in text format."""
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    fake_run = {"run_id": "abc123", "status": "completed", "created_at": "2025-01-01"}

    with patch(
        "miniautogen.cli.commands.sessions.run_async",
        return_value=fake_run,
    ):
        runner = CliRunner()
        result = runner.invoke(cli, ["sessions", "show", "abc123"])

    assert result.exit_code == 0, result.output
    assert "run_id" in result.output
    assert "abc123" in result.output


def test_sessions_show_json(tmp_path, monkeypatch) -> None:
    """Show a run in JSON format."""
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    fake_run = {"run_id": "xyz789", "status": "failed"}

    with patch(
        "miniautogen.cli.commands.sessions.run_async",
        return_value=fake_run,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli, ["sessions", "show", "xyz789", "--format", "json"],
        )

    assert result.exit_code == 0, result.output
    assert '"run_id"' in result.output


def test_sessions_show_not_found(tmp_path, monkeypatch) -> None:
    """Show a run that doesn't exist exits with error."""
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    with patch(
        "miniautogen.cli.commands.sessions.run_async",
        return_value=None,
    ):
        runner = CliRunner()
        result = runner.invoke(cli, ["sessions", "show", "nonexistent"])

    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# sessions list: with filters
# ---------------------------------------------------------------------------


def test_sessions_list_with_status_filter(tmp_path, monkeypatch) -> None:
    """List runs filtered by --status."""
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    fake_runs = [
        {"run_id": "r1", "status": "completed", "created_at": "2025-01-01"},
    ]

    with patch(
        "miniautogen.cli.commands.sessions.run_async",
        return_value=fake_runs,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli, ["sessions", "list", "--status", "completed"],
        )

    assert result.exit_code == 0, result.output
    assert "r1" in result.output


def test_sessions_list_with_limit(tmp_path, monkeypatch) -> None:
    """List runs with --limit."""
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    with patch(
        "miniautogen.cli.commands.sessions.run_async",
        return_value=[],
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli, ["sessions", "list", "--limit", "5"],
        )

    assert result.exit_code == 0, result.output


def test_sessions_list_text_table(tmp_path, monkeypatch) -> None:
    """List runs in text format renders a table with rows."""
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    fake_runs = [
        {"run_id": "aaa111bbb222", "status": "completed", "created_at": "2025-01-01T00:00:00Z"},
        {"run_id": "ccc333ddd444", "status": "failed", "created_at": "2025-01-02T00:00:00Z"},
    ]

    with patch(
        "miniautogen.cli.commands.sessions.run_async",
        return_value=fake_runs,
    ):
        runner = CliRunner()
        result = runner.invoke(cli, ["sessions", "list"])

    assert result.exit_code == 0, result.output
    # Table should contain truncated run IDs
    assert "aaa111bbb222"[:12] in result.output
    assert "Run ID" in result.output


def test_sessions_list_json_format(tmp_path, monkeypatch) -> None:
    """List runs in JSON format."""
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    fake_runs = [{"run_id": "r1", "status": "completed"}]

    with patch(
        "miniautogen.cli.commands.sessions.run_async",
        return_value=fake_runs,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli, ["sessions", "list", "--format", "json"],
        )

    assert result.exit_code == 0, result.output
    assert '"run_id"' in result.output


# ---------------------------------------------------------------------------
# sessions clean
# ---------------------------------------------------------------------------


def test_sessions_clean_older_than_confirm_yes(tmp_path, monkeypatch) -> None:
    """Clean with --older-than prompts for confirmation; user says yes."""
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    with patch(
        "miniautogen.cli.commands.sessions.run_async",
        return_value=3,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli, ["sessions", "clean", "--older-than", "7"],
            input="y\n",
        )

    assert result.exit_code == 0, result.output
    assert "deleted" in result.output.lower()


def test_sessions_clean_older_than_confirm_no(tmp_path, monkeypatch) -> None:
    """Clean with --older-than; user declines confirmation."""
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["sessions", "clean", "--older-than", "7"],
        input="n\n",
    )

    assert result.exit_code == 0, result.output
    assert "cancelled" in result.output.lower()


def test_sessions_clean_yes_flag_skips_confirm(tmp_path, monkeypatch) -> None:
    """Clean with --yes skips the confirmation prompt."""
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    with patch(
        "miniautogen.cli.commands.sessions.run_async",
        return_value=0,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli, ["sessions", "clean", "--yes"],
        )

    assert result.exit_code == 0, result.output
    assert "deleted" in result.output.lower()


def test_sessions_clean_older_than_with_yes(tmp_path, monkeypatch) -> None:
    """Clean with both --older-than and --yes skips prompt."""
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    with patch(
        "miniautogen.cli.commands.sessions.run_async",
        return_value=2,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli, ["sessions", "clean", "--older-than", "30", "--yes"],
        )

    assert result.exit_code == 0, result.output
    assert "deleted 2 run(s)" in result.output.lower()


def test_sessions_clean_no_flags_errors(tmp_path, monkeypatch) -> None:
    """Clean without --older-than or --yes exits with error."""
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["sessions", "clean"])

    assert result.exit_code != 0
