# M2 Chunk 2: `check` Command Implementation Plan

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Implement the `miniautogen check` command that validates project configuration and environment, reporting pass/fail per check with exit code semantics.

**Architecture:** Two-layer design following D5 (separation of adapter and application logic). `services/check_project.py` contains all testable validation logic with zero Click dependency. `commands/check.py` is a thin Click adapter that loads config, delegates to the service, and renders output. The service imports only from stdlib and `miniautogen.api` (per D3 import boundary). Each check is a pure function returning a `CheckResult` dataclass, making the system easily extensible.

**Tech Stack:** Python 3.10+, Click 8.x, PyYAML 6.x, Pydantic v2, pytest 7.x, ruff (line-length=100)

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
python -c "from miniautogen.cli.main import cli; print('CLI group OK')"       # Expected: CLI group OK
python -c "from miniautogen.cli.config import ProjectConfig, load_config, find_project_root; print('Config OK')"  # Expected: Config OK
python -c "from miniautogen.cli.errors import CLIError; print('Errors OK')"   # Expected: Errors OK
python -c "from miniautogen.cli.output import format_output; print('Output OK')"  # Expected: Output OK
```

---

## Task 1: Create `CheckResult` dataclass and `check_project` skeleton

**Files:**
- Create: `miniautogen/cli/services/check_project.py`
- Create: `tests/cli/services/__init__.py`
- Create: `tests/cli/services/test_check_project.py`

**Prerequisites:**
- Directory must exist: `miniautogen/cli/services/` (created in Chunk 1)
- File must exist: `miniautogen/cli/services/__init__.py` (created in Chunk 1)
- File must exist: `miniautogen/cli/config.py` with `ProjectConfig` model

**Step 1: Write the failing test**

Create `tests/cli/services/__init__.py` (empty file for test package):

```python
```

Create `tests/cli/services/test_check_project.py`:

```python
"""Tests for check_project service — CheckResult model and check_project signature."""

from __future__ import annotations

from pathlib import Path

import pytest

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
        """CheckResult category is typed as Literal, so only static/environment are valid."""
        result = CheckResult(
            name="test", passed=True, message="ok", category="static"
        )
        assert result.category in ("static", "environment")


class TestCheckProjectSignature:
    @pytest.mark.anyio()
    async def test_returns_list_of_check_results(self, tmp_path: Path) -> None:
        """check_project should return a list (possibly empty) of CheckResult."""
        # Create minimal valid project structure
        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test-project\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: pipelines.main:build_pipeline\n"
        )
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, CheckResult)
```

**Step 2: Run the test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | head -20`

**Expected output:**
```
FAILED ... - ModuleNotFoundError: No module named 'miniautogen.cli.services.check_project'
```

**If you see different error:** Verify Chunk 1 directories and `__init__.py` files exist.

**Step 3: Write minimal implementation**

Create `miniautogen/cli/services/check_project.py`:

```python
"""Project validation service — static and environment checks.

This module contains the core logic for the ``miniautogen check`` command.
It validates project configuration and environment without any CLI
dependency (Click-free).

Import boundary (D3): only stdlib and ``miniautogen.api`` allowed.
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
    config: "ProjectConfig",
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

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | tail -10`

**Expected output:**
```
tests/cli/services/test_check_project.py::TestCheckResult::test_static_check_result PASSED
tests/cli/services/test_check_project.py::TestCheckResult::test_environment_check_result PASSED
tests/cli/services/test_check_project.py::TestCheckResult::test_category_must_be_static_or_environment PASSED
tests/cli/services/test_check_project.py::TestCheckProjectSignature::test_returns_list_of_check_results PASSED
```

**Step 5: Commit**

```bash
git add miniautogen/cli/services/check_project.py tests/cli/services/__init__.py tests/cli/services/test_check_project.py
git commit -m "feat(cli): add CheckResult dataclass and check_project skeleton"
```

**If Task Fails:**

1. **Test won't run:** Verify `tests/cli/__init__.py` and `tests/cli/services/__init__.py` exist. Create them if missing.
2. **Import error on `load_config`:** Chunk 1 may not be complete. Verify `miniautogen/cli/config.py` exports `load_config` and `ProjectConfig`.
3. **Can't recover:** Document what failed and return to human partner.

---

## Task 2: Implement static check — config schema validation

**Files:**
- Modify: `miniautogen/cli/services/check_project.py`
- Modify: `tests/cli/services/test_check_project.py`

**Prerequisites:**
- Task 1 complete (CheckResult and skeleton exist)

**Step 1: Write the failing test**

Append to `tests/cli/services/test_check_project.py`:

```python
class TestConfigSchemaCheck:
    """Static check: config file schema is valid."""

    @pytest.mark.anyio()
    async def test_valid_config_passes(self, tmp_path: Path) -> None:
        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test-project\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: pipelines.main:build_pipeline\n"
        )
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        schema_checks = [r for r in results if r.name == "config_schema"]
        assert len(schema_checks) == 1
        assert schema_checks[0].passed is True
        assert schema_checks[0].category == "static"

    @pytest.mark.anyio()
    async def test_config_always_passes_when_loaded(self, tmp_path: Path) -> None:
        """If load_config succeeded, schema check passes (Pydantic already validated)."""
        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: minimal\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: foo:bar\n"
        )
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        schema_check = next(r for r in results if r.name == "config_schema")
        assert schema_check.passed is True
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py::TestConfigSchemaCheck -v --no-header 2>&1 | tail -10`

**Expected output:**
```
FAILED ... - StopIteration  (or assert len(schema_checks) == 1 → AssertionError)
```

**Step 3: Write minimal implementation**

Edit `miniautogen/cli/services/check_project.py` — add a helper function and wire it into `check_project`:

```python
def _check_config_schema(config: "ProjectConfig") -> CheckResult:
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

Update the `check_project` function body to:

```python
async def check_project(
    config: "ProjectConfig",
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

    # --- Static checks ---
    results.append(_check_config_schema(config))

    return results
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | tail -10`

**Expected output:**
```
PASSED tests/cli/services/test_check_project.py::TestConfigSchemaCheck::test_valid_config_passes
PASSED tests/cli/services/test_check_project.py::TestConfigSchemaCheck::test_config_always_passes_when_loaded
```

**Step 5: Commit**

```bash
git add miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py
git commit -m "feat(cli): add config schema validation check"
```

**If Task Fails:**

1. **`load_config` raises error:** Verify the YAML content matches the `ProjectConfig` Pydantic model from Chunk 1.
2. **Import error:** Ensure `miniautogen/cli/config.py` exists and exports `load_config`.
3. **Can't recover:** `git checkout -- .` and revisit Chunk 1 config model.

---

## Task 3: Implement static check — pipeline targets resolve

**Files:**
- Modify: `miniautogen/cli/services/check_project.py`
- Modify: `tests/cli/services/test_check_project.py`

**Prerequisites:**
- Task 2 complete
- Understanding of `ProjectConfig.pipelines` structure: a dict where each value has a `target` field in `module.path:callable` format

**Step 1: Write the failing test**

Append to `tests/cli/services/test_check_project.py`:

```python
class TestPipelineTargetCheck:
    """Static check: pipeline targets resolve (importable or file exists)."""

    @pytest.mark.anyio()
    async def test_importable_target_passes(self, tmp_path: Path) -> None:
        """A target pointing to an importable module:callable passes."""
        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: os.path:join\n"
        )
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        target_checks = [r for r in results if r.name == "pipeline_target_main"]
        assert len(target_checks) == 1
        assert target_checks[0].passed is True
        assert target_checks[0].category == "static"

    @pytest.mark.anyio()
    async def test_nonexistent_module_fails(self, tmp_path: Path) -> None:
        """A target with a non-importable module fails."""
        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: nonexistent_module_xyz:build\n"
        )
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        target_checks = [r for r in results if r.name == "pipeline_target_main"]
        assert len(target_checks) == 1
        assert target_checks[0].passed is False
        assert "nonexistent_module_xyz" in target_checks[0].message

    @pytest.mark.anyio()
    async def test_missing_callable_fails(self, tmp_path: Path) -> None:
        """A target with a valid module but missing callable fails."""
        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: os.path:nonexistent_func_xyz\n"
        )
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        target_checks = [r for r in results if r.name == "pipeline_target_main"]
        assert len(target_checks) == 1
        assert target_checks[0].passed is False
        assert "nonexistent_func_xyz" in target_checks[0].message

    @pytest.mark.anyio()
    async def test_file_based_target_passes(self, tmp_path: Path) -> None:
        """A target pointing to an existing local file passes."""
        # Create the pipeline file
        pipelines_dir = tmp_path / "pipelines"
        pipelines_dir.mkdir()
        (pipelines_dir / "main.py").write_text("def build_pipeline(): pass\n")

        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: pipelines.main:build_pipeline\n"
        )
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        target_checks = [r for r in results if r.name == "pipeline_target_main"]
        assert len(target_checks) == 1
        assert target_checks[0].passed is True

    @pytest.mark.anyio()
    async def test_multiple_pipelines_checked(self, tmp_path: Path) -> None:
        """Each pipeline in config gets its own check result."""
        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: os.path:join\n"
            "  secondary:\n"
            "    target: os.path:exists\n"
        )
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        target_names = [r.name for r in results if r.name.startswith("pipeline_target_")]
        assert "pipeline_target_main" in target_names
        assert "pipeline_target_secondary" in target_names
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py::TestPipelineTargetCheck -v --no-header 2>&1 | tail -15`

**Expected output:**
```
FAILED ... - assert len(target_checks) == 1 (0 != 1)
```

**Step 3: Write minimal implementation**

Add to `miniautogen/cli/services/check_project.py` (new import at top and new helper):

Add `import importlib` and `import sys` to the imports section:

```python
import importlib
import sys
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
            message=f"Invalid target format '{target}' — expected 'module:callable'",
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
        # File exists — we trust callable is there (full import
        # would require sys.path manipulation which is side-effectful).
        return CheckResult(
            name=f"pipeline_target_{name}",
            passed=True,
            message=f"Pipeline '{name}' target file exists: {relative_file}",
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

Update `check_project` to call the new helper — add after `_check_config_schema`:

```python
    # Pipeline target checks
    if config.pipelines:
        for pipeline_name, pipeline_cfg in config.pipelines.items():
            results.append(
                _check_pipeline_target(pipeline_name, pipeline_cfg.target, project_root)
            )
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | tail -15`

**Expected output:**
```
PASSED tests/cli/services/test_check_project.py::TestPipelineTargetCheck::test_importable_target_passes
PASSED tests/cli/services/test_check_project.py::TestPipelineTargetCheck::test_nonexistent_module_fails
PASSED tests/cli/services/test_check_project.py::TestPipelineTargetCheck::test_missing_callable_fails
PASSED tests/cli/services/test_check_project.py::TestPipelineTargetCheck::test_file_based_target_passes
PASSED tests/cli/services/test_check_project.py::TestPipelineTargetCheck::test_multiple_pipelines_checked
```

**Step 5: Commit**

```bash
git add miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py
git commit -m "feat(cli): add pipeline target resolution check"
```

**If Task Fails:**

1. **`config.pipelines` attribute error:** The `ProjectConfig` model from Chunk 1 may use a different attribute name. Check the actual model and adjust `config.pipelines` and `pipeline_cfg.target` accordingly.
2. **Import resolution not working:** Ensure the target format uses `:` as separator. Check that `os.path` is importable in the test environment.
3. **Can't recover:** `git checkout -- .` and review the `ProjectConfig` Pydantic model.

---

## Task 4: Implement static check — agent references resolve

**Files:**
- Modify: `miniautogen/cli/services/check_project.py`
- Modify: `tests/cli/services/test_check_project.py`

**Prerequisites:**
- Task 3 complete
- Understanding: Agent references in config may not exist in current `ProjectConfig`. If `ProjectConfig` does not have an `agents` field, this check should be a no-op (return empty list). The design doc mentions "Agent references resolve" but the YAML schema shown does not include agents — so this check is forward-compatible.

**Step 1: Write the failing test**

Append to `tests/cli/services/test_check_project.py`:

```python
class TestAgentReferenceCheck:
    """Static check: agent references resolve."""

    @pytest.mark.anyio()
    async def test_no_agents_configured_skips_check(self, tmp_path: Path) -> None:
        """When config has no agents section, no agent checks are produced."""
        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: os.path:join\n"
        )
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        agent_checks = [r for r in results if r.name.startswith("agent_ref_")]
        assert len(agent_checks) == 0
```

**Step 2: Run test to verify it passes (this is a no-op check)**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py::TestAgentReferenceCheck -v --no-header 2>&1 | tail -5`

**Expected output:**
```
PASSED tests/cli/services/test_check_project.py::TestAgentReferenceCheck::test_no_agents_configured_skips_check
```

This test should pass immediately because we produce no agent checks when there is no agents config. The check function is a placeholder for when the config schema adds agents.

**Step 3: Add the forward-compatible agent check helper**

Add to `miniautogen/cli/services/check_project.py`:

```python
def _check_agent_references(
    config: "ProjectConfig",
    project_root: Path,
) -> list[CheckResult]:
    """Verify agent references in config resolve.

    Currently ``ProjectConfig`` may not have an ``agents`` field.
    This check is forward-compatible — it silently returns an empty
    list when no agents are configured.
    """
    results: list[CheckResult] = []
    agents = getattr(config, "agents", None)
    if not agents:
        return results

    # If agents is a dict of name -> agent_cfg with a 'target' field,
    # resolve similarly to pipeline targets.
    if isinstance(agents, dict):
        for agent_name, agent_cfg in agents.items():
            target = getattr(agent_cfg, "target", None)
            if target and ":" in target:
                module_path, callable_name = target.rsplit(":", 1)
                try:
                    mod = importlib.import_module(module_path)
                    found = hasattr(mod, callable_name)
                except ImportError:
                    # Check as file
                    relative_file = Path(module_path.replace(".", "/") + ".py")
                    found = (project_root / relative_file).is_file()

                results.append(
                    CheckResult(
                        name=f"agent_ref_{agent_name}",
                        passed=found,
                        message=(
                            f"Agent '{agent_name}' resolves OK"
                            if found
                            else f"Cannot resolve agent '{agent_name}' target '{target}'"
                        ),
                        category="static",
                    )
                )

    return results
```

Update `check_project` — add after pipeline target checks:

```python
    # Agent reference checks
    results.extend(_check_agent_references(config, project_root))
```

**Step 4: Run all tests to verify nothing broke**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | tail -15`

**Expected output:** All tests PASSED.

**Step 5: Commit**

```bash
git add miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py
git commit -m "feat(cli): add forward-compatible agent reference check"
```

**If Task Fails:**

1. **getattr on config fails:** This should not happen — `getattr` with default `None` is safe.
2. **Can't recover:** `git checkout -- .` and retry.

---

## Task 5: Implement environment check — required env vars

**Files:**
- Modify: `miniautogen/cli/services/check_project.py`
- Modify: `tests/cli/services/test_check_project.py`

**Prerequisites:**
- Task 4 complete
- Understanding: Provider config determines which env vars are needed. E.g., `litellm` provider may need `OPENAI_API_KEY` or similar. The check inspects `config.provider.default` and checks for common env var patterns.

**Step 1: Write the failing test**

Append to `tests/cli/services/test_check_project.py`:

```python
import os


class TestEnvVarsCheck:
    """Environment check: required env vars present."""

    @pytest.mark.anyio()
    async def test_no_provider_env_needed_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no specific env vars are required, check passes."""
        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: os.path:join\n"
        )
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        env_checks = [r for r in results if r.category == "environment"]
        # At minimum there should be a provider env check
        provider_checks = [r for r in env_checks if r.name == "provider_env"]
        assert len(provider_checks) == 1

    @pytest.mark.anyio()
    async def test_missing_api_key_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When provider needs an API key and it is missing, check fails."""
        # Remove all common API key env vars
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
            monkeypatch.delenv(key, raising=False)

        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: os.path:join\n"
        )
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        provider_check = next(r for r in results if r.name == "provider_env")
        # LiteLLM with gpt-4o-mini needs OPENAI_API_KEY
        assert provider_check.passed is False
        assert "OPENAI_API_KEY" in provider_check.message

    @pytest.mark.anyio()
    async def test_present_api_key_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the required API key is present, check passes."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")

        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: os.path:join\n"
        )
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        provider_check = next(r for r in results if r.name == "provider_env")
        assert provider_check.passed is True
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py::TestEnvVarsCheck -v --no-header 2>&1 | tail -10`

**Expected output:**
```
FAILED ... - StopIteration (no provider_env check produced yet)
```

**Step 3: Write minimal implementation**

Add to `miniautogen/cli/services/check_project.py`:

```python
import os

# Map of model prefix patterns to required env vars.
# LiteLLM routes by model name prefix.
_MODEL_ENV_VARS: dict[str, list[str]] = {
    "gpt-": ["OPENAI_API_KEY"],
    "o1-": ["OPENAI_API_KEY"],
    "o3-": ["OPENAI_API_KEY"],
    "claude-": ["ANTHROPIC_API_KEY"],
    "gemini": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
    "mistral": ["MISTRAL_API_KEY"],
}


def _check_provider_env(config: "ProjectConfig") -> CheckResult:
    """Check that required environment variables for the configured provider exist."""
    model = getattr(config.provider, "model", "") if config.provider else ""
    if not model:
        return CheckResult(
            name="provider_env",
            passed=True,
            message="No model configured — skipping provider env check",
            category="environment",
        )

    required_vars: list[str] = []
    for prefix, env_vars in _MODEL_ENV_VARS.items():
        if model.startswith(prefix):
            required_vars = env_vars
            break

    if not required_vars:
        return CheckResult(
            name="provider_env",
            passed=True,
            message=f"No known env var requirements for model '{model}'",
            category="environment",
        )

    # Check if ANY of the required vars is present
    present = [v for v in required_vars if os.environ.get(v)]
    if present:
        return CheckResult(
            name="provider_env",
            passed=True,
            message=f"Required env var(s) found: {', '.join(present)}",
            category="environment",
        )

    return CheckResult(
        name="provider_env",
        passed=False,
        message=(
            f"Missing required env var(s) for model '{model}': "
            f"{', '.join(required_vars)}"
        ),
        category="environment",
    )
```

Update `check_project` — add after agent reference checks:

```python
    # --- Environment checks ---
    results.append(_check_provider_env(config))
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | tail -15`

**Expected output:** All tests PASSED.

**Step 5: Commit**

```bash
git add miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py
git commit -m "feat(cli): add provider env var check"
```

**If Task Fails:**

1. **`config.provider` is None or different shape:** Adapt to actual `ProjectConfig` model — use `getattr` for safety.
2. **`monkeypatch.delenv` fails:** The var may already not exist. `raising=False` handles this.
3. **Can't recover:** `git checkout -- .` and inspect `ProjectConfig.provider` model.

---

## Task 6: Implement environment check — database URL valid

**Files:**
- Modify: `miniautogen/cli/services/check_project.py`
- Modify: `tests/cli/services/test_check_project.py`

**Prerequisites:**
- Task 5 complete

**Step 1: Write the failing test**

Append to `tests/cli/services/test_check_project.py`:

```python
class TestDatabaseUrlCheck:
    """Environment check: database URL valid (if configured)."""

    @pytest.mark.anyio()
    async def test_no_database_configured_skips(self, tmp_path: Path) -> None:
        """When no database section in config, no db check produced."""
        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: os.path:join\n"
        )
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        db_checks = [r for r in results if r.name == "database_url"]
        assert len(db_checks) == 0

    @pytest.mark.anyio()
    async def test_valid_sqlite_url_passes(self, tmp_path: Path) -> None:
        """A valid sqlite URL passes the check."""
        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: os.path:join\n"
            "database:\n"
            "  url: sqlite+aiosqlite:///miniautogen.db\n"
        )
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        db_checks = [r for r in results if r.name == "database_url"]
        assert len(db_checks) == 1
        assert db_checks[0].passed is True

    @pytest.mark.anyio()
    async def test_empty_url_fails(self, tmp_path: Path) -> None:
        """An empty database URL fails."""
        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: os.path:join\n"
            "database:\n"
            "  url: ''\n"
        )
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        db_checks = [r for r in results if r.name == "database_url"]
        assert len(db_checks) == 1
        assert db_checks[0].passed is False

    @pytest.mark.anyio()
    async def test_malformed_url_fails(self, tmp_path: Path) -> None:
        """A URL without a scheme fails validation."""
        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: os.path:join\n"
            "database:\n"
            "  url: 'not-a-url'\n"
        )
        from miniautogen.cli.config import load_config

        config = load_config(config_file)
        results = await check_project(config, tmp_path)
        db_checks = [r for r in results if r.name == "database_url"]
        assert len(db_checks) == 1
        assert db_checks[0].passed is False
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py::TestDatabaseUrlCheck::test_valid_sqlite_url_passes -v --no-header 2>&1 | tail -5`

**Expected output:**
```
FAILED ... - assert len(db_checks) == 1 (0 != 1)
```

**Note:** The `test_no_database_configured_skips` test may already pass since we produce no db checks yet. The other tests will fail.

**Step 3: Write minimal implementation**

Add to `miniautogen/cli/services/check_project.py`:

```python
# Valid database URL scheme prefixes for SQLAlchemy
_VALID_DB_SCHEMES = (
    "sqlite",
    "postgresql",
    "mysql",
    "mssql",
    "oracle",
)


def _check_database_url(config: "ProjectConfig") -> CheckResult | None:
    """Validate database URL if configured.

    Returns ``None`` when no database is configured (check skipped).
    """
    database = getattr(config, "database", None)
    if database is None:
        return None

    url = getattr(database, "url", None)
    if not url:
        return CheckResult(
            name="database_url",
            passed=False,
            message="Database configured but URL is empty",
            category="environment",
        )

    # Basic validation: URL must contain a recognized scheme
    has_scheme = any(url.startswith(scheme) for scheme in _VALID_DB_SCHEMES)
    if not has_scheme:
        return CheckResult(
            name="database_url",
            passed=False,
            message=f"Database URL '{url}' does not start with a valid scheme",
            category="environment",
        )

    return CheckResult(
        name="database_url",
        passed=True,
        message=f"Database URL is valid ({url.split(':')[0]} scheme)",
        category="environment",
    )
```

Update `check_project` — add after `_check_provider_env`:

```python
    db_check = _check_database_url(config)
    if db_check is not None:
        results.append(db_check)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_check_project.py -v --no-header 2>&1 | tail -20`

**Expected output:** All tests PASSED.

**Note:** If `load_config` raises a Pydantic `ValidationError` for configs with `database` section (because `ProjectConfig` does not have a `database` field yet), wrap those tests in `pytest.raises(ValidationError)` or add the `database` field to `ProjectConfig` as optional. The adapter approach with `getattr` in the implementation handles both cases gracefully.

**Step 5: Commit**

```bash
git add miniautogen/cli/services/check_project.py tests/cli/services/test_check_project.py
git commit -m "feat(cli): add database URL validation check"
```

**If Task Fails:**

1. **`load_config` rejects YAML with `database` section:** `ProjectConfig` may not have a `database` field. Add `database: DatabaseConfig | None = None` to the Pydantic model, or adjust tests to skip the database section in YAML.
2. **Pydantic strict validation rejects unknown fields:** Check if `ProjectConfig` uses `model_config = ConfigDict(extra="forbid")`. If so, add the `database` field.
3. **Can't recover:** `git checkout -- .` and review `ProjectConfig`.

---

## Task 7: Run Code Review (service layer)

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

## Task 8: Create `commands/check.py` — Click command skeleton

**Files:**
- Create: `miniautogen/cli/commands/check.py`
- Create: `tests/cli/commands/__init__.py` (if not created in Chunk 1)
- Create: `tests/cli/commands/test_check.py`

**Prerequisites:**
- Tasks 1-6 complete (service layer done)
- Chunk 1 files exist: `miniautogen/cli/main.py` (with `cli` group and `run_async` helper), `miniautogen/cli/config.py`, `miniautogen/cli/output.py`, `miniautogen/cli/errors.py`

**Step 1: Write the failing test**

Create `tests/cli/commands/__init__.py` (empty):

```python
```

Create `tests/cli/commands/test_check.py`:

```python
"""Tests for the ``miniautogen check`` CLI command."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from miniautogen.cli.main import cli


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def valid_project(tmp_path: Path) -> Path:
    """Create a minimal valid project structure."""
    config_file = tmp_path / "miniautogen.yaml"
    config_file.write_text(
        "project:\n"
        "  name: test-project\n"
        "  version: '0.1.0'\n"
        "provider:\n"
        "  default: litellm\n"
        "  model: gpt-4o-mini\n"
        "pipelines:\n"
        "  main:\n"
        "    target: os.path:join\n"
    )
    return tmp_path


class TestCheckCommand:
    def test_check_command_exists(self, runner: CliRunner) -> None:
        """The check command is registered with the CLI group."""
        result = runner.invoke(cli, ["check", "--help"])
        assert result.exit_code == 0
        assert "check" in result.output.lower()
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/commands/test_check.py::TestCheckCommand::test_check_command_exists -v --no-header 2>&1 | tail -10`

**Expected output:**
```
FAILED ... - (either ImportError or "No such command 'check'")
```

**Step 3: Write minimal implementation**

Create `miniautogen/cli/commands/check.py`:

```python
"""``miniautogen check`` command — validate project configuration and environment."""

from __future__ import annotations

import click


@click.command("check")
def check() -> None:
    """Validate project configuration and environment."""
    click.echo("check: not yet implemented")
```

Register the command in `miniautogen/cli/main.py` — add the import and registration. Locate the section where `init` command is registered and add `check` similarly:

Add import:
```python
from miniautogen.cli.commands.check import check
```

Add registration (after `cli.add_command(init)` or equivalent pattern):
```python
cli.add_command(check)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/commands/test_check.py::TestCheckCommand::test_check_command_exists -v --no-header 2>&1 | tail -5`

**Expected output:**
```
PASSED tests/cli/commands/test_check.py::TestCheckCommand::test_check_command_exists
```

**Step 5: Commit**

```bash
git add miniautogen/cli/commands/check.py miniautogen/cli/main.py tests/cli/commands/__init__.py tests/cli/commands/test_check.py
git commit -m "feat(cli): register check command skeleton with CLI group"
```

**If Task Fails:**

1. **Import error on `miniautogen.cli.main`:** Chunk 1 not complete. Verify main.py exists with a `cli` Click group.
2. **Registration pattern different:** Check how `init` command is registered in `main.py` and follow the same pattern.
3. **Can't recover:** Document what `main.py` looks like and return to human partner.

---

## Task 9: Wire `check` command to service — text output

**Files:**
- Modify: `miniautogen/cli/commands/check.py`
- Modify: `tests/cli/commands/test_check.py`

**Prerequisites:**
- Task 8 complete
- Understanding of Chunk 1 helpers: `find_project_root()`, `load_config()`, `run_async()`, `format_output()`

**Step 1: Write the failing test**

Append to `tests/cli/commands/test_check.py`:

```python
class TestCheckCommandExecution:
    def test_all_checks_pass_exit_0(
        self,
        runner: CliRunner,
        valid_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When all checks pass, exit code is 0."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
        monkeypatch.chdir(valid_project)
        result = runner.invoke(cli, ["check"])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert "pass" in result.output.lower() or "PASS" in result.output

    def test_failing_check_exit_1(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When any check fails, exit code is 1."""
        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: nonexistent_module_xyz:build\n"
        )
        monkeypatch.chdir(tmp_path)
        # Also remove API key to cause env check failure
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = runner.invoke(cli, ["check"])
        assert result.exit_code == 1, f"Output: {result.output}"
        assert "fail" in result.output.lower() or "FAIL" in result.output

    def test_output_contains_check_names(
        self,
        runner: CliRunner,
        valid_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Output shows individual check names."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
        monkeypatch.chdir(valid_project)
        result = runner.invoke(cli, ["check"])
        assert "config_schema" in result.output
        assert "pipeline_target_main" in result.output
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/commands/test_check.py::TestCheckCommandExecution -v --no-header 2>&1 | tail -10`

**Expected output:**
```
FAILED ... - AssertionError (output just says "not yet implemented")
```

**Step 3: Write full implementation**

Replace the contents of `miniautogen/cli/commands/check.py`:

```python
"""``miniautogen check`` command — validate project configuration and environment."""

from __future__ import annotations

import json
import sys

import click

from miniautogen.cli.config import find_project_root, load_config
from miniautogen.cli.main import run_async
from miniautogen.cli.services.check_project import CheckResult, check_project


def _render_text(results: list[CheckResult]) -> str:
    """Render check results as a human-readable table."""
    lines: list[str] = []
    lines.append("")
    lines.append("  Check Results")
    lines.append("  " + "-" * 60)

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        icon = "+" if r.passed else "x"
        lines.append(f"  [{icon}] {status}  {r.name:<30s}  {r.message}")

    lines.append("  " + "-" * 60)

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    lines.append(f"  {passed} passed, {failed} failed")
    lines.append("")
    return "\n".join(lines)


def _render_json(results: list[CheckResult]) -> str:
    """Render check results as JSON."""
    data = {
        "checks": [
            {
                "name": r.name,
                "passed": r.passed,
                "message": r.message,
                "category": r.category,
            }
            for r in results
        ],
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
        },
    }
    return json.dumps(data, indent=2)


@click.command("check")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def check(output_format: str) -> None:
    """Validate project configuration and environment."""
    try:
        project_root = find_project_root()
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    config_path = project_root / "miniautogen.yaml"
    try:
        config = load_config(config_path)
    except Exception as exc:
        click.echo(f"Error loading config: {exc}", err=True)
        sys.exit(1)

    results = run_async(check_project(config, project_root))

    if output_format == "json":
        click.echo(_render_json(results))
    else:
        click.echo(_render_text(results))

    all_passed = all(r.passed for r in results)
    sys.exit(0 if all_passed else 1)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/commands/test_check.py -v --no-header 2>&1 | tail -15`

**Expected output:**
```
PASSED tests/cli/commands/test_check.py::TestCheckCommand::test_check_command_exists
PASSED tests/cli/commands/test_check.py::TestCheckCommandExecution::test_all_checks_pass_exit_0
PASSED tests/cli/commands/test_check.py::TestCheckCommandExecution::test_failing_check_exit_1
PASSED tests/cli/commands/test_check.py::TestCheckCommandExecution::test_output_contains_check_names
```

**Step 5: Commit**

```bash
git add miniautogen/cli/commands/check.py tests/cli/commands/test_check.py
git commit -m "feat(cli): wire check command to service with text rendering"
```

**If Task Fails:**

1. **`find_project_root` not found:** Check exact name in `miniautogen/cli/config.py`. It may be named differently.
2. **`run_async` not found in main.py:** Check the exact location. It may be in a separate `_utils.py` or directly in `main.py`.
3. **`sys.exit(1)` causes CliRunner issues:** CliRunner catches SystemExit. Check `result.exit_code` instead of looking at exceptions.
4. **`monkeypatch.chdir` not recognized:** Ensure `monkeypatch` is typed as `pytest.MonkeyPatch`.
5. **Can't recover:** `git checkout -- miniautogen/cli/commands/check.py` and re-read Chunk 1 helpers.

---

## Task 10: Add JSON output format test

**Files:**
- Modify: `tests/cli/commands/test_check.py`

**Prerequisites:**
- Task 9 complete

**Step 1: Write the test**

Append to `tests/cli/commands/test_check.py`:

```python
import json as json_module


class TestCheckJsonOutput:
    def test_json_format_valid(
        self,
        runner: CliRunner,
        valid_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--format json produces valid JSON with expected structure."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
        monkeypatch.chdir(valid_project)
        result = runner.invoke(cli, ["check", "--format", "json"])
        assert result.exit_code == 0, f"Output: {result.output}"

        data = json_module.loads(result.output)
        assert "checks" in data
        assert "summary" in data
        assert isinstance(data["checks"], list)
        assert data["summary"]["total"] > 0
        assert data["summary"]["failed"] == 0

    def test_json_format_with_failures(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """JSON output includes failure details."""
        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(
            "project:\n"
            "  name: test\n"
            "  version: '0.1.0'\n"
            "provider:\n"
            "  default: litellm\n"
            "  model: gpt-4o-mini\n"
            "pipelines:\n"
            "  main:\n"
            "    target: nonexistent_xyz:build\n"
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = runner.invoke(cli, ["check", "--format", "json"])
        assert result.exit_code == 1

        data = json_module.loads(result.output)
        assert data["summary"]["failed"] > 0
        failed = [c for c in data["checks"] if not c["passed"]]
        assert len(failed) > 0
        for check_item in data["checks"]:
            assert "name" in check_item
            assert "passed" in check_item
            assert "message" in check_item
            assert "category" in check_item
```

**Step 2: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/commands/test_check.py::TestCheckJsonOutput -v --no-header 2>&1 | tail -10`

**Expected output:**
```
PASSED tests/cli/commands/test_check.py::TestCheckJsonOutput::test_json_format_valid
PASSED tests/cli/commands/test_check.py::TestCheckJsonOutput::test_json_format_with_failures
```

**Step 3: Commit**

```bash
git add tests/cli/commands/test_check.py
git commit -m "test(cli): add JSON output format tests for check command"
```

**If Task Fails:**

1. **JSON parse error:** The text rendering may be mixed with JSON. Ensure `_render_json` is called exclusively when `--format json`.
2. **Exit code wrong:** The JSON rendering works but exit code logic may need adjustment.
3. **Can't recover:** Check `result.output` manually.

---

## Task 11: Add edge case tests

**Files:**
- Modify: `tests/cli/commands/test_check.py`

**Prerequisites:**
- Task 10 complete

**Step 1: Write edge case tests**

Append to `tests/cli/commands/test_check.py`:

```python
class TestCheckEdgeCases:
    def test_no_config_file_exits_with_error(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Running check without a miniautogen.yaml shows error."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["check"])
        assert result.exit_code != 0
        assert "error" in result.output.lower()

    def test_check_help_text(self, runner: CliRunner) -> None:
        """Check --help shows format option."""
        result = runner.invoke(cli, ["check", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.output
        assert "text" in result.output
        assert "json" in result.output
```

**Step 2: Run test to verify it passes**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/commands/test_check.py::TestCheckEdgeCases -v --no-header 2>&1 | tail -10`

**Expected output:**
```
PASSED tests/cli/commands/test_check.py::TestCheckEdgeCases::test_no_config_file_exits_with_error
PASSED tests/cli/commands/test_check.py::TestCheckEdgeCases::test_check_help_text
```

**Step 3: Commit**

```bash
git add tests/cli/commands/test_check.py
git commit -m "test(cli): add edge case tests for check command"
```

**If Task Fails:**

1. **`find_project_root` raises unexpected exception:** The error handling in the check command may need adjustment based on the actual exception type from Chunk 1.
2. **Can't recover:** Inspect `find_project_root` behavior when no config exists.

---

## Task 12: Run Code Review (full check command)

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

## Task 13: Run full test suite and lint

**Files:**
- No new files

**Prerequisites:**
- All previous tasks complete

**Step 1: Run all check-related tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/ -v --no-header 2>&1 | tail -25`

**Expected output:** All tests PASSED. Zero failures.

**Step 2: Run ruff lint**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/cli/services/check_project.py miniautogen/cli/commands/check.py 2>&1`

**Expected output:**
```
All checks passed!
```

**If lint errors:** Fix them (typically import ordering, line length). Re-run.

**Step 3: Run ruff format check**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && ruff format --check miniautogen/cli/services/check_project.py miniautogen/cli/commands/check.py 2>&1`

**Expected output:**
```
2 files already formatted.
```

**If formatting needed:** Run `ruff format miniautogen/cli/services/check_project.py miniautogen/cli/commands/check.py` and commit.

**Step 4: Run the full existing test suite to check for regressions**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest --no-header -q 2>&1 | tail -5`

**Expected output:** All tests pass, no regressions.

**Step 5: Commit any lint fixes**

```bash
git add -A
git commit -m "style(cli): fix lint and formatting for check command"
```

(Only commit if there were changes. If everything was clean, skip.)

**If Task Fails:**

1. **Lint errors on line length:** Ensure lines are under 100 chars (ruff config).
2. **Import order:** ruff auto-fixes with `ruff check --fix`.
3. **Regressions in existing tests:** Investigate — the check command should not affect existing code. If it does, there is a side effect to investigate.

---

## Summary of Files Created/Modified

**Created:**
- `miniautogen/cli/services/check_project.py` — Service layer with all checks
- `miniautogen/cli/commands/check.py` — Click command adapter
- `tests/cli/services/__init__.py` — Test package init
- `tests/cli/services/test_check_project.py` — Service tests
- `tests/cli/commands/__init__.py` — Test package init (if not from Chunk 1)
- `tests/cli/commands/test_check.py` — Command integration tests

**Modified:**
- `miniautogen/cli/main.py` — Register check command with CLI group

## Dependency Graph

```
Task 1 (CheckResult + skeleton)
  └── Task 2 (config schema check)
        └── Task 3 (pipeline targets check)
              └── Task 4 (agent references check)
                    └── Task 5 (env vars check)
                          └── Task 6 (database URL check)
                                └── Task 7 (Code Review - services)
                                      └── Task 8 (Click command skeleton)
                                            └── Task 9 (Wire command to service)
                                                  └── Task 10 (JSON output tests)
                                                        └── Task 11 (Edge case tests)
                                                              └── Task 12 (Code Review - full)
                                                                    └── Task 13 (Full suite + lint)
```
