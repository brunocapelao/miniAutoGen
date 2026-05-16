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
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from miniautogen.core.contracts.coordination import MailboxConfig, PlanApprovalConfig
from miniautogen.core.contracts.team_task import TaskEntrySpec, TaskListConfig

CONFIG_FILENAME = "miniautogen.yaml"


def _has_cycle(specs: list[TaskEntrySpec]) -> bool:
    """Detect cycles in a list of TaskEntrySpec DAG using Kahn's algorithm."""
    ids = {s.id or f"task[{i}]" for i, s in enumerate(specs)}
    id_map: dict[str, TaskEntrySpec] = {}
    for i, spec in enumerate(specs or []):
        sid = spec.id or f"task[{i}]"
        id_map[sid] = spec

    in_degree: dict[str, int] = {sid: 0 for sid in ids}
    adj: dict[str, list[str]] = {sid: [] for sid in ids}

    for sid, spec in id_map.items():
        for dep in spec.depends_on:
            if dep in id_map:
                adj[dep].append(sid)
                in_degree[sid] = in_degree.get(sid, 0) + 1

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    visited = 0

    while queue:
        node = queue.pop(0)
        visited += 1
        for neighbor in adj.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return visited != len(ids)


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
    """Flow configuration — supports both callable and config-driven modes.

    DA-9: Renamed from PipelineConfig.
    Two execution paths:
    - Callable: set ``target`` to a Python module:callable reference
    - Config-driven: set ``mode`` + ``participants`` for YAML-only flows
    """

    target: str | None = None
    mode: str | None = None  # workflow | deliberation | loop | team | composite
    participants: list[str] = Field(default_factory=list)
    input_text: str | None = None
    # Mode-specific options
    leader: str | None = None  # deliberation
    max_rounds: int = 3  # deliberation
    max_turns: int = 20  # agentic loop
    router: str | None = None  # agentic loop
    chain_flows: list[str] = Field(default_factory=list)  # composite

    # Team mode options (Spec 015)
    lead: str | None = None  # team mode
    teammate_prompts: dict[str, str] = Field(default_factory=dict)  # team mode
    on_teammate_failure: Literal["isolate", "abort_team"] = "isolate"  # team mode
    max_concurrent_teammates: int | None = None  # team mode
    team_lead_prompt: str | None = None  # team mode

    # Team task list options (Spec 016)
    task_list: TaskListConfig | None = None

    # Team mailbox options (Spec 017)
    mailbox: MailboxConfig | dict[str, Any] | None = None
    plan_approval: PlanApprovalConfig | dict[str, Any] | None = None

    # AgentRuntime agnostic design fields
    response_format: str = "json"  # free_text | json | structured
    prompts: dict[str, str] = Field(default_factory=dict)
    response_schema: str | None = None  # Python dotted path for structured format

    # Per-agent timeout fields (Spec 013)
    agent_timeouts: dict[str, float] = Field(default_factory=dict)
    round_timeouts: dict[str, float] = Field(default_factory=dict)
    on_timeout_action: Literal["continue", "abort"] = "continue"

    @model_validator(mode="after")
    def validate_flow_config(self) -> "FlowConfig":
        if not self.target and not self.mode:
            raise ValueError("Flow must have either 'target' or 'mode'")
        # participants only required for pure config-driven flows (mode set, no target)
        if self.mode and not self.target and not self.participants:
            raise ValueError("Config-driven flow requires 'participants'")
        # mode-specific validations only apply to pure config-driven flows
        if self.mode and not self.target:
            if self.mode == "deliberation" and not self.leader:
                raise ValueError("Deliberation mode requires 'leader'")
            if self.mode == "loop" and not self.router:
                raise ValueError("Loop mode requires 'router'")
            if self.mode == "team":
                if not self.lead:
                    raise ValueError("Team mode requires 'lead'")
                if not self.participants:
                    raise ValueError("Team mode requires 'participants'")
        # Validate task list DAG cycles
        if self.task_list and self.task_list.enabled:
            if _has_cycle(self.task_list.initial_tasks):
                raise ValueError(
                    "task_list.initial_tasks contains a cycle in depends_on"
                )
        return self

    @model_validator(mode="after")
    def validate_response_format(self) -> "FlowConfig":
        valid_formats = {"free_text", "json", "structured"}
        if self.response_format not in valid_formats:
            raise ValueError(
                f"response_format must be one of {valid_formats}, got '{self.response_format}'"
            )
        if self.response_format == "structured" and not self.response_schema:
            raise ValueError(
                "response_format='structured' requires 'response_schema' "
                "(Python dotted path to Pydantic model)"
            )
        if self.response_schema:
            allowed_prefixes = ("miniautogen.",)
            if not any(self.response_schema.startswith(p) for p in allowed_prefixes):
                raise ValueError(
                    f"response_schema must start with 'miniautogen.', got '{self.response_schema}'"
                )
        return self

    @model_validator(mode="after")
    def validate_timeout_values(self) -> "FlowConfig":
        for k, v in self.agent_timeouts.items():
            if v < 1.0:
                raise ValueError(f"agent_timeouts[{k!r}] must be >= 1.0 (got {v})")
        for k, v in self.round_timeouts.items():
            if v < 1.0:
                raise ValueError(f"round_timeouts[{k!r}] must be >= 1.0 (got {v})")
        for agent_id in self.agent_timeouts:
            if self.participants and agent_id not in self.participants:
                import warnings

                warnings.warn(
                    f"agent_timeouts has unknown agent {agent_id!r} "
                    f"(not in participants {self.participants})",
                    UserWarning,
                    stacklevel=2,
                )
        return self


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
