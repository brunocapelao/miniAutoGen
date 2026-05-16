"""Workspace management tools for the lead agent.

Enables a lead agent to inspect and modify the workspace configuration:
agents, flows, engines, and run execution via chat.

Follows the same pattern as team_task_tools.py and builtin_team_tools.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.contracts.tool_registry import ToolDefinition
from miniautogen.core.runtime.tool_registry import ToolHandler


def build_workspace_tools(
    project_root: Path,
) -> list[tuple[ToolDefinition, ToolHandler]]:
    return [
        (_list_agents_def(), _make_list_agents_handler(project_root)),
        (_show_agent_def(), _make_show_agent_handler(project_root)),
        (_create_agent_def(), _make_create_agent_handler(project_root)),
        (_update_agent_def(), _make_update_agent_handler(project_root)),
        (_delete_agent_def(), _make_delete_agent_handler(project_root)),
        (_list_flows_def(), _make_list_flows_handler(project_root)),
        (_show_flow_def(), _make_show_flow_handler(project_root)),
        (_create_flow_def(), _make_create_flow_handler(project_root)),
        (_delete_flow_def(), _make_delete_flow_handler(project_root)),
        (_list_engines_def(), _make_list_engines_handler(project_root)),
        (_show_engine_def(), _make_show_engine_handler(project_root)),
        (_run_flow_def(), _make_run_flow_handler(project_root)),
        (_check_project_def(), _make_check_project_handler(project_root)),
    ]


# ---------------------------------------------------------------------------
# Agent tools
# ---------------------------------------------------------------------------


def _list_agents_def() -> ToolDefinition:
    return ToolDefinition(
        name="list_agents",
        description="List all agents in the workspace.",
        parameters={"type": "object", "properties": {}},
    )


def _make_list_agents_handler(project_root: Path) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        from miniautogen.cli.services.agent_ops import list_agents

        agents = list_agents(project_root)
        return ToolResult(success=True, output={"agents": agents})

    return handler


def _show_agent_def() -> ToolDefinition:
    return ToolDefinition(
        name="show_agent",
        description="Show detailed configuration of a specific agent.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Agent name"},
            },
            "required": ["name"],
        },
    )


def _make_show_agent_handler(project_root: Path) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        from miniautogen.cli.services.agent_ops import show_agent

        name = params.get("name", "")
        if not name:
            return ToolResult(success=False, error="name is required")
        try:
            data = show_agent(project_root, name)
            return ToolResult(success=True, output={"agent": data})
        except KeyError as exc:
            return ToolResult(success=False, error=str(exc))

    return handler


def _create_agent_def() -> ToolDefinition:
    return ToolDefinition(
        name="create_agent",
        description="Create a new agent in the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Agent name (id)"},
                "role": {"type": "string", "description": "Agent role description"},
                "goal": {"type": "string", "description": "Agent goal"},
                "engine_profile": {"type": "string", "description": "Engine profile name"},
            },
            "required": ["name", "role", "goal", "engine_profile"],
        },
    )


def _make_create_agent_handler(project_root: Path) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        from miniautogen.cli.services.agent_ops import create_agent

        name = params.get("name", "")
        role = params.get("role", "")
        goal = params.get("goal", "")
        engine = params.get("engine_profile", "")
        try:
            data = create_agent(
                project_root, name,
                role=role, goal=goal, engine_profile=engine,
            )
            return ToolResult(success=True, output={"agent": data})
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))

    return handler


def _update_agent_def() -> ToolDefinition:
    return ToolDefinition(
        name="update_agent",
        description="Update fields on an existing agent.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Agent name"},
                "role": {"type": "string", "description": "New role"},
                "goal": {"type": "string", "description": "New goal"},
                "engine_profile": {"type": "string", "description": "New engine profile"},
            },
            "required": ["name"],
        },
    )


def _make_update_agent_handler(project_root: Path) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        from miniautogen.cli.services.agent_ops import update_agent

        name = params.get("name", "")
        if not name:
            return ToolResult(success=False, error="name is required")
        updates = {k: v for k, v in params.items() if k != "name" and v is not None}
        if not updates:
            return ToolResult(success=False, error="No fields to update")
        try:
            data = update_agent(project_root, name, **updates)
            return ToolResult(success=True, output=data)
        except (ValueError, KeyError) as exc:
            return ToolResult(success=False, error=str(exc))

    return handler


def _delete_agent_def() -> ToolDefinition:
    return ToolDefinition(
        name="delete_agent",
        description="Delete an agent from the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Agent name"},
            },
            "required": ["name"],
        },
    )


def _make_delete_agent_handler(project_root: Path) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        from miniautogen.cli.services.agent_ops import delete_agent

        name = params.get("name", "")
        if not name:
            return ToolResult(success=False, error="name is required")
        try:
            data = delete_agent(project_root, name)
            return ToolResult(success=True, output=data)
        except (ValueError, KeyError) as exc:
            return ToolResult(success=False, error=str(exc))

    return handler


# ---------------------------------------------------------------------------
# Flow tools
# ---------------------------------------------------------------------------


def _list_flows_def() -> ToolDefinition:
    return ToolDefinition(
        name="list_flows",
        description="List all flows (pipelines) in the workspace.",
        parameters={"type": "object", "properties": {}},
    )


def _make_list_flows_handler(project_root: Path) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        from miniautogen.cli.services.flow_ops import list_flows

        flows = list_flows(project_root)
        return ToolResult(success=True, output={"flows": flows})

    return handler


def _show_flow_def() -> ToolDefinition:
    return ToolDefinition(
        name="show_flow",
        description="Show detailed configuration of a specific flow.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Flow name"},
            },
            "required": ["name"],
        },
    )


def _make_show_flow_handler(project_root: Path) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        from miniautogen.cli.services.flow_ops import show_flow

        name = params.get("name", "")
        if not name:
            return ToolResult(success=False, error="name is required")
        try:
            data = show_flow(project_root, name)
            return ToolResult(success=True, output={"flow": data})
        except KeyError as exc:
            return ToolResult(success=False, error=str(exc))

    return handler


def _create_flow_def() -> ToolDefinition:
    return ToolDefinition(
        name="create_flow",
        description="Create a new flow (pipeline) configuration.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Flow name"},
                "mode": {
                    "type": "string",
                    "description": "Flow mode: workflow, deliberation, loop, team",
                    "enum": ["workflow", "deliberation", "loop", "team"],
                },
                "participants": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of agent names participating",
                },
                "leader": {
                    "type": "string",
                    "description": "Leader agent (required for deliberation mode)",
                },
                "max_rounds": {
                    "type": "integer",
                    "description": "Max deliberation rounds (default 3)",
                },
            },
            "required": ["name", "mode", "participants"],
        },
    )


def _make_create_flow_handler(project_root: Path) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        from miniautogen.cli.services.pipeline_ops import create_pipeline

        name = params.get("name", "")
        mode = params.get("mode", "workflow")
        participants = params.get("participants") or []
        leader = params.get("leader")
        max_rounds = params.get("max_rounds")
        try:
            data = create_pipeline(
                project_root, name,
                mode=mode, participants=participants,
                leader=leader, max_rounds=max_rounds,
            )
            return ToolResult(success=True, output={"flow": data})
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))

    return handler


def _delete_flow_def() -> ToolDefinition:
    return ToolDefinition(
        name="delete_flow",
        description="Delete a flow configuration.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Flow name"},
            },
            "required": ["name"],
        },
    )


def _make_delete_flow_handler(project_root: Path) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        from miniautogen.cli.services.flow_ops import delete_flow

        name = params.get("name", "")
        if not name:
            return ToolResult(success=False, error="name is required")
        try:
            data = delete_flow(project_root, name)
            return ToolResult(success=True, output=data)
        except (ValueError, KeyError) as exc:
            return ToolResult(success=False, error=str(exc))

    return handler


# ---------------------------------------------------------------------------
# Engine tools
# ---------------------------------------------------------------------------


def _list_engines_def() -> ToolDefinition:
    return ToolDefinition(
        name="list_engines",
        description="List all engine (LLM backend) profiles in the workspace.",
        parameters={"type": "object", "properties": {}},
    )


def _make_list_engines_handler(project_root: Path) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        from miniautogen.cli.services.engine_ops import list_engines

        engines = list_engines(project_root)
        return ToolResult(success=True, output={"engines": engines})

    return handler


def _show_engine_def() -> ToolDefinition:
    return ToolDefinition(
        name="show_engine",
        description="Show detailed configuration of a specific engine profile.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Engine name"},
            },
            "required": ["name"],
        },
    )


def _make_show_engine_handler(project_root: Path) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        from miniautogen.cli.services.engine_ops import show_engine

        name = params.get("name", "")
        if not name:
            return ToolResult(success=False, error="name is required")
        try:
            data = show_engine(project_root, name)
            return ToolResult(success=True, output={"engine": data})
        except KeyError as exc:
            return ToolResult(success=False, error=str(exc))

    return handler


# ---------------------------------------------------------------------------
# Execution tools
# ---------------------------------------------------------------------------


def _run_flow_def() -> ToolDefinition:
    return ToolDefinition(
        name="run_flow",
        description="Execute a flow (pipeline) in the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "flow_name": {"type": "string", "description": "Flow name to execute"},
                "input": {"type": "string", "description": "Optional input text"},
                "timeout": {"type": "number", "description": "Optional timeout in seconds"},
            },
            "required": ["flow_name"],
        },
    )


def _make_run_flow_handler(project_root: Path) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        from miniautogen.api import NullEventSink
        from miniautogen.cli.config import CONFIG_FILENAME, load_config
        from miniautogen.cli.services.run_pipeline import execute_pipeline

        flow_name = params.get("flow_name", "")
        input_text = params.get("input")
        timeout = params.get("timeout")

        if not flow_name:
            return ToolResult(success=False, error="flow_name is required")

        config_path = project_root / CONFIG_FILENAME
        if not config_path.is_file():
            return ToolResult(success=False, error="No workspace config found")

        config = load_config(config_path)
        try:
            result = await execute_pipeline(
                config, flow_name, project_root,
                timeout=timeout,
                pipeline_input=input_text,
                event_sink=NullEventSink(),
            )
            return ToolResult(success=result.get("status") == "completed", output=result)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    return handler


# ---------------------------------------------------------------------------
# Validation tool
# ---------------------------------------------------------------------------


def _check_project_def() -> ToolDefinition:
    return ToolDefinition(
        name="check_project",
        description="Validate the workspace configuration.",
        parameters={"type": "object", "properties": {}},
    )


def _make_check_project_handler(project_root: Path) -> ToolHandler:
    async def handler(params: dict[str, Any]) -> ToolResult:
        from miniautogen.cli.config import CONFIG_FILENAME, load_config
        from miniautogen.cli.services.check_project import check_project

        config_path = project_root / CONFIG_FILENAME
        if not config_path.is_file():
            return ToolResult(success=False, error="No workspace config found")
        config = load_config(config_path)
        results = check_project(config, project_root)
        failures = [
            {"name": r.name, "message": r.message, "category": r.category}
            for r in results
            if not r.passed
        ]
        if failures:
            return ToolResult(
                success=False,
                error=f"Project validation failed: {failures[0]['message']}",
                output={"valid": False, "errors": failures},
            )
        return ToolResult(success=True, output={"valid": True})

    return handler
