"""Tests for check_project service."""

from pathlib import Path

import pytest
import yaml

from miniautogen.cli.config import CONFIG_FILENAME, load_config
from miniautogen.cli.services.check_project import check_project


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data))


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal valid project."""
    config = {
        "project": {"name": "test", "version": "0.1.0"},
        "defaults": {"engine_profile": "default_api", "memory_profile": "default"},
        "engine_profiles": {
            "default_api": {"kind": "api", "provider": "litellm", "model": "gpt-4o-mini"},
        },
        "memory_profiles": {
            "default": {"session": True},
        },
        "pipelines": {"main": {"target": "pipelines.main:build_pipeline"}},
    }
    _write_yaml(tmp_path / CONFIG_FILENAME, config)
    # Create pipeline module
    (tmp_path / "pipelines").mkdir()
    (tmp_path / "pipelines" / "main.py").write_text("def build_pipeline(): pass")
    # Create agent
    _write_yaml(tmp_path / "agents" / "researcher.yaml", {
        "id": "researcher",
        "name": "Researcher",
        "skills": {"attached": ["example"]},
        "tool_access": {"mode": "allowlist", "allow": ["web_search"]},
        "engine_profile": "default_api",
    })
    # Create skill
    skill_dir = tmp_path / "skills" / "example"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Example")
    (skill_dir / "skill.yaml").write_text("id: example\nname: Example")
    # Create tool
    _write_yaml(tmp_path / "tools" / "web_search.yaml", {
        "name": "web_search",
        "description": "Search the web",
    })
    return tmp_path


@pytest.mark.anyio
async def test_check_valid_project(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    config = load_config(project / CONFIG_FILENAME)
    results = await check_project(config, project)
    failed = [r for r in results if not r.passed]
    assert len(failed) == 0, f"Failed checks: {failed}"


@pytest.mark.anyio
async def test_check_missing_skill(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    # Remove skill directory
    import shutil
    shutil.rmtree(project / "skills" / "example")
    config = load_config(project / CONFIG_FILENAME)
    results = await check_project(config, project)
    failed = [r for r in results if not r.passed]
    assert any("example" in r.message for r in failed)


@pytest.mark.anyio
async def test_check_missing_tool(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    (project / "tools" / "web_search.yaml").unlink()
    config = load_config(project / CONFIG_FILENAME)
    results = await check_project(config, project)
    failed = [r for r in results if not r.passed]
    assert any("web_search" in r.message for r in failed)


@pytest.mark.anyio
async def test_check_invalid_agent_yaml(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    (project / "agents" / "researcher.yaml").write_text("not: a: valid: agent")
    config = load_config(project / CONFIG_FILENAME)
    results = await check_project(config, project)
    failed = [r for r in results if not r.passed]
    assert any("id" in r.message.lower() or "agent" in r.name for r in failed)


@pytest.mark.anyio
async def test_check_missing_pipeline_module(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    (project / "pipelines" / "main.py").unlink()
    config = load_config(project / CONFIG_FILENAME)
    results = await check_project(config, project)
    failed = [r for r in results if not r.passed]
    assert any("pipeline" in r.name for r in failed)


@pytest.mark.anyio
async def test_check_skill_missing_skill_md(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    (project / "skills" / "example" / "SKILL.md").unlink()
    config = load_config(project / CONFIG_FILENAME)
    results = await check_project(config, project)
    failed = [r for r in results if not r.passed]
    assert any("SKILL.md" in r.message for r in failed)


@pytest.mark.anyio
async def test_check_engine_profile_valid(tmp_path: Path) -> None:
    """Default engine profile exists in config -- pass."""
    project = _make_project(tmp_path)
    config = load_config(project / CONFIG_FILENAME)
    results = await check_project(config, project)
    engine_checks = [r for r in results if "engine" in r.name]
    assert all(r.passed for r in engine_checks)


@pytest.mark.anyio
async def test_check_engine_profile_missing(tmp_path: Path) -> None:
    """Default engine profile not in config -- fail."""
    project = _make_project(tmp_path)
    config_path = project / CONFIG_FILENAME
    with config_path.open() as f:
        data = yaml.safe_load(f)
    data["defaults"]["engine_profile"] = "nonexistent"
    config_path.write_text(yaml.dump(data))
    config = load_config(config_path)
    results = await check_project(config, project)
    engine_checks = [r for r in results if "engine" in r.name]
    assert any(not r.passed for r in engine_checks)


@pytest.mark.anyio
async def test_check_memory_profile_valid(tmp_path: Path) -> None:
    """Default memory profile exists -- pass."""
    project = _make_project(tmp_path)
    config = load_config(project / CONFIG_FILENAME)
    results = await check_project(config, project)
    mem_checks = [r for r in results if "memory" in r.name]
    assert all(r.passed for r in mem_checks)


@pytest.mark.anyio
async def test_check_memory_profile_missing(tmp_path: Path) -> None:
    """Default memory profile not defined -- fail."""
    project = _make_project(tmp_path)
    config_path = project / CONFIG_FILENAME
    with config_path.open() as f:
        data = yaml.safe_load(f)
    data["defaults"]["memory_profile"] = "nonexistent"
    data["memory_profiles"] = {"other": {"session": True}}
    config_path.write_text(yaml.dump(data))
    config = load_config(config_path)
    results = await check_project(config, project)
    mem_checks = [r for r in results if "memory" in r.name]
    assert any(not r.passed for r in mem_checks)


@pytest.mark.anyio
async def test_check_no_agents_dir(tmp_path: Path) -> None:
    """Project without agents/ dir passes (agents are optional)."""
    import shutil

    project = _make_project(tmp_path)
    shutil.rmtree(project / "agents")
    config = load_config(project / CONFIG_FILENAME)
    results = await check_project(config, project)
    agent_checks = [r for r in results if "agent" in r.name]
    assert all(r.passed for r in agent_checks)


@pytest.mark.anyio
async def test_check_no_tools_dir(tmp_path: Path) -> None:
    """Project without tools/ dir passes (tools are optional)."""
    import shutil

    project = _make_project(tmp_path)
    shutil.rmtree(project / "tools")
    # Also remove tool reference from agent
    agent_path = project / "agents" / "researcher.yaml"
    with agent_path.open() as f:
        agent = yaml.safe_load(f)
    agent.pop("tool_access", None)
    agent_path.write_text(yaml.dump(agent))
    config = load_config(project / CONFIG_FILENAME)
    results = await check_project(config, project)
    failed = [r for r in results if not r.passed]
    assert len(failed) == 0


@pytest.mark.anyio
async def test_check_environment_missing_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider requires API key but it's not set -- env check fails."""
    project = _make_project(tmp_path)
    config_path = project / CONFIG_FILENAME
    with config_path.open() as f:
        data = yaml.safe_load(f)
    data["engine_profiles"]["default_api"]["provider"] = "openai"
    config_path.write_text(yaml.dump(data))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = load_config(config_path)
    results = await check_project(config, project)
    env_checks = [r for r in results if r.category == "environment"]
    assert any(not r.passed for r in env_checks)


@pytest.mark.anyio
async def test_check_environment_key_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider API key is set -- env check passes."""
    project = _make_project(tmp_path)
    config_path = project / CONFIG_FILENAME
    with config_path.open() as f:
        data = yaml.safe_load(f)
    data["engine_profiles"]["default_api"]["provider"] = "openai"
    config_path.write_text(yaml.dump(data))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    config = load_config(config_path)
    results = await check_project(config, project)
    env_checks = [r for r in results if r.category == "environment"]
    assert all(r.passed for r in env_checks)


@pytest.mark.anyio
async def test_check_agent_with_invalid_engine_ref(
    tmp_path: Path,
) -> None:
    """Agent references nonexistent engine profile -- fail."""
    project = _make_project(tmp_path)
    agent_path = project / "agents" / "researcher.yaml"
    with agent_path.open() as f:
        agent = yaml.safe_load(f)
    agent["engine_profile"] = "nonexistent_engine"
    agent_path.write_text(yaml.dump(agent))
    config = load_config(project / CONFIG_FILENAME)
    results = await check_project(config, project)
    failed = [r for r in results if not r.passed]
    assert any(
        "engine" in r.message.lower() or "engine" in r.name
        for r in failed
    )


@pytest.mark.anyio
async def test_check_pipeline_invalid_format(tmp_path: Path) -> None:
    """Pipeline target without ':' -- fail."""
    project = _make_project(tmp_path)
    config_path = project / CONFIG_FILENAME
    with config_path.open() as f:
        data = yaml.safe_load(f)
    data["pipelines"]["main"]["target"] = "pipelines.main"
    config_path.write_text(yaml.dump(data))
    config = load_config(config_path)
    results = await check_project(config, project)
    pipe_checks = [r for r in results if "pipeline" in r.name]
    assert any(not r.passed for r in pipe_checks)
