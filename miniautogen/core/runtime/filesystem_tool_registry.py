"""Filesystem-backed tool registry loaded from tools.yml."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.contracts.tool_registry import (
    ToolCall, ToolDefinition, ToolRegistryProtocol,
)
from miniautogen.core.runtime.agent_sandbox import AgentFilesystemSandbox

logger = logging.getLogger(__name__)


class FileSystemToolRegistry:
    """Loads tool definitions from a tools.yml file."""

    def __init__(
        self,
        tools_path: Path,
        workspace_root: Path | None = None,
        sandbox: AgentFilesystemSandbox | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._tools_path = tools_path
        self._workspace_root = workspace_root or tools_path.parent.parent.parent  # .miniautogen/agents/{name}/
        self._sandbox = sandbox
        self._timeout = timeout
        self._definitions: dict[str, ToolDefinition] = {}
        self._tool_configs: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self._tools_path.exists():
            return
        try:
            data = yaml.safe_load(self._tools_path.read_text()) or {}
            for tool_cfg in data.get("tools", []):
                name = tool_cfg.get("name", "")
                if not name:
                    continue
                if tool_cfg.get("builtin"):
                    continue  # Handled by BuiltinToolRegistry
                # Validate script paths — reject traversal attempts
                if "script" in tool_cfg:
                    script = tool_cfg["script"]
                    if script.startswith("/") or ".." in Path(script).parts:
                        logger.warning("Rejected tool '%s': script path traversal", name)
                        continue
                self._definitions[name] = ToolDefinition(
                    name=name,
                    description=tool_cfg.get("description", ""),
                    parameters=tool_cfg.get("parameters"),
                )
                self._tool_configs[name] = tool_cfg
        except Exception:
            logger.exception("Failed to load tools from %s", self._tools_path)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._definitions.values())

    def has_tool(self, name: str) -> bool:
        return name in self._definitions

    async def execute_tool(self, call: ToolCall) -> ToolResult:
        if call.tool_name not in self._definitions:
            return ToolResult(success=False, error=f"Unknown tool: {call.tool_name}")

        # Validate params against JSON Schema if defined (Fix 7)
        defn = self._definitions[call.tool_name]
        if defn.parameters:
            try:
                import jsonschema

                jsonschema.validate(call.params, defn.parameters)
            except ImportError:
                pass  # jsonschema not installed, skip validation
            except jsonschema.ValidationError as e:
                return ToolResult(
                    success=False, error=f"Invalid params: {e.message}"
                )

        cfg = self._tool_configs[call.tool_name]

        if "script" in cfg:
            return await self._execute_script(cfg["script"], call.params)

        return ToolResult(success=False, error=f"No handler for tool '{call.tool_name}'")

    async def _execute_script(self, script_rel: str, params: dict) -> ToolResult:
        import anyio
        script_path = (self._workspace_root / script_rel).resolve()
        if not script_path.is_relative_to(self._workspace_root.resolve()):
            return ToolResult(success=False, error="Script path traversal blocked")
        if not script_path.is_file():
            return ToolResult(success=False, error=f"Script not found: {script_rel}")

        # Sandbox read check (Fix 5)
        if self._sandbox is not None and not self._sandbox.can_read(script_path):
            return ToolResult(
                success=False,
                error=f"Sandbox denied read access to: {script_rel}",
            )

        try:
            # Wrap with timeout (Fix 8)
            with anyio.fail_after(self._timeout):
                result = await anyio.run_process(
                    [str(script_path)],
                    input=json.dumps(params).encode(),
                )
            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout.decode(),
                error=result.stderr.decode() if result.returncode != 0 else None,
            )
        except TimeoutError:
            return ToolResult(
                success=False,
                error=f"Script timed out after {self._timeout}s",
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
