"""Tests for engine CLI command group."""

import yaml
from pathlib import Path

from miniautogen.cli.main import cli


def _cfg():
    return yaml.safe_load((Path.cwd() / "miniautogen.yaml").read_text())


def _engines(cfg=None):
    """Get engines dict from raw YAML, supporting both old and new keys."""
    if cfg is None:
        cfg = _cfg()
    return cfg.get("engines", cfg.get("engine_profiles", {}))


def test_engine_create_silent(init_project) -> None:
    runner = init_project
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
    cfg = _cfg()
    assert "gpt4" in _engines(cfg)
    assert _engines(cfg)["gpt4"]["model"] == "gpt-4o"
    assert _engines(cfg)["gpt4"]["api_key"] == "${OPENAI_API_KEY}"


def test_engine_create_with_capabilities(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, [
        "engine", "create", "gemini",
        "--provider", "gemini",
        "--model", "gemini-2.5-pro",
        "--endpoint", "https://generativelanguage.googleapis.com/v1",
        "--api-key-env", "GEMINI_API_KEY",
        "--capabilities", "chat,embedding",
    ], input="y\n")
    assert result.exit_code == 0, result.output
    cfg = _cfg()
    assert _engines(cfg)["gemini"]["capabilities"] == ["chat", "embedding"]


def test_engine_create_interactive(init_project) -> None:
    """Test interactive wizard prompts for missing fields."""
    runner = init_project
    result = runner.invoke(
        cli,
        ["engine", "create", "myengine"],
        input="openai\ngpt-4o\nhttps://api.openai.com/v1\nOPENAI_API_KEY\nchat\ny\n",
    )
    assert result.exit_code == 0, result.output
    assert "created" in result.output.lower()


def test_engine_create_cancelled(init_project) -> None:
    """Test wizard cancellation at confirmation prompt."""
    runner = init_project
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
    cfg = _cfg()
    assert "gpt4" not in _engines(cfg)


def test_engine_create_duplicate_fails(init_project) -> None:
    runner = init_project
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


def test_engine_create_validates_schema(init_project) -> None:
    """Engine create validates against EngineProfileConfig."""
    runner = init_project
    result = runner.invoke(cli, [
        "engine", "create", "valid",
        "--provider", "openai",
        "--model", "gpt-4o",
        "--endpoint", "x",
        "--api-key-env", "X",
        "--capabilities", "chat",
    ], input="y\n")
    assert result.exit_code == 0


def test_engine_create_credential_safety(init_project) -> None:
    """Engine create stores only env var references, not keys."""
    runner = init_project
    result = runner.invoke(cli, [
        "engine", "create", "safe",
        "--provider", "openai",
        "--model", "gpt-4o",
        "--endpoint", "x",
        "--api-key-env", "MY_SECRET_KEY",
        "--capabilities", "chat",
    ], input="y\n")
    assert result.exit_code == 0
    cfg = _cfg()
    assert _engines(cfg)["safe"]["api_key"] == "${MY_SECRET_KEY}"


def test_engine_list(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["engine", "list"])
    assert result.exit_code == 0
    assert "default_api" in result.output


def test_engine_list_json(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["engine", "list", "--format", "json"])
    assert result.exit_code == 0
    assert '"name"' in result.output


def test_engine_show(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["engine", "show", "default_api"])
    assert result.exit_code == 0
    assert "provider:" in result.output or "litellm" in result.output


def test_engine_show_json(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["engine", "show", "default_api", "--format", "json"])
    assert result.exit_code == 0
    assert '"provider"' in result.output


def test_engine_show_not_found(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, ["engine", "show", "nonexistent"])
    assert result.exit_code != 0


def test_engine_update(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, [
        "engine", "update", "default_api",
        "--model", "gpt-4o-mini",
    ])
    assert result.exit_code == 0
    assert "updated" in result.output.lower()

    cfg = _cfg()
    assert _engines(cfg)["default_api"]["model"] == "gpt-4o-mini"


def test_engine_update_dry_run(init_project) -> None:
    runner = init_project
    cfg_before = _cfg()
    original_model = _engines(cfg_before)["default_api"]["model"]

    result = runner.invoke(cli, [
        "engine", "update", "default_api",
        "--model", "claude-3.5-sonnet",
        "--dry-run",
    ])
    assert result.exit_code == 0
    assert "dry run" in result.output.lower()

    cfg = _cfg()
    assert _engines(cfg)["default_api"]["model"] == original_model


def test_engine_update_not_found(init_project) -> None:
    runner = init_project
    result = runner.invoke(cli, [
        "engine", "update", "nonexistent",
        "--model", "x",
    ])
    assert result.exit_code != 0


def test_engine_delete(init_project) -> None:
    """Test engine deletion with confirmation."""
    runner = init_project
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

    cfg = _cfg()
    assert "extra" not in _engines(cfg)


def test_engine_delete_default_blocked(init_project) -> None:
    """Cannot delete the default engine profile."""
    runner = init_project
    result = runner.invoke(cli, ["engine", "delete", "default_api", "--yes"])
    assert result.exit_code != 0
    assert "default" in result.output.lower()
