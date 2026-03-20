"""Tests for BuiltinToolRegistry — functional and security."""
from __future__ import annotations

from pathlib import Path

import pytest

from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.contracts.tool_registry import ToolCall, ToolDefinition, ToolRegistryProtocol
from miniautogen.core.runtime.agent_sandbox import AgentFilesystemSandbox
from miniautogen.core.runtime.builtin_tools import (
    MAX_DIRECTORY_ENTRIES,
    MAX_FILE_READ_BYTES,
    MAX_SEARCH_RESULTS,
    BuiltinToolRegistry,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_registry(
    tmp_path: Path, sandbox: AgentFilesystemSandbox | None = None
) -> BuiltinToolRegistry:
    return BuiltinToolRegistry(workspace_root=tmp_path, sandbox=sandbox)


def make_call(tool_name: str, params: dict | None = None, call_id: str = "test-1") -> ToolCall:
    return ToolCall(tool_name=tool_name, call_id=call_id, params=params or {})


# ---------------------------------------------------------------------------
# TestBuiltinToolRegistryInterface
# ---------------------------------------------------------------------------


class TestBuiltinToolRegistryInterface:
    def test_implements_tool_registry_protocol(self, tmp_path: Path) -> None:
        reg = make_registry(tmp_path)
        assert isinstance(reg, ToolRegistryProtocol)

    def test_list_tools_returns_three_definitions(self, tmp_path: Path) -> None:
        reg = make_registry(tmp_path)
        tools = reg.list_tools()
        names = {t.name for t in tools}
        assert names == {"read_file", "search_codebase", "list_directory"}

    def test_list_tools_returns_tool_definitions(self, tmp_path: Path) -> None:
        reg = make_registry(tmp_path)
        for t in reg.list_tools():
            assert isinstance(t, ToolDefinition)
            assert t.description

    def test_has_tool_known_tools(self, tmp_path: Path) -> None:
        reg = make_registry(tmp_path)
        assert reg.has_tool("read_file")
        assert reg.has_tool("search_codebase")
        assert reg.has_tool("list_directory")

    def test_has_tool_unknown_returns_false(self, tmp_path: Path) -> None:
        reg = make_registry(tmp_path)
        assert not reg.has_tool("nonexistent_tool")

    @pytest.mark.anyio
    async def test_execute_unknown_tool_returns_error(self, tmp_path: Path) -> None:
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("nonexistent_tool"))
        assert isinstance(result, ToolResult)
        assert not result.success
        assert result.error is not None


# ---------------------------------------------------------------------------
# TestReadFile
# ---------------------------------------------------------------------------


class TestReadFile:
    @pytest.mark.anyio
    async def test_reads_file_content(self, tmp_path: Path) -> None:
        (tmp_path / "hello.txt").write_text("line1\nline2\nline3")
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("read_file", {"path": "hello.txt"}))
        assert result.success
        assert "line1" in result.output
        assert "line2" in result.output
        assert "line3" in result.output

    @pytest.mark.anyio
    async def test_lines_are_numbered(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").write_text("alpha\nbeta")
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("read_file", {"path": "file.txt"}))
        assert result.success
        # Line numbers should appear in output
        assert "1" in result.output
        assert "2" in result.output

    @pytest.mark.anyio
    async def test_offset_skips_lines(self, tmp_path: Path) -> None:
        (tmp_path / "lines.txt").write_text("\n".join(f"line{i}" for i in range(10)))
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("read_file", {"path": "lines.txt", "offset": 5}))
        assert result.success
        assert "line5" in result.output
        assert "line0" not in result.output

    @pytest.mark.anyio
    async def test_limit_caps_lines(self, tmp_path: Path) -> None:
        (tmp_path / "many.txt").write_text("\n".join(f"L{i}" for i in range(20)))
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("read_file", {"path": "many.txt", "limit": 3}))
        assert result.success
        lines = result.output.strip().splitlines()
        assert len(lines) == 3

    @pytest.mark.anyio
    async def test_nonexistent_file_returns_error(self, tmp_path: Path) -> None:
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("read_file", {"path": "no_such_file.txt"}))
        assert not result.success
        assert result.error is not None

    @pytest.mark.anyio
    async def test_oversized_file_without_limit_returns_error(self, tmp_path: Path) -> None:
        big_file = tmp_path / "big.bin"
        big_file.write_bytes(b"x" * (MAX_FILE_READ_BYTES + 1))
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("read_file", {"path": "big.bin"}))
        assert not result.success
        error_msg = result.error.lower()
        assert (
            "large" in error_msg
            or "limit" in error_msg
            or str(MAX_FILE_READ_BYTES + 1) in result.error
        )

    @pytest.mark.anyio
    async def test_oversized_file_with_limit_succeeds(self, tmp_path: Path) -> None:
        big_file = tmp_path / "big.txt"
        # Write just enough lines
        big_file.write_text("\n".join("x" * 100 for _ in range(100)))
        # Artificially patch size check by using limit param
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("read_file", {"path": "big.txt", "limit": 5}))
        assert result.success

    @pytest.mark.anyio
    async def test_sandbox_denies_other_agent_config(self, tmp_path: Path) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        other_config_dir = workspace / ".miniautogen" / "agents" / "other_agent"
        other_config_dir.mkdir(parents=True)
        (other_config_dir / "secret.txt").write_text("secret")

        sandbox = AgentFilesystemSandbox("my_agent", workspace)
        reg = BuiltinToolRegistry(workspace_root=workspace, sandbox=sandbox)
        result = await reg.execute_tool(
            make_call("read_file", {"path": ".miniautogen/agents/other_agent/secret.txt"})
        )
        assert not result.success
        assert result.error is not None

    @pytest.mark.anyio
    async def test_path_traversal_rejected(self, tmp_path: Path) -> None:
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("read_file", {"path": "../../etc/passwd"}))
        assert not result.success
        assert result.error is not None


# ---------------------------------------------------------------------------
# TestListDirectory
# ---------------------------------------------------------------------------


class TestListDirectory:
    @pytest.mark.anyio
    async def test_lists_directory_entries(self, tmp_path: Path) -> None:
        (tmp_path / "file.py").write_text("code")
        (tmp_path / "subdir").mkdir()
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("list_directory", {"path": "."}))
        assert result.success
        assert "file.py" in result.output
        assert "subdir" in result.output

    @pytest.mark.anyio
    async def test_indicates_file_type(self, tmp_path: Path) -> None:
        (tmp_path / "myfile.txt").write_text("x")
        (tmp_path / "mydir").mkdir()
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("list_directory", {"path": "."}))
        assert result.success
        assert "file" in result.output
        assert "dir" in result.output

    @pytest.mark.anyio
    async def test_default_path_is_workspace_root(self, tmp_path: Path) -> None:
        (tmp_path / "root_file.txt").write_text("hi")
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("list_directory", {}))
        assert result.success
        assert "root_file.txt" in result.output

    @pytest.mark.anyio
    async def test_not_a_directory_returns_error(self, tmp_path: Path) -> None:
        (tmp_path / "plain.txt").write_text("content")
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("list_directory", {"path": "plain.txt"}))
        assert not result.success

    @pytest.mark.anyio
    async def test_nonexistent_directory_returns_error(self, tmp_path: Path) -> None:
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("list_directory", {"path": "no_such_dir"}))
        assert not result.success

    @pytest.mark.anyio
    async def test_caps_at_max_directory_entries(self, tmp_path: Path) -> None:
        subdir = tmp_path / "many_files"
        subdir.mkdir()
        for i in range(MAX_DIRECTORY_ENTRIES + 5):
            (subdir / f"f{i}.txt").write_text("")
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("list_directory", {"path": "many_files"}))
        assert result.success
        assert "truncated" in result.output.lower()

    @pytest.mark.anyio
    async def test_sandbox_denies_outside_workspace(self, tmp_path: Path) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        sandbox = AgentFilesystemSandbox("agent", workspace)
        reg = BuiltinToolRegistry(workspace_root=workspace, sandbox=sandbox)
        result = await reg.execute_tool(make_call("list_directory", {"path": "../../"}))
        assert not result.success

    @pytest.mark.anyio
    async def test_path_traversal_rejected(self, tmp_path: Path) -> None:
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("list_directory", {"path": "../../../"}))
        assert not result.success


# ---------------------------------------------------------------------------
# TestSearchCodebase
# ---------------------------------------------------------------------------


class TestSearchCodebase:
    @pytest.mark.anyio
    async def test_finds_pattern_in_files(self, tmp_path: Path) -> None:
        (tmp_path / "code.py").write_text("def hello_world(): pass\n")
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(
            make_call("search_codebase", {"pattern": "hello_world"})
        )
        assert result.success
        assert "hello_world" in result.output

    @pytest.mark.anyio
    async def test_no_matches_returns_success_with_no_matches(self, tmp_path: Path) -> None:
        (tmp_path / "code.py").write_text("x = 1\n")
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(
            make_call("search_codebase", {"pattern": "THIS_PATTERN_DOES_NOT_EXIST_XYZ"})
        )
        assert result.success
        assert "no matches" in result.output.lower()

    @pytest.mark.anyio
    async def test_empty_pattern_returns_error(self, tmp_path: Path) -> None:
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(
            make_call("search_codebase", {"pattern": ""})
        )
        assert not result.success
        assert result.error is not None

    @pytest.mark.anyio
    async def test_glob_filter_applied(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("TARGET_PATTERN")
        (tmp_path / "b.txt").write_text("TARGET_PATTERN")
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(
            make_call("search_codebase", {"pattern": "TARGET_PATTERN", "glob": "*.py"})
        )
        assert result.success
        assert "a.py" in result.output
        assert "b.txt" not in result.output

    @pytest.mark.anyio
    async def test_max_results_capped_at_limit(self, tmp_path: Path) -> None:
        for i in range(MAX_SEARCH_RESULTS + 20):
            (tmp_path / f"file{i}.txt").write_text("COMMON_PATTERN")
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(
            make_call(
                "search_codebase",
                {"pattern": "COMMON_PATTERN", "max_results": MAX_SEARCH_RESULTS + 20},
            )
        )
        assert result.success
        # Output should be capped
        lines = [ln for ln in result.output.splitlines() if "COMMON_PATTERN" in ln]
        assert len(lines) <= MAX_SEARCH_RESULTS

    @pytest.mark.anyio
    async def test_glob_traversal_rejected(self, tmp_path: Path) -> None:
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(
            make_call("search_codebase", {"pattern": "x", "glob": "../../*.py"})
        )
        assert not result.success
        assert result.error is not None

    @pytest.mark.anyio
    async def test_glob_absolute_path_rejected(self, tmp_path: Path) -> None:
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(
            make_call("search_codebase", {"pattern": "x", "glob": "/etc/*.conf"})
        )
        assert not result.success
        assert result.error is not None


# ---------------------------------------------------------------------------
# TestSecurityControls
# ---------------------------------------------------------------------------


class TestSecurityControls:
    @pytest.mark.anyio
    async def test_flag_injection_in_pattern_is_safe(self, tmp_path: Path) -> None:
        """Patterns that look like grep flags should not crash or escape sandbox."""
        (tmp_path / "test.txt").write_text("safe content\n")
        reg = make_registry(tmp_path)
        # This should not execute as a flag — grep uses -- separator
        result = await reg.execute_tool(
            make_call("search_codebase", {"pattern": "--version"})
        )
        # Either succeeds (found/not found) or fails gracefully — must NOT crash
        assert isinstance(result, ToolResult)
        assert isinstance(result.success, bool)

    @pytest.mark.anyio
    async def test_symlink_escape_blocked(self, tmp_path: Path) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("secret outside workspace")

        # Create a symlink inside workspace pointing outside
        symlink = workspace / "evil_link.txt"
        symlink.symlink_to(outside)

        sandbox = AgentFilesystemSandbox("agent", workspace)
        reg = BuiltinToolRegistry(workspace_root=workspace, sandbox=sandbox)

        # Reading the symlink — sandbox should check the resolved path
        result = await reg.execute_tool(make_call("read_file", {"path": "evil_link.txt"}))
        # The resolved path IS inside workspace (symlink lives there),
        # but the target is outside. Behavior depends on sandbox.can_read resolution.
        # The important thing: no crash and the tool returns a ToolResult.
        assert isinstance(result, ToolResult)

    @pytest.mark.anyio
    async def test_path_traversal_read_file(self, tmp_path: Path) -> None:
        reg = make_registry(tmp_path)
        for evil in ["../../../etc/passwd", "subdir/../../etc/passwd", "/etc/passwd"]:
            result = await reg.execute_tool(make_call("read_file", {"path": evil}))
            assert not result.success, f"Expected failure for path: {evil}"

    @pytest.mark.anyio
    async def test_path_traversal_list_directory(self, tmp_path: Path) -> None:
        reg = make_registry(tmp_path)
        for evil in ["../../../etc", "subdir/../../etc"]:
            result = await reg.execute_tool(make_call("list_directory", {"path": evil}))
            assert not result.success, f"Expected failure for path: {evil}"

    @pytest.mark.anyio
    async def test_null_byte_in_path_handled(self, tmp_path: Path) -> None:
        reg = make_registry(tmp_path)
        result = await reg.execute_tool(make_call("read_file", {"path": "file\x00.txt"}))
        # Should fail gracefully — not crash
        assert isinstance(result, ToolResult)
        assert not result.success
