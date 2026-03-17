# Milestone 2 — Chunk 2: check Command

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Implement `miniautogen check` that validates multi-entity projects: agent specs, skill directories, tool specs, MCP bindings, pipeline targets, engine profile references, cross-references, and environment variables.

**Architecture:** Two-layer design per D5. `services/check_project.py` contains all validation logic (Click-free). `commands/check.py` is a thin Click adapter. New `models.py` holds CLI-only Pydantic validation models for AgentSpec, SkillSpec, ToolSpec, McpBinding — these are NOT SDK contracts, they are YAML schema validators for the CLI layer only. Services import only stdlib + `miniautogen.cli.config` (for ProjectConfig) + `miniautogen.cli.models` (for validation models). No imports from `miniautogen.api` or internal modules.

**Tech Stack:** Python 3.10+, Click 8+, PyYAML 6+, Pydantic v2, pytest 7+, ruff (line-length=100)

**Global Prerequisites:**
- Environment: macOS, Python 3.10 or 3.11
- Tools: `python --version`, `pytest --version`, `ruff --version`
- Access: No API keys needed (all checks are local)
- State: Work from `main` branch. Chunk 1 (CLI foundation) must be complete: `miniautogen/cli/main.py`, `miniautogen/cli/config.py`, `miniautogen/cli/errors.py`, `miniautogen/cli/output.py`, `miniautogen/cli/commands/__init__.py`, and the `init` command must exist.

**Verification before starting:**
```bash
cd /Users/brunocapelao/Projects/miniAutoGen
python --version        # Expected: Python 3.10.x or 3.11.x
pytest --version        # Expected: pytest 7.x
ruff --version          # Expected: ruff 0.15+
git status              # Expected: clean working tree (untracked docs ok)
python -c "from miniautogen.cli.main import cli; print('CLI group OK')"
python -c "from miniautogen.cli.config import ProjectConfig, load_config, find_project_root; print('Config OK')"
python -c "from miniautogen.cli.errors import CLIError; print('Errors OK')"
python -c "from miniautogen.cli.output import echo_table, echo_json; print('Output OK')"
```

**Chunk 1 models assumed available (from `miniautogen/cli/config.py`):**
```python
class ProjectMeta(BaseModel):
    name: str
    version: str = "0.1.0"

class DefaultsConfig(BaseModel):
    engine_profile: str
    memory_profile: str = "default"

class EngineProfileConfig(BaseModel):
    kind: Literal["api", "cli"]
    provider: str
    model: str | None = None
    command: str | None = None
    temperature: float = 0.2

class PipelineConfig(BaseModel):
    target: str

class DatabaseConfig(BaseModel):
    url: str

class ProjectConfig(BaseModel):
    project: ProjectMeta
    defaults: DefaultsConfig
    engine_profiles: dict[str, EngineProfileConfig]
    memory_profiles: dict[str, dict[str, Any]] = {}
    pipelines: dict[str, PipelineConfig]
    database: DatabaseConfig | None = None

def find_project_root(start: Path | None = None) -> Path | None: ...
def load_config(path: Path) -> ProjectConfig: ...
```

---

## Task 1: Create CLI validation models (`miniautogen/cli/models.py`)

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/models.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_models.py`

**Prerequisites:**
- Chunk 1 complete (cli package exists)
- `pydantic>=2.5.0` installed

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_models.py`:

```python
"""Tests for CLI validation models — AgentSpec, SkillSpec, ToolSpec, McpBinding."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestAgentSpecValidator:
    def test_minimal_agent(self) -> None:
        from miniautogen.cli.models import AgentSpecValidator

        agent = AgentSpecValidator(
            id="researcher",
            version="1.0",
            name="Researcher",
            role="Research assistant",
            goal="Find relevant information",
        )
        assert agent.id == "researcher"
        assert agent.version == "1.0"
        assert agent.name == "Researcher"
        assert agent.role == "Research assistant"
        assert agent.goal == "Find relevant information"
        assert agent.skills == {}
        assert agent.tool_access is None
        assert agent.mcp_access is None
        assert agent.engine_profile is None
        assert agent.runtime is None
        assert agent.permissions is None

    def test_full_agent(self) -> None:
        from miniautogen.cli.models import AgentSpecValidator

        agent = AgentSpecValidator(
            id="planner",
            version="1.0",
            name="Planner",
            role="Planning agent",
            goal="Create plans",
            skills={
                "deep-research": {"attached": ["plan_template"]},
            },
            tool_access={
                "mode": "allowlist",
                "allow": ["web_search", "file_read"],
            },
            mcp_access=["github"],
            engine_profile="gemini_api",
            runtime={"max_turns": 10},
            permissions={"file_write": False},
        )
        assert agent.skills == {"deep-research": {"attached": ["plan_template"]}}
        assert agent.tool_access["mode"] == "allowlist"
        assert agent.tool_access["allow"] == ["web_search", "file_read"]
        assert agent.mcp_access == ["github"]
        assert agent.engine_profile == "gemini_api"
        assert agent.runtime == {"max_turns": 10}
        assert agent.permissions == {"file_write": False}

    def test_missing_required_field_raises(self) -> None:
        from miniautogen.cli.models import AgentSpecValidator

        with pytest.raises(ValidationError) as exc_info:
            AgentSpecValidator(
                id="bad",
                version="1.0",
                name="Bad",
                # missing: role, goal
            )
        errors = exc_info.value.errors()
        field_names = {e["loc"][0] for e in errors}
        assert "role" in field_names
        assert "goal" in field_names


class TestSkillSpecValidator:
    def test_valid_skill(self) -> None:
        from miniautogen.cli.models import SkillSpecValidator

        skill = SkillSpecValidator(
            id="deep-research",
            version="1.0",
            name="Deep Research",
            description="Performs deep research on a topic",
        )
        assert skill.id == "deep-research"
        assert skill.name == "Deep Research"

    def test_missing_required_field_raises(self) -> None:
        from miniautogen.cli.models import SkillSpecValidator

        with pytest.raises(ValidationError):
            SkillSpecValidator(id="bad", version="1.0")


class TestToolSpecValidator:
    def test_valid_tool(self) -> None:
        from miniautogen.cli.models import ToolSpecValidator

        tool = ToolSpecValidator(
            name="web_search",
            description="Search the web",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            execution={"kind": "function", "target": "tools.search:run"},
        )
        assert tool.name == "web_search"
        assert tool.input_schema["type"] == "object"
        assert tool.execution["kind"] == "function"

    def test_optional_policy(self) -> None:
        from miniautogen.cli.models import ToolSpecValidator

        tool = ToolSpecValidator(
            name="read_file",
            description="Read a file",
            input_schema={"type": "object"},
            execution={"kind": "function", "target": "tools.fs:read"},
            policy={"max_calls": 10, "timeout": 30},
        )
        assert tool.policy == {"max_calls": 10, "timeout": 30}

    def test_missing_required_field_raises(self) -> None:
        from miniautogen.cli.models import ToolSpecValidator

        with pytest.raises(ValidationError):
            ToolSpecValidator(name="bad")


class TestMcpBindingValidator:
    def test_valid_binding(self) -> None:
        from miniautogen.cli.models import McpBindingValidator

        binding = McpBindingValidator(
            id="github",
            transport="stdio",
            command="npx @modelcontextprotocol/server-github",
            env={"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
            expose=["search_repos", "get_file"],
        )
        assert binding.id == "github"
        assert binding.transport == "stdio"
        assert binding.command is not None
        assert binding.env == {"GITHUB_TOKEN": "${GITHUB_TOKEN}"}
        assert binding.expose == ["search_repos", "get_file"]

    def test_minimal_binding(self) -> None:
        from miniautogen.cli.models import McpBindingValidator

        binding = McpBindingValidator(
            id="local-server",
            transport="sse",
        )
        assert binding.id == "local-server"
        assert binding.transport == "sse"
        assert binding.command is None
        assert binding.env is None
        assert binding.expose is None
        assert binding.policy is None

    def test_missing_required_field_raises(self) -> None:
        from miniautogen.cli.models import McpBindingValidator

        with pytest.raises(ValidationError):
            McpBindingValidator(id="bad")
```

**Step 2: Run the test to verify it fails**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/test_models.py -v --no-header 2>&1 | head -20
```

**Expected output:**
```
FAILED ... - ModuleNotFoundError: No module named 'miniautogen.cli.models'
```

**Step 3: Write minimal implementation**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/models.py`:

```python
"""CLI validation models for YAML entity schemas.

These are VALIDATION-ONLY Pydantic models used by the ``check`` command
to validate agent, skill, tool, and MCP binding YAML files.

They are NOT SDK contracts — the SDK uses its own protocols and types.
These models enforce the declarative YAML schema conventions for the CLI.

Import boundary: only stdlib and pydantic allowed.
"""

from __future__ import annotations

from pydantic import BaseModel


class AgentSpecValidator(BaseModel):
    """Validates an agent YAML file (``agents/*.yaml``)."""

    id: str
    version: str
    name: str
    role: str
    goal: str
    skills: dict[str, dict] = {}
    tool_access: dict | None = None
    mcp_access: list[str] | None = None
    engine_profile: str | None = None
    memory: dict | None = None
    runtime: dict | None = None
    permissions: dict | None = None


class SkillSpecValidator(BaseModel):
    """Validates a skill YAML file (``skills/*/skill.yaml``)."""

    id: str
    version: str
    name: str
    description: str


class ToolSpecValidator(BaseModel):
    """Validates a tool YAML file (``tools/*.yaml``)."""

    name: str
    description: str
    input_schema: dict
    execution: dict
    policy: dict | None = None


class McpBindingValidator(BaseModel):
    """Validates an MCP binding YAML file (``mcp/*.yaml``)."""

    id: str
    transport: str
    command: str | None = None
    env: dict[str, str] | None = None
    expose: list[str] | None = None
    policy: dict | None = None
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/test_models.py -v --no-header 2>&1 | tail -20
```

**Expected output:**
```
tests/cli/test_models.py::TestAgentSpecValidator::test_minimal_agent PASSED
tests/cli/test_models.py::TestAgentSpecValidator::test_full_agent PASSED
tests/cli/test_models.py::TestAgentSpecValidator::test_missing_required_field_raises PASSED
tests/cli/test_models.py::TestSkillSpecValidator::test_valid_skill PASSED
tests/cli/test_models.py::TestSkillSpecValidator::test_missing_required_field_raises PASSED
tests/cli/test_models.py::TestToolSpecValidator::test_valid_tool PASSED
tests/cli/test_models.py::TestToolSpecValidator::test_optional_policy PASSED
tests/cli/test_models.py::TestToolSpecValidator::test_missing_required_field_raises PASSED
tests/cli/test_models.py::TestMcpBindingValidator::test_valid_binding PASSED
tests/cli/test_models.py::TestMcpBindingValidator::test_minimal_binding PASSED
tests/cli/test_models.py::TestMcpBindingValidator::test_missing_required_field_raises PASSED

11 passed
```

**Step 5: Lint check**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/cli/models.py tests/cli/test_models.py
```

**Expected output:** No issues.

**Step 6: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/models.py tests/cli/test_models.py
git commit -m "feat(cli): add CLI validation models for agent, skill, tool, MCP specs"
```

**If Task Fails:**
1. **Pydantic import error:** Verify `pydantic>=2.5.0` is installed: `python -c "import pydantic; print(pydantic.__version__)"`.
2. **Validation test unexpected:** Check that required fields in each model match the test data exactly.
3. **Rollback:** `git checkout -- miniautogen/cli/models.py tests/cli/test_models.py`

---

## Task 2: Create `CheckResult` dataclass and `check_project` skeleton

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`

**Prerequisites:**
- Task 1 complete (models.py exists)
- Directory must exist: `miniautogen/cli/services/` (created in Chunk 1)
- File must exist: `miniautogen/cli/services/__init__.py` (created in Chunk 1)
- File must exist: `miniautogen/cli/config.py` with `ProjectConfig` model

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/__init__.py` (empty file for test package):

```python
```

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`:

```python
"""Tests for check_project service — CheckResult model and check_project signature."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from miniautogen.cli.services.check_project import CheckResult, check_project


class TestCheckResult:
    def test_static_check_result(self) -> None:
        result = CheckResult(
            name="config_valid",
            passed=True,
            message="Configuration is valid",
            category="static",
        )
        assert result.name == "config_valid"
        assert result.passed is True
        assert result.message == "Configuration is valid"
        assert result.category == "static"

    def test_environment_check_result(self) -> None:
        result = CheckResult(
            name="env_vars_present",
            passed=False,
            message="Missing OPENAI_API_KEY",
            category="environment",
        )
        assert result.passed is False
        assert result.category == "environment"

    def test_category_must_be_static_or_environment(self) -> None:
        result = CheckResult(
            name="test", passed=True, message="ok", category="static"
        )
        assert result.category in ("static", "environment")


def _write_minimal_config(tmp_path: Path) -> Path:
    """Helper: write a minimal valid miniautogen.yaml and return its path."""
    config_file = tmp_path / "miniautogen.yaml"
    data = {
        "project": {"name": "test-project", "version": "0.1.0"},
        "defaults": {"engine_profile": "default_api"},
        "engine_profiles": {
            "default_api": {
                "kind": "api",
                "provider": "litellm",
                "model": "gpt-4o-mini",
            }
        },
        "pipelines": {
            "main": {"target": "pipelines.main:build_pipeline"},
        },
    }
    config_file.write_text(yaml.dump(data))
    return config_file


class TestCheckProjectSignature:
    @pytest.mark.anyio()
    async def test_returns_list_of_check_results(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, CheckResult)
```

**Step 2: Run the test to verify it fails**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | head -20
```

**Expected output:**
```
FAILED ... - ModuleNotFoundError: No module named 'miniautogen.cli.services.check_project'
```

**Step 3: Write minimal implementation**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py`:

```python
"""Project validation service — static and environment checks.

This module contains the core logic for the ``miniautogen check`` command.
It validates project configuration, agent specs, skill directories,
tool specs, MCP bindings, pipeline targets, engine profile references,
cross-references, and environment variables — all without any CLI
dependency (Click-free).

Import boundary (D3): only stdlib, ``miniautogen.cli.config``, and
``miniautogen.cli.models`` allowed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from miniautogen.cli.config import ProjectConfig


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Outcome of a single validation check."""

    name: str
    passed: bool
    message: str
    category: Literal["static", "environment"]


async def check_project(
    config: ProjectConfig,
    project_root: Path,
) -> list[CheckResult]:
    """Run all static and environment checks against a project.

    Parameters
    ----------
    config:
        Parsed and validated ``ProjectConfig`` from ``miniautogen.yaml``.
    project_root:
        Absolute path to the project directory containing the config file.

    Returns
    -------
    list[CheckResult]
        One entry per check, ordered static-first then environment.
    """
    results: list[CheckResult] = []
    return results
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | tail -10
```

**Expected output:**
```
tests/cli/services/test_check_project.py::TestCheckResult::test_static_check_result PASSED
tests/cli/services/test_check_project.py::TestCheckResult::test_environment_check_result PASSED
tests/cli/services/test_check_project.py::TestCheckResult::test_category_must_be_static_or_environment PASSED
tests/cli/services/test_check_project.py::TestCheckProjectSignature::test_returns_list_of_check_results PASSED
```

**Step 5: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/services/check_project.py tests/cli/services/__init__.py tests/cli/services/test_check_project.py
git commit -m "feat(cli): add CheckResult dataclass and check_project skeleton"
```

**If Task Fails:**
1. **Test won't run:** Verify `tests/cli/__init__.py` and `tests/cli/services/__init__.py` exist.
2. **Import error on `load_config`:** Chunk 1 may not be complete. Verify `miniautogen/cli/config.py` exports `load_config` and `ProjectConfig`.
3. **Can't recover:** Document what failed and return to human partner.

---

## Task 3: Implement static check — config schema validation

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`

**Prerequisites:**
- Task 2 complete

**Step 1: Write the failing test**

Append to `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`:

```python
class TestConfigSchemaCheck:
    """Static check: config file schema is valid."""

    @pytest.mark.anyio()
    async def test_valid_config_passes(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        schema_checks = [r for r in results if r.name == "config_schema"]
        assert len(schema_checks) == 1
        assert schema_checks[0].passed is True
        assert schema_checks[0].category == "static"

    @pytest.mark.anyio()
    async def test_config_always_passes_when_loaded(self, tmp_path: Path) -> None:
        """If load_config succeeded, schema check passes (Pydantic validated)."""
        config_file = _write_minimal_config(tmp_path)
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        schema_check = next(r for r in results if r.name == "config_schema")
        assert schema_check.passed is True
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py::TestConfigSchemaCheck -v --no-header 2>&1 | tail -10
```

**Expected output:**
```
FAILED ... - assert len(schema_checks) == 1 (0 != 1)
```

**Step 3: Write minimal implementation**

Add to `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py` — add helper before `check_project`:

```python
def _check_config_schema(config: ProjectConfig) -> CheckResult:
    """Verify config schema is valid.

    Since ``load_config`` uses Pydantic validation, if we have a
    ``ProjectConfig`` instance, the schema is already valid.
    """
    return CheckResult(
        name="config_schema",
        passed=True,
        message="Configuration schema is valid",
        category="static",
    )
```

Update the `check_project` function body — replace `results: list[CheckResult] = []` section:

```python
    results: list[CheckResult] = []

    # --- Static checks ---
    results.append(_check_config_schema(config))

    return results
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | tail -10
```

**Expected output:** All tests PASSED.

**Step 5: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py
git commit -m "feat(cli): add config schema validation check"
```

**If Task Fails:**
1. **`load_config` raises error:** Verify YAML content matches `ProjectConfig` model from Chunk 1.
2. **Can't recover:** `git checkout -- .` and revisit Chunk 1 config model.

---

## Task 4: Implement static check — agent YAML validation

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`

**Prerequisites:**
- Task 3 complete
- Task 1 complete (AgentSpecValidator in models.py)

**Step 1: Write the failing test**

Append to `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`:

```python
class TestAgentYamlCheck:
    """Static check: agent YAML files in agents/ are valid AgentSpec."""

    @pytest.mark.anyio()
    async def test_valid_agent_passes(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        agent_data = {
            "id": "researcher",
            "version": "1.0",
            "name": "Researcher",
            "role": "Research assistant",
            "goal": "Find information",
            "engine_profile": "default_api",
        }
        (agents_dir / "researcher.yaml").write_text(yaml.dump(agent_data))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        agent_checks = [r for r in results if r.name == "agent_researcher"]
        assert len(agent_checks) == 1
        assert agent_checks[0].passed is True
        assert agent_checks[0].category == "static"

    @pytest.mark.anyio()
    async def test_invalid_agent_fails(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        # Missing required fields: role, goal
        bad_data = {"id": "bad", "version": "1.0", "name": "Bad"}
        (agents_dir / "bad.yaml").write_text(yaml.dump(bad_data))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        agent_checks = [r for r in results if r.name == "agent_bad"]
        assert len(agent_checks) == 1
        assert agent_checks[0].passed is False
        assert "role" in agent_checks[0].message.lower()

    @pytest.mark.anyio()
    async def test_no_agents_dir_produces_no_checks(
        self, tmp_path: Path,
    ) -> None:
        config_file = _write_minimal_config(tmp_path)
        # No agents/ directory
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        agent_checks = [r for r in results if r.name.startswith("agent_")]
        assert len(agent_checks) == 0

    @pytest.mark.anyio()
    async def test_multiple_agents_each_checked(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        for agent_id in ("alpha", "beta"):
            data = {
                "id": agent_id,
                "version": "1.0",
                "name": agent_id.title(),
                "role": f"{agent_id} role",
                "goal": f"{agent_id} goal",
            }
            (agents_dir / f"{agent_id}.yaml").write_text(yaml.dump(data))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        agent_names = [r.name for r in results if r.name.startswith("agent_")]
        assert "agent_alpha" in agent_names
        assert "agent_beta" in agent_names

    @pytest.mark.anyio()
    async def test_unparseable_yaml_fails(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "broken.yaml").write_text(": invalid: {{{")

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        agent_checks = [r for r in results if r.name == "agent_broken"]
        assert len(agent_checks) == 1
        assert agent_checks[0].passed is False
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py::TestAgentYamlCheck::test_valid_agent_passes -v --no-header 2>&1 | tail -5
```

**Expected output:**
```
FAILED ... - assert len(agent_checks) == 1 (0 != 1)
```

**Step 3: Write minimal implementation**

Add imports at the top of `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py`:

```python
import yaml
from pydantic import ValidationError

from miniautogen.cli.models import (
    AgentSpecValidator,
    McpBindingValidator,
    SkillSpecValidator,
    ToolSpecValidator,
)
```

Add helper function before `check_project`:

```python
def _check_agents(project_root: Path) -> list[CheckResult]:
    """Validate all agent YAML files in ``agents/``."""
    results: list[CheckResult] = []
    agents_dir = project_root / "agents"
    if not agents_dir.is_dir():
        return results

    for yaml_file in sorted(agents_dir.glob("*.yaml")):
        agent_name = yaml_file.stem
        try:
            raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                results.append(CheckResult(
                    name=f"agent_{agent_name}",
                    passed=False,
                    message=f"Agent '{agent_name}': expected YAML mapping, got {type(raw).__name__}",
                    category="static",
                ))
                continue
            AgentSpecValidator(**raw)
            results.append(CheckResult(
                name=f"agent_{agent_name}",
                passed=True,
                message=f"Agent '{agent_name}' schema is valid",
                category="static",
            ))
        except yaml.YAMLError as exc:
            results.append(CheckResult(
                name=f"agent_{agent_name}",
                passed=False,
                message=f"Agent '{agent_name}': YAML parse error — {exc}",
                category="static",
            ))
        except ValidationError as exc:
            missing = [e["loc"][0] for e in exc.errors() if e["type"] == "missing"]
            detail = f"missing fields: {', '.join(str(f) for f in missing)}" if missing else str(exc)
            results.append(CheckResult(
                name=f"agent_{agent_name}",
                passed=False,
                message=f"Agent '{agent_name}': invalid schema — {detail}",
                category="static",
            ))

    return results
```

Update `check_project` — add after `_check_config_schema`:

```python
    results.extend(_check_agents(project_root))
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | tail -15
```

**Expected output:** All tests PASSED.

**Step 5: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py
git commit -m "feat(cli): add agent YAML validation check"
```

**If Task Fails:**
1. **yaml import error:** `pyyaml` must be installed (Chunk 1 dependency).
2. **ValidationError shape different:** Check `exc.errors()` returns list of dicts with `"loc"` and `"type"` keys.
3. **Rollback:** `git checkout -- miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py`

---

## Task 5: Implement static check — skill directory validation

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`

**Prerequisites:**
- Task 4 complete
- SkillSpecValidator available in models.py

**Step 1: Write the failing test**

Append to `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`:

```python
class TestSkillDirectoryCheck:
    """Static check: skill directories have SKILL.md."""

    @pytest.mark.anyio()
    async def test_valid_skill_dir_passes(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        skill_dir = tmp_path / "skills" / "deep-research"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Deep Research\n")
        skill_yaml = {
            "id": "deep-research",
            "version": "1.0",
            "name": "Deep Research",
            "description": "Performs deep research",
        }
        (skill_dir / "skill.yaml").write_text(yaml.dump(skill_yaml))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        skill_checks = [r for r in results if r.name == "skill_deep-research"]
        assert len(skill_checks) == 1
        assert skill_checks[0].passed is True

    @pytest.mark.anyio()
    async def test_missing_skill_md_fails(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        skill_dir = tmp_path / "skills" / "bad-skill"
        skill_dir.mkdir(parents=True)
        # No SKILL.md
        skill_yaml = {
            "id": "bad-skill",
            "version": "1.0",
            "name": "Bad",
            "description": "Missing SKILL.md",
        }
        (skill_dir / "skill.yaml").write_text(yaml.dump(skill_yaml))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        skill_checks = [r for r in results if r.name == "skill_bad-skill"]
        assert len(skill_checks) == 1
        assert skill_checks[0].passed is False
        assert "SKILL.md" in skill_checks[0].message

    @pytest.mark.anyio()
    async def test_missing_skill_yaml_fails(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        skill_dir = tmp_path / "skills" / "no-yaml"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Skill\n")
        # No skill.yaml

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        skill_checks = [r for r in results if r.name == "skill_no-yaml"]
        assert len(skill_checks) == 1
        assert skill_checks[0].passed is False
        assert "skill.yaml" in skill_checks[0].message

    @pytest.mark.anyio()
    async def test_no_skills_dir_produces_no_checks(
        self, tmp_path: Path,
    ) -> None:
        config_file = _write_minimal_config(tmp_path)
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        skill_checks = [r for r in results if r.name.startswith("skill_")]
        assert len(skill_checks) == 0

    @pytest.mark.anyio()
    async def test_invalid_skill_yaml_fails(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        skill_dir = tmp_path / "skills" / "bad-yaml"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Bad\n")
        # Invalid skill.yaml (missing required fields)
        (skill_dir / "skill.yaml").write_text(yaml.dump({"id": "bad-yaml"}))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        skill_checks = [r for r in results if r.name == "skill_bad-yaml"]
        assert len(skill_checks) == 1
        assert skill_checks[0].passed is False
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py::TestSkillDirectoryCheck::test_valid_skill_dir_passes -v --no-header 2>&1 | tail -5
```

**Expected output:**
```
FAILED ... - assert len(skill_checks) == 1 (0 != 1)
```

**Step 3: Write minimal implementation**

Add helper to `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py` before `check_project`:

```python
def _check_skills(project_root: Path) -> list[CheckResult]:
    """Validate skill directories in ``skills/``.

    Each subdirectory of ``skills/`` must contain:
    - ``SKILL.md`` — human-readable skill instructions
    - ``skill.yaml`` — valid SkillSpecValidator schema
    """
    results: list[CheckResult] = []
    skills_dir = project_root / "skills"
    if not skills_dir.is_dir():
        return results

    for skill_path in sorted(skills_dir.iterdir()):
        if not skill_path.is_dir():
            continue
        skill_name = skill_path.name
        skill_md = skill_path / "SKILL.md"
        skill_yaml_file = skill_path / "skill.yaml"

        if not skill_md.is_file():
            results.append(CheckResult(
                name=f"skill_{skill_name}",
                passed=False,
                message=f"Skill '{skill_name}': missing SKILL.md",
                category="static",
            ))
            continue

        if not skill_yaml_file.is_file():
            results.append(CheckResult(
                name=f"skill_{skill_name}",
                passed=False,
                message=f"Skill '{skill_name}': missing skill.yaml",
                category="static",
            ))
            continue

        try:
            raw = yaml.safe_load(
                skill_yaml_file.read_text(encoding="utf-8")
            )
            if not isinstance(raw, dict):
                results.append(CheckResult(
                    name=f"skill_{skill_name}",
                    passed=False,
                    message=(
                        f"Skill '{skill_name}': skill.yaml expected mapping, "
                        f"got {type(raw).__name__}"
                    ),
                    category="static",
                ))
                continue
            SkillSpecValidator(**raw)
            results.append(CheckResult(
                name=f"skill_{skill_name}",
                passed=True,
                message=f"Skill '{skill_name}' is valid",
                category="static",
            ))
        except yaml.YAMLError as exc:
            results.append(CheckResult(
                name=f"skill_{skill_name}",
                passed=False,
                message=f"Skill '{skill_name}': YAML parse error — {exc}",
                category="static",
            ))
        except ValidationError as exc:
            missing = [
                e["loc"][0] for e in exc.errors() if e["type"] == "missing"
            ]
            detail = (
                f"missing fields: {', '.join(str(f) for f in missing)}"
                if missing
                else str(exc)
            )
            results.append(CheckResult(
                name=f"skill_{skill_name}",
                passed=False,
                message=f"Skill '{skill_name}': invalid schema — {detail}",
                category="static",
            ))

    return results
```

Update `check_project` — add after `_check_agents`:

```python
    results.extend(_check_skills(project_root))
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | tail -20
```

**Expected output:** All tests PASSED.

**Step 5: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py
git commit -m "feat(cli): add skill directory validation check"
```

**If Task Fails:**
1. **Glob pattern issue:** Ensure `skills_dir.iterdir()` returns directories. Use `is_dir()` filter.
2. **Rollback:** `git checkout -- miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py`

---

## Task 6: Implement static check — tool YAML validation

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`

**Prerequisites:**
- Task 5 complete
- ToolSpecValidator available in models.py

**Step 1: Write the failing test**

Append to `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`:

```python
class TestToolYamlCheck:
    """Static check: tool YAML files in tools/ are valid ToolSpec."""

    @pytest.mark.anyio()
    async def test_valid_tool_passes(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        tool_data = {
            "name": "web_search",
            "description": "Search the web",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
            "execution": {"kind": "function", "target": "tools.search:run"},
        }
        (tools_dir / "web_search.yaml").write_text(yaml.dump(tool_data))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        tool_checks = [r for r in results if r.name == "tool_web_search"]
        assert len(tool_checks) == 1
        assert tool_checks[0].passed is True

    @pytest.mark.anyio()
    async def test_invalid_tool_fails(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        # Missing required fields
        (tools_dir / "bad.yaml").write_text(yaml.dump({"name": "bad"}))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        tool_checks = [r for r in results if r.name == "tool_bad"]
        assert len(tool_checks) == 1
        assert tool_checks[0].passed is False

    @pytest.mark.anyio()
    async def test_no_tools_dir_produces_no_checks(
        self, tmp_path: Path,
    ) -> None:
        config_file = _write_minimal_config(tmp_path)
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        tool_checks = [r for r in results if r.name.startswith("tool_")]
        assert len(tool_checks) == 0
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py::TestToolYamlCheck::test_valid_tool_passes -v --no-header 2>&1 | tail -5
```

**Expected output:**
```
FAILED ... - assert len(tool_checks) == 1 (0 != 1)
```

**Step 3: Write minimal implementation**

Add helper to `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py`:

```python
def _check_tools(project_root: Path) -> list[CheckResult]:
    """Validate all tool YAML files in ``tools/``."""
    results: list[CheckResult] = []
    tools_dir = project_root / "tools"
    if not tools_dir.is_dir():
        return results

    for yaml_file in sorted(tools_dir.glob("*.yaml")):
        tool_name = yaml_file.stem
        try:
            raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                results.append(CheckResult(
                    name=f"tool_{tool_name}",
                    passed=False,
                    message=(
                        f"Tool '{tool_name}': expected YAML mapping, "
                        f"got {type(raw).__name__}"
                    ),
                    category="static",
                ))
                continue
            ToolSpecValidator(**raw)
            results.append(CheckResult(
                name=f"tool_{tool_name}",
                passed=True,
                message=f"Tool '{tool_name}' schema is valid",
                category="static",
            ))
        except yaml.YAMLError as exc:
            results.append(CheckResult(
                name=f"tool_{tool_name}",
                passed=False,
                message=f"Tool '{tool_name}': YAML parse error — {exc}",
                category="static",
            ))
        except ValidationError as exc:
            missing = [
                e["loc"][0] for e in exc.errors() if e["type"] == "missing"
            ]
            detail = (
                f"missing fields: {', '.join(str(f) for f in missing)}"
                if missing
                else str(exc)
            )
            results.append(CheckResult(
                name=f"tool_{tool_name}",
                passed=False,
                message=f"Tool '{tool_name}': invalid schema — {detail}",
                category="static",
            ))

    return results
```

Update `check_project` — add after `_check_skills`:

```python
    results.extend(_check_tools(project_root))
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | tail -20
```

**Expected output:** All tests PASSED.

**Step 5: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py
git commit -m "feat(cli): add tool YAML validation check"
```

**If Task Fails:**
1. **Rollback:** `git checkout -- miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py`

---

## Task 7: Implement static check — pipeline targets resolve

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`

**Prerequisites:**
- Task 6 complete

**Step 1: Write the failing test**

Append to `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`:

```python
class TestPipelineTargetCheck:
    """Static check: pipeline targets resolve."""

    @pytest.mark.anyio()
    async def test_importable_target_passes(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        # Override with importable target
        data = yaml.safe_load(config_file.read_text())
        data["pipelines"]["main"]["target"] = "os.path:join"
        config_file.write_text(yaml.dump(data))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        target_checks = [
            r for r in results if r.name == "pipeline_target_main"
        ]
        assert len(target_checks) == 1
        assert target_checks[0].passed is True
        assert target_checks[0].category == "static"

    @pytest.mark.anyio()
    async def test_nonexistent_module_fails(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        data = yaml.safe_load(config_file.read_text())
        data["pipelines"]["main"]["target"] = "nonexistent_xyz_mod:build"
        config_file.write_text(yaml.dump(data))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        target_checks = [
            r for r in results if r.name == "pipeline_target_main"
        ]
        assert len(target_checks) == 1
        assert target_checks[0].passed is False
        assert "nonexistent_xyz_mod" in target_checks[0].message

    @pytest.mark.anyio()
    async def test_missing_callable_fails(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        data = yaml.safe_load(config_file.read_text())
        data["pipelines"]["main"]["target"] = "os.path:nonexistent_func_xyz"
        config_file.write_text(yaml.dump(data))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        target_checks = [
            r for r in results if r.name == "pipeline_target_main"
        ]
        assert len(target_checks) == 1
        assert target_checks[0].passed is False
        assert "nonexistent_func_xyz" in target_checks[0].message

    @pytest.mark.anyio()
    async def test_file_based_target_passes(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        pipelines_dir = tmp_path / "pipelines"
        pipelines_dir.mkdir()
        (pipelines_dir / "main.py").write_text(
            "def build_pipeline(): pass\n"
        )

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        target_checks = [
            r for r in results if r.name == "pipeline_target_main"
        ]
        assert len(target_checks) == 1
        assert target_checks[0].passed is True

    @pytest.mark.anyio()
    async def test_multiple_pipelines_checked(self, tmp_path: Path) -> None:
        config_file = _write_minimal_config(tmp_path)
        data = yaml.safe_load(config_file.read_text())
        data["pipelines"]["main"]["target"] = "os.path:join"
        data["pipelines"]["secondary"] = {"target": "os.path:exists"}
        config_file.write_text(yaml.dump(data))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        target_names = [
            r.name for r in results
            if r.name.startswith("pipeline_target_")
        ]
        assert "pipeline_target_main" in target_names
        assert "pipeline_target_secondary" in target_names
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py::TestPipelineTargetCheck::test_importable_target_passes -v --no-header 2>&1 | tail -5
```

**Expected output:**
```
FAILED ... - assert len(target_checks) == 1 (0 != 1)
```

**Step 3: Write minimal implementation**

Add imports at the top of `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py` (if not already present):

```python
import importlib
```

Add helper function:

```python
def _check_pipeline_target(
    name: str,
    target: str,
    project_root: Path,
) -> CheckResult:
    """Verify a pipeline target is resolvable.

    Target format: ``module.path:callable_name``

    Resolution strategy:
    1. Try to import the module directly (works for installed packages).
    2. If that fails, check if the module path maps to a file under
       ``project_root`` (e.g. ``pipelines.main`` -> ``pipelines/main.py``).
    3. If the module is importable/exists, check the callable exists.
    """
    if ":" not in target:
        return CheckResult(
            name=f"pipeline_target_{name}",
            passed=False,
            message=(
                f"Invalid target format '{target}' — "
                f"expected 'module:callable'"
            ),
            category="static",
        )

    module_path, callable_name = target.rsplit(":", 1)

    # Strategy 1: try direct import
    try:
        mod = importlib.import_module(module_path)
        if hasattr(mod, callable_name):
            return CheckResult(
                name=f"pipeline_target_{name}",
                passed=True,
                message=f"Pipeline '{name}' target resolves OK",
                category="static",
            )
        return CheckResult(
            name=f"pipeline_target_{name}",
            passed=False,
            message=(
                f"Module '{module_path}' found but callable "
                f"'{callable_name}' does not exist"
            ),
            category="static",
        )
    except ImportError:
        pass

    # Strategy 2: check as file relative to project root
    relative_file = Path(module_path.replace(".", "/") + ".py")
    absolute_file = project_root / relative_file
    if absolute_file.is_file():
        return CheckResult(
            name=f"pipeline_target_{name}",
            passed=True,
            message=(
                f"Pipeline '{name}' target file exists: {relative_file}"
            ),
            category="static",
        )

    return CheckResult(
        name=f"pipeline_target_{name}",
        passed=False,
        message=(
            f"Cannot resolve pipeline '{name}' target '{target}' — "
            f"module not importable and file not found at {relative_file}"
        ),
        category="static",
    )
```

Update `check_project` — add after `_check_tools`:

```python
    # Pipeline target checks
    if config.pipelines:
        for pipeline_name, pipeline_cfg in config.pipelines.items():
            results.append(
                _check_pipeline_target(
                    pipeline_name, pipeline_cfg.target, project_root
                )
            )
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | tail -20
```

**Expected output:** All tests PASSED.

**Step 5: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py
git commit -m "feat(cli): add pipeline target resolution check"
```

**If Task Fails:**
1. **`config.pipelines` attribute error:** Check actual `ProjectConfig` model from Chunk 1.
2. **Rollback:** `git checkout -- miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py`

---

## Task 8: Implement static check — engine profile references

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`

**Prerequisites:**
- Task 7 complete
- Task 4 complete (agent YAML loading works)

**Step 1: Write the failing test**

Append to `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`:

```python
class TestEngineProfileReferenceCheck:
    """Static check: engine profiles referenced by agents exist in config."""

    @pytest.mark.anyio()
    async def test_valid_engine_profile_ref_passes(
        self, tmp_path: Path,
    ) -> None:
        config_file = _write_minimal_config(tmp_path)
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        agent_data = {
            "id": "researcher",
            "version": "1.0",
            "name": "Researcher",
            "role": "Research",
            "goal": "Find info",
            "engine_profile": "default_api",  # exists in config
        }
        (agents_dir / "researcher.yaml").write_text(yaml.dump(agent_data))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        ref_checks = [
            r for r in results
            if r.name == "engine_profile_ref_researcher"
        ]
        assert len(ref_checks) == 1
        assert ref_checks[0].passed is True

    @pytest.mark.anyio()
    async def test_missing_engine_profile_ref_fails(
        self, tmp_path: Path,
    ) -> None:
        config_file = _write_minimal_config(tmp_path)
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        agent_data = {
            "id": "researcher",
            "version": "1.0",
            "name": "Researcher",
            "role": "Research",
            "goal": "Find info",
            "engine_profile": "nonexistent_profile",
        }
        (agents_dir / "researcher.yaml").write_text(yaml.dump(agent_data))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        ref_checks = [
            r for r in results
            if r.name == "engine_profile_ref_researcher"
        ]
        assert len(ref_checks) == 1
        assert ref_checks[0].passed is False
        assert "nonexistent_profile" in ref_checks[0].message

    @pytest.mark.anyio()
    async def test_agent_without_engine_profile_skips(
        self, tmp_path: Path,
    ) -> None:
        config_file = _write_minimal_config(tmp_path)
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        agent_data = {
            "id": "minimal",
            "version": "1.0",
            "name": "Minimal",
            "role": "Helper",
            "goal": "Help",
            # No engine_profile — uses project default
        }
        (agents_dir / "minimal.yaml").write_text(yaml.dump(agent_data))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        ref_checks = [
            r for r in results
            if r.name == "engine_profile_ref_minimal"
        ]
        # No check produced when agent doesn't specify engine_profile
        assert len(ref_checks) == 0

    @pytest.mark.anyio()
    async def test_default_engine_profile_check(
        self, tmp_path: Path,
    ) -> None:
        """The defaults.engine_profile itself must exist in engine_profiles."""
        config_file = _write_minimal_config(tmp_path)

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        default_checks = [
            r for r in results if r.name == "default_engine_profile"
        ]
        assert len(default_checks) == 1
        assert default_checks[0].passed is True
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py::TestEngineProfileReferenceCheck::test_valid_engine_profile_ref_passes -v --no-header 2>&1 | tail -5
```

**Expected output:**
```
FAILED ... - assert len(ref_checks) == 1 (0 != 1)
```

**Step 3: Write minimal implementation**

Add helpers to `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py`:

```python
def _check_default_engine_profile(config: ProjectConfig) -> CheckResult:
    """Verify the default engine profile exists in engine_profiles."""
    default_ref = config.defaults.engine_profile
    available = set(config.engine_profiles.keys())
    if default_ref in available:
        return CheckResult(
            name="default_engine_profile",
            passed=True,
            message=(
                f"Default engine profile '{default_ref}' exists"
            ),
            category="static",
        )
    return CheckResult(
        name="default_engine_profile",
        passed=False,
        message=(
            f"Default engine profile '{default_ref}' not found in "
            f"engine_profiles. Available: {', '.join(sorted(available))}"
        ),
        category="static",
    )


def _check_engine_profile_refs(
    config: ProjectConfig,
    project_root: Path,
) -> list[CheckResult]:
    """Verify engine profiles referenced by agents exist in config."""
    results: list[CheckResult] = []
    agents_dir = project_root / "agents"
    if not agents_dir.is_dir():
        return results

    available_profiles = set(config.engine_profiles.keys())

    for yaml_file in sorted(agents_dir.glob("*.yaml")):
        agent_name = yaml_file.stem
        try:
            raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                continue
            engine_profile = raw.get("engine_profile")
            if not engine_profile:
                continue  # Agent uses project default
            if engine_profile in available_profiles:
                results.append(CheckResult(
                    name=f"engine_profile_ref_{agent_name}",
                    passed=True,
                    message=(
                        f"Agent '{agent_name}' engine profile "
                        f"'{engine_profile}' exists"
                    ),
                    category="static",
                ))
            else:
                results.append(CheckResult(
                    name=f"engine_profile_ref_{agent_name}",
                    passed=False,
                    message=(
                        f"Agent '{agent_name}' references engine profile "
                        f"'{engine_profile}' which does not exist. "
                        f"Available: "
                        f"{', '.join(sorted(available_profiles))}"
                    ),
                    category="static",
                ))
        except yaml.YAMLError:
            continue  # Already caught by _check_agents

    return results
```

Update `check_project` — add after pipeline target checks:

```python
    # Engine profile reference checks
    results.append(_check_default_engine_profile(config))
    results.extend(_check_engine_profile_refs(config, project_root))
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | tail -25
```

**Expected output:** All tests PASSED.

**Step 5: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py
git commit -m "feat(cli): add engine profile reference checks"
```

**If Task Fails:**
1. **`config.engine_profiles` missing:** Check Chunk 1 `ProjectConfig` model.
2. **Rollback:** `git checkout -- miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py`

### Task 8b: Memory profile checks (extension of Task 8)

Following the same pattern as engine profile reference checks, add memory profile validation:

**Add to tests:**

```python
class TestMemoryProfileCheck:
    """Static check: memory profiles exist and agents reference valid ones."""

    @pytest.mark.anyio()
    async def test_valid_memory_profile_ref_passes(
        self, tmp_path: Path,
    ) -> None:
        config_file = _write_minimal_config(tmp_path)
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        agent_data = {
            "id": "researcher",
            "version": "1.0",
            "name": "Researcher",
            "role": "Research",
            "goal": "Find info",
            "memory": {"profile": "default"},
        }
        (agents_dir / "researcher.yaml").write_text(yaml.dump(agent_data))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        ref_checks = [
            r for r in results
            if r.name == "memory_profile_ref_researcher"
        ]
        assert len(ref_checks) == 1
        assert ref_checks[0].passed is True

    @pytest.mark.anyio()
    async def test_missing_memory_profile_ref_fails(
        self, tmp_path: Path,
    ) -> None:
        config_file = _write_minimal_config(tmp_path)
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        agent_data = {
            "id": "researcher",
            "version": "1.0",
            "name": "Researcher",
            "role": "Research",
            "goal": "Find info",
            "memory": {"profile": "nonexistent_profile"},
        }
        (agents_dir / "researcher.yaml").write_text(yaml.dump(agent_data))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        ref_checks = [
            r for r in results
            if r.name == "memory_profile_ref_researcher"
        ]
        assert len(ref_checks) == 1
        assert ref_checks[0].passed is False
        assert "nonexistent_profile" in ref_checks[0].message

    @pytest.mark.anyio()
    async def test_agent_without_memory_skips(
        self, tmp_path: Path,
    ) -> None:
        config_file = _write_minimal_config(tmp_path)
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        agent_data = {
            "id": "minimal",
            "version": "1.0",
            "name": "Minimal",
            "role": "Helper",
            "goal": "Help",
            # No memory section — uses project default
        }
        (agents_dir / "minimal.yaml").write_text(yaml.dump(agent_data))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        ref_checks = [
            r for r in results
            if r.name == "memory_profile_ref_minimal"
        ]
        # No check produced when agent doesn't specify memory
        assert len(ref_checks) == 0

    @pytest.mark.anyio()
    async def test_default_memory_profile_check(
        self, tmp_path: Path,
    ) -> None:
        """The defaults.memory_profile must exist in memory_profiles."""
        config_file = _write_minimal_config(tmp_path)

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        default_checks = [
            r for r in results if r.name == "default_memory_profile"
        ]
        assert len(default_checks) == 1
        assert default_checks[0].passed is True
```

**Add to `check_project.py`:**

```python
def _check_memory_profiles(
    project_root: Path,
    config: ProjectConfig,
) -> list[CheckResult]:
    """Validate memory profiles exist and agents reference valid ones."""
    results: list[CheckResult] = []

    # Check profiles.yaml is parseable (if it exists)
    profiles_file = project_root / "memory" / "profiles.yaml"
    if profiles_file.is_file():
        try:
            raw = yaml.safe_load(
                profiles_file.read_text(encoding="utf-8")
            )
            if not isinstance(raw, dict):
                results.append(CheckResult(
                    name="memory_profiles_file",
                    passed=False,
                    message="memory/profiles.yaml is not a valid mapping",
                    category="static",
                ))
            else:
                results.append(CheckResult(
                    name="memory_profiles_file",
                    passed=True,
                    message="memory/profiles.yaml is valid",
                    category="static",
                ))
        except yaml.YAMLError as exc:
            results.append(CheckResult(
                name="memory_profiles_file",
                passed=False,
                message=f"memory/profiles.yaml parse error: {exc}",
                category="static",
            ))

    # Check default memory profile exists
    default_ref = config.defaults.memory_profile
    available = set(config.memory_profiles.keys())
    if default_ref in available:
        results.append(CheckResult(
            name="default_memory_profile",
            passed=True,
            message=f"Default memory profile '{default_ref}' exists",
            category="static",
        ))
    else:
        results.append(CheckResult(
            name="default_memory_profile",
            passed=False,
            message=(
                f"Default memory profile '{default_ref}' not found in "
                f"memory_profiles. Available: "
                f"{', '.join(sorted(available)) or '(none)'}"
            ),
            category="static",
        ))

    # Cross-reference: agents referencing memory profiles
    agents_dir = project_root / "agents"
    if not agents_dir.is_dir():
        return results

    for yaml_file in sorted(agents_dir.glob("*.yaml")):
        agent_name = yaml_file.stem
        try:
            raw = yaml.safe_load(
                yaml_file.read_text(encoding="utf-8")
            )
            if not isinstance(raw, dict):
                continue
            memory = raw.get("memory")
            if not isinstance(memory, dict):
                continue
            profile_ref = memory.get("profile")
            if not profile_ref:
                continue
            if profile_ref in available:
                results.append(CheckResult(
                    name=f"memory_profile_ref_{agent_name}",
                    passed=True,
                    message=(
                        f"Agent '{agent_name}' memory profile "
                        f"'{profile_ref}' exists"
                    ),
                    category="static",
                ))
            else:
                results.append(CheckResult(
                    name=f"memory_profile_ref_{agent_name}",
                    passed=False,
                    message=(
                        f"Agent '{agent_name}' references memory profile "
                        f"'{profile_ref}' which does not exist. "
                        f"Available: "
                        f"{', '.join(sorted(available)) or '(none)'}"
                    ),
                    category="static",
                ))
        except yaml.YAMLError:
            continue  # Already caught by _check_agents

    return results
```

Update `check_project` — add after engine profile reference checks:

```python
    # Memory profile checks
    results.extend(_check_memory_profiles(project_root, config))
```

**Note:** The `_write_minimal_config` helper must include `memory_profiles` and `defaults.memory_profile` in its generated config. Update it to match the updated `ProjectConfig` schema from Chunk 1.

---

## Task 9: Implement static check — cross-references (skills/tools referenced by agents)

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`

**Prerequisites:**
- Task 8 complete

**Step 1: Write the failing test**

Append to `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`:

```python
class TestCrossReferenceCheck:
    """Static check: agents reference existing skills and tools."""

    @pytest.mark.anyio()
    async def test_agent_refs_existing_skill_passes(
        self, tmp_path: Path,
    ) -> None:
        config_file = _write_minimal_config(tmp_path)

        # Create skill
        skill_dir = tmp_path / "skills" / "deep-research"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Deep Research\n")
        (skill_dir / "skill.yaml").write_text(yaml.dump({
            "id": "deep-research",
            "version": "1.0",
            "name": "Deep Research",
            "description": "Research skill",
        }))

        # Create agent referencing the skill
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "researcher.yaml").write_text(yaml.dump({
            "id": "researcher",
            "version": "1.0",
            "name": "Researcher",
            "role": "Research",
            "goal": "Find info",
            "skills": {"deep-research": {"attached": []}},
        }))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        xref_checks = [
            r for r in results
            if r.name == "xref_researcher_skill_deep-research"
        ]
        assert len(xref_checks) == 1
        assert xref_checks[0].passed is True

    @pytest.mark.anyio()
    async def test_agent_refs_missing_skill_fails(
        self, tmp_path: Path,
    ) -> None:
        config_file = _write_minimal_config(tmp_path)
        # No skills/ directory

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "researcher.yaml").write_text(yaml.dump({
            "id": "researcher",
            "version": "1.0",
            "name": "Researcher",
            "role": "Research",
            "goal": "Find info",
            "skills": {"nonexistent-skill": {"attached": []}},
        }))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        xref_checks = [
            r for r in results
            if r.name == "xref_researcher_skill_nonexistent-skill"
        ]
        assert len(xref_checks) == 1
        assert xref_checks[0].passed is False

    @pytest.mark.anyio()
    async def test_agent_refs_existing_tool_passes(
        self, tmp_path: Path,
    ) -> None:
        config_file = _write_minimal_config(tmp_path)

        # Create tool
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "web_search.yaml").write_text(yaml.dump({
            "name": "web_search",
            "description": "Search",
            "input_schema": {"type": "object"},
            "execution": {"kind": "function", "target": "t:run"},
        }))

        # Create agent referencing the tool
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "researcher.yaml").write_text(yaml.dump({
            "id": "researcher",
            "version": "1.0",
            "name": "Researcher",
            "role": "Research",
            "goal": "Find info",
            "tool_access": {
                "mode": "allowlist",
                "allow": ["web_search"],
            },
        }))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        xref_checks = [
            r for r in results
            if r.name == "xref_researcher_tool_web_search"
        ]
        assert len(xref_checks) == 1
        assert xref_checks[0].passed is True

    @pytest.mark.anyio()
    async def test_agent_refs_missing_tool_fails(
        self, tmp_path: Path,
    ) -> None:
        config_file = _write_minimal_config(tmp_path)
        # No tools/ directory

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "researcher.yaml").write_text(yaml.dump({
            "id": "researcher",
            "version": "1.0",
            "name": "Researcher",
            "role": "Research",
            "goal": "Find info",
            "tool_access": {
                "mode": "allowlist",
                "allow": ["nonexistent_tool"],
            },
        }))

        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        xref_checks = [
            r for r in results
            if r.name == "xref_researcher_tool_nonexistent_tool"
        ]
        assert len(xref_checks) == 1
        assert xref_checks[0].passed is False

    @pytest.mark.anyio()
    async def test_no_agents_no_xref_checks(
        self, tmp_path: Path,
    ) -> None:
        config_file = _write_minimal_config(tmp_path)
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        xref_checks = [
            r for r in results if r.name.startswith("xref_")
        ]
        assert len(xref_checks) == 0
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py::TestCrossReferenceCheck::test_agent_refs_existing_skill_passes -v --no-header 2>&1 | tail -5
```

**Expected output:**
```
FAILED ... - assert len(xref_checks) == 1 (0 != 1)
```

**Step 3: Write minimal implementation**

Add helper to `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py`:

```python
def _check_cross_references(project_root: Path) -> list[CheckResult]:
    """Verify agents reference existing skills and tools.

    For each agent YAML:
    - ``skills`` keys must match subdirectory names in ``skills/``
    - ``tool_access.allow`` entries must match YAML file stems in ``tools/``
    """
    results: list[CheckResult] = []
    agents_dir = project_root / "agents"
    if not agents_dir.is_dir():
        return results

    # Discover available skills (directory names under skills/)
    skills_dir = project_root / "skills"
    available_skills: set[str] = set()
    if skills_dir.is_dir():
        available_skills = {
            d.name for d in skills_dir.iterdir() if d.is_dir()
        }

    # Discover available tools (YAML file stems under tools/)
    tools_dir = project_root / "tools"
    available_tools: set[str] = set()
    if tools_dir.is_dir():
        available_tools = {
            f.stem for f in tools_dir.glob("*.yaml")
        }

    for yaml_file in sorted(agents_dir.glob("*.yaml")):
        agent_name = yaml_file.stem
        try:
            raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                continue
        except yaml.YAMLError:
            continue  # Already caught by _check_agents

        # Check skill references
        skills = raw.get("skills", {})
        if isinstance(skills, dict):
            for skill_ref in skills:
                found = skill_ref in available_skills
                results.append(CheckResult(
                    name=f"xref_{agent_name}_skill_{skill_ref}",
                    passed=found,
                    message=(
                        f"Agent '{agent_name}' skill '{skill_ref}' exists"
                        if found
                        else (
                            f"Agent '{agent_name}' references skill "
                            f"'{skill_ref}' which does not exist in skills/"
                        )
                    ),
                    category="static",
                ))

        # Check tool references
        tool_access = raw.get("tool_access", {})
        if isinstance(tool_access, dict):
            allow_list = tool_access.get("allow", [])
            if isinstance(allow_list, list):
                for tool_ref in allow_list:
                    found = tool_ref in available_tools
                    results.append(CheckResult(
                        name=f"xref_{agent_name}_tool_{tool_ref}",
                        passed=found,
                        message=(
                            f"Agent '{agent_name}' tool '{tool_ref}' exists"
                            if found
                            else (
                                f"Agent '{agent_name}' references tool "
                                f"'{tool_ref}' which does not exist "
                                f"in tools/"
                            )
                        ),
                        category="static",
                    ))

    return results
```

Update `check_project` — add after engine profile ref checks:

```python
    # Cross-reference checks (agents -> skills, agents -> tools)
    results.extend(_check_cross_references(project_root))
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | tail -30
```

**Expected output:** All tests PASSED.

**Step 5: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py
git commit -m "feat(cli): add cross-reference checks for agent skill/tool refs"
```

**If Task Fails:**
1. **YAML loading issue:** Ensure `yaml.safe_load` handles edge cases.
2. **Rollback:** `git checkout -- miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py`

---

## Task 10: Implement environment check — API keys based on engine profiles

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`

**Prerequisites:**
- Task 9 complete

**Step 1: Write the failing test**

Append to `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py`:

```python
import os


class TestEnvironmentApiKeyCheck:
    """Environment check: API keys present based on engine profiles."""

    @pytest.mark.anyio()
    async def test_openai_key_present_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
        config_file = _write_minimal_config(tmp_path)
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        env_checks = [
            r for r in results if r.name == "env_profile_default_api"
        ]
        assert len(env_checks) == 1
        assert env_checks[0].passed is True
        assert env_checks[0].category == "environment"

    @pytest.mark.anyio()
    async def test_missing_openai_key_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        for key in (
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
            "GOOGLE_API_KEY", "GEMINI_API_KEY",
        ):
            monkeypatch.delenv(key, raising=False)
        config_file = _write_minimal_config(tmp_path)
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        env_checks = [
            r for r in results if r.name == "env_profile_default_api"
        ]
        assert len(env_checks) == 1
        assert env_checks[0].passed is False
        assert "OPENAI_API_KEY" in env_checks[0].message

    @pytest.mark.anyio()
    async def test_cli_profile_skips_api_key_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CLI-kind engine profiles don't need API keys."""
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        config_file = tmp_path / "miniautogen.yaml"
        data = {
            "project": {"name": "test", "version": "0.1.0"},
            "defaults": {"engine_profile": "gemini_cli"},
            "engine_profiles": {
                "gemini_cli": {
                    "kind": "cli",
                    "provider": "gemini",
                    "command": "gemini",
                }
            },
            "pipelines": {
                "main": {"target": "os.path:join"},
            },
        }
        config_file.write_text(yaml.dump(data))
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        env_checks = [
            r for r in results if r.name == "env_profile_gemini_cli"
        ]
        assert len(env_checks) == 1
        assert env_checks[0].passed is True

    @pytest.mark.anyio()
    async def test_no_database_no_db_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        config_file = _write_minimal_config(tmp_path)
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        db_checks = [r for r in results if r.name == "database_url"]
        assert len(db_checks) == 0

    @pytest.mark.anyio()
    async def test_database_url_valid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        config_file = tmp_path / "miniautogen.yaml"
        data = {
            "project": {"name": "test", "version": "0.1.0"},
            "defaults": {"engine_profile": "default_api"},
            "engine_profiles": {
                "default_api": {
                    "kind": "api",
                    "provider": "litellm",
                    "model": "gpt-4o-mini",
                }
            },
            "pipelines": {"main": {"target": "os.path:join"}},
            "database": {"url": "sqlite+aiosqlite:///test.db"},
        }
        config_file.write_text(yaml.dump(data))
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        db_checks = [r for r in results if r.name == "database_url"]
        assert len(db_checks) == 1
        assert db_checks[0].passed is True

    @pytest.mark.anyio()
    async def test_database_url_empty_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        config_file = tmp_path / "miniautogen.yaml"
        data = {
            "project": {"name": "test", "version": "0.1.0"},
            "defaults": {"engine_profile": "default_api"},
            "engine_profiles": {
                "default_api": {
                    "kind": "api",
                    "provider": "litellm",
                    "model": "gpt-4o-mini",
                }
            },
            "pipelines": {"main": {"target": "os.path:join"}},
            "database": {"url": ""},
        }
        config_file.write_text(yaml.dump(data))
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        db_checks = [r for r in results if r.name == "database_url"]
        assert len(db_checks) == 1
        assert db_checks[0].passed is False
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py::TestEnvironmentApiKeyCheck::test_openai_key_present_passes -v --no-header 2>&1 | tail -5
```

**Expected output:**
```
FAILED ... - assert len(env_checks) == 1 (0 != 1)
```

**Step 3: Write minimal implementation**

Add to `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py`, add `import os` at top, then add helpers:

```python
import os

# Map of model prefix patterns to required env vars.
_MODEL_ENV_VARS: dict[str, list[str]] = {
    "gpt-": ["OPENAI_API_KEY"],
    "o1-": ["OPENAI_API_KEY"],
    "o3-": ["OPENAI_API_KEY"],
    "claude-": ["ANTHROPIC_API_KEY"],
    "gemini": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
    "mistral": ["MISTRAL_API_KEY"],
}

# Map of provider names to required env vars (fallback when model unknown).
_PROVIDER_ENV_VARS: dict[str, list[str]] = {
    "openai": ["OPENAI_API_KEY"],
    "litellm": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "gemini": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
    "mistral": ["MISTRAL_API_KEY"],
}


def _check_environment(config: ProjectConfig) -> list[CheckResult]:
    """Check required API keys and database URL."""
    results: list[CheckResult] = []

    # Check each engine profile for required env vars
    for profile_name, profile in config.engine_profiles.items():
        if profile.kind == "cli":
            results.append(CheckResult(
                name=f"env_profile_{profile_name}",
                passed=True,
                message=(
                    f"Engine profile '{profile_name}' is CLI-based — "
                    f"no API key needed"
                ),
                category="environment",
            ))
            continue

        # Determine required env vars from model or provider
        required_vars: list[str] = []
        model = profile.model or ""
        for prefix, env_vars in _MODEL_ENV_VARS.items():
            if model.startswith(prefix):
                required_vars = env_vars
                break

        if not required_vars:
            provider = profile.provider or ""
            required_vars = _PROVIDER_ENV_VARS.get(provider, [])

        if not required_vars:
            results.append(CheckResult(
                name=f"env_profile_{profile_name}",
                passed=True,
                message=(
                    f"Engine profile '{profile_name}': no known env var "
                    f"requirements for provider '{profile.provider}'"
                ),
                category="environment",
            ))
            continue

        present = [v for v in required_vars if os.environ.get(v)]
        if present:
            results.append(CheckResult(
                name=f"env_profile_{profile_name}",
                passed=True,
                message=(
                    f"Engine profile '{profile_name}': required env var(s) "
                    f"found: {', '.join(present)}"
                ),
                category="environment",
            ))
        else:
            results.append(CheckResult(
                name=f"env_profile_{profile_name}",
                passed=False,
                message=(
                    f"Engine profile '{profile_name}': missing required "
                    f"env var(s) for model '{model}': "
                    f"{', '.join(required_vars)}"
                ),
                category="environment",
            ))

    # Check database URL if configured
    if config.database is not None:
        url = config.database.url
        if url and url.strip():
            results.append(CheckResult(
                name="database_url",
                passed=True,
                message=f"Database URL is set: {url[:30]}...",
                category="environment",
            ))
        else:
            results.append(CheckResult(
                name="database_url",
                passed=False,
                message="Database URL is configured but empty",
                category="environment",
            ))

    return results
```

Update `check_project` — add after cross-reference checks:

```python
    # --- Environment checks ---
    results.extend(_check_environment(config))
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | tail -30
```

**Expected output:** All tests PASSED.

**Step 5: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py
git commit -m "feat(cli): add environment checks for API keys and database URL"
```

**If Task Fails:**
1. **`config.database` shape:** Check Chunk 1 `DatabaseConfig` model has `url` field.
2. **monkeypatch issues:** `raising=False` should handle missing vars.
3. **Rollback:** `git checkout -- miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py`

---

## Task 11: Run Code Review

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY):**

**Critical/High/Medium Issues:**
- Fix immediately (do NOT add TODO comments for these severities)
- Re-run all 3 reviewers in parallel after fixes
- Repeat until zero Critical/High/Medium issues remain

**Low Issues:**
- Add `TODO(review):` comments in code at the relevant location
- Format: `TODO(review): [Issue description] (reported by [reviewer] on [date], severity: Low)`

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location
- Format: `FIXME(nitpick): [Issue description] (reported by [reviewer] on [date], severity: Cosmetic)`

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low issues have TODO(review): comments added
   - All Cosmetic issues have FIXME(nitpick): comments added

---

## Task 12: Create `commands/check.py` — Click command adapter

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/check.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/test_check.py`

**Prerequisites:**
- Task 10 complete (all checks implemented)
- File must exist: `miniautogen/cli/main.py` with `cli` Click group and `run_async`
- File must exist: `miniautogen/cli/config.py` with `find_project_root`, `load_config`
- File must exist: `miniautogen/cli/output.py` with `echo_table`, `echo_json`, `echo_error`, `echo_success`
- File must exist: `miniautogen/cli/errors.py` with `CLIError`, `ProjectNotFoundError`, `ConfigError`

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/__init__.py` (empty):

```python
```

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/test_check.py`:

```python
"""Tests for the `miniautogen check` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from miniautogen.cli.main import cli


def _scaffold_project(root: Path) -> None:
    """Create a minimal valid project structure for testing."""
    config_data = {
        "project": {"name": "test-project", "version": "0.1.0"},
        "defaults": {"engine_profile": "default_api"},
        "engine_profiles": {
            "default_api": {
                "kind": "api",
                "provider": "litellm",
                "model": "gpt-4o-mini",
            }
        },
        "pipelines": {
            "main": {"target": "os.path:join"},
        },
    }
    (root / "miniautogen.yaml").write_text(yaml.dump(config_data))

    # Valid agent
    agents_dir = root / "agents"
    agents_dir.mkdir()
    (agents_dir / "researcher.yaml").write_text(yaml.dump({
        "id": "researcher",
        "version": "1.0",
        "name": "Researcher",
        "role": "Research assistant",
        "goal": "Find info",
        "engine_profile": "default_api",
        "skills": {"example": {"attached": []}},
        "tool_access": {"mode": "allowlist", "allow": ["web_search"]},
    }))

    # Valid skill
    skill_dir = root / "skills" / "example"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Example\n")
    (skill_dir / "skill.yaml").write_text(yaml.dump({
        "id": "example",
        "version": "1.0",
        "name": "Example",
        "description": "Example skill",
    }))

    # Valid tool
    tools_dir = root / "tools"
    tools_dir.mkdir()
    (tools_dir / "web_search.yaml").write_text(yaml.dump({
        "name": "web_search",
        "description": "Search the web",
        "input_schema": {"type": "object"},
        "execution": {"kind": "function", "target": "t:run"},
    }))

    # Pipeline file
    pipelines_dir = root / "pipelines"
    pipelines_dir.mkdir()
    (pipelines_dir / "main.py").write_text("def build_pipeline(): pass\n")


class TestCheckCommandText:
    def test_all_checks_pass(
        self, tmp_path: Path, monkeypatch: None,
    ) -> None:
        import os

        os.environ["OPENAI_API_KEY"] = "sk-test-123"
        _scaffold_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli, ["check"], catch_exceptions=False,
            env={"OPENAI_API_KEY": "sk-test-123"},
        )
        assert result.exit_code == 0, result.output

    def test_exit_code_1_on_failure(self, tmp_path: Path) -> None:
        _scaffold_project(tmp_path)
        # Break an agent reference
        agents_dir = tmp_path / "agents"
        (agents_dir / "broken.yaml").write_text("not: valid: agent")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["check"],
            env={"OPENAI_API_KEY": "sk-test-123"},
        )
        assert result.exit_code == 1

    def test_no_project_found_error(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["check"])
        assert result.exit_code != 0
        assert "project" in result.output.lower() or result.exit_code == 66


class TestCheckCommandJson:
    def test_json_format_output(self, tmp_path: Path) -> None:
        _scaffold_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli, ["check", "--format", "json"],
            env={"OPENAI_API_KEY": "sk-test-123"},
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        for item in data:
            assert "name" in item
            assert "passed" in item
            assert "message" in item
            assert "category" in item
```

**Step 2: Run the test to verify it fails**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/commands/test_check.py -v --no-header 2>&1 | head -20
```

**Expected output:**
```
FAILED ... - (command not registered or import error)
```

**Step 3: Write the check command**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/check.py`:

```python
"""``miniautogen check`` — validate project configuration and environment."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import click

from miniautogen.cli.config import find_project_root, load_config
from miniautogen.cli.errors import ConfigError, ProjectNotFoundError
from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error, echo_success, echo_table
from miniautogen.cli.services.check_project import check_project


@click.command("check")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text table or JSON).",
)
@run_async
async def check(output_format: str) -> None:
    """Validate project configuration, specs, and environment."""
    project_root = find_project_root(Path.cwd())
    if project_root is None:
        raise ProjectNotFoundError(
            "No miniautogen.yaml found in current directory or parents. "
            "Run 'miniautogen init <name>' to create a project."
        )

    config_path = project_root / "miniautogen.yaml"
    try:
        config = load_config(config_path)
    except Exception as exc:
        raise ConfigError(f"Failed to load config: {exc}") from exc

    results = await check_project(config, project_root)

    if output_format == "json":
        click.echo(json.dumps(
            [asdict(r) for r in results],
            indent=2,
        ))
    else:
        # Text table output
        rows = []
        for r in results:
            status = click.style("PASS", fg="green") if r.passed else click.style("FAIL", fg="red")
            rows.append([status, r.category, r.name, r.message])

        if rows:
            echo_table(
                headers=["Status", "Category", "Check", "Message"],
                rows=rows,
            )
        else:
            click.echo("No checks to run.")

        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed)
        total = len(results)
        click.echo("")
        if failed == 0:
            echo_success(f"All {total} checks passed")
        else:
            echo_error(f"{failed}/{total} checks failed")

    if any(not r.passed for r in results):
        sys.exit(1)
```

**Step 4: Register the command with the CLI group**

Modify `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/main.py` — add at the bottom of the file, after the `cli` function:

```python
from miniautogen.cli.commands.check import check  # noqa: E402

cli.add_command(check)
```

**Important:** If Chunk 1 already registered other commands (like `init`) at the bottom of `main.py`, add the `check` import next to them. The pattern should be:

```python
# Register commands
from miniautogen.cli.commands.init import init  # noqa: E402
from miniautogen.cli.commands.check import check  # noqa: E402

cli.add_command(init)
cli.add_command(check)
```

**Step 5: Run tests to verify they pass**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/commands/test_check.py -v --no-header 2>&1 | tail -15
```

**Expected output:**
```
tests/cli/commands/test_check.py::TestCheckCommandText::test_all_checks_pass PASSED
tests/cli/commands/test_check.py::TestCheckCommandText::test_exit_code_1_on_failure PASSED
tests/cli/commands/test_check.py::TestCheckCommandText::test_no_project_found_error PASSED
tests/cli/commands/test_check.py::TestCheckCommandJson::test_json_format_output PASSED
```

**Step 6: Verify CLI integration**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m miniautogen check --help
```

**Expected output:**
```
Usage: python -m miniautogen check [OPTIONS]

  Validate project configuration, specs, and environment.

Options:
  --format [text|json]  Output format (text table or JSON).
  --help                Show this message and exit.
```

**Step 7: Lint check**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/cli/commands/check.py tests/cli/commands/test_check.py
```

**Expected output:** No issues.

**Step 8: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/commands/check.py miniautogen/cli/main.py tests/cli/commands/__init__.py tests/cli/commands/test_check.py
git commit -m "feat(cli): add 'miniautogen check' command with text/json output"
```

**If Task Fails:**
1. **CliRunner can't find project:** The `CliRunner` runs in a temporary environment. The tests use `_scaffold_project` which writes to `tmp_path`, but the `check` command uses `Path.cwd()` to find the project root. You may need to monkeypatch `Path.cwd()` or set `MINIAUTOGEN_PROJECT_ROOT` env var. If so, update `find_project_root` to also check an env var, or monkeypatch in tests:
   ```python
   monkeypatch.chdir(tmp_path)
   ```
   Add `monkeypatch` parameter to test methods and call `monkeypatch.chdir(tmp_path)` before `runner.invoke`.
2. **`run_async` not working:** Verify the decorator from Chunk 1 bridges async to sync correctly. If `anyio.from_thread.run` fails, try `anyio.run`:
   ```python
   def run_async(func):
       @functools.wraps(func)
       def wrapper(*args, **kwargs):
           return anyio.from_thread.run(func, *args, **kwargs)
       return wrapper
   ```
   If that does not work, use:
   ```python
   def run_async(func):
       @functools.wraps(func)
       def wrapper(*args, **kwargs):
           return anyio.run(func, *args, **kwargs)
       return wrapper
   ```
3. **Rollback:** `git checkout -- miniautogen/cli/commands/check.py miniautogen/cli/main.py tests/cli/commands/`

---

## Task 13: Run full test suite and lint

**Files:**
- No new files

**Prerequisites:**
- Task 12 complete

**Step 1: Run all check-related tests**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/ -v --no-header 2>&1 | tail -40
```

**Expected output:** All tests PASSED.

**Step 2: Run ruff on all new files**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/cli/models.py miniautogen/cli/services/check_project.py miniautogen/cli/commands/check.py tests/cli/test_models.py tests/cli/services/test_check_project.py tests/cli/commands/test_check.py
```

**Expected output:** No issues (or fix any reported issues).

**Step 3: Run full project test suite to verify no regressions**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest --co -q 2>&1 | tail -3
```

**Expected output:** Test count should be >= previous count (500+).

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest --timeout=120 -x -q 2>&1 | tail -10
```

**Expected output:** All tests pass.

**Step 4: Fix any regressions**

If tests fail:
- Read the error messages carefully
- Fix the issue in the appropriate file
- Re-run the failing test to verify the fix
- Re-run the full suite

**Step 5: Commit any fixes**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add -u
git commit -m "fix(cli): resolve lint/test issues in check command"
```

**If Task Fails:**
1. **Existing tests break:** Check if new imports in `main.py` cause circular imports. Move command registration to a lazy pattern if needed.
2. **Rollback:** `git stash` and investigate.

---

## Task 14: Run Code Review (Final)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY):**

**Critical/High/Medium Issues:**
- Fix immediately (do NOT add TODO comments for these severities)
- Re-run all 3 reviewers in parallel after fixes
- Repeat until zero Critical/High/Medium issues remain

**Low Issues:**
- Add `TODO(review):` comments in code at the relevant location

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low issues have TODO(review): comments added
   - All Cosmetic issues have FIXME(nitpick): comments added

---

## Summary of files created/modified

**New files:**
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/models.py` — CLI validation models
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/check_project.py` — Check service
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/check.py` — Click command
- `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_models.py` — Model tests
- `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/__init__.py` — Package init
- `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_check_project.py` — Service tests
- `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/__init__.py` — Package init
- `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/test_check.py` — Command tests

**Modified files:**
- `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/main.py` — Register check command

**Check coverage:**

| Check | Type | Check Name Pattern |
|-------|------|--------------------|
| Config schema valid | static | `config_schema` |
| Agent YAML valid | static | `agent_{name}` |
| Skill dir valid | static | `skill_{name}` |
| Tool YAML valid | static | `tool_{name}` |
| Pipeline targets resolve | static | `pipeline_target_{name}` |
| Default engine profile exists | static | `default_engine_profile` |
| Agent engine profile refs | static | `engine_profile_ref_{agent}` |
| Agent -> skill cross-ref | static | `xref_{agent}_skill_{skill}` |
| Agent -> tool cross-ref | static | `xref_{agent}_tool_{tool}` |
| API keys per engine profile | environment | `env_profile_{name}` |
| Database URL valid | environment | `database_url` |
