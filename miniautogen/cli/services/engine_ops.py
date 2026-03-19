"""Engine (LLM backend) management service for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from miniautogen.cli.config import EngineProfileConfig
from miniautogen.cli.services.yaml_ops import (
    read_yaml,
    update_yaml_preserving,
    validate_resource_name,
    write_yaml,
)


def _get_engines_section(data: dict[str, Any]) -> dict[str, Any]:
    """Get the engines section, supporting both old and new key names."""
    if "engines" in data:
        return data["engines"]
    if "engine_profiles" in data:
        from miniautogen.cli.deprecation import emit_deprecation

        emit_deprecation("engine_profiles", "engines", since="0.5.0")
        # Migrate in-memory: move to new key
        data["engines"] = data.pop("engine_profiles")
        return data["engines"]
    return data.setdefault("engines", {})


def _detect_engines_key(data: dict[str, Any]) -> str:
    """Return the YAML key name used for engines in this data (before migration)."""
    if "engines" in data:
        return "engines"
    if "engine_profiles" in data:
        return "engine_profiles"
    return "engines"


def _config_path(project_root: Path) -> Path:
    return project_root / "miniautogen.yaml"


def _validate_engine(data: dict[str, Any]) -> None:
    """Validate engine data against EngineProfileConfig schema.

    Raises ValueError with details if invalid.
    """
    try:
        EngineProfileConfig.model_validate(data)
    except ValidationError as exc:
        errors = "; ".join(
            f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        )
        msg = f"Engine validation failed: {errors}"
        raise ValueError(msg) from exc


def create_engine(
    project_root: Path,
    name: str,
    *,
    provider: str,
    model: str,
    kind: str = "api",
    temperature: float = 0.2,
    api_key_env: str | None = None,
    endpoint: str | None = None,
    capabilities: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new engine profile in miniautogen.yaml.

    Validates against EngineProfileConfig before writing.
    Stores only env var references for API keys, never plain text.

    Returns the created engine config dict.
    """
    validate_resource_name(name, "engine")
    cfg_path = _config_path(project_root)
    data = read_yaml(cfg_path)

    engines = _get_engines_section(data)
    if name in engines:
        msg = f"Engine '{name}' already exists. Use 'miniautogen engine update {name}' to modify it."
        raise ValueError(msg)

    engine: dict[str, Any] = {
        "kind": kind,
        "provider": provider,
        "model": model,
        "temperature": temperature,
    }
    if api_key_env:
        # Store only the env var reference, never the actual key
        engine["api_key"] = f"${{{api_key_env}}}"
    if endpoint:
        engine["endpoint"] = endpoint
    if capabilities:
        engine["capabilities"] = capabilities

    # Validate before writing
    _validate_engine(engine)

    engines[name] = engine
    write_yaml(cfg_path, data)
    return engine


def list_engines(
    project_root: Path,
) -> list[dict[str, Any]]:
    """List all engine profiles from project config."""
    cfg_path = _config_path(project_root)
    data = read_yaml(cfg_path)
    engines = _get_engines_section(data)
    result = []
    for ename, ecfg in engines.items():
        result.append({
            "name": ename,
            "provider": ecfg.get("provider", "?"),
            "model": ecfg.get("model", "?"),
            "kind": ecfg.get("kind", "api"),
            "capabilities": ecfg.get("capabilities", []),
        })
    return result


def show_engine(
    project_root: Path,
    name: str,
) -> dict[str, Any]:
    """Get detailed info for a single engine profile."""
    validate_resource_name(name, "engine")
    cfg_path = _config_path(project_root)
    data = read_yaml(cfg_path)
    engines = _get_engines_section(data)
    if name not in engines:
        available = ", ".join(engines) or "(none)"
        msg = f"Engine '{name}' not found. Available: {available}"
        raise KeyError(msg)
    cfg = dict(engines[name])
    cfg["name"] = name
    return cfg


def update_engine(
    project_root: Path,
    name: str,
    *,
    dry_run: bool = False,
    **updates: Any,
) -> dict[str, Any]:
    """Update fields on an existing engine profile.

    Validates the resulting config before writing.
    Uses ruamel.yaml to preserve comments when available.

    Returns a dict with 'before' and 'after' states.
    If dry_run is True, does not write changes.
    """
    validate_resource_name(name, "engine")
    cfg_path = _config_path(project_root)
    data = read_yaml(cfg_path)
    engines = _get_engines_section(data)
    if name not in engines:
        available = ", ".join(engines) or "(none)"
        msg = f"Engine '{name}' not found. Available: {available}"
        raise KeyError(msg)

    before = dict(engines[name])
    after = dict(before)

    api_key = updates.get("api_key")
    if api_key is not None and not (api_key.startswith("${") and api_key.endswith("}")):
        msg = (
            "API keys must be environment variable references in ${VAR_NAME} format. "
            "Never store plain-text credentials in configuration files."
        )
        raise ValueError(msg)

    for k, v in updates.items():
        if v is not None:
            after[k] = v

    # Validate before writing
    _validate_engine(after)

    result = {"before": before, "after": after}

    if not dry_run:
        update_yaml_preserving(
            cfg_path,
            {name: after},
            section=_detect_engines_key(read_yaml(cfg_path)),
        )

    return result


def delete_engine(
    project_root: Path,
    name: str,
) -> dict[str, Any]:
    """Delete an engine profile, checking for agent references first.

    Returns info about the deletion. Raises ValueError if engine
    is referenced by any agent config.
    """
    validate_resource_name(name, "engine")
    import yaml as _yaml

    cfg_path = _config_path(project_root)
    data = read_yaml(cfg_path)
    engines = _get_engines_section(data)
    if name not in engines:
        available = ", ".join(engines) or "(none)"
        msg = f"Engine '{name}' not found. Available: {available}"
        raise KeyError(msg)

    # Check for agent references
    agents_dir = project_root / "agents"
    referencing: list[str] = []
    if agents_dir.is_dir():
        for yaml_file in agents_dir.glob("*.yaml"):
            try:
                agent_data = _yaml.safe_load(yaml_file.read_text())
                if isinstance(agent_data, dict) and agent_data.get("engine_profile") == name:
                    referencing.append(yaml_file.stem)
            except _yaml.YAMLError:
                pass

    # Check defaults reference
    defaults = data.get("defaults", {})
    is_default = defaults.get("engine_profile") == name

    if referencing:
        msg = (
            f"Cannot delete engine '{name}': referenced by agent(s): "
            f"{', '.join(referencing)}. "
            f"Update these agents first: miniautogen agent update <name> --engine <other>"
        )
        raise ValueError(msg)

    if is_default:
        msg = (
            f"Cannot delete engine '{name}': it is the default engine profile. "
            f"Change the default first in miniautogen.yaml."
        )
        raise ValueError(msg)

    engine_data = dict(engines[name])
    del engines[name]
    write_yaml(cfg_path, data)
    return {"deleted": name, "config": engine_data}
