import pytest
import yaml
from pathlib import Path
from miniautogen.core.contracts.tool_registry import ToolRegistryProtocol, ToolCall
from miniautogen.core.runtime.filesystem_tool_registry import FileSystemToolRegistry


@pytest.fixture
def tools_yaml(tmp_path):
    """Create a sample tools.yml file."""
    tools_file = tmp_path / "tools.yml"
    config = {
        "tools": [
            {"name": "read_file", "description": "Read a file from workspace", "builtin": True},
            {"name": "search", "description": "Search codebase", "builtin": True},
        ]
    }
    tools_file.write_text(yaml.dump(config))
    return tools_file


def test_implements_protocol(tools_yaml):
    reg = FileSystemToolRegistry(tools_yaml)
    assert isinstance(reg, ToolRegistryProtocol)


def test_loads_tools_from_yaml(tools_yaml):
    reg = FileSystemToolRegistry(tools_yaml)
    tools = reg.list_tools()
    assert len(tools) == 2
    assert tools[0].name == "read_file"
    assert tools[1].name == "search"


def test_has_tool(tools_yaml):
    reg = FileSystemToolRegistry(tools_yaml)
    assert reg.has_tool("read_file")
    assert not reg.has_tool("nonexistent")


def test_empty_when_file_missing(tmp_path):
    reg = FileSystemToolRegistry(tmp_path / "nonexistent.yml")
    assert reg.list_tools() == []
    assert not reg.has_tool("anything")


@pytest.mark.anyio
async def test_execute_unknown_tool(tools_yaml):
    reg = FileSystemToolRegistry(tools_yaml)
    result = await reg.execute_tool(ToolCall(tool_name="unknown", call_id="1", params={}))
    assert not result.success
    assert "unknown" in result.error.lower()


@pytest.mark.anyio
async def test_execute_builtin_tool(tools_yaml):
    """Builtin tools should return a 'not implemented' result for now."""
    reg = FileSystemToolRegistry(tools_yaml)
    result = await reg.execute_tool(ToolCall(tool_name="read_file", call_id="1", params={"path": "test.py"}))
    # Builtin tools are placeholders for now — they should not crash
    assert isinstance(result.success, bool)


def test_script_tool_path_traversal_rejected(tmp_path):
    """Script paths with traversal should be rejected at load time."""
    tools_file = tmp_path / "tools.yml"
    config = {
        "tools": [
            {"name": "evil", "description": "Evil tool", "script": "../../etc/passwd"},
        ]
    }
    tools_file.write_text(yaml.dump(config))
    reg = FileSystemToolRegistry(tools_file, workspace_root=tmp_path)
    # Tool should be rejected/ignored
    assert not reg.has_tool("evil")
