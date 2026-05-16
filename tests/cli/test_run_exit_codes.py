"""Tests for CLI exit codes on cancel/timeout/success."""

from unittest.mock import patch

import yaml
from click.testing import CliRunner

from miniautogen.cli.config import CONFIG_FILENAME
from miniautogen.cli.main import cli


def _mock_project(tmp_path):
    config = {
        "project": {"name": "test"},
        "defaults": {"engine_profile": "default_api"},
        "engine_profiles": {
            "default_api": {"kind": "api", "provider": "litellm"},
        },
        "pipelines": {"main": {"target": "pipelines.main:build_pipeline"}},
    }
    (tmp_path / CONFIG_FILENAME).write_text(yaml.dump(config))
    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    (pipelines_dir / "__init__.py").write_text("")
    (pipelines_dir / "main.py").write_text(
        "class P:\n"
        "    async def run(self, state):\n"
        '        return {**state, "done": True}\n'
        "def build_pipeline():\n"
        "    return P()\n"
    )
    return tmp_path


class TestRunExitCodes:
    def test_sigint_exits_130(self, tmp_path, monkeypatch):
        _mock_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        with patch(
            "miniautogen.cli.commands.run.run_async",
            side_effect=KeyboardInterrupt(),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["run"])

        assert result.exit_code == 130

    def test_timeout_exits_124(self, tmp_path, monkeypatch):
        _mock_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        with patch(
            "miniautogen.cli.commands.run.run_async",
            side_effect=TimeoutError("timed out"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["run"])

        assert result.exit_code == 124

    def test_success_exits_0(self, tmp_path, monkeypatch):
        _mock_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        with patch(
            "miniautogen.cli.commands.run.run_async",
            return_value={
                "status": "completed",
                "output": {"output": "hello"},
                "events": 5,
            },
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["run"])

        assert result.exit_code == 0
