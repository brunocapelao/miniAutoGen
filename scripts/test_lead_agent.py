"""Smoke test for Lead Agent — workspace tools, event awareness, session lifecycle.

Tests 4 layers:
  Layer 1 — workspace_tools: CRUD agents, flows, engines (no LLM needed)
  Layer 2 — LeadAgentSession: send/close/events with mock runtime
  Layer 3 — Event awareness: get_events tool + event capture
  Layer 4 — CLI command: command registration and help

Usage::
    uv run python scripts/test_lead_agent.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import anyio
import yaml


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

G = "\033[92m"  # green
R = "\033[91m"  # red
Y = "\033[93m"  # yellow
B = "\033[94m"  # blue
N = "\033[0m"   # reset


def ok(msg: str) -> None:
    print(f"  {G}✓{N} {msg}")


def fail(msg: str) -> None:
    print(f"  {R}✗{N} {msg}")
    _failures.append(msg)


def info(msg: str) -> None:
    print(f"  {Y}→{N} {msg}")


def section(title: str) -> None:
    print(f"\n{B}═══ {title} ═══{N}")


_failures: list[str] = []
_workspace: Path | None = None


# ---------------------------------------------------------------------------
# Fixture: create a temporary workspace
# ---------------------------------------------------------------------------


def create_workspace() -> Path:
    """Create a temporary workspace with config and agents."""
    tmp = Path(tempfile.mkdtemp(prefix="lead_smoke_"))

    config = {
        "project": {"name": "smoke-test", "version": "0.1.0"},
        "defaults": {"engine": "openai"},
        "engines": {
            "openai": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "temperature": 0.2,
            },
        },
        "flows": {
            "main": {
                "mode": "workflow",
                "participants": ["coder"],
            },
            "review": {
                "mode": "workflow",
                "participants": ["coder", "reviewer"],
            },
        },
    }
    (tmp / "miniautogen.yaml").write_text(yaml.dump(config))

    agents_dir = tmp / "agents"
    agents_dir.mkdir()
    (agents_dir / "coder.yaml").write_text(
        yaml.dump({
            "id": "coder",
            "name": "coder",
            "role": "Developer",
            "goal": "Write Python code",
            "engine_profile": "openai",
        })
    )
    (agents_dir / "reviewer.yaml").write_text(
        yaml.dump({
            "id": "reviewer",
            "name": "reviewer",
            "role": "Code Reviewer",
            "goal": "Review code thoroughly",
            "engine_profile": "openai",
        })
    )

    return tmp


def cleanup_workspace(path: Path) -> None:
    """Remove temporary workspace."""
    import shutil
    shutil.rmtree(path, ignore_errors=True)


# ---------------------------------------------------------------------------
# Layer 1: workspace_tools — direct tool execution against YAML
# ---------------------------------------------------------------------------


async def test_workspace_tools(root: Path) -> None:
    section("Layer 1: workspace_tools — CRUD agents, flows, engines")

    from miniautogen.core.runtime.workspace_tools import build_workspace_tools
    from miniautogen.core.runtime.tool_registry import InMemoryToolRegistry

    registry = InMemoryToolRegistry()
    for definition, handler in build_workspace_tools(root):
        registry.register(definition, handler)

    from miniautogen.core.contracts.tool_registry import ToolCall

    # ---- list_agents ----
    info("list_agents — should return 2 agents")
    result = await registry.execute_tool(ToolCall(tool_name="list_agents", call_id="1", params={}))
    assert result.success, f"list_agents failed: {result.error}"
    agents = result.output.get("agents", [])
    assert len(agents) == 2, f"Expected 2 agents, got {len(agents)}"
    names = [a["name"] for a in agents]
    assert "coder" in names
    assert "reviewer" in names
    ok(f"list_agents: {len(agents)} agents ({', '.join(names)})")

    # ---- show_agent ----
    info("show_agent coder")
    result = await registry.execute_tool(ToolCall(tool_name="show_agent", call_id="2", params={"name": "coder"}))
    assert result.success, f"show_agent failed: {result.error}"
    assert result.output["agent"]["name"] == "coder"
    ok(f"show_agent: {result.output['agent']['name']} ({result.output['agent']['role']})")

    # ---- show_agent not found ----
    info("show_agent nonexistent — should fail")
    result = await registry.execute_tool(ToolCall(tool_name="show_agent", call_id="3", params={"name": "ghost"}))
    assert not result.success, "Expected failure for non-existent agent"
    ok(f"show_agent error: {result.error}")

    # ---- create_agent ----
    info("create_agent analyst")
    result = await registry.execute_tool(ToolCall(
        tool_name="create_agent", call_id="4",
        params={"name": "analyst", "role": "Data Analyst", "goal": "Analyze data", "engine_profile": "openai"},
    ))
    assert result.success, f"create_agent failed: {result.error}"
    ok(f"create_agent: {result.output['agent']['name']}")

    # ---- verify agent file exists ----
    assert (root / "agents" / "analyst.yaml").is_file()
    ok("analyst.yaml created on disk")

    # ---- list_agents after create ----
    result = await registry.execute_tool(ToolCall(tool_name="list_agents", call_id="5", params={}))
    assert len(result.output["agents"]) == 3
    ok(f"list_agents after create: {len(result.output['agents'])} agents")

    # ---- create_agent duplicate ----
    info("create_agent duplicate — should fail")
    result = await registry.execute_tool(ToolCall(
        tool_name="create_agent", call_id="6",
        params={"name": "coder", "role": "x", "goal": "x", "engine_profile": "openai"},
    ))
    assert not result.success, "Expected failure for duplicate agent"
    ok(f"duplicate error: {result.error}")

    # ---- update_agent ----
    info("update_agent coder — change role")
    result = await registry.execute_tool(ToolCall(
        tool_name="update_agent", call_id="7",
        params={"name": "coder", "role": "Senior Developer"},
    ))
    assert result.success, f"update_agent failed: {result.error}"
    assert result.output["after"]["role"] == "Senior Developer"
    ok(f"update_agent: role changed to '{result.output['after']['role']}'")

    # ---- delete_agent ----
    info("delete_agent analyst")
    result = await registry.execute_tool(ToolCall(tool_name="delete_agent", call_id="8", params={"name": "analyst"}))
    assert result.success, f"delete_agent failed: {result.error}"
    assert not (root / "agents" / "analyst.yaml").is_file()
    ok("delete_agent: file removed")

    # ---- list_flows ----
    info("list_flows — should return 2 flows")
    result = await registry.execute_tool(ToolCall(tool_name="list_flows", call_id="9", params={}))
    assert result.success, f"list_flows failed: {result.error}"
    flows = result.output["flows"]
    assert len(flows) == 2
    ok(f"list_flows: {len(flows)} flows ({', '.join(f['name'] for f in flows)})")

    # ---- show_flow ----
    info("show_flow main")
    result = await registry.execute_tool(ToolCall(tool_name="show_flow", call_id="10", params={"name": "main"}))
    assert result.success, f"show_flow failed: {result.error}"
    assert result.output["flow"]["name"] == "main"
    ok(f"show_flow: {result.output['flow']['name']} mode={result.output['flow']['mode']}")

    # ---- create_flow ----
    info("create_flow data-pipeline")
    result = await registry.execute_tool(ToolCall(
        tool_name="create_flow", call_id="11",
        params={"name": "data-pipeline", "mode": "workflow", "participants": ["coder", "reviewer"]},
    ))
    assert result.success, f"create_flow failed: {result.error}"
    ok(f"create_flow: {result.output['flow']}")

    # ---- delete_flow ----
    info("delete_flow data-pipeline")
    result = await registry.execute_tool(ToolCall(tool_name="delete_flow", call_id="12", params={"name": "data-pipeline"}))
    assert result.success, f"delete_flow failed: {result.error}"
    ok(f"delete_flow: {result.output['deleted']}")

    # ---- list_engines ----
    info("list_engines — should return 1 engine")
    result = await registry.execute_tool(ToolCall(tool_name="list_engines", call_id="13", params={}))
    assert result.success, f"list_engines failed: {result.error}"
    engines = result.output["engines"]
    assert len(engines) == 1
    ok(f"list_engines: {len(engines)} engines ({', '.join(e['name'] for e in engines)})")

    # ---- show_engine ----
    info("show_engine openai")
    result = await registry.execute_tool(ToolCall(tool_name="show_engine", call_id="14", params={"name": "openai"}))
    assert result.success, f"show_engine failed: {result.error}"
    assert result.output["engine"]["model"] == "gpt-4o-mini"
    ok(f"show_engine: {result.output['engine']['name']} ({result.output['engine']['provider']})")

    # ---- check_project ----
    info("check_project — should pass for valid workspace")
    result = await registry.execute_tool(ToolCall(tool_name="check_project", call_id="15", params={}))
    assert result.success, f"check_project failed: {result.error}"
    ok("check_project: workspace is valid")

    # ---- delete_agent with flow reference ----
    info("delete_agent coder — should fail (referenced by flows)")
    result = await registry.execute_tool(ToolCall(tool_name="delete_agent", call_id="16", params={"name": "coder"}))
    assert not result.success, "Expected failure: coder is referenced by flows"
    ok(f"delete_agent blocked: {result.error}")


# ---------------------------------------------------------------------------
# Layer 2: LeadAgentSession — session lifecycle with mock runtime
# ---------------------------------------------------------------------------


async def test_lead_agent_session(root: Path) -> None:
    section("Layer 2: LeadAgentSession — lifecycle + tool injection")

    from unittest.mock import AsyncMock, patch

    mock_runtime = AsyncMock()
    mock_runtime.tool_registry = None
    mock_runtime.process = AsyncMock(return_value="I have full workspace access.")

    with patch("miniautogen.cli.services.lead_agent_session.create_runtime",
               return_value=(mock_runtime, "lead-smoke-001")):
        from miniautogen.cli.services.lead_agent_session import LeadAgentSession
        session = await LeadAgentSession.create(root)

    # Session state
    assert session.agent_name == "coder", f"Expected coder, got {session.agent_name}"
    assert session.run_id == "lead-smoke-001"
    assert not session.is_closed
    assert session.history == []
    info(f"Session created: agent={session.agent_name}, run={session.run_id}")

    # Tool injection — workspace tools
    assert mock_runtime.tool_registry is not None
    tool_names = [t.name for t in mock_runtime.tool_registry.list_tools()]
    required_tools = {
        "list_agents", "show_agent", "create_agent", "update_agent", "delete_agent",
        "list_flows", "show_flow", "create_flow", "delete_flow",
        "list_engines", "show_engine",
        "run_flow", "check_project",
        "get_events",
    }
    missing = required_tools - set(tool_names)
    assert not missing, f"Missing tools: {missing}"
    ok(f"All {len(tool_names)} tools injected: {', '.join(tool_names)}")

    # send
    response = await session.send("List all agents")
    assert response == "I have full workspace access."
    assert len(session.history) == 2
    assert session.history[0] == {"role": "user", "content": "List all agents"}
    assert session.history[1] == {"role": "assistant", "content": "I have full workspace access."}
    ok(f"send works: '{response}'")

    # history tracking
    response2 = await session.send("Create a flow")
    assert len(session.history) == 4
    ok(f"history tracking: {len(session.history)} messages")

    # clear_history
    session.clear_history()
    assert session.history == []
    ok("clear_history works")

    # close
    await session.close()
    assert session.is_closed
    mock_runtime.close.assert_awaited_once()
    ok("close works")

    # send after close
    try:
        await session.send("test")
        fail("Expected RuntimeError for send after close")
    except RuntimeError:
        ok("send after close raises RuntimeError as expected")


# ---------------------------------------------------------------------------
# Layer 3: Event awareness — get_events tool + event capture
# ---------------------------------------------------------------------------


async def test_event_awareness(root: Path) -> None:
    section("Layer 3: Event awareness — get_events tool + event capture")

    from unittest.mock import AsyncMock, patch

    mock_runtime = AsyncMock()
    mock_runtime.tool_registry = None
    mock_runtime.process = AsyncMock(return_value="OK")

    with patch("miniautogen.cli.services.lead_agent_session.create_runtime",
               return_value=(mock_runtime, "lead-events-001")):
        from miniautogen.cli.services.lead_agent_session import LeadAgentSession
        session = await LeadAgentSession.create(root)

    # Send a message — should generate 2 events
    await session.send("Hello")
    events = session.recent_events
    assert len(events) == 2, f"Expected 2 events, got {len(events)}"
    assert events[0].type == "component_started"
    assert events[1].type == "component_finished"
    ok(f"Event capture: {len(events)} events (started + finished)")

    # Second send — 2 more events
    await session.send("World")
    assert len(session.recent_events) == 4
    ok(f"Events accumulate: {len(session.recent_events)} total")

    # — get_events tool via registry —
    from miniautogen.core.contracts.tool_registry import ToolCall

    event_registry = mock_runtime.tool_registry
    assert event_registry.has_tool("get_events")

    # get all events
    result = await event_registry.execute_tool(
        ToolCall(tool_name="get_events", call_id="e1", params={})
    )
    assert result.success, f"get_events failed: {result.error}"
    output = result.output
    assert output["total"] >= 4
    ok(f"get_events(all): {output['total']} events returned")

    # filter by type
    result = await event_registry.execute_tool(
        ToolCall(tool_name="get_events", call_id="e2", params={"event_type": "component_started"})
    )
    assert result.success
    for ev in result.output["events"]:
        assert ev["type"] == "component_started"
    ok(f"get_events(filter=component_started): {result.output['total']} events")

    # limit
    result = await event_registry.execute_tool(
        ToolCall(tool_name="get_events", call_id="e3", params={"limit": 2})
    )
    assert result.success
    assert result.output["total"] <= 2
    ok(f"get_events(limit=2): {result.output['total']} events")

    await session.close()
    ok("Session closed cleanly")


# ---------------------------------------------------------------------------
# Layer 4: CLI command — registration and structure
# ---------------------------------------------------------------------------


def test_cli_command() -> None:
    section("Layer 4: CLI command — registration + help")

    from click.testing import CliRunner
    from miniautogen.cli.main import cli

    runner = CliRunner()

    # --help shows the command
    result = runner.invoke(cli, ["lead", "--help"])
    assert result.exit_code == 0, f"lead --help failed: {result.output}"
    assert "lead agent" in result.output.lower()
    ok("miniautogen lead --help shows correct description")

    # Command is registered in the CLI group
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "lead" in result.output
    ok("miniautogen --help lists lead command")


# ---------------------------------------------------------------------------
# Run all layers
# ---------------------------------------------------------------------------


async def main() -> None:
    print(f"\n{G}██ Lead Agent — Smoke Test Suite ██{N}")
    print(f"{Y}Testing workspace tools, session lifecycle, event awareness, and CLI{N}")

    root = create_workspace()
    global _workspace
    _workspace = root

    # Set dummy API key so workspace validation passes
    os.environ["OPENAI_API_KEY"] = "sk-test-dummy-key"

    try:
        await test_workspace_tools(root)
        await test_lead_agent_session(root)
        await test_event_awareness(root)
        test_cli_command()
    finally:
        os.environ.pop("OPENAI_API_KEY", None)
        cleanup_workspace(root)

    total = 18  # approximate assertion count across all tests
    print(f"\n{'─' * 50}")
    if _failures:
        print(f"{R}{len(_failures)} failures:{N}")
        for f in _failures:
            print(f"  {R}•{N} {f}")
        sys.exit(1)
    else:
        print(f"{G}All smoke tests passed.{N}")
        print(f"  Workspace tools: 13 tools, full CRUD + validation verified")
        print(f"  Session lifecycle: create/send/clear/close")
        print(f"  Event awareness: capture, filter, limit")
        print(f"  CLI command: lead registered in miniautogen group")


if __name__ == "__main__":
    anyio.run(main)
