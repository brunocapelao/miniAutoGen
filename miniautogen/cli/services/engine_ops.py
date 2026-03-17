"""Engine (LLM backend) management service for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from miniautogen.cli.config import ProjectConfig, load_config
from miniautogen.cli.services.yaml_ops import read_yaml, write_yaml


def _config_path(project_root: Path) -> Path:
    return project_root / "miniautogen.yaml"


async def create_engine(
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

    Returns the created engine config dict.
    """
    cfg_path = _config_path(project_root)
    data = read_yaml(cfg_path)

    engines = data.setdefault("engine_profiles", {})
    if name in engines:
        msg = f"Engine '{name}' already exists"
        raise ValueError(msg)

    engine: dict[str, Any] = {
        "kind": kind,
        "provider": provider,
        "model": model,
        "temperature": temperature,
    }
    if api_key_env:
        engine["api_key"] = f"${{{api_key_env}}}"
    if endpoint:
        engine["endpoint"] = endpoint
    if capabilities:
        engine["capabilities"] = capabilities

    engines[name] = engine
    write_yaml(cfg_path, data)
    return engine


async def list_engines(
    project_root: Path,
) -> list[dict[str, Any]]:
    """List all engine profiles from project config."""
    cfg_path = _config_path(project_root)
    data = read_yaml(cfg_path)
    engines = data.get("engine_profiles", {})
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


async def show_engine(
    project_root: Path,
    name: str,
) -> dict[str, Any]:
    """Get detailed info for a single engine profile."""
    cfg_path = _config_path(project_root)
    data = read_yaml(cfg_path)
    engines = data.get("engine_profiles", {})
    if name not in engines:
        msg = f"Engine '{name}' not found"
        raise KeyError(msg)
    cfg = dict(engines[name])
    cfg["name"] = name
    return cfg


async def update_engine(
    project_root: Path,
    name: str,
    *,
    dry_run: bool = False,
    **updates: Any,
) -> dict[str, Any]:
    """Update fields on an existing engine profile.

    Returns a dict with 'before' and 'after' states.
    If dry_run is True, does not write changes.
    """
    cfg_path = _config_path(project_root)
    data = read_yaml(cfg_path)
    engines = data.get("engine_profiles", {})
    if name not in engines:
        msg = f"Engine '{name}' not found"
        raise KeyError(msg)

    before = dict(engines[name])
    after = dict(before)

    for k, v in updates.items():
        if v is not None:
            after[k] = v

    result = {"before": before, "after": after}

    if not dry_run:
        engines[name] = after
        write_yaml(cfg_path, data)

    return result
