"""Engine (LLM backend) management service for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from miniautogen.cli.config import EngineProfileConfig
from miniautogen.cli.services.yaml_ops import (
    read_yaml,
    update_yaml_preserving,
    write_yaml,
)


def _config_path(project_root: Path) -> Path:
    return project_root / "miniautogen.yaml"


def _validate_engine(data: dict[str, Any]) -> None:
    """Validate engine data against EngineProfileConfig schema.

    Raises ValueError with details if invalid.
    """
    # Strip non-schema keys for validation
    validatable = {
        k: v for k, v in data.items()
        if k in {"kind", "provider", "model", "command", "temperature"}
    }
    try:
        EngineProfileConfig.model_validate(validatable)
    except ValidationError as exc:
        errors = "; ".join(
            f"{e['loc']}: {e['msg']}" for e in exc.errors()
        )
        msg = f"Engine validation failed: {errors}"
        raise ValueError(msg) from exc


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

    Validates against EngineProfileConfig before writing.
    Stores only env var references for API keys, never plain text.

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

    Validates the resulting config before writing.
    Uses ruamel.yaml to preserve comments when available.

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

    # Validate before writing
    _validate_engine(after)

    result = {"before": before, "after": after}

    if not dry_run:
        update_yaml_preserving(
            cfg_path,
            {name: after},
            section="engine_profiles",
        )

    return result
