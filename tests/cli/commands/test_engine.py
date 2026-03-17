"""Tests for engine CLI command group."""

import yaml
from click.testing import CliRunner

from miniautogen.cli.main import cli


def _init_project(tmp_path, monkeypatch):
    """Helper: init a project and chdir into it."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["init", "proj"])
    monkeypatch.chdir(tmp_path / "proj")
    return runner


def test_engine_create_silent(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "engine", "create", "gpt4",
        "--provider", "openai",
        "--model", "gpt-4o",
        "--endpoint", "https://api.openai.com/v1",
        "--api-key-env", "OPENAI_API_KEY",
        "--capabilities", "chat",
    ], input="y\n")
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()

    # Verify written to YAML
    cfg = yaml.safe_load((tmp_path / "proj" / "miniautogen.yaml").read_text())
    assert "gpt4" in cfg["engine_profiles"]
    assert cfg["engine_profiles"]["gpt4"]["model"] == "gpt-4o"
    assert cfg["engine_profiles"]["gpt4"]["api_key"] == "${OPENAI_API_KEY}"


def test_engine_create_with_capabilities(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "engine", "create", "gemini",
        "--provider", "gemini",
        "--model", "gemini-2.5-pro",
        "--endpoint", "https://generativelanguage.googleapis.com/v1",
        "--api-key-env", "GEMINI_API_KEY",
        "--capabilities", "chat,embedding",
    ], input="y\n")
    assert result.exit_code == 0, result.output
    cfg = yaml.safe_load((tmp_path / "proj" / "miniautogen.yaml").read_text())
    assert cfg["engine_profiles"]["gemini"]["capabilities"] == ["chat", "embedding"]


def test_engine_create_interactive(tmp_path, monkeypatch) -> None:
    """Test interactive wizard prompts for missing fields."""
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(
        cli,
        ["engine", "create", "myengine"],
        input="openai\ngpt-4o\nhttps://api.openai.com/v1\nOPENAI_API_KEY\nchat\ny\n",
    )
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()


def test_engine_create_cancelled(tmp_path, monkeypatch) -> None:
    """Test wizard cancellation at confirmation prompt."""
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "engine", "create", "gpt4",
        "--provider", "openai",
        "--model", "gpt-4o",
        "--endpoint", "x",
        "--api-key-env", "X",
        "--capabilities", "chat",
    ], input="n\n")
    assert result.exit_code == 0
    assert "cancelled" in result.output.lower()
    # Engine should NOT be created
    cfg = yaml.safe_load((tmp_path / "proj" / "miniautogen.yaml").read_text())
    assert "gpt4" not in cfg.get("engine_profiles", {})


def test_engine_create_duplicate_fails(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    # default_api already exists from init
    result = runner.invoke(cli, [
        "engine", "create", "default_api",
        "--provider", "openai",
        "--model", "gpt-4o",
        "--endpoint", "x",
        "--api-key-env", "X",
        "--capabilities", "chat",
    ], input="y\n")
    assert result.exit_code != 0


def test_engine_create_validates_schema(tmp_path, monkeypatch) -> None:
    """Engine create validates against EngineProfileConfig."""
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "engine", "create", "valid",
        "--provider", "openai",
        "--model", "gpt-4o",
        "--endpoint", "x",
        "--api-key-env", "X",
        "--capabilities", "chat",
    ], input="y\n")
    assert result.exit_code == 0


def test_engine_create_credential_safety(tmp_path, monkeypatch) -> None:
    """Engine create stores only env var references, not keys."""
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "engine", "create", "safe",
        "--provider", "openai",
        "--model", "gpt-4o",
        "--endpoint", "x",
        "--api-key-env", "MY_SECRET_KEY",
        "--capabilities", "chat",
    ], input="y\n")
    assert result.exit_code == 0
    cfg = yaml.safe_load((tmp_path / "proj" / "miniautogen.yaml").read_text())
    assert cfg["engine_profiles"]["safe"]["api_key"] == "${MY_SECRET_KEY}"


def test_engine_list(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["engine", "list"])
    assert result.exit_code == 0
    assert "default_api" in result.output


def test_engine_list_json(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["engine", "list", "--format", "json"])
    assert result.exit_code == 0
    assert '"name"' in result.output


def test_engine_show(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["engine", "show", "default_api"])
    assert result.exit_code == 0
    assert "provider:" in result.output or "litellm" in result.output


def test_engine_show_json(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["engine", "show", "default_api", "--format", "json"])
    assert result.exit_code == 0
    assert '"provider"' in result.output


def test_engine_show_not_found(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["engine", "show", "nonexistent"])
    assert result.exit_code != 0


def test_engine_update(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "engine", "update", "default_api",
        "--model", "gpt-4o-mini",
    ])
    assert result.exit_code == 0
    assert "updated" in result.output.lower()

    cfg = yaml.safe_load((tmp_path / "proj" / "miniautogen.yaml").read_text())
    assert cfg["engine_profiles"]["default_api"]["model"] == "gpt-4o-mini"


def test_engine_update_dry_run(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    cfg_before = yaml.safe_load((tmp_path / "proj" / "miniautogen.yaml").read_text())
    original_model = cfg_before["engine_profiles"]["default_api"]["model"]

    result = runner.invoke(cli, [
        "engine", "update", "default_api",
        "--model", "claude-3.5-sonnet",
        "--dry-run",
    ])
    assert result.exit_code == 0
    assert "dry run" in result.output.lower()

    cfg = yaml.safe_load((tmp_path / "proj" / "miniautogen.yaml").read_text())
    assert cfg["engine_profiles"]["default_api"]["model"] == original_model


def test_engine_update_not_found(tmp_path, monkeypatch) -> None:
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, [
        "engine", "update", "nonexistent",
        "--model", "x",
    ])
    assert result.exit_code != 0


def test_engine_delete(tmp_path, monkeypatch) -> None:
    """Test engine deletion with confirmation."""
    runner = _init_project(tmp_path, monkeypatch)
    # Create a non-default engine first
    runner.invoke(cli, [
        "engine", "create", "extra",
        "--provider", "openai",
        "--model", "gpt-4o",
        "--endpoint", "x",
        "--api-key-env", "X",
        "--capabilities", "chat",
    ], input="y\n")
    # Delete it
    result = runner.invoke(cli, ["engine", "delete", "extra", "--yes"])
    assert result.exit_code == 0
    assert "deleted" in result.output.lower()

    cfg = yaml.safe_load((tmp_path / "proj" / "miniautogen.yaml").read_text())
    assert "extra" not in cfg.get("engine_profiles", {})


def test_engine_delete_default_blocked(tmp_path, monkeypatch) -> None:
    """Cannot delete the default engine profile."""
    runner = _init_project(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["engine", "delete", "default_api", "--yes"])
    assert result.exit_code != 0
    assert "default" in result.output.lower()
