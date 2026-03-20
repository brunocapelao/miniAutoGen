import pytest
import yaml
from pathlib import Path
from miniautogen.core.contracts.tool_registry import ToolRegistryProtocol, ToolCall
from miniautogen.core.runtime.filesystem_tool_registry import FileSystemToolRegistry


@pytest.fixture
def tools_yaml(tmp_path):
    """Create a sample tools.yml file with mixed builtin and script tools."""
    tools_file = tmp_path / "tools.yml"
    config = {
        "tools": [
            {"name": "read_file", "description": "Read a file from workspace", "builtin": True},
            {"name": "search", "description": "Search codebase", "builtin": True},
            {"name": "my_script", "description": "Custom script", "script": "run.sh"},
        ]
    }
    tools_file.write_text(yaml.dump(config))
    return tools_file


def test_implements_protocol(tools_yaml):
    reg = FileSystemToolRegistry(tools_yaml)
    assert isinstance(reg, ToolRegistryProtocol)


def test_loads_tools_from_yaml(tools_yaml):
    """Only non-builtin tools should be loaded; builtins are delegated to BuiltinToolRegistry."""
    reg = FileSystemToolRegistry(tools_yaml)
    tools = reg.list_tools()
    names = [t.name for t in tools]
    assert "read_file" not in names  # Builtin — skipped
    assert "search" not in names     # Builtin — skipped
    assert "my_script" in names      # Script tool — loaded


def test_has_tool_non_builtin(tools_yaml):
    reg = FileSystemToolRegistry(tools_yaml)
    assert reg.has_tool("my_script")
    assert not reg.has_tool("read_file")   # Builtin — not registered here
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


def test_builtin_tools_not_loaded(tmp_path):
    """Builtin tools are skipped so BuiltinToolRegistry handles them instead."""
    tools_yml = tmp_path / "tools.yml"
    tools_yml.write_text(
        "tools:\n"
        "  - name: read_file\n"
        "    builtin: true\n"
        "    description: Read a file\n"
        "  - name: my_script\n"
        "    description: Custom script\n"
        "    script: run.sh\n"
    )
    reg = FileSystemToolRegistry(tools_yml, tmp_path)
    assert not reg.has_tool("read_file")  # Skipped
    assert reg.has_tool("my_script")      # Loaded
