"""Agent management service for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from miniautogen.cli.services.yaml_ops import read_yaml, write_yaml


def _agents_dir(project_root: Path) -> Path:
    d = project_root / "agents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _config_path(project_root: Path) -> Path:
    return project_root / "miniautogen.yaml"


async def create_agent(
    project_root: Path,
    name: str,
    *,
    role: str,
    goal: str,
    engine_profile: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Create a new agent YAML file in agents/ directory.

    Returns the created agent config dict.
    """
    agents = _agents_dir(project_root)
    agent_path = agents / f"{name}.yaml"

    if agent_path.exists():
        msg = f"Agent '{name}' already exists"
        raise ValueError(msg)

    # Verify engine profile exists
    cfg_data = read_yaml(_config_path(project_root))
    engine_profiles = cfg_data.get("engine_profiles", {})
    if engine_profile not in engine_profiles:
        msg = (
            f"Engine profile '{engine_profile}' not found. "
            f"Available: {', '.join(engine_profiles) or '(none)'}"
        )
        raise ValueError(msg)

    agent: dict[str, Any] = {
        "id": name,
        "version": "1.0.0",
        "name": name,
        "role": role,
        "goal": goal,
        "engine_profile": engine_profile,
    }
    if temperature is not None:
        agent["temperature"] = temperature
    if max_tokens is not None:
        agent["max_tokens"] = max_tokens

    write_yaml(agent_path, agent, backup=False)
    return agent


async def list_agents(
    project_root: Path,
) -> list[dict[str, Any]]:
    """List all agents in agents/ directory."""
    agents_dir = project_root / "agents"
    if not agents_dir.is_dir():
        return []

    result = []
    for yaml_file in sorted(agents_dir.glob("*.yaml")):
        try:
            data = read_yaml(yaml_file)
            result.append({
                "name": data.get("id", yaml_file.stem),
                "role": data.get("role", "?"),
                "engine_profile": data.get("engine_profile", "?"),
            })
        except (ValueError, yaml.YAMLError):
            result.append({
                "name": yaml_file.stem,
                "role": "(invalid)",
                "engine_profile": "?",
            })
    return result


async def show_agent(
    project_root: Path,
    name: str,
) -> dict[str, Any]:
    """Get detailed info for a single agent."""
    agent_path = project_root / "agents" / f"{name}.yaml"
    if not agent_path.is_file():
        msg = f"Agent '{name}' not found"
        raise KeyError(msg)
    return read_yaml(agent_path)


async def update_agent(
    project_root: Path,
    name: str,
    *,
    dry_run: bool = False,
    **updates: Any,
) -> dict[str, Any]:
    """Update fields on an existing agent.

    Returns a dict with 'before' and 'after' states.
    """
    agent_path = project_root / "agents" / f"{name}.yaml"
    if not agent_path.is_file():
        msg = f"Agent '{name}' not found"
        raise KeyError(msg)

    before = read_yaml(agent_path)
    after = dict(before)
    for k, v in updates.items():
        if v is not None:
            after[k] = v

    result = {"before": before, "after": after}
    if not dry_run:
        write_yaml(agent_path, after)
    return result


async def delete_agent(
    project_root: Path,
    name: str,
) -> dict[str, Any]:
    """Delete an agent, checking for pipeline references first.

    Returns info about the deletion. Raises ValueError if agent
    is referenced by any pipeline config.
    """
    agent_path = project_root / "agents" / f"{name}.yaml"
    if not agent_path.is_file():
        msg = f"Agent '{name}' not found"
        raise KeyError(msg)

    # Check for pipeline references in miniautogen.yaml
    cfg_data = read_yaml(_config_path(project_root))
    pipelines = cfg_data.get("pipelines", {})
    referencing: list[str] = []
    for pname, pcfg in pipelines.items():
        if isinstance(pcfg, dict):
            participants = pcfg.get("participants", [])
            leader = pcfg.get("leader")
            if name in participants or leader == name:
                referencing.append(pname)

    if referencing:
        msg = (
            f"Cannot delete agent '{name}': referenced by pipeline(s): "
            f"{', '.join(referencing)}"
        )
        raise ValueError(msg)

    data = read_yaml(agent_path)
    agent_path.unlink()
    return {"deleted": name, "config": data}
