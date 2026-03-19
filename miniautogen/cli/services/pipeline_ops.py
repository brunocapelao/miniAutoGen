"""Pipeline management service for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from miniautogen.cli.services.yaml_ops import (
    read_yaml,
    update_yaml_preserving,
    validate_resource_name,
    write_yaml,
)


def _get_pipelines_section(data: dict[str, Any]) -> dict[str, Any]:
    """Get the pipelines/flows section, supporting both old and new key names."""
    if "flows" in data:
        return data["flows"]
    if "pipelines" in data:
        return data["pipelines"]
    return data.setdefault("pipelines", {})


def _detect_pipelines_key(data: dict[str, Any]) -> str:
    """Return the YAML key name used for pipelines/flows in this data."""
    if "flows" in data:
        return "flows"
    if "pipelines" in data:
        return "pipelines"
    return "flows"


def _config_path(project_root: Path) -> Path:
    return project_root / "miniautogen.yaml"


def create_pipeline(
    project_root: Path,
    name: str,
    *,
    mode: str = "workflow",
    participants: list[str] | None = None,
    leader: str | None = None,
    target: str | None = None,
    max_rounds: int | None = None,
    chain_pipelines: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new pipeline configuration in miniautogen.yaml.

    Returns the created pipeline config dict.
    """
    validate_resource_name(name, "pipeline")
    cfg_path = _config_path(project_root)
    data = read_yaml(cfg_path)
    pipelines = _get_pipelines_section(data)

    if name in pipelines:
        msg = f"Pipeline '{name}' already exists. Use 'miniautogen pipeline update {name}' to modify it."
        raise ValueError(msg)

    # Validate that referenced agents exist
    agents_dir = project_root / "agents"
    if participants:
        for agent_name in participants:
            validate_resource_name(agent_name, "agent")
            agent_file = agents_dir / f"{agent_name}.yaml"
            if not agent_file.is_file():
                msg = f"Agent '{agent_name}' not found in agents/"
                raise ValueError(msg)

    if leader:
        validate_resource_name(leader, "agent")
        leader_file = agents_dir / f"{leader}.yaml"
        if not leader_file.is_file():
            msg = f"Leader agent '{leader}' not found in agents/"
            raise ValueError(msg)

    # For composite mode, validate referenced pipelines exist
    if chain_pipelines:
        for pname in chain_pipelines:
            if pname not in pipelines:
                msg = f"Pipeline '{pname}' not found (needed for composite chain)"
                raise ValueError(msg)

    pipeline: dict[str, Any] = {"mode": mode}

    if target:
        pipeline["target"] = target
    else:
        pipeline["target"] = f"pipelines.{name}:build_pipeline"

    if participants:
        pipeline["participants"] = participants
    if leader:
        pipeline["leader"] = leader
    if max_rounds is not None:
        pipeline["max_rounds"] = max_rounds
    if chain_pipelines:
        pipeline["chain"] = chain_pipelines

    pipelines[name] = pipeline
    write_yaml(cfg_path, data)

    # Create pipeline module file if it doesn't exist
    pipelines_dir = project_root / "pipelines"
    pipelines_dir.mkdir(parents=True, exist_ok=True)
    pipeline_file = pipelines_dir / f"{name}.py"
    if not pipeline_file.exists():
        pipeline_file.write_text(
            f'"""Pipeline: {name} ({mode} mode)."""\n\n'
            f"from miniautogen.api import Pipeline\n\n\n"
            f"def build_pipeline() -> Pipeline:\n"
            f'    """Build the {name} pipeline."""\n'
            f"    return Pipeline(name={name!r})\n"
        )

    return pipeline


def list_pipelines(
    project_root: Path,
) -> list[dict[str, Any]]:
    """List all pipelines from project config."""
    cfg_path = _config_path(project_root)
    data = read_yaml(cfg_path)
    pipelines = _get_pipelines_section(data)
    result = []
    for pname, pcfg in pipelines.items():
        if isinstance(pcfg, dict):
            result.append({
                "name": pname,
                "mode": pcfg.get("mode", "?"),
                "target": pcfg.get("target", "?"),
                "participants": pcfg.get("participants", []),
            })
        else:
            result.append({
                "name": pname,
                "mode": "?",
                "target": str(pcfg) if pcfg else "?",
                "participants": [],
            })
    return result


def show_pipeline(
    project_root: Path,
    name: str,
) -> dict[str, Any]:
    """Get detailed info for a single pipeline."""
    validate_resource_name(name, "pipeline")
    cfg_path = _config_path(project_root)
    data = read_yaml(cfg_path)
    pipelines = _get_pipelines_section(data)
    if name not in pipelines:
        available = ", ".join(pipelines) or "(none)"
        msg = f"Pipeline '{name}' not found. Available: {available}"
        raise KeyError(msg)
    cfg = pipelines[name]
    if isinstance(cfg, dict):
        result = dict(cfg)
    else:
        result = {"target": str(cfg)}
    result["name"] = name
    return result


def update_pipeline(
    project_root: Path,
    name: str,
    *,
    dry_run: bool = False,
    **updates: Any,
) -> dict[str, Any]:
    """Update fields on an existing pipeline config.

    Supports add_participant and remove_participant for
    incremental participant management.

    Returns a dict with 'before' and 'after' states.
    """
    validate_resource_name(name, "pipeline")
    cfg_path = _config_path(project_root)
    data = read_yaml(cfg_path)
    pipelines = _get_pipelines_section(data)
    if name not in pipelines:
        available = ", ".join(pipelines) or "(none)"
        msg = f"Pipeline '{name}' not found. Available: {available}"
        raise KeyError(msg)

    raw_cfg = pipelines[name]
    before = dict(raw_cfg) if isinstance(raw_cfg, dict) else {"target": str(raw_cfg)}
    after = dict(before)

    # Handle add_participant / remove_participant
    add_p = updates.pop("add_participant", None)
    remove_p = updates.pop("remove_participant", None)

    if add_p is not None:
        validate_resource_name(add_p, "agent")
        current = list(after.get("participants", []))
        # Validate agent exists
        agents_dir = project_root / "agents"
        agent_file = agents_dir / f"{add_p}.yaml"
        if not agent_file.is_file():
            msg = f"Agent '{add_p}' not found in agents/"
            raise ValueError(msg)
        if add_p not in current:
            current.append(add_p)
        after["participants"] = current

    if remove_p is not None:
        current = list(after.get("participants", []))
        if remove_p in current:
            current.remove(remove_p)
        after["participants"] = current

    if "participants" in updates and updates["participants"] is not None:
        agents_dir = project_root / "agents"
        for agent_name in updates["participants"]:
            validate_resource_name(agent_name, "agent")
            agent_file = agents_dir / f"{agent_name}.yaml"
            if not agent_file.is_file():
                msg = f"Agent '{agent_name}' not found in agents/"
                raise ValueError(msg)

    if "leader" in updates and updates["leader"] is not None:
        validate_resource_name(updates["leader"], "agent")
        agents_dir = project_root / "agents"
        leader_file = agents_dir / f"{updates['leader']}.yaml"
        if not leader_file.is_file():
            msg = f"Leader agent '{updates['leader']}' not found in agents/"
            raise ValueError(msg)

    for k, v in updates.items():
        if v is not None:
            after[k] = v

    result = {"before": before, "after": after}
    if not dry_run:
        section = _detect_pipelines_key(read_yaml(cfg_path))
        update_yaml_preserving(cfg_path, {name: after}, section=section)

    return result
