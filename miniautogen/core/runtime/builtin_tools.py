"""Builtin tools provided by the runtime (not the provider)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import anyio

from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.contracts.tool_registry import ToolCall, ToolDefinition
from miniautogen.core.runtime.agent_sandbox import AgentFilesystemSandbox

logger = logging.getLogger(__name__)

MAX_FILE_READ_BYTES = 1_048_576  # 1 MB
MAX_DIRECTORY_ENTRIES = 1_000
MAX_SEARCH_RESULTS = 200
MAX_SEARCH_LINE_LENGTH = 500

_TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="read_file",
        description="Read a file from the workspace. Returns numbered lines.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from workspace root"},
                "offset": {"type": "integer", "description": "Line offset (0-based)", "default": 0},
                "limit": {"type": "integer", "description": "Max lines to read"},
            },
            "required": ["path"],
        },
    ),
    ToolDefinition(
        name="search_codebase",
        description="Search for a pattern in workspace files using grep.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Search pattern (fixed string)"},
                "glob": {"type": "string", "description": "File glob filter", "default": "*"},
                "max_results": {"type": "integer", "description": "Max matches", "default": 50},
            },
            "required": ["pattern"],
        },
    ),
    ToolDefinition(
        name="list_directory",
        description="List entries in a directory with type indicators.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path from workspace root",
                    "default": ".",
                },
            },
        },
    ),
]


class BuiltinToolRegistry:
    """Registry of runtime-provided tools with sandbox and resource limits."""

    def __init__(
        self,
        workspace_root: Path,
        sandbox: AgentFilesystemSandbox | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._sandbox = sandbox
        self._timeout = timeout
        self._handlers: dict[str, Any] = {
            "read_file": self._read_file,
            "search_codebase": self._search_codebase,
            "list_directory": self._list_directory,
        }

    def list_tools(self) -> list[ToolDefinition]:
        return list(_TOOL_DEFINITIONS)

    def has_tool(self, name: str) -> bool:
        return name in self._handlers

    async def execute_tool(self, call: ToolCall) -> ToolResult:
        handler = self._handlers.get(call.tool_name)
        if handler is None:
            return ToolResult(success=False, error=f"Unknown tool: {call.tool_name}")
        try:
            with anyio.fail_after(self._timeout):
                return await handler(call.params or {})
        except TimeoutError:
            return ToolResult(success=False, error=f"Tool timed out after {self._timeout}s")
        except Exception as exc:
            logger.exception("Builtin tool '%s' failed", call.tool_name)
            return ToolResult(success=False, error=str(exc))

    def _resolve_and_check(self, rel_path: str) -> tuple[Path, str | None]:
        """Resolve a relative path and verify it is within the workspace.

        Returns (resolved_path, error_message_or_None).
        """
        try:
            resolved = (self._workspace_root / rel_path).resolve()
        except (ValueError, OSError) as exc:
            return self._workspace_root, str(exc)

        if not resolved.is_relative_to(self._workspace_root):
            return resolved, "Path is outside workspace"

        if self._sandbox and not self._sandbox.can_read(resolved):
            return resolved, "Sandbox denied read access"

        return resolved, None

    async def _read_file(self, params: dict) -> ToolResult:
        path_str = params.get("path", "")
        offset = int(params.get("offset", 0))
        limit = params.get("limit")

        resolved, err = self._resolve_and_check(path_str)
        if err:
            return ToolResult(success=False, error=err)

        apath = anyio.Path(resolved)
        if not await apath.is_file():
            return ToolResult(success=False, error=f"File not found: {path_str}")

        stat = await apath.stat()
        if stat.st_size > MAX_FILE_READ_BYTES and limit is None:
            return ToolResult(
                success=False,
                error=(
                    f"File too large ({stat.st_size} bytes). "
                    f"Use offset/limit params or keep files under {MAX_FILE_READ_BYTES} bytes."
                ),
            )

        content = await apath.read_text(errors="replace")
        lines = content.splitlines()
        selected = lines[offset : offset + limit] if limit is not None else lines[offset:]
        numbered = [f"{i + offset + 1:>6}\t{line}" for i, line in enumerate(selected)]
        return ToolResult(success=True, output="\n".join(numbered))

    async def _search_codebase(self, params: dict) -> ToolResult:
        pattern = params.get("pattern", "")
        glob_filter = params.get("glob", "*")
        max_results = min(int(params.get("max_results", 50)), MAX_SEARCH_RESULTS)

        if not pattern:
            return ToolResult(success=False, error="Pattern is required")

        if ".." in glob_filter or glob_filter.startswith("/"):
            return ToolResult(success=False, error="Invalid glob pattern")

        search_root = self._workspace_root
        if self._sandbox and not self._sandbox.can_read(search_root):
            return ToolResult(success=False, error="Sandbox denied access to workspace root")

        cmd = [
            "grep",
            "-rn",
            "--max-count",
            str(max_results),
            "--include",
            glob_filter,
            "--",
            pattern,
            str(search_root),
        ]

        try:
            result = await anyio.run_process(cmd, check=False)
            output = result.stdout.decode(errors="replace")
            lines = output.splitlines()[:max_results]
            truncated = [
                line[:MAX_SEARCH_LINE_LENGTH] + "..."
                if len(line) > MAX_SEARCH_LINE_LENGTH
                else line
                for line in lines
            ]
            return ToolResult(
                success=True, output="\n".join(truncated) if truncated else "No matches found"
            )
        except FileNotFoundError:
            return ToolResult(success=False, error="grep not found on system")

    async def _list_directory(self, params: dict) -> ToolResult:
        path_str = params.get("path", ".")

        resolved, err = self._resolve_and_check(path_str)
        if err:
            return ToolResult(success=False, error=err)

        apath = anyio.Path(resolved)
        if not await apath.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {path_str}")

        entries: list[str] = []
        count = 0
        async for entry in apath.iterdir():
            if count >= MAX_DIRECTORY_ENTRIES:
                entries.append(f"... truncated at {MAX_DIRECTORY_ENTRIES} entries")
                break
            entry_type = "dir" if await entry.is_dir() else "file"
            entries.append(f"{entry_type}\t{entry.name}")
            count += 1

        return ToolResult(success=True, output="\n".join(sorted(entries)))
