"""Agent management service for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from miniautogen.api import AgentSpec
from miniautogen.cli.services.yaml_ops import (
    read_yaml,
    update_yaml_preserving,
    write_yaml,
)


def _agents_dir(project_root: Path) -> Path:
    d = project_root / "agents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _config_path(project_root: Path) -> Path:
    return project_root / "miniautogen.yaml"


def _validate_agent(data: dict[str, Any]) -> None:
    """Validate agent data against AgentSpec schema.

    Raises ValueError with details if invalid.
    """
    try:
        AgentSpec.model_validate(data)
    except ValidationError as exc:
        errors = "; ".join(
            f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        )
        msg = f"Agent validation failed: {errors}"
        raise ValueError(msg) from exc


def create_agent(
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

    Validates against AgentSpec schema before writing.

    Returns the created agent config dict.
    """
    agents = _agents_dir(project_root)
    agent_path = agents / f"{name}.yaml"

    if agent_path.exists():
        msg = f"Agent '{name}' already exists. Use 'miniautogen agent update {name}' to modify it."
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
        agent["runtime"] = {"max_tokens": max_tokens}

    # Validate against AgentSpec before writing
    _validate_agent(agent)

    write_yaml(agent_path, agent, backup=False)
    return agent


def list_agents(
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


def show_agent(
    project_root: Path,
    name: str,
) -> dict[str, Any]:
    """Get detailed info for a single agent."""
    agent_path = project_root / "agents" / f"{name}.yaml"
    if not agent_path.is_file():
        msg = f"Agent '{name}' not found. Run 'miniautogen agent list' to see available agents."
        raise KeyError(msg)
    return read_yaml(agent_path)


def update_agent(
    project_root: Path,
    name: str,
    *,
    dry_run: bool = False,
    **updates: Any,
) -> dict[str, Any]:
    """Update fields on an existing agent.

    Validates the resulting config against AgentSpec before writing.
    Uses ruamel.yaml to preserve comments when available.

    Returns a dict with 'before' and 'after' states.
    """
    agent_path = project_root / "agents" / f"{name}.yaml"
    if not agent_path.is_file():
        msg = f"Agent '{name}' not found. Run 'miniautogen agent list' to see available agents."
        raise KeyError(msg)

    before = read_yaml(agent_path)
    after = dict(before)
    for k, v in updates.items():
        if v is not None:
            after[k] = v

    # Validate before writing
    _validate_agent(after)

    result = {"before": before, "after": after}
    if not dry_run:
        update_yaml_preserving(agent_path, updates)
    return result


def delete_agent(
    project_root: Path,
    name: str,
) -> dict[str, Any]:
    """Delete an agent, checking for pipeline references first.

    Returns info about the deletion. Raises ValueError if agent
    is referenced by any pipeline config.
    """
    agent_path = project_root / "agents" / f"{name}.yaml"
    if not agent_path.is_file():
        msg = f"Agent '{name}' not found. Run 'miniautogen agent list' to see available agents."
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
            f"{', '.join(referencing)}. "
            f"Remove the agent from these pipelines first."
        )
        raise ValueError(msg)

    data = read_yaml(agent_path)
    agent_path.unlink()
    return {"deleted": name, "config": data}
