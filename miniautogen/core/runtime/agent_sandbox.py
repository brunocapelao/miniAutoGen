"""Agent filesystem sandbox and tool execution policy."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class ToolExecutionPolicy(BaseModel):
    """Resource limits for tool execution per turn."""

    timeout_per_tool: float = 30.0
    max_concurrent_tools: int = 5
    max_tool_calls_per_turn: int = 20
    max_cumulative_tool_time: float = 120.0


class AgentFilesystemSandbox:
    """Enforces per-agent filesystem boundaries.

    Read rules:
    - Agents may read any path inside the workspace, EXCEPT another agent's
      config directory under ``.miniautogen/agents/<other>/``.
    - Agents may read their own config directory.
    - Agents may read the shared directory.

    Write rules:
    - Agents may NOT write immutable files (e.g. ``prompt.md``).
    - Agents may write to their own config directory.
    - Agents may write to the shared directory.
    - Agents may write to workspace source paths (outside ``.miniautogen/agents/``).
    """

    def __init__(self, agent_name: str, workspace: Path) -> None:
        self._workspace = workspace.resolve()
        self._agent_name = agent_name
        self._own_config = (workspace / ".miniautogen" / "agents" / agent_name).resolve()
        self._agents_root = (workspace / ".miniautogen" / "agents").resolve()
        self._shared = (workspace / ".miniautogen" / "shared").resolve()
        self._immutable = {
            (workspace / ".miniautogen" / "agents" / agent_name / "prompt.md").resolve(),
        }

    def can_read(self, path: Path) -> bool:
        """Return True if the agent is allowed to read *path*."""
        resolved = path.resolve()
        if not resolved.is_relative_to(self._workspace):
            return False
        # Inside .miniautogen/agents/ — only own config or shared allowed
        if resolved.is_relative_to(self._agents_root):
            return resolved.is_relative_to(self._own_config) or resolved.is_relative_to(self._shared)
        return True

    def can_write(self, path: Path) -> bool:
        """Return True if the agent is allowed to write *path*."""
        resolved = path.resolve()
        # Immutable files are never writable
        if resolved in self._immutable:
            return False
        # Own config directory is writable
        if resolved.is_relative_to(self._own_config):
            return True
        # Shared directory is writable
        if resolved.is_relative_to(self._shared):
            return True
        # Workspace source (outside agents root) is writable
        if resolved.is_relative_to(self._workspace) and not resolved.is_relative_to(self._agents_root):
            return True
        return False
