# End-to-End Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the end-to-end loop so `mag init` → configure YAML → `mag run` executes with real AgentRuntimes (builtin tools, persistent memory, config-driven flows).

**Architecture:** Three new components (BuiltinToolRegistry, CompositeToolRegistry, config-driven flow execution) compose with existing AgentRuntime, PersistentMemoryProvider, and coordination runtimes. PipelineRunner gains `run_from_config()` for YAML-only flows. FlowConfig schema extended with `mode`/`participants`.

**Tech Stack:** Python 3.10+, anyio, Pydantic v2, pytest + anyio

**Spec:** `.specs/end-to-end-wiring.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|----------------|
| `miniautogen/core/runtime/builtin_tools.py` | BuiltinToolRegistry — read_file, search_codebase, list_directory with sandbox + resource limits |
| `miniautogen/core/runtime/composite_tool_registry.py` | CompositeToolRegistry — chains N registries under ToolRegistryProtocol |
| `tests/core/runtime/test_builtin_tools.py` | Tests for BuiltinToolRegistry (functional + security) |
| `tests/core/runtime/test_composite_tool_registry.py` | Tests for CompositeToolRegistry |
| `tests/core/runtime/test_config_driven_flow.py` | Integration tests for config-driven flow execution |
| `tests/cli/test_flow_config_schema.py` | Tests for FlowConfig schema changes |
| `tests/cli/services/test_load_agent_specs.py` | Tests for agent spec loading |

### Modified Files
| File | Change |
|------|--------|
| `miniautogen/core/runtime/filesystem_tool_registry.py` | Remove builtin hack, skip builtin tools in `_load()` |
| `miniautogen/core/runtime/pipeline_runner.py` | `_build_agent_runtimes()` → async + real impls; add `run_from_config()` + `_build_coordination_from_config()` |
| `miniautogen/cli/config.py` | Extend FlowConfig with mode, participants, mode-specific fields |
| `miniautogen/cli/services/agent_ops.py` | Add `load_agent_specs()` |
| `miniautogen/cli/services/run_pipeline.py` | Wire config-driven path |
| `miniautogen/api.py` | Export new public symbols |

---

### Task 1: BuiltinToolRegistry

**Files:**
- Create: `miniautogen/core/runtime/builtin_tools.py`
- Create: `tests/core/runtime/test_builtin_tools.py`

**Context:** The BuiltinToolRegistry provides runtime-managed filesystem tools (read_file, search_codebase, list_directory) for agents whose engines don't have native tool support. All I/O uses `anyio.Path`. All operations check `AgentFilesystemSandbox.can_read()`. Resource limits prevent DoS.

- [ ] **Step 1: Write failing tests for read_file**

```python
# tests/core/runtime/test_builtin_tools.py
from __future__ import annotations

from pathlib import Path

import pytest

from miniautogen.core.contracts.tool_registry import ToolCall, ToolDefinition
from miniautogen.core.runtime.agent_sandbox import AgentFilesystemSandbox


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "project"
    ws.mkdir()
    (ws / ".miniautogen" / "agents" / "test-agent").mkdir(parents=True)
    return ws


@pytest.fixture
def sandbox(workspace: Path) -> AgentFilesystemSandbox:
    return AgentFilesystemSandbox(agent_name="test-agent", workspace=workspace)


@pytest.fixture
def registry(workspace: Path, sandbox: AgentFilesystemSandbox):
    from miniautogen.core.runtime.builtin_tools import BuiltinToolRegistry

    return BuiltinToolRegistry(workspace_root=workspace, sandbox=sandbox)


class TestBuiltinToolRegistryInterface:
    def test_list_tools_returns_three(self, registry):
        tools = registry.list_tools()
        assert len(tools) == 3
        names = {t.name for t in tools}
        assert names == {"read_file", "search_codebase", "list_directory"}

    def test_has_tool_known(self, registry):
        assert registry.has_tool("read_file")
        assert registry.has_tool("search_codebase")
        assert registry.has_tool("list_directory")

    def test_has_tool_unknown(self, registry):
        assert not registry.has_tool("delete_file")

    def test_tool_definitions_are_valid(self, registry):
        for tool in registry.list_tools():
            assert isinstance(tool, ToolDefinition)
            assert tool.name
            assert tool.description


class TestReadFile:
    @pytest.mark.anyio
    async def test_reads_file_content(self, registry, workspace: Path):
        (workspace / "hello.txt").write_text("line1\nline2\nline3\n")
        result = await registry.execute_tool(
            ToolCall(tool_name="read_file", call_id="1", params={"path": "hello.txt"})
        )
        assert result.success
        assert "line1" in result.output
        assert "line2" in result.output

    @pytest.mark.anyio
    async def test_reads_with_offset_and_limit(self, registry, workspace: Path):
        content = "\n".join(f"line{i}" for i in range(20))
        (workspace / "big.txt").write_text(content)
        result = await registry.execute_tool(
            ToolCall(
                tool_name="read_file",
                call_id="2",
                params={"path": "big.txt", "offset": 5, "limit": 3},
            )
        )
        assert result.success
        assert "line5" in result.output
        assert "line7" in result.output
        assert "line8" not in result.output

    @pytest.mark.anyio
    async def test_rejects_file_outside_sandbox(self, registry):
        result = await registry.execute_tool(
            ToolCall(
                tool_name="read_file",
                call_id="3",
                params={"path": "/etc/passwd"},
            )
        )
        assert not result.success
        assert "sandbox" in result.error.lower() or "denied" in result.error.lower()

    @pytest.mark.anyio
    async def test_rejects_nonexistent_file(self, registry):
        result = await registry.execute_tool(
            ToolCall(
                tool_name="read_file",
                call_id="4",
                params={"path": "nonexistent.txt"},
            )
        )
        assert not result.success

    @pytest.mark.anyio
    async def test_rejects_oversized_file_without_limit(self, registry, workspace: Path):
        huge = workspace / "huge.bin"
        huge.write_bytes(b"x" * 2_000_000)
        result = await registry.execute_tool(
            ToolCall(
                tool_name="read_file",
                call_id="5",
                params={"path": "huge.bin"},
            )
        )
        assert not result.success
        assert "too large" in result.error.lower()


class TestListDirectory:
    @pytest.mark.anyio
    async def test_lists_entries(self, registry, workspace: Path):
        (workspace / "a.txt").touch()
        (workspace / "subdir").mkdir()
        result = await registry.execute_tool(
            ToolCall(
                tool_name="list_directory",
                call_id="6",
                params={"path": "."},
            )
        )
        assert result.success
        assert "a.txt" in result.output
        assert "subdir" in result.output

    @pytest.mark.anyio
    async def test_rejects_outside_sandbox(self, registry):
        result = await registry.execute_tool(
            ToolCall(
                tool_name="list_directory",
                call_id="7",
                params={"path": "/etc"},
            )
        )
        assert not result.success

    @pytest.mark.anyio
    async def test_caps_entries(self, registry, workspace: Path):
        d = workspace / "big_dir"
        d.mkdir()
        for i in range(1100):
            (d / f"f{i}.txt").touch()
        result = await registry.execute_tool(
            ToolCall(
                tool_name="list_directory",
                call_id="8",
                params={"path": "big_dir"},
            )
        )
        assert result.success
        lines = result.output.strip().splitlines()
        assert len(lines) <= 1001  # 1000 entries + truncation msg


class TestSearchCodebase:
    @pytest.mark.anyio
    async def test_finds_pattern(self, registry, workspace: Path):
        (workspace / "code.py").write_text("def hello():\n    return 'world'\n")
        result = await registry.execute_tool(
            ToolCall(
                tool_name="search_codebase",
                call_id="9",
                params={"pattern": "hello"},
            )
        )
        assert result.success
        assert "hello" in result.output

    @pytest.mark.anyio
    async def test_no_matches_returns_success(self, registry, workspace: Path):
        (workspace / "code.py").write_text("nothing here\n")
        result = await registry.execute_tool(
            ToolCall(
                tool_name="search_codebase",
                call_id="10",
                params={"pattern": "zzzzz_nonexistent"},
            )
        )
        assert result.success

    @pytest.mark.anyio
    async def test_rejects_empty_pattern(self, registry):
        result = await registry.execute_tool(
            ToolCall(
                tool_name="search_codebase",
                call_id="11",
                params={"pattern": ""},
            )
        )
        assert not result.success

    @pytest.mark.anyio
    async def test_rejects_traversal_in_glob(self, registry):
        result = await registry.execute_tool(
            ToolCall(
                tool_name="search_codebase",
                call_id="12",
                params={"pattern": "test", "glob": "../../../etc/*"},
            )
        )
        assert not result.success


class TestSecurityControls:
    @pytest.mark.anyio
    async def test_search_flag_injection_prevented(self, registry, workspace: Path):
        """Pattern starting with '-' must not be interpreted as grep flag."""
        (workspace / "data.txt").write_text("safe content\n")
        result = await registry.execute_tool(
            ToolCall(
                tool_name="search_codebase",
                call_id="13",
                params={"pattern": "--include=*.env -r /etc"},
            )
        )
        # Should not contain /etc content — grep '--' separator prevents flag injection
        assert "/etc/passwd" not in (result.output or "")

    @pytest.mark.anyio
    async def test_symlink_outside_workspace_denied(self, registry, workspace: Path):
        link = workspace / "escape"
        try:
            link.symlink_to("/etc/hosts")
        except OSError:
            pytest.skip("Cannot create symlinks")
        result = await registry.execute_tool(
            ToolCall(
                tool_name="read_file",
                call_id="14",
                params={"path": "escape"},
            )
        )
        assert not result.success
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/core/runtime/test_builtin_tools.py -v`
Expected: FAIL (ImportError — module doesn't exist yet)

- [ ] **Step 3: Implement BuiltinToolRegistry**

```python
# miniautogen/core/runtime/builtin_tools.py
"""Builtin tools provided by the runtime (not the provider).

These tools give agents filesystem capabilities managed by the runtime
with sandbox enforcement, observability, and resource limits.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import anyio

from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.contracts.tool_registry import ToolCall, ToolDefinition
from miniautogen.core.runtime.agent_sandbox import AgentFilesystemSandbox

logger = logging.getLogger(__name__)

# Resource limits
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
                "path": {"type": "string", "description": "Relative path from workspace root", "default": "."},
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
        """Resolve path and check sandbox. Returns (resolved, error_or_None)."""
        resolved = (self._workspace_root / rel_path).resolve()
        if self._sandbox and not self._sandbox.can_read(resolved):
            return resolved, "Sandbox denied read access"
        if not resolved.is_relative_to(self._workspace_root):
            return resolved, "Path is outside workspace"
        return resolved, None

    async def _read_file(self, params: dict) -> ToolResult:
        path_str = params.get("path", "")
        offset = params.get("offset", 0)
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
                error=f"File too large ({stat.st_size} bytes). Use offset/limit params.",
            )

        content = await apath.read_text(errors="replace")
        lines = content.splitlines()
        selected = lines[offset : offset + limit] if limit else lines[offset:]
        numbered = [f"{i + offset + 1:>6}\t{line}" for i, line in enumerate(selected)]
        return ToolResult(success=True, output="\n".join(numbered))

    async def _search_codebase(self, params: dict) -> ToolResult:
        pattern = params.get("pattern", "")
        glob_filter = params.get("glob", "*")
        max_results = min(params.get("max_results", 50), MAX_SEARCH_RESULTS)

        if not pattern:
            return ToolResult(success=False, error="Pattern is required")
        if ".." in glob_filter or glob_filter.startswith("/"):
            return ToolResult(success=False, error="Invalid glob pattern")

        search_root = self._workspace_root
        if self._sandbox and not self._sandbox.can_read(search_root):
            return ToolResult(success=False, error="Sandbox denied access")

        cmd = [
            "grep", "-rn",
            "--max-count", str(max_results),
            "--include", glob_filter,
            "--",  # Prevents pattern from being interpreted as flag
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
            return ToolResult(success=True, output="\n".join(truncated) or "No matches found")
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/core/runtime/test_builtin_tools.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/core/runtime/builtin_tools.py tests/core/runtime/test_builtin_tools.py
git commit -m "feat(runtime): add BuiltinToolRegistry with read_file, search_codebase, list_directory"
```

---

### Task 2: CompositeToolRegistry

**Files:**
- Create: `miniautogen/core/runtime/composite_tool_registry.py`
- Create: `tests/core/runtime/test_composite_tool_registry.py`

**Context:** Chains multiple ToolRegistryProtocol implementations. First registry with a matching tool wins. Logs warnings when user tools shadow builtins.

- [ ] **Step 1: Write failing tests**

```python
# tests/core/runtime/test_composite_tool_registry.py
from __future__ import annotations

import pytest

from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.contracts.tool_registry import ToolCall, ToolDefinition


class FakeRegistry:
    def __init__(self, tools: dict[str, str]):
        self._tools = tools

    def list_tools(self) -> list[ToolDefinition]:
        return [ToolDefinition(name=n, description=d) for n, d in self._tools.items()]

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    async def execute_tool(self, call: ToolCall) -> ToolResult:
        if call.tool_name in self._tools:
            return ToolResult(success=True, output=f"from-{self._tools[call.tool_name]}")
        return ToolResult(success=False, error="not found")


@pytest.fixture
def composite():
    from miniautogen.core.runtime.composite_tool_registry import CompositeToolRegistry

    reg_a = FakeRegistry({"read_file": "user", "custom_tool": "user"})
    reg_b = FakeRegistry({"read_file": "builtin", "search_codebase": "builtin"})
    return CompositeToolRegistry([reg_a, reg_b])


class TestCompositeToolRegistry:
    def test_list_tools_deduplicates(self, composite):
        tools = composite.list_tools()
        names = [t.name for t in tools]
        assert names.count("read_file") == 1
        assert "custom_tool" in names
        assert "search_codebase" in names

    def test_has_tool_from_any_registry(self, composite):
        assert composite.has_tool("read_file")
        assert composite.has_tool("custom_tool")
        assert composite.has_tool("search_codebase")
        assert not composite.has_tool("nonexistent")

    @pytest.mark.anyio
    async def test_first_registry_wins(self, composite):
        result = await composite.execute_tool(
            ToolCall(tool_name="read_file", call_id="1", params={})
        )
        assert result.success
        assert result.output == "from-user"

    @pytest.mark.anyio
    async def test_falls_through_to_second(self, composite):
        result = await composite.execute_tool(
            ToolCall(tool_name="search_codebase", call_id="2", params={})
        )
        assert result.success
        assert result.output == "from-builtin"

    @pytest.mark.anyio
    async def test_unknown_tool_returns_error(self, composite):
        result = await composite.execute_tool(
            ToolCall(tool_name="nonexistent", call_id="3", params={})
        )
        assert not result.success

    def test_empty_registries(self):
        from miniautogen.core.runtime.composite_tool_registry import CompositeToolRegistry

        c = CompositeToolRegistry([])
        assert c.list_tools() == []
        assert not c.has_tool("anything")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/core/runtime/test_composite_tool_registry.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement CompositeToolRegistry**

```python
# miniautogen/core/runtime/composite_tool_registry.py
"""Composite tool registry that chains multiple registries."""
from __future__ import annotations

import logging
from collections.abc import Sequence

from miniautogen.core.contracts.tool import ToolResult
from miniautogen.core.contracts.tool_registry import (
    ToolCall,
    ToolDefinition,
    ToolRegistryProtocol,
)

logger = logging.getLogger(__name__)


class CompositeToolRegistry:
    """Chains multiple ToolRegistryProtocol implementations.

    First registry containing a tool wins (first-match precedence).
    Emits a warning when a later registry's tool is shadowed.
    """

    def __init__(self, registries: Sequence[ToolRegistryProtocol]) -> None:
        self._registries = list(registries)

    def list_tools(self) -> list[ToolDefinition]:
        tools: list[ToolDefinition] = []
        seen: set[str] = set()
        for reg in self._registries:
            for tool in reg.list_tools():
                if tool.name not in seen:
                    tools.append(tool)
                    seen.add(tool.name)
                else:
                    logger.warning("Tool '%s' shadowed by earlier registry", tool.name)
        return tools

    def has_tool(self, name: str) -> bool:
        return any(r.has_tool(name) for r in self._registries)

    async def execute_tool(self, call: ToolCall) -> ToolResult:
        for reg in self._registries:
            if reg.has_tool(call.tool_name):
                return await reg.execute_tool(call)
        return ToolResult(success=False, error=f"Unknown tool: {call.tool_name}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/core/runtime/test_composite_tool_registry.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/core/runtime/composite_tool_registry.py tests/core/runtime/test_composite_tool_registry.py
git commit -m "feat(runtime): add CompositeToolRegistry for chaining tool registries"
```

---

### Task 3: Refactor FileSystemToolRegistry

**Files:**
- Modify: `miniautogen/core/runtime/filesystem_tool_registry.py:38-61` (\_load) and `:86-92` (execute_tool)
- Modify: `tests/core/runtime/test_filesystem_tool_registry.py` (update expectations)

**Context:** Remove the `if cfg.get("builtin")` hack from `execute_tool()` and skip `builtin: true` tools in `_load()`. Builtin tools are now handled by BuiltinToolRegistry via CompositeToolRegistry.

- [ ] **Step 1: Write test that builtin tools are skipped**

```python
# Add to tests/core/runtime/test_filesystem_tool_registry.py

class TestBuiltinSkip:
    def test_builtin_tools_not_loaded(self, tmp_path: Path):
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
        from miniautogen.core.runtime.filesystem_tool_registry import FileSystemToolRegistry

        reg = FileSystemToolRegistry(tools_yml, tmp_path)
        assert not reg.has_tool("read_file")  # Skipped
        assert reg.has_tool("my_script")  # Loaded
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/runtime/test_filesystem_tool_registry.py::TestBuiltinSkip -v`
Expected: FAIL (read_file IS currently loaded, returns "not yet implemented")

- [ ] **Step 3: Modify FileSystemToolRegistry**

In `miniautogen/core/runtime/filesystem_tool_registry.py`:

**In `_load()`, after `if not name: continue`, add:**
```python
if tool_cfg.get("builtin"):
    continue  # Handled by BuiltinToolRegistry
```

**In `execute_tool()`, remove lines 88-92:**
```python
# DELETE THIS BLOCK:
if cfg.get("builtin"):
    return ToolResult(
        success=False,
        error=f"Builtin tool '{call.tool_name}' not yet implemented",
    )
```

- [ ] **Step 4: Run all filesystem tool registry tests**

Run: `python -m pytest tests/core/runtime/test_filesystem_tool_registry.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/core/runtime/filesystem_tool_registry.py tests/core/runtime/test_filesystem_tool_registry.py
git commit -m "refactor(runtime): remove builtin hack from FileSystemToolRegistry"
```

---

### Task 4: FlowConfig Schema Update

**Files:**
- Modify: `miniautogen/cli/config.py` (FlowConfig class)
- Create: `tests/cli/test_flow_config_schema.py`

**Context:** FlowConfig currently only has `target: str`. Extend it with optional `mode`, `participants`, and mode-specific fields while keeping backward compat.

- [ ] **Step 1: Write failing tests**

```python
# tests/cli/test_flow_config_schema.py
from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestFlowConfigSchema:
    def test_target_only_valid(self):
        from miniautogen.cli.config import FlowConfig

        fc = FlowConfig(target="pipelines.main:run")
        assert fc.target == "pipelines.main:run"
        assert fc.mode is None

    def test_mode_and_participants_valid(self):
        from miniautogen.cli.config import FlowConfig

        fc = FlowConfig(mode="workflow", participants=["agent1", "agent2"])
        assert fc.mode == "workflow"
        assert fc.participants == ["agent1", "agent2"]
        assert fc.target is None

    def test_neither_target_nor_mode_invalid(self):
        from miniautogen.cli.config import FlowConfig

        with pytest.raises(ValidationError, match="target.*mode"):
            FlowConfig()

    def test_mode_without_participants_invalid(self):
        from miniautogen.cli.config import FlowConfig

        with pytest.raises(ValidationError, match="participants"):
            FlowConfig(mode="workflow")

    def test_deliberation_requires_leader(self):
        from miniautogen.cli.config import FlowConfig

        with pytest.raises(ValidationError, match="leader"):
            FlowConfig(mode="deliberation", participants=["a", "b"])

    def test_deliberation_with_leader_valid(self):
        from miniautogen.cli.config import FlowConfig

        fc = FlowConfig(
            mode="deliberation",
            participants=["researcher", "reviewer"],
            leader="reviewer",
            max_rounds=5,
        )
        assert fc.leader == "reviewer"
        assert fc.max_rounds == 5

    def test_loop_requires_router(self):
        from miniautogen.cli.config import FlowConfig

        with pytest.raises(ValidationError, match="router"):
            FlowConfig(mode="loop", participants=["a", "b"])

    def test_loop_with_router_valid(self):
        from miniautogen.cli.config import FlowConfig

        fc = FlowConfig(
            mode="loop",
            participants=["agent1", "agent2"],
            router="agent1",
            max_turns=10,
        )
        assert fc.router == "agent1"
        assert fc.max_turns == 10

    def test_backward_compat_alias(self):
        from miniautogen.cli.config import PipelineConfig

        pc = PipelineConfig(target="main:run")
        assert pc.target == "main:run"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/cli/test_flow_config_schema.py -v`
Expected: FAIL (FlowConfig doesn't accept mode/participants)

- [ ] **Step 3: Update FlowConfig in config.py**

In `miniautogen/cli/config.py`, replace the FlowConfig class:

```python
class FlowConfig(BaseModel):
    """Flow configuration — supports both callable and config-driven modes.

    DA-9: Renamed from PipelineConfig.

    Two execution paths:
    - Callable: set ``target`` to a Python module:callable reference
    - Config-driven: set ``mode`` + ``participants`` for YAML-only flows
    """

    target: str | None = None
    mode: str | None = None  # workflow | deliberation | loop | composite
    participants: list[str] = Field(default_factory=list)
    input_text: str | None = None

    # Mode-specific options
    leader: str | None = None  # deliberation
    max_rounds: int = 3  # deliberation
    max_turns: int = 20  # agentic loop
    router: str | None = None  # agentic loop
    chain_flows: list[str] = Field(default_factory=list)  # composite

    @model_validator(mode="after")
    def validate_flow_config(self) -> FlowConfig:
        if not self.target and not self.mode:
            raise ValueError("Flow must have either 'target' or 'mode'")
        if self.mode and not self.participants:
            raise ValueError("Config-driven flow requires 'participants'")
        if self.mode == "deliberation" and not self.leader:
            raise ValueError("Deliberation mode requires 'leader'")
        if self.mode == "loop" and not self.router:
            raise ValueError("Loop mode requires 'router'")
        return self
```

Ensure `model_validator` is imported from pydantic at the top of the file.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/cli/test_flow_config_schema.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run existing CLI tests to check no regressions**

Run: `python -m pytest tests/cli/ -v --timeout=60`
Expected: ALL PASS (488 tests)

- [ ] **Step 6: Commit**

```bash
git add miniautogen/cli/config.py tests/cli/test_flow_config_schema.py
git commit -m "feat(cli): extend FlowConfig with mode, participants, and mode-specific fields"
```

---

### Task 5: load_agent_specs()

**Files:**
- Modify: `miniautogen/cli/services/agent_ops.py`
- Create: `tests/cli/services/test_load_agent_specs.py`

**Context:** New function that discovers agent YAML files from `agents/` dir and parses them into `dict[str, AgentSpec]`.

- [ ] **Step 1: Write failing tests**

```python
# tests/cli/services/test_load_agent_specs.py
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    agents_dir = root / "agents"
    agents_dir.mkdir()
    (agents_dir / "researcher.yaml").write_text(
        yaml.dump({
            "role": "Research assistant",
            "goal": "Find information",
            "engine_profile": "default",
        })
    )
    (agents_dir / "writer.yaml").write_text(
        yaml.dump({
            "role": "Content writer",
            "goal": "Write content",
            "engine_profile": "default",
        })
    )
    return root


class TestLoadAgentSpecs:
    def test_loads_agents_from_yaml(self, project: Path):
        from miniautogen.cli.services.agent_ops import load_agent_specs

        specs = load_agent_specs(project)
        assert "researcher" in specs
        assert "writer" in specs
        assert specs["researcher"].role == "Research assistant"

    def test_empty_agents_dir(self, tmp_path: Path):
        from miniautogen.cli.services.agent_ops import load_agent_specs

        root = tmp_path / "empty"
        root.mkdir()
        (root / "agents").mkdir()
        specs = load_agent_specs(root)
        assert specs == {}

    def test_no_agents_dir(self, tmp_path: Path):
        from miniautogen.cli.services.agent_ops import load_agent_specs

        root = tmp_path / "noagents"
        root.mkdir()
        specs = load_agent_specs(root)
        assert specs == {}

    def test_agent_name_from_filename(self, project: Path):
        from miniautogen.cli.services.agent_ops import load_agent_specs

        specs = load_agent_specs(project)
        for name, spec in specs.items():
            assert spec.id == name
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/cli/services/test_load_agent_specs.py -v`
Expected: FAIL (load_agent_specs doesn't exist)

- [ ] **Step 3: Implement load_agent_specs**

Add to the end of `miniautogen/cli/services/agent_ops.py`:

```python
def load_agent_specs(project_root: Path) -> dict[str, AgentSpec]:
    """Discover and parse agent definitions from workspace.

    Loads agent specs from ``agents/*.yaml`` in the project root.
    Each YAML file's stem becomes the agent name/id.

    Returns:
        Mapping of agent_name -> AgentSpec.
    """
    from miniautogen.core.contracts.agent_spec import AgentSpec

    specs: dict[str, AgentSpec] = {}
    agents_dir = project_root / "agents"
    if not agents_dir.is_dir():
        return specs

    for yaml_file in sorted(agents_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text()) or {}
            name = yaml_file.stem
            data.setdefault("id", name)
            specs[name] = AgentSpec(**data)
        except Exception:
            logger.exception("Failed to load agent spec from %s", yaml_file)

    return specs
```

Ensure `yaml` and `logger` are already imported (they should be).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/cli/services/test_load_agent_specs.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/cli/services/agent_ops.py tests/cli/services/test_load_agent_specs.py
git commit -m "feat(cli): add load_agent_specs() for agent YAML discovery"
```

---

### Task 6: PipelineRunner Factory Update (async + real implementations)

**Files:**
- Modify: `miniautogen/core/runtime/pipeline_runner.py:56-153` (_build_agent_runtimes)
- Modify: `tests/core/runtime/test_pipeline_runner_agent_runtime.py` (update for async)

**Context:** Convert `_build_agent_runtimes()` to `async def`. Replace InMemoryToolRegistry with CompositeToolRegistry(FileSystem + Builtin). Replace InMemoryMemoryProvider with PersistentMemoryProvider. Load prompt.md async. Use real sandbox. Receive run_id parameter.

- [ ] **Step 1: Write test for updated factory**

```python
# Add to tests/core/runtime/test_pipeline_runner_agent_runtime.py

@pytest.mark.anyio
async def test_build_agent_runtimes_uses_composite_registry(tmp_path: Path):
    """Factory should use CompositeToolRegistry, not InMemoryToolRegistry."""
    from miniautogen.core.runtime.pipeline_runner import PipelineRunner
    from miniautogen.core.runtime.composite_tool_registry import CompositeToolRegistry

    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".miniautogen" / "agents" / "test-agent").mkdir(parents=True)
    (workspace / "agents").mkdir()

    runner = PipelineRunner()
    spec = AgentSpec(id="test-agent", role="test", goal="test", engine_profile="default")

    # This will fail at driver creation without a real engine, but we can
    # test the structure by mocking the resolver
    # ... (mock-based test depending on exact signature)
```

- [ ] **Step 2: Update _build_agent_runtimes to async with real implementations**

Replace `_build_agent_runtimes` in `miniautogen/core/runtime/pipeline_runner.py`. Key changes:
1. `def` → `async def`
2. `InMemoryToolRegistry()` → `CompositeToolRegistry([FileSystemToolRegistry(...), BuiltinToolRegistry(...)])`
3. `InMemoryMemoryProvider()` → `PersistentMemoryProvider(config_dir / "memory")`
4. Add sandbox creation: `AgentFilesystemSandbox(agent_name, workspace)`
5. Load prompt.md async: `await anyio.Path(...).read_text()`
6. Add `run_id: str` parameter, use real RunContext
7. Extract `_build_prompt_from_spec()` helper

See spec section 3.2 for the complete implementation.

- [ ] **Step 3: Run existing pipeline runner tests**

Run: `python -m pytest tests/core/runtime/test_pipeline_runner_agent_runtime.py -v`
Expected: ALL PASS (or update tests for async change)

- [ ] **Step 4: Commit**

```bash
git add miniautogen/core/runtime/pipeline_runner.py tests/core/runtime/test_pipeline_runner_agent_runtime.py
git commit -m "feat(runtime): upgrade _build_agent_runtimes to async with real tool/memory/sandbox"
```

---

### Task 7: _build_coordination_from_config()

**Files:**
- Modify: `miniautogen/core/runtime/pipeline_runner.py` (add function)
- Create: `tests/core/runtime/test_config_driven_flow.py`

**Context:** Factory function that maps FlowConfig to (plan, runtime) tuples. Uses actual coordination runtime constructors: `WorkflowRuntime(runner, agent_registry)`, `DeliberationRuntime(runner, agent_registry)`, `AgenticLoopRuntime(runner, agent_registry)`. Plans use actual model fields: WorkflowPlan(steps), DeliberationPlan(topic, participants, leader_agent, max_rounds), AgenticLoopPlan(router_agent, participants, initial_message).

- [ ] **Step 1: Write failing tests**

```python
# tests/core/runtime/test_config_driven_flow.py
from __future__ import annotations

import pytest

from miniautogen.cli.config import FlowConfig


class TestBuildCoordinationFromConfig:
    def test_workflow_mode(self):
        from miniautogen.core.runtime.pipeline_runner import _build_coordination_from_config

        flow = FlowConfig(mode="workflow", participants=["a1", "a2"])
        # Mock runtimes as simple objects with agent_id
        runtimes = {"a1": "fake_rt_a1", "a2": "fake_rt_a2"}

        plan, runtime = _build_coordination_from_config(
            flow_config=flow,
            runtimes=runtimes,
            runner=None,  # Will be mocked
            pipeline_input="Do the task",
        )
        assert len(plan.steps) == 2

    def test_deliberation_mode(self):
        from miniautogen.core.runtime.pipeline_runner import _build_coordination_from_config

        flow = FlowConfig(
            mode="deliberation",
            participants=["researcher", "reviewer"],
            leader="reviewer",
            max_rounds=5,
        )
        runtimes = {"researcher": "fake", "reviewer": "fake"}

        plan, runtime = _build_coordination_from_config(
            flow_config=flow,
            runtimes=runtimes,
            runner=None,
            pipeline_input="Review the code",
        )
        assert plan.topic == "Review the code"
        assert plan.max_rounds == 5
        assert plan.leader_agent == "reviewer"

    def test_loop_mode(self):
        from miniautogen.core.runtime.pipeline_runner import _build_coordination_from_config

        flow = FlowConfig(
            mode="loop",
            participants=["agent1", "agent2"],
            router="agent1",
            max_turns=10,
        )
        runtimes = {"agent1": "fake", "agent2": "fake"}

        plan, runtime = _build_coordination_from_config(
            flow_config=flow,
            runtimes=runtimes,
            runner=None,
            pipeline_input="Start working",
        )
        assert plan.router_agent == "agent1"
        assert plan.initial_message == "Start working"

    def test_unknown_mode_raises(self):
        from miniautogen.core.runtime.pipeline_runner import _build_coordination_from_config

        flow = FlowConfig(target="dummy")  # bypass validation
        flow.mode = "unknown"
        flow.participants = ["a"]

        with pytest.raises(Exception, match="Unknown flow mode"):
            _build_coordination_from_config(
                flow_config=flow,
                runtimes={"a": "fake"},
                runner=None,
                pipeline_input=None,
            )

    def test_missing_participant_raises(self):
        from miniautogen.core.runtime.pipeline_runner import _build_coordination_from_config

        flow = FlowConfig(mode="workflow", participants=["missing_agent"])

        with pytest.raises(KeyError):
            _build_coordination_from_config(
                flow_config=flow,
                runtimes={},
                runner=None,
                pipeline_input=None,
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/core/runtime/test_config_driven_flow.py -v`
Expected: FAIL (function doesn't exist)

- [ ] **Step 3: Implement _build_coordination_from_config**

Add to `miniautogen/core/runtime/pipeline_runner.py`:

```python
def _build_coordination_from_config(
    *,
    flow_config: FlowConfig,
    runtimes: dict[str, Any],
    runner: PipelineRunner | None,
    pipeline_input: str | None = None,
) -> tuple[Any, Any]:
    """Build a coordination plan and runtime from FlowConfig."""
    mode = flow_config.mode
    participant_runtimes = {name: runtimes[name] for name in flow_config.participants}

    if mode == "workflow":
        from miniautogen.core.contracts.coordination import WorkflowPlan, WorkflowStep

        steps = [
            WorkflowStep(
                component_name=name,
                agent_id=name,
                config={"task": pipeline_input or f"Execute as {name}"},
            )
            for name in flow_config.participants
        ]
        plan = WorkflowPlan(steps=steps)

        from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime

        runtime = WorkflowRuntime(runner=runner, agent_registry=participant_runtimes)
        return plan, runtime

    elif mode == "deliberation":
        from miniautogen.core.contracts.coordination import DeliberationPlan

        plan = DeliberationPlan(
            topic=pipeline_input or "Deliberate on the given task",
            participants=flow_config.participants,
            max_rounds=flow_config.max_rounds,
            leader_agent=flow_config.leader,
        )

        from miniautogen.core.runtime.deliberation_runtime import DeliberationRuntime

        runtime = DeliberationRuntime(runner=runner, agent_registry=participant_runtimes)
        return plan, runtime

    elif mode == "loop":
        from miniautogen.core.contracts.coordination import AgenticLoopPlan

        plan = AgenticLoopPlan(
            router_agent=flow_config.router,
            participants=flow_config.participants,
            initial_message=pipeline_input or "Begin the task",
        )

        from miniautogen.core.runtime.agentic_loop_runtime import AgenticLoopRuntime

        runtime = AgenticLoopRuntime(runner=runner, agent_registry=participant_runtimes)
        return plan, runtime

    elif mode == "composite":
        raise NotImplementedError(
            "Composite config-driven flows require sub-flow resolution — use target callable"
        )
    else:
        from miniautogen.cli.errors import ConfigurationError

        raise ConfigurationError(
            f"Unknown flow mode: {mode}. Valid: workflow, deliberation, loop, composite"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/core/runtime/test_config_driven_flow.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add miniautogen/core/runtime/pipeline_runner.py tests/core/runtime/test_config_driven_flow.py
git commit -m "feat(runtime): add _build_coordination_from_config plan factory"
```

---

### Task 8: PipelineRunner.run_from_config()

**Files:**
- Modify: `miniautogen/core/runtime/pipeline_runner.py` (add run_from_config method)
- Modify: `tests/core/runtime/test_config_driven_flow.py` (add integration test)

**Context:** New public method on PipelineRunner. Builds AgentRuntimes, initializes them, creates coordination runtime from config, executes, emits events, and closes runtimes in finally block.

- [ ] **Step 1: Add run_from_config method**

Add to PipelineRunner class in `pipeline_runner.py`:

```python
async def run_from_config(
    self,
    *,
    flow_config: FlowConfig,
    agent_specs: dict[str, AgentSpec],
    workspace: Path,
    config: WorkspaceConfig,
    pipeline_input: str | None = None,
    run_id: str | None = None,
) -> Any:
    """Execute a flow defined entirely in YAML config.

    Config-driven execution path: when FlowConfig has mode + participants
    (instead of target), this method builds AgentRuntimes and creates
    the coordination runtime from config.
    """
    from miniautogen.core.contracts.run_context import RunContext

    run_id = run_id or str(uuid4())
    self.last_run_id = run_id

    # Validate participants exist
    for name in flow_config.participants:
        if name not in agent_specs:
            from miniautogen.cli.errors import ConfigurationError

            raise ConfigurationError(
                f"Flow participant '{name}' not found in agent specs. "
                f"Available: {list(agent_specs.keys())}"
            )

    # Build agent runtimes
    runtimes = await self._build_agent_runtimes(
        agent_specs=agent_specs,
        workspace=workspace,
        config=config,
        run_id=run_id,
    )

    try:
        # Initialize all runtimes
        for rt in runtimes.values():
            await rt.initialize()

        # Build coordination plan and runtime
        plan, coordination_runtime = _build_coordination_from_config(
            flow_config=flow_config,
            runtimes=runtimes,
            runner=self,
            pipeline_input=pipeline_input,
        )

        # Emit run_started
        await self.event_sink.emit(ExecutionEvent(
            event_type=EventType.RUN_STARTED,
            run_id=run_id,
            timestamp=datetime.now(timezone.utc),
            payload={"mode": flow_config.mode, "participants": flow_config.participants},
        ))

        # Build RunContext
        context = RunContext(
            run_id=run_id,
            started_at=datetime.now(timezone.utc),
            correlation_id=run_id,
        )

        # Execute
        agents_list = [runtimes[name] for name in flow_config.participants]
        result = await coordination_runtime.run(agents_list, context, plan)

        # Emit run_completed
        await self.event_sink.emit(ExecutionEvent(
            event_type=EventType.RUN_COMPLETED,
            run_id=run_id,
            timestamp=datetime.now(timezone.utc),
            payload={"status": "completed"},
        ))

        return result

    except Exception as exc:
        await self.event_sink.emit(ExecutionEvent(
            event_type=EventType.RUN_FAILED,
            run_id=run_id,
            timestamp=datetime.now(timezone.utc),
            payload={"error": str(exc)},
        ))
        raise
    finally:
        for rt in runtimes.values():
            await rt.close()
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/core/runtime/test_config_driven_flow.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add miniautogen/core/runtime/pipeline_runner.py
git commit -m "feat(runtime): add PipelineRunner.run_from_config for config-driven flows"
```

---

### Task 9: Wire run_pipeline.py

**Files:**
- Modify: `miniautogen/cli/services/run_pipeline.py`

**Context:** Add the config-driven branch to `execute_pipeline()`. When flow has no `target` but has `mode`, use `runner.run_from_config()`.

- [ ] **Step 1: Read current run_pipeline.py**

Read `miniautogen/cli/services/run_pipeline.py` to understand the exact current structure before modifying.

- [ ] **Step 2: Add config-driven branch**

In `execute_pipeline()`, after the flow is loaded and before the existing target resolution, add:

```python
# Config-driven path — flow has mode + participants, no target callable
if not flow.target and flow.mode:
    from miniautogen.cli.services.agent_ops import load_agent_specs

    agent_specs = load_agent_specs(root)
    result = await runner.run_from_config(
        flow_config=flow,
        agent_specs=agent_specs,
        workspace=root,
        config=config,
        pipeline_input=pipeline_input,
    )
    return {"run_id": runner.last_run_id, "status": "completed", "result": result}
```

The existing callable path remains unchanged below.

- [ ] **Step 3: Run existing run pipeline tests**

Run: `python -m pytest tests/cli/services/test_run_pipeline.py -v`
Expected: ALL PASS (no regressions)

- [ ] **Step 4: Commit**

```bash
git add miniautogen/cli/services/run_pipeline.py
git commit -m "feat(cli): wire config-driven flow execution in run_pipeline"
```

---

### Task 10: Update API Exports

**Files:**
- Modify: `miniautogen/api.py`

**Context:** Export new public symbols.

- [ ] **Step 1: Add exports**

Add to `miniautogen/api.py`:

```python
from miniautogen.core.runtime.builtin_tools import BuiltinToolRegistry
from miniautogen.core.runtime.composite_tool_registry import CompositeToolRegistry
```

- [ ] **Step 2: Verify imports work**

Run: `python -c "from miniautogen.api import BuiltinToolRegistry, CompositeToolRegistry; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add miniautogen/api.py
git commit -m "chore(runtime): export BuiltinToolRegistry and CompositeToolRegistry in api.py"
```

---

### Task 11: Full Regression Test

**Files:** None (test-only)

**Context:** Run the full test suite to verify zero regressions.

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v --timeout=120`
Expected: ALL PASS

- [ ] **Step 2: If any failures, fix and re-run**

Debug and fix any regressions introduced by the changes.

- [ ] **Step 3: Final commit if fixes needed**

```bash
git commit -m "fix(runtime): resolve regression from end-to-end wiring"
```

---

## Summary

| Task | Component | Files | Depends On |
|------|-----------|-------|------------|
| 1 | BuiltinToolRegistry | 2 new | — |
| 2 | CompositeToolRegistry | 2 new | Task 1 |
| 3 | FileSystemToolRegistry refactor | 2 modified | Task 2 |
| 4 | FlowConfig schema | 2 files | — |
| 5 | load_agent_specs | 2 files | — |
| 6 | PipelineRunner factory (async) | 2 modified | Tasks 1-3 |
| 7 | _build_coordination_from_config | 2 files | Task 4 |
| 8 | run_from_config() | 1 modified | Tasks 6-7 |
| 9 | run_pipeline.py wiring | 1 modified | Tasks 5, 8 |
| 10 | API exports | 1 modified | Tasks 1-2 |
| 11 | Full regression test | 0 | All |

**Parallelizable:** Tasks 1-3 (tools), Tasks 4-5 (config/specs) can run in parallel. Tasks 6+ are sequential.
