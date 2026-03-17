"""Tests for init CLI command."""

from click.testing import CliRunner

from miniautogen.cli.main import cli


def test_init_creates_project(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "myproject"])
    assert result.exit_code == 0
    assert "Project created" in result.output
    assert "Next steps:" in result.output
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


def test_init_fails_if_exists_nonempty(tmp_path, monkeypatch) -> None:
    """Non-empty directory without --force should fail."""
    monkeypatch.chdir(tmp_path)
    d = tmp_path / "myproject"
    d.mkdir()
    (d / "existing.txt").write_text("existing content")
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "myproject"])
    assert result.exit_code != 0


def test_init_empty_dir_succeeds(tmp_path, monkeypatch) -> None:
    """Empty existing directory is fine."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "myproject").mkdir()
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "myproject"])
    assert result.exit_code == 0


def test_init_force_preserves_existing(tmp_path, monkeypatch) -> None:
    """--force adds missing files without overwriting existing ones."""
    monkeypatch.chdir(tmp_path)
    d = tmp_path / "myproject"
    d.mkdir()
    # Create a custom file that should be preserved
    custom = d / "miniautogen.yaml"
    custom.write_text("custom: true\n")
    (d / "my_notes.txt").write_text("keep me")

    runner = CliRunner()
    result = runner.invoke(cli, ["init", "myproject", "--force"])
    assert result.exit_code == 0, result.output

    # Custom miniautogen.yaml should NOT be overwritten
    assert custom.read_text() == "custom: true\n"
    # But missing files should be added
    assert (d / "pipelines" / "main.py").is_file()
    # Non-template files preserved
    assert (d / "my_notes.txt").read_text() == "keep me"


def test_init_force_adds_missing_files(tmp_path, monkeypatch) -> None:
    """--force on existing project adds only missing files."""
    monkeypatch.chdir(tmp_path)
    # Create project normally first
    runner = CliRunner()
    runner.invoke(cli, ["init", "myproject"])

    # Delete a file
    (tmp_path / "myproject" / "agents" / "researcher.yaml").unlink()
    assert not (tmp_path / "myproject" / "agents" / "researcher.yaml").exists()

    # Force init should recreate it
    result = runner.invoke(cli, ["init", "myproject", "--force"])
    assert result.exit_code == 0
    assert (tmp_path / "myproject" / "agents" / "researcher.yaml").is_file()
