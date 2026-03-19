"""Workspace resolution and configuration for the MiniAutoGen CLI.

Handles: locating workspace root, loading miniautogen.yaml,
validating schema, and resolving relative paths.

DA-9 Terminology Migration:
- ProjectConfig -> WorkspaceConfig (alias kept)
- PipelineConfig -> FlowConfig (alias kept)
- EngineProfileConfig -> EngineConfig (alias kept)
- engine_profiles -> engines (old key accepted with deprecation)
- pipelines -> flows (old key accepted with deprecation)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

CONFIG_FILENAME = "miniautogen.yaml"


class ProjectMeta(BaseModel):
    """Project/workspace metadata."""

    name: str
    version: str = "0.1.0"


class DefaultsConfig(BaseModel):
    """Project-wide defaults.

    DA-9: 'engine_profile' renamed to 'engine'. Old name accepted
    with deprecation warning.
    """

    engine: str = "default_api"
    memory_profile: str = "default"

    @model_validator(mode="before")
    @classmethod
    def _migrate_engine_profile(cls, data: Any) -> Any:
        if isinstance(data, dict) and "engine_profile" in data:
            from miniautogen.cli.deprecation import emit_deprecation

            emit_deprecation("engine_profile", "engine", since="0.5.0")
            if "engine" not in data:
                data["engine"] = data.pop("engine_profile")
            else:
                data.pop("engine_profile")
        return data

    @property
    def engine_profile(self) -> str:
        """Backward compatibility alias for 'engine'."""
        return self.engine


class EngineConfig(BaseModel):
    """Engine configuration for inference binding.

    DA-9: Renamed from EngineProfileConfig.
    """

    kind: str = "api"
    provider: str = "openai-compat"
    model: str | None = None
    command: str | None = None
    temperature: float = 0.2
    endpoint: str | None = None
    api_key: str | None = None
    max_tokens: int | None = None
    timeout_seconds: float = 120.0
    fallbacks: list[str] = Field(default_factory=list)
    max_retries: int = 3
    retry_delay: float = 1.0
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# Backward compatibility alias
EngineProfileConfig = EngineConfig


class MemoryProfileConfig(BaseModel):
    """Memory profile configuration."""

    session: bool = True
    retrieval: dict[str, Any] = Field(default_factory=dict)
    compaction: dict[str, Any] = Field(default_factory=dict)
    summaries: dict[str, Any] = Field(default_factory=dict)
    retention: dict[str, Any] = Field(default_factory=dict)


class FlowConfig(BaseModel):
    """Flow (formerly Pipeline) target configuration.

    DA-9: Renamed from PipelineConfig.
    """

    target: str


# Backward compatibility alias
PipelineConfig = FlowConfig


class DatabaseConfig(BaseModel):
    """Database configuration."""

    url: str = "sqlite+aiosqlite:///miniautogen.db"


class WorkspaceConfig(BaseModel):
    """Root configuration for a MiniAutoGen workspace.

    Loaded from miniautogen.yaml at the workspace root.

    DA-9: Renamed from ProjectConfig. Accepts both old keys
    (engine_profiles, pipelines) and new keys (engines, flows).
    """

    project: ProjectMeta
    defaults: DefaultsConfig = Field(
        default_factory=DefaultsConfig,
    )
    engines: dict[str, EngineConfig] = Field(
        default_factory=dict,
    )
    memory_profiles: dict[str, MemoryProfileConfig] = Field(
        default_factory=dict,
    )
    flows: dict[str, FlowConfig] = Field(
        default_factory=dict,
    )
    database: DatabaseConfig | None = None

    @model_validator(mode="before")
    @classmethod
    def _migrate_old_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "engine_profiles" in data:
            from miniautogen.cli.deprecation import emit_deprecation

            emit_deprecation("engine_profiles", "engines", since="0.5.0")
            if "engines" not in data:
                data["engines"] = data.pop("engine_profiles")
            else:
                data.pop("engine_profiles")
        if "pipelines" in data:
            from miniautogen.cli.deprecation import emit_deprecation

            emit_deprecation("pipelines", "flows", since="0.5.0")
            if "flows" not in data:
                data["flows"] = data.pop("pipelines")
            else:
                data.pop("pipelines")
        return data

    @property
    def engine_profiles(self) -> dict[str, EngineConfig]:
        """Backward compatibility alias for 'engines'."""
        return self.engines

    @property
    def pipelines(self) -> dict[str, FlowConfig]:
        """Backward compatibility alias for 'flows'."""
        return self.flows


# Backward compatibility alias
ProjectConfig = WorkspaceConfig


def require_project_config(
    start: Path | None = None,
) -> tuple[Path, "WorkspaceConfig"]:
    """Find workspace root and load config, or raise.

    Returns:
        Tuple of (workspace_root, config).

    Raises:
        ProjectNotFoundError: If no miniautogen.yaml is found.
    """
    from miniautogen.cli.errors import ProjectNotFoundError

    root = find_project_root(start or Path.cwd())
    if root is None:
        msg = f"No {CONFIG_FILENAME} found in directory tree"
        raise ProjectNotFoundError(msg)
    return root, load_config(root / CONFIG_FILENAME)


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from start looking for miniautogen.yaml.

    Returns the directory containing the config file, or None.
    """
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        if (directory / CONFIG_FILENAME).is_file():
            return directory
    return None


def load_config(path: Path) -> WorkspaceConfig:
    """Load and validate a miniautogen.yaml file.

    Args:
        path: Path to the YAML file (not the directory).

    Returns:
        Validated WorkspaceConfig.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the YAML is invalid or doesn't match schema.
    """
    if not path.is_file():
        msg = f"Config file not found: {path}"
        raise FileNotFoundError(msg)

    with path.open() as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        msg = f"Invalid config: expected mapping, got {type(raw).__name__}"
        raise ValueError(msg)

    return WorkspaceConfig.model_validate(raw)
