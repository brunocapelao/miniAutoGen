"""Tests for init template variants (quickstart, minimal, advanced, from-example)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from miniautogen.cli.commands.init import init_command
from miniautogen.cli.services.init_project import scaffold_project


class TestScaffoldProjectTemplates:
    """Unit tests for scaffold_project with template parameter."""

    def test_init_quickstart_template(self, tmp_path: Path) -> None:
        """Quickstart template creates project with assistant agent."""
        project_dir = scaffold_project("myproj", tmp_path, template="quickstart")

        assert (project_dir / "miniautogen.yaml").exists()
        assert (project_dir / ".env").exists()
        assert (project_dir / "README.md").exists()
        assert (project_dir / "agents" / "assistant.yaml").exists()

        config = (project_dir / "miniautogen.yaml").read_text()
        assert "myproj" in config
        assert "default_api" in config

    def test_init_minimal_template(self, tmp_path: Path) -> None:
        """Minimal template creates bare project with no agents dir."""
        project_dir = scaffold_project("myproj", tmp_path, template="minimal")

        assert (project_dir / "miniautogen.yaml").exists()
        assert (project_dir / ".env").exists()
        assert not (project_dir / "agents").exists()
        assert not (project_dir / "README.md").exists()

        config = (project_dir / "miniautogen.yaml").read_text()
        assert "myproj" in config
        assert "flows: {}" in config

    def test_init_advanced_template(self, tmp_path: Path) -> None:
        """Advanced template creates project with 3 agents."""
        project_dir = scaffold_project("myproj", tmp_path, template="advanced")

        assert (project_dir / "miniautogen.yaml").exists()
        assert (project_dir / ".env").exists()
        assert (project_dir / "README.md").exists()
        assert (project_dir / "agents" / "researcher.yaml").exists()
        assert (project_dir / "agents" / "reviewer.yaml").exists()
        assert (project_dir / "agents" / "architect.yaml").exists()

        config = (project_dir / "miniautogen.yaml").read_text()
        assert "primary_api" in config
        assert "creative_api" in config
        assert "research" in config
        assert "design" in config

    def test_init_from_example(self, tmp_path: Path) -> None:
        """from_example copies files from examples/hello-world."""
        project_dir = scaffold_project(
            "myproj", tmp_path, from_example="hello-world",
        )

        assert (project_dir / "miniautogen.yaml").exists()
        assert (project_dir / "agents" / "assistant.yaml").exists()

    def test_init_default_is_project(self, tmp_path: Path) -> None:
        """Default template is project (legacy layout with skills/, tools/, pipelines/)."""
        project_dir = scaffold_project("myproj", tmp_path)

        assert (project_dir / "miniautogen.yaml").exists()
        assert (project_dir / "agents" / "researcher.yaml").exists()
        assert (project_dir / "skills" / "example" / "SKILL.md").exists()
        assert (project_dir / "tools" / "web_search.yaml").exists()
        assert (project_dir / "pipelines" / "main.py").exists()

    def test_init_invalid_example(self, tmp_path: Path) -> None:
        """Invalid example name raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            scaffold_project("myproj", tmp_path, from_example="nonexistent-example")


class TestInitCommandTemplates:
    """CLI integration tests for init with --template and --from-example."""

    def test_cli_template_quickstart(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(init_command, ["myproj", "--template", "quickstart"])
        assert result.exit_code == 0
        assert (tmp_path / "myproj" / "agents" / "assistant.yaml").exists()

    def test_cli_template_minimal(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(init_command, ["myproj", "--template", "minimal"])
        assert result.exit_code == 0
        assert not (tmp_path / "myproj" / "agents").exists()

    def test_cli_template_advanced(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(init_command, ["myproj", "--template", "advanced"])
        assert result.exit_code == 0
        assert (tmp_path / "myproj" / "agents" / "researcher.yaml").exists()
        assert (tmp_path / "myproj" / "agents" / "reviewer.yaml").exists()
        assert (tmp_path / "myproj" / "agents" / "architect.yaml").exists()

    def test_cli_from_example(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(init_command, ["myproj", "--from-example", "hello-world"])
        assert result.exit_code == 0
        assert (tmp_path / "myproj" / "miniautogen.yaml").exists()

    def test_cli_invalid_template(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(init_command, ["myproj", "--template", "bogus"])
        assert result.exit_code != 0

    def test_cli_invalid_example(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(init_command, ["myproj", "--from-example", "nope"])
        assert result.exit_code != 0
