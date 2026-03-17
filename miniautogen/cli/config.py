"""Project resolution and configuration for the MiniAutoGen CLI.

Handles: locating project root, loading miniautogen.yaml,
validating schema, and resolving relative paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

CONFIG_FILENAME = "miniautogen.yaml"


class ProjectMeta(BaseModel):
    """Project metadata."""

    name: str
    version: str = "0.1.0"


class DefaultsConfig(BaseModel):
    """Project-wide defaults."""

    engine_profile: str = "default_api"
    memory_profile: str = "default"


class EngineProfileConfig(BaseModel):
    """Engine profile for inference binding."""

    kind: str = "api"
    provider: str = "litellm"
    model: str | None = None
    command: str | None = None
    temperature: float = 0.2


class MemoryProfileConfig(BaseModel):
    """Memory profile configuration."""

    session: bool = True
    retrieval: dict[str, Any] = Field(default_factory=dict)
    compaction: dict[str, Any] = Field(default_factory=dict)
    summaries: dict[str, Any] = Field(default_factory=dict)
    retention: dict[str, Any] = Field(default_factory=dict)


class PipelineConfig(BaseModel):
    """Pipeline target configuration."""

    target: str


class DatabaseConfig(BaseModel):
    """Database configuration."""

    url: str = "sqlite+aiosqlite:///miniautogen.db"


class ProjectConfig(BaseModel):
    """Root configuration for a MiniAutoGen project.

    Loaded from miniautogen.yaml at the project root.
    """

    project: ProjectMeta
    defaults: DefaultsConfig = Field(
        default_factory=DefaultsConfig,
    )
    engine_profiles: dict[str, EngineProfileConfig] = Field(
        default_factory=dict,
    )
    memory_profiles: dict[str, MemoryProfileConfig] = Field(
        default_factory=dict,
    )
    pipelines: dict[str, PipelineConfig] = Field(
        default_factory=dict,
    )
    database: DatabaseConfig | None = None


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from start looking for miniautogen.yaml.

    Returns the directory containing the config file, or None.
    """
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        if (directory / CONFIG_FILENAME).is_file():
            return directory
    return None


def load_config(path: Path) -> ProjectConfig:
    """Load and validate a miniautogen.yaml file.

    Args:
        path: Path to the YAML file (not the directory).

    Returns:
        Validated ProjectConfig.

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

    return ProjectConfig.model_validate(raw)
