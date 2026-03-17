"""Tests for init CLI command."""

from click.testing import CliRunner

from miniautogen.cli.main import cli


def test_init_creates_project(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "myproject"])
    assert result.exit_code == 0
    assert "Project created" in result.output
    assert (tmp_path / "myproject" / "miniautogen.yaml").is_file()


def test_init_creates_full_structure(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "myproject"])
    assert result.exit_code == 0
    p = tmp_path / "myproject"
    assert (p / "agents" / "researcher.yaml").is_file()
    assert (p / "skills" / "example" / "SKILL.md").is_file()
    assert (p / "tools" / "web_search.yaml").is_file()
    assert (p / "memory" / "profiles.yaml").is_file()
    assert (p / "pipelines" / "main.py").is_file()
    assert (p / ".env").is_file()
    assert (p / "mcp").is_dir()


def test_init_no_examples(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "myproject", "--no-examples"])
    assert result.exit_code == 0
    p = tmp_path / "myproject"
    assert (p / "miniautogen.yaml").is_file()
    assert not (p / "agents" / "researcher.yaml").exists()


def test_init_custom_model(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli, ["init", "myproject", "--model", "gemini-2.5-pro"],
    )
    assert result.exit_code == 0
    content = (tmp_path / "myproject" / "miniautogen.yaml").read_text()
    assert "gemini-2.5-pro" in content


def test_init_fails_if_exists(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "myproject").mkdir()
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "myproject"])
    assert result.exit_code != 0
