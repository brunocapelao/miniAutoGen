# Milestone 2 — Chunk 1: CLI Foundation + init Command

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Set up CLI infrastructure (main group, config, errors, output) and implement `miniautogen init <name>` that scaffolds a multi-agent project with agents, skills, tools, mcp, memory, and pipelines.

> **Note — Project layouts:** Two valid project structures are supported (see agent-architecture-spec.md). The CLI `init` command generates the **flat/per-registry layout** by default (agents/, skills/, tools/, mcp/, memory/, pipelines/ at project root). The per-agent layout (resources nested under each agent directory) is also valid but not scaffolded by `init`.

**Architecture:** CLI as pure SDK consumer. `commands/` are Click adapters (parse args, render output). `services/` contain testable application logic that never touches Click. `config.py` handles YAML project resolution with Pydantic v2 models. All CLI code may only import from `miniautogen.api` and `miniautogen.cli.*` — never from internal modules (`core`, `stores`, `backends`, etc.). An architectural import boundary test enforces this.

**Tech Stack:** Python 3.10+, Click 8+, PyYAML 6+, Jinja2 3.1+, Pydantic v2, AnyIO 4+, pytest 7+, ruff (line-length=100)

**Global Prerequisites:**
- Environment: macOS, Python 3.10 or 3.11
- Tools: `python --version`, `pytest --version`, `ruff --version`, `poetry --version`
- State: Work from `main` branch, clean working tree
- Existing: `miniautogen/api.py` with public exports, 500+ tests passing

**Verification before starting:**
```bash
cd /Users/brunocapelao/Projects/miniAutoGen
python --version        # Expected: Python 3.10.x or 3.11.x
pytest --version        # Expected: pytest 7.x
ruff --version          # Expected: ruff 0.15+
poetry --version        # Expected: Poetry 1.x or 2.x
git status              # Expected: clean working tree (untracked docs ok)
pytest --co -q 2>&1 | tail -1  # Expected: "NNN tests collected"
```

---

## Task 1: Add click and pyyaml dependencies to pyproject.toml

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/pyproject.toml`

**Prerequisites:**
- File exists: `/Users/brunocapelao/Projects/miniAutoGen/pyproject.toml`

**Step 1: Add click and pyyaml to `[tool.poetry.dependencies]`**

Open `/Users/brunocapelao/Projects/miniAutoGen/pyproject.toml` and add two lines after the `httpx` dependency:

```toml
click = ">=8.0"
pyyaml = ">=6.0"
```

The `[tool.poetry.dependencies]` section should now contain (showing last 3 lines + new):

```toml
httpx = ">=0.28.0"
click = ">=8.0"
pyyaml = ">=6.0"
```

**Step 2: Add poetry scripts entry point**

Add this new section after `[tool.poetry.group.dev.dependencies]` and before `[tool.ruff]`:

```toml
[tool.poetry.scripts]
miniautogen = "miniautogen.cli.main:cli"
```

**Step 3: Install dependencies**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry lock --no-update && poetry install
```

**Expected output:** Lock file updated, packages installed without errors.

**Step 4: Verify imports**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -c "import click; import yaml; print('click', click.__version__); print('pyyaml OK')"
```

**Expected output:**
```
click 8.x.x
pyyaml OK
```

**Step 5: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add pyproject.toml poetry.lock
git commit -m "feat(cli): add click and pyyaml dependencies + CLI entry point"
```

**If Task Fails:**
1. `poetry lock` fails: Check version constraints are valid. Try `poetry lock` without `--no-update`.
2. Import fails: Run `poetry install` again, check virtualenv is active.
3. Rollback: `git checkout -- pyproject.toml`

---

## Task 2: Create CLI foundation — main.py, __main__.py, and package __init__.py files

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/main.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/__main__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/__init__.py`

**Prerequisites:**
- Task 1 complete (click installed)

**Step 1: Create directory structure**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen
mkdir -p miniautogen/cli/commands miniautogen/cli/services miniautogen/cli/templates/project/agents miniautogen/cli/templates/project/skills/example miniautogen/cli/templates/project/tools miniautogen/cli/templates/project/memory miniautogen/cli/templates/project/pipelines tests/cli
```

**Expected output:** No output (directories created silently).

**Step 2: Create `miniautogen/cli/__init__.py`**

```python
"""MiniAutoGen CLI — developer-facing command-line interface."""
```

**Step 3: Create `miniautogen/cli/commands/__init__.py`**

```python
"""CLI command adapters."""
```

**Step 4: Create `miniautogen/cli/services/__init__.py`**

```python
"""CLI application services — testable logic, no Click dependency."""
```

**Step 5: Create `tests/cli/__init__.py`**

```python
```

(Empty file.)

**Step 6: Create `miniautogen/cli/main.py`**

```python
"""Click group and async bridge for the MiniAutoGen CLI."""

from __future__ import annotations

import functools
from typing import Any

import anyio
import click


def run_async(func):  # noqa: ANN001, ANN201
    """Decorator that bridges an async Click command to sync Click entry."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return anyio.from_thread.run(func, *args, **kwargs)

    return wrapper


@click.group()
@click.version_option(package_name="miniautogen")
def cli() -> None:
    """MiniAutoGen — Multi-agent orchestration framework."""
```

**Step 7: Create `miniautogen/__main__.py`**

```python
"""Allow `python -m miniautogen` to launch the CLI."""

from miniautogen.cli.main import cli

cli()
```

**Step 8: Verify CLI loads**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m miniautogen --help
```

**Expected output:**
```
Usage: python -m miniautogen [OPTIONS] COMMAND [ARGS]...

  MiniAutoGen — Multi-agent orchestration framework.

Options:
  --version  Show the version number and exit.
  --help     Show this message and exit.
```

**Step 9: Verify `--version`**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m miniautogen --version
```

**Expected output:**
```
python -m miniautogen, version 0.1.0
```

**Step 10: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/__main__.py miniautogen/cli/ tests/cli/__init__.py
git commit -m "feat(cli): create CLI foundation with Click group and async bridge"
```

**If Task Fails:**
1. Import error on `anyio`: Verify `poetry install` was run (anyio is an existing dependency).
2. `--version` shows wrong version: Check `pyproject.toml` has `version = "0.1.0"`.
3. Rollback: `git checkout -- miniautogen/ tests/`

---

## Task 3: Create config.py with full ProjectConfig Pydantic model

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/config.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_config.py`

**Prerequisites:**
- Task 2 complete (cli package exists)
- `pydantic>=2.5.0` installed (existing dependency)
- `pyyaml>=6.0` installed (Task 1)

**Step 1: Write failing tests for ProjectConfig**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_config.py`:

```python
"""Tests for CLI config loading and ProjectConfig model."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


class TestEngineProfileConfig:
    def test_api_profile(self) -> None:
        from miniautogen.cli.config import EngineProfileConfig

        profile = EngineProfileConfig(
            kind="api",
            provider="litellm",
            model="gpt-4o-mini",
            temperature=0.2,
        )
        assert profile.kind == "api"
        assert profile.provider == "litellm"
        assert profile.model == "gpt-4o-mini"
        assert profile.temperature == 0.2
        assert profile.command is None

    def test_cli_profile(self) -> None:
        from miniautogen.cli.config import EngineProfileConfig

        profile = EngineProfileConfig(
            kind="cli",
            provider="gemini",
            command="gemini",
        )
        assert profile.kind == "cli"
        assert profile.command == "gemini"
        assert profile.model is None

    def test_default_temperature(self) -> None:
        from miniautogen.cli.config import EngineProfileConfig

        profile = EngineProfileConfig(kind="api", provider="litellm")
        assert profile.temperature == 0.2


class TestProjectConfig:
    def test_full_config(self) -> None:
        from miniautogen.cli.config import ProjectConfig

        data = {
            "project": {"name": "test-project", "version": "0.1.0"},
            "defaults": {"engine_profile": "default_api"},
            "engine_profiles": {
                "default_api": {
                    "kind": "api",
                    "provider": "litellm",
                    "model": "gpt-4o-mini",
                    "temperature": 0.2,
                }
            },
            "pipelines": {"main": {"target": "pipelines.main:build_pipeline"}},
            "database": {"url": "sqlite+aiosqlite:///miniautogen.db"},
        }
        config = ProjectConfig(**data)
        assert config.project.name == "test-project"
        assert config.project.version == "0.1.0"
        assert config.defaults.engine_profile == "default_api"
        assert config.engine_profiles["default_api"].kind == "api"
        assert config.pipelines["main"].target == "pipelines.main:build_pipeline"
        assert config.database is not None
        assert config.database.url == "sqlite+aiosqlite:///miniautogen.db"

    def test_config_without_database(self) -> None:
        from miniautogen.cli.config import ProjectConfig

        data = {
            "project": {"name": "test-project", "version": "0.1.0"},
            "defaults": {"engine_profile": "default_api"},
            "engine_profiles": {
                "default_api": {"kind": "api", "provider": "litellm"}
            },
            "pipelines": {"main": {"target": "pipelines.main:build_pipeline"}},
        }
        config = ProjectConfig(**data)
        assert config.database is None


class TestFindProjectRoot:
    def test_finds_root_with_yaml(self, tmp_path: Path) -> None:
        from miniautogen.cli.config import find_project_root

        (tmp_path / "miniautogen.yaml").write_text("project:\n  name: test\n")
        sub = tmp_path / "a" / "b"
        sub.mkdir(parents=True)
        found = find_project_root(sub)
        assert found == tmp_path

    def test_returns_none_when_not_found(self, tmp_path: Path) -> None:
        from miniautogen.cli.config import find_project_root

        found = find_project_root(tmp_path)
        assert found is None


class TestLoadConfig:
    def test_loads_yaml_into_model(self, tmp_path: Path) -> None:
        from miniautogen.cli.config import load_config

        yaml_content = {
            "project": {"name": "loaded-project", "version": "1.0.0"},
            "defaults": {"engine_profile": "default_api"},
            "engine_profiles": {
                "default_api": {
                    "kind": "api",
                    "provider": "litellm",
                    "model": "gpt-4o-mini",
                }
            },
            "pipelines": {"main": {"target": "pipelines.main:build_pipeline"}},
            "database": {"url": "sqlite+aiosqlite:///test.db"},
        }
        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(yaml.dump(yaml_content))
        config = load_config(config_file)
        assert config.project.name == "loaded-project"
        assert config.engine_profiles["default_api"].provider == "litellm"

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        from miniautogen.cli.config import load_config

        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_raises_on_invalid_yaml(self, tmp_path: Path) -> None:
        from miniautogen.cli.config import load_config

        config_file = tmp_path / "miniautogen.yaml"
        config_file.write_text(": invalid: yaml: {{{")
        with pytest.raises(Exception):
            load_config(config_file)
```

**Step 2: Run tests to verify they fail**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/test_config.py -v 2>&1 | head -30
```

**Expected output:** All tests FAIL with `ImportError` or `ModuleNotFoundError` — the config module does not exist yet.

**Step 3: Implement config.py**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/config.py`:

```python
"""Project configuration resolution and Pydantic models.

Responsible for:
- Finding the project root (walks up to find miniautogen.yaml)
- Loading and validating miniautogen.yaml into typed Pydantic models
- Providing EngineProfileConfig, DefaultsConfig, PipelineConfig,
  DatabaseConfig, and the root ProjectConfig
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

CONFIG_FILENAME = "miniautogen.yaml"


class ProjectMeta(BaseModel):
    """Project-level metadata."""

    name: str
    version: str = "0.1.0"


class DefaultsConfig(BaseModel):
    """Project-wide defaults."""

    engine_profile: str
    memory_profile: str = "default"


class EngineProfileConfig(BaseModel):
    """Engine profile — defines how an agent runs."""

    kind: Literal["api", "cli"]
    provider: str
    model: str | None = None
    command: str | None = None
    temperature: float = 0.2


class PipelineConfig(BaseModel):
    """Pipeline reference — a Python import path target."""

    target: str


class DatabaseConfig(BaseModel):
    """Database connection configuration."""

    url: str


class ProjectConfig(BaseModel):
    """Root project configuration parsed from miniautogen.yaml."""

    project: ProjectMeta
    defaults: DefaultsConfig
    engine_profiles: dict[str, EngineProfileConfig]
    memory_profiles: dict[str, dict[str, Any]] = {}
    pipelines: dict[str, PipelineConfig]
    database: DatabaseConfig | None = None


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from *start* looking for miniautogen.yaml.

    Returns the directory containing the config file, or None.
    """
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        if (directory / CONFIG_FILENAME).is_file():
            return directory
    return None


def load_config(path: Path) -> ProjectConfig:
    """Load and validate a miniautogen.yaml file.

    Args:
        path: Exact path to the YAML config file.

    Returns:
        A validated ProjectConfig instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If YAML parsing fails.
        pydantic.ValidationError: If the data does not match the schema.
    """
    if not path.is_file():
        msg = f"Config file not found: {path}"
        raise FileNotFoundError(msg)
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return ProjectConfig(**data)
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/test_config.py -v
```

**Expected output:**
```
tests/cli/test_config.py::TestEngineProfileConfig::test_api_profile PASSED
tests/cli/test_config.py::TestEngineProfileConfig::test_cli_profile PASSED
tests/cli/test_config.py::TestEngineProfileConfig::test_default_temperature PASSED
tests/cli/test_config.py::TestProjectConfig::test_full_config PASSED
tests/cli/test_config.py::TestProjectConfig::test_config_without_database PASSED
tests/cli/test_config.py::TestFindProjectRoot::test_finds_root_with_yaml PASSED
tests/cli/test_config.py::TestFindProjectRoot::test_returns_none_when_not_found PASSED
tests/cli/test_config.py::TestLoadConfig::test_loads_yaml_into_model PASSED
tests/cli/test_config.py::TestLoadConfig::test_raises_on_missing_file PASSED
tests/cli/test_config.py::TestLoadConfig::test_raises_on_invalid_yaml PASSED

10 passed
```

**Step 5: Lint check**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/cli/config.py tests/cli/test_config.py
```

**Expected output:** `All checks passed!` (or no output = no issues)

**Step 6: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/config.py tests/cli/test_config.py
git commit -m "feat(cli): add ProjectConfig model with YAML loading and project root discovery"
```

**If Task Fails:**
1. Pydantic validation error in tests: Check field names match exactly (`engine_profile`, not `engine-profile`).
2. YAML parse error: Ensure `yaml.safe_load` is used, not `yaml.load`.
3. Rollback: `git checkout -- miniautogen/cli/config.py tests/cli/test_config.py`

---

## Task 4: Create errors.py — CLI error hierarchy and exit codes

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/errors.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_errors.py`

**Prerequisites:**
- Task 2 complete (cli package exists)

**Step 1: Write failing tests**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_errors.py`:

```python
"""Tests for CLI error hierarchy and exit codes."""

from __future__ import annotations


class TestCLIErrorHierarchy:
    def test_base_error(self) -> None:
        from miniautogen.cli.errors import CLIError

        err = CLIError("something went wrong")
        assert str(err) == "something went wrong"
        assert err.exit_code == 1

    def test_config_error(self) -> None:
        from miniautogen.cli.errors import ConfigError

        err = ConfigError("bad config")
        assert isinstance(err, Exception)
        assert err.exit_code == 78

    def test_project_not_found_error(self) -> None:
        from miniautogen.cli.errors import ProjectNotFoundError

        err = ProjectNotFoundError("no project here")
        assert err.exit_code == 66

    def test_scaffold_error(self) -> None:
        from miniautogen.cli.errors import ScaffoldError

        err = ScaffoldError("cannot create")
        assert err.exit_code == 73

    def test_pipeline_error(self) -> None:
        from miniautogen.cli.errors import PipelineError

        err = PipelineError("pipeline failed")
        assert err.exit_code == 70


class TestExitCodes:
    def test_exit_code_constants(self) -> None:
        from miniautogen.cli.errors import (
            EX_CANTCREAT,
            EX_CONFIG,
            EX_NOINPUT,
            EX_OK,
            EX_SOFTWARE,
            EX_USAGE,
        )

        assert EX_OK == 0
        assert EX_USAGE == 64
        assert EX_NOINPUT == 66
        assert EX_SOFTWARE == 70
        assert EX_CANTCREAT == 73
        assert EX_CONFIG == 78
```

**Step 2: Run tests to verify they fail**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/test_errors.py -v 2>&1 | head -20
```

**Expected output:** All tests FAIL with `ImportError`.

**Step 3: Implement errors.py**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/errors.py`:

```python
"""CLI error hierarchy and sysexits-compatible exit codes.

Exit codes follow the BSD sysexits convention (see sysexits.h).
"""

from __future__ import annotations

# --- Exit code constants (BSD sysexits) ---
EX_OK = 0
EX_USAGE = 64
EX_NOINPUT = 66
EX_SOFTWARE = 70
EX_CANTCREAT = 73
EX_CONFIG = 78


class CLIError(Exception):
    """Base exception for all CLI errors."""

    exit_code: int = 1

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


class ConfigError(CLIError):
    """Invalid or unparseable project configuration."""

    exit_code: int = EX_CONFIG


class ProjectNotFoundError(CLIError):
    """No miniautogen.yaml found in directory tree."""

    exit_code: int = EX_NOINPUT


class ScaffoldError(CLIError):
    """Failed to create project scaffold."""

    exit_code: int = EX_CANTCREAT


class PipelineError(CLIError):
    """Pipeline execution failure."""

    exit_code: int = EX_SOFTWARE
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/test_errors.py -v
```

**Expected output:**
```
tests/cli/test_errors.py::TestCLIErrorHierarchy::test_base_error PASSED
tests/cli/test_errors.py::TestCLIErrorHierarchy::test_config_error PASSED
tests/cli/test_errors.py::TestCLIErrorHierarchy::test_project_not_found_error PASSED
tests/cli/test_errors.py::TestCLIErrorHierarchy::test_scaffold_error PASSED
tests/cli/test_errors.py::TestCLIErrorHierarchy::test_pipeline_error PASSED
tests/cli/test_errors.py::TestExitCodes::test_exit_code_constants PASSED

6 passed
```

**Step 5: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/errors.py tests/cli/test_errors.py
git commit -m "feat(cli): add CLI error hierarchy with BSD sysexits codes"
```

**If Task Fails:**
1. Exit code mismatch: Verify class attribute `exit_code` is set as class-level, not only in `__init__`.
2. Rollback: `git checkout -- miniautogen/cli/errors.py tests/cli/test_errors.py`

---

## Task 5: Create output.py — terminal output helpers

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/output.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_output.py`

**Prerequisites:**
- Task 2 complete (cli package exists)
- `click>=8.0` installed (Task 1)

**Step 1: Write failing tests**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_output.py`:

```python
"""Tests for CLI output helpers."""

from __future__ import annotations

from unittest.mock import patch


class TestOutputHelpers:
    def test_echo_success(self) -> None:
        from miniautogen.cli.output import echo_success

        with patch("click.echo") as mock_echo:
            echo_success("done")
            mock_echo.assert_called_once()
            output = mock_echo.call_args[0][0]
            assert "done" in output

    def test_echo_error(self) -> None:
        from miniautogen.cli.output import echo_error

        with patch("click.echo") as mock_echo:
            echo_error("fail")
            mock_echo.assert_called_once()
            call_kwargs = mock_echo.call_args
            assert call_kwargs[1].get("err") is True

    def test_echo_info(self) -> None:
        from miniautogen.cli.output import echo_info

        with patch("click.echo") as mock_echo:
            echo_info("info message")
            mock_echo.assert_called_once()
            output = mock_echo.call_args[0][0]
            assert "info message" in output

    def test_echo_json(self) -> None:
        import json

        from miniautogen.cli.output import echo_json

        with patch("click.echo") as mock_echo:
            echo_json({"key": "value"})
            mock_echo.assert_called_once()
            output = mock_echo.call_args[0][0]
            parsed = json.loads(output)
            assert parsed == {"key": "value"}

    def test_echo_table(self) -> None:
        from miniautogen.cli.output import echo_table

        with patch("click.echo") as mock_echo:
            echo_table(
                headers=["Name", "Status"],
                rows=[["alpha", "ok"], ["beta", "fail"]],
            )
            assert mock_echo.call_count >= 1
```

**Step 2: Run tests to verify they fail**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/test_output.py -v 2>&1 | head -20
```

**Expected output:** All tests FAIL with `ImportError`.

**Step 3: Implement output.py**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/output.py`:

```python
"""Terminal output helpers for the MiniAutoGen CLI.

Provides colored output, JSON rendering, and basic table formatting.
This module only depends on click.echo for actual I/O.
"""

from __future__ import annotations

import json

import click


def echo_success(message: str) -> None:
    """Print a green success message."""
    click.echo(click.style(f"[OK] {message}", fg="green"))


def echo_error(message: str) -> None:
    """Print a red error message to stderr."""
    click.echo(click.style(f"[ERROR] {message}", fg="red"), err=True)


def echo_info(message: str) -> None:
    """Print a blue info message."""
    click.echo(click.style(f"[INFO] {message}", fg="blue"))


def echo_json(data: dict | list) -> None:
    """Print data as formatted JSON."""
    click.echo(json.dumps(data, indent=2, default=str))


def echo_table(headers: list[str], rows: list[list[str]]) -> None:
    """Print a simple aligned table.

    Args:
        headers: Column header names.
        rows: List of rows, each a list of string values.
    """
    if not rows:
        click.echo("(no data)")
        return

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    header_line = "  ".join(
        h.ljust(col_widths[i]) for i, h in enumerate(headers)
    )
    separator = "  ".join("-" * w for w in col_widths)
    click.echo(header_line)
    click.echo(separator)
    for row in rows:
        line = "  ".join(
            str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)
        )
        click.echo(line)
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/test_output.py -v
```

**Expected output:**
```
tests/cli/test_output.py::TestOutputHelpers::test_echo_success PASSED
tests/cli/test_output.py::TestOutputHelpers::test_echo_error PASSED
tests/cli/test_output.py::TestOutputHelpers::test_echo_info PASSED
tests/cli/test_output.py::TestOutputHelpers::test_echo_json PASSED
tests/cli/test_output.py::TestOutputHelpers::test_echo_table PASSED

5 passed
```

**Step 5: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/output.py tests/cli/test_output.py
git commit -m "feat(cli): add terminal output helpers (success, error, info, json, table)"
```

**If Task Fails:**
1. Mock not capturing call: Verify `patch("click.echo")` path is correct.
2. Rollback: `git checkout -- miniautogen/cli/output.py tests/cli/test_output.py`

---

## Task 6: Create ALL Jinja2 templates for project scaffolding

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/miniautogen.yaml.j2`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/agents/researcher.yaml.j2`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/skills/example/SKILL.md.j2`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/skills/example/skill.yaml.j2`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/tools/web_search.yaml.j2`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/memory/profiles.yaml.j2`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/pipelines/main.py.j2`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/.env.j2`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_templates.py`

**Prerequisites:**
- Task 2 complete (directory structure created)
- `jinja2>=3.1.0` installed (existing dependency)

**Step 1: Write failing test for template rendering**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_templates.py`:

```python
"""Tests that all project templates render without errors."""

from __future__ import annotations

from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "miniautogen"
    / "cli"
    / "templates"
    / "project"
)

CONTEXT = {
    "project_name": "test-project",
    "model": "gpt-4o-mini",
    "provider": "litellm",
}


class TestTemplateRendering:
    def _render(self, template_path: str) -> str:
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            keep_trailing_newline=True,
        )
        tmpl = env.get_template(template_path)
        return tmpl.render(**CONTEXT)

    def test_miniautogen_yaml_renders(self) -> None:
        result = self._render("miniautogen.yaml.j2")
        parsed = yaml.safe_load(result)
        assert parsed["project"]["name"] == "test-project"
        assert parsed["defaults"]["engine_profile"] == "default_api"
        assert parsed["defaults"]["memory_profile"] == "default"
        assert "default_api" in parsed["engine_profiles"]
        assert parsed["engine_profiles"]["default_api"]["model"] == "gpt-4o-mini"
        assert parsed["engine_profiles"]["default_api"]["provider"] == "litellm"
        assert "default" in parsed["memory_profiles"]
        assert parsed["memory_profiles"]["default"]["session"] is True
        assert parsed["pipelines"]["main"]["target"] == "pipelines.main:build_pipeline"
        assert "database" in parsed

    def test_researcher_yaml_renders(self) -> None:
        result = self._render("agents/researcher.yaml.j2")
        parsed = yaml.safe_load(result)
        assert parsed["id"] == "researcher"
        assert "skills" in parsed
        assert "tool_access" in parsed
        assert parsed["engine_profile"] == "default_api"
        assert parsed["memory"]["profile"] == "default"
        assert parsed["memory"]["session_memory"] is True

    def test_skill_yaml_renders(self) -> None:
        result = self._render("skills/example/skill.yaml.j2")
        parsed = yaml.safe_load(result)
        assert parsed["id"] == "example"
        assert parsed["name"] == "Example Skill"

    def test_skill_md_renders(self) -> None:
        result = self._render("skills/example/SKILL.md.j2")
        assert "Example Skill" in result

    def test_tool_yaml_renders(self) -> None:
        result = self._render("tools/web_search.yaml.j2")
        parsed = yaml.safe_load(result)
        assert parsed["name"] == "web_search"
        assert "input_schema" in parsed
        assert "execution" in parsed
        assert "policy" in parsed

    def test_pipeline_main_renders(self) -> None:
        result = self._render("pipelines/main.py.j2")
        assert "build_pipeline" in result
        assert "Pipeline" in result

    def test_env_renders(self) -> None:
        result = self._render(".env.j2")
        assert "MINIAUTOGEN" in result or "DATABASE_URL" in result

    def test_memory_profiles_yaml_renders(self) -> None:
        result = self._render("memory/profiles.yaml.j2")
        parsed = yaml.safe_load(result)
        assert "default" in parsed
        assert parsed["default"]["session"] is True

    def test_all_templates_exist(self) -> None:
        expected = [
            "miniautogen.yaml.j2",
            "agents/researcher.yaml.j2",
            "skills/example/SKILL.md.j2",
            "skills/example/skill.yaml.j2",
            "tools/web_search.yaml.j2",
            "memory/profiles.yaml.j2",
            "pipelines/main.py.j2",
            ".env.j2",
        ]
        for tmpl in expected:
            path = TEMPLATES_DIR / tmpl
            assert path.is_file(), f"Template missing: {tmpl}"
```

**Step 2: Run tests to verify they fail**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/test_templates.py -v 2>&1 | head -20
```

**Expected output:** Tests FAIL because templates do not exist.

**Step 3: Create `miniautogen.yaml.j2`**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/miniautogen.yaml.j2`:

```
project:
  name: {{ project_name }}
  version: "0.1.0"

defaults:
  engine_profile: default_api
  memory_profile: default

engine_profiles:
  default_api:
    kind: api
    provider: {{ provider }}
    model: {{ model }}
    temperature: 0.2

memory_profiles:
  default:
    session: true
    retrieval:
      enabled: false
    compaction:
      enabled: false

pipelines:
  main:
    target: pipelines.main:build_pipeline

database:
  url: sqlite+aiosqlite:///miniautogen.db
```

**Step 4: Create `agents/researcher.yaml.j2`**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/agents/researcher.yaml.j2`:

```
id: researcher
version: "1.0.0"
name: Research Specialist
role: Research Specialist
goal: Investigate topics and produce structured syntheses.

skills:
  attached:
    - example

tool_access:
  mode: allowlist
  allow:
    - web_search

engine_profile: default_api

memory:
  profile: default
  session_memory: true
  retrieval_memory: false
  max_context_tokens: 16000

runtime:
  max_turns: 10
  timeout_seconds: 300
```

**Step 5: Create `skills/example/skill.yaml.j2`**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/skills/example/skill.yaml.j2`:

```
id: example
version: "1.0.0"
name: Example Skill
description: A starter skill template.
```

**Step 6: Create `skills/example/SKILL.md.j2`**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/skills/example/SKILL.md.j2`:

```
# Example Skill

This is a starter skill template. Replace with your own instructions.
```

**Step 7: Create `tools/web_search.yaml.j2`**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/tools/web_search.yaml.j2`:

```
name: web_search
description: Search the web for relevant information.

input_schema:
  type: object
  properties:
    query:
      type: string
  required:
    - query

execution:
  kind: python
  target: miniautogen.tools.web_search:execute

policy:
  approval: none
  timeout_seconds: 30
```

**Step 8: Create `memory/profiles.yaml.j2`**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/memory/profiles.yaml.j2`:

```
# Memory profiles for {{ project_name }}
# Agents reference these profiles by name in their memory.profile field.

default:
  session: true
  retrieval:
    enabled: false
  compaction:
    enabled: false
```

**Step 9: Create `pipelines/main.py.j2`**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/pipelines/main.py.j2`:

```
"""Main pipeline for {{ project_name }}."""

from miniautogen.api import Pipeline


def build_pipeline() -> Pipeline:
    """Build and return the main pipeline.

    Customize this function to define your agent workflow.
    """
    pipeline = Pipeline(name="main")
    # Add your pipeline components here:
    # pipeline.add_component(...)
    return pipeline
```

**Step 10: Create `.env.j2`**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/.env.j2`:

```
# MiniAutoGen environment variables
# See: https://github.com/your-org/miniautogen

DATABASE_URL=sqlite+aiosqlite:///miniautogen.db

# Provider API keys (uncomment as needed)
# OPENAI_API_KEY=sk-...
# GEMINI_API_KEY=...
# ANTHROPIC_API_KEY=...

# MiniAutoGen settings
# MINIAUTOGEN_DEFAULT_PROVIDER={{ provider }}
# MINIAUTOGEN_DEFAULT_MODEL={{ model }}
# MINIAUTOGEN_DEFAULT_TIMEOUT_SECONDS=30
```

**Step 11: Run tests to verify they pass**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/test_templates.py -v
```

**Expected output:**
```
tests/cli/test_templates.py::TestTemplateRendering::test_miniautogen_yaml_renders PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_researcher_yaml_renders PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_skill_yaml_renders PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_skill_md_renders PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_tool_yaml_renders PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_memory_profiles_yaml_renders PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_pipeline_main_renders PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_env_renders PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_all_templates_exist PASSED

9 passed
```

**Step 12: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/templates/ tests/cli/test_templates.py
git commit -m "feat(cli): add Jinja2 templates for multi-agent project scaffold"
```

**If Task Fails:**
1. YAML parse error in rendered template: Check Jinja2 syntax — `{{ }}` must not conflict with YAML braces.
2. Template not found: Verify directory structure matches expected paths.
3. Rollback: `git checkout -- miniautogen/cli/templates/ tests/cli/test_templates.py`

---

## Task 7: Create services/init_project.py — scaffold service

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/init_project.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_init_service.py`

**Prerequisites:**
- Task 6 complete (templates exist)
- Task 3 complete (config models exist)
- Task 4 complete (errors exist)

**Step 1: Write failing tests for the init service**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_init_service.py`:

```python
"""Tests for init_project service — scaffolds a new MiniAutoGen project."""

from __future__ import annotations

from pathlib import Path

import yaml


class TestInitProject:
    def test_creates_project_directory(self, tmp_path: Path) -> None:
        from miniautogen.cli.services.init_project import init_project

        project_dir = tmp_path / "my-project"
        init_project(
            target_dir=project_dir,
            project_name="my-project",
            model="gpt-4o-mini",
            provider="litellm",
        )
        assert project_dir.is_dir()

    def test_creates_miniautogen_yaml(self, tmp_path: Path) -> None:
        from miniautogen.cli.services.init_project import init_project

        project_dir = tmp_path / "my-project"
        init_project(
            target_dir=project_dir,
            project_name="my-project",
            model="gpt-4o-mini",
            provider="litellm",
        )
        config_file = project_dir / "miniautogen.yaml"
        assert config_file.is_file()
        parsed = yaml.safe_load(config_file.read_text())
        assert parsed["project"]["name"] == "my-project"
        assert parsed["engine_profiles"]["default_api"]["model"] == "gpt-4o-mini"

    def test_creates_agent_spec(self, tmp_path: Path) -> None:
        from miniautogen.cli.services.init_project import init_project

        project_dir = tmp_path / "my-project"
        init_project(
            target_dir=project_dir,
            project_name="my-project",
            model="gpt-4o-mini",
            provider="litellm",
        )
        agent_file = project_dir / "agents" / "researcher.yaml"
        assert agent_file.is_file()
        parsed = yaml.safe_load(agent_file.read_text())
        assert parsed["id"] == "researcher"
        assert parsed["engine_profile"] == "default_api"

    def test_creates_skill_directory(self, tmp_path: Path) -> None:
        from miniautogen.cli.services.init_project import init_project

        project_dir = tmp_path / "my-project"
        init_project(
            target_dir=project_dir,
            project_name="my-project",
            model="gpt-4o-mini",
            provider="litellm",
        )
        skill_yaml = project_dir / "skills" / "example" / "skill.yaml"
        skill_md = project_dir / "skills" / "example" / "SKILL.md"
        assert skill_yaml.is_file()
        assert skill_md.is_file()
        parsed = yaml.safe_load(skill_yaml.read_text())
        assert parsed["id"] == "example"

    def test_creates_tool_spec(self, tmp_path: Path) -> None:
        from miniautogen.cli.services.init_project import init_project

        project_dir = tmp_path / "my-project"
        init_project(
            target_dir=project_dir,
            project_name="my-project",
            model="gpt-4o-mini",
            provider="litellm",
        )
        tool_file = project_dir / "tools" / "web_search.yaml"
        assert tool_file.is_file()
        parsed = yaml.safe_load(tool_file.read_text())
        assert parsed["name"] == "web_search"

    def test_creates_mcp_directory(self, tmp_path: Path) -> None:
        from miniautogen.cli.services.init_project import init_project

        project_dir = tmp_path / "my-project"
        init_project(
            target_dir=project_dir,
            project_name="my-project",
            model="gpt-4o-mini",
            provider="litellm",
        )
        mcp_dir = project_dir / "mcp"
        assert mcp_dir.is_dir()

    def test_creates_pipeline(self, tmp_path: Path) -> None:
        from miniautogen.cli.services.init_project import init_project

        project_dir = tmp_path / "my-project"
        init_project(
            target_dir=project_dir,
            project_name="my-project",
            model="gpt-4o-mini",
            provider="litellm",
        )
        pipeline_file = project_dir / "pipelines" / "main.py"
        assert pipeline_file.is_file()
        content = pipeline_file.read_text()
        assert "build_pipeline" in content

    def test_creates_env_file(self, tmp_path: Path) -> None:
        from miniautogen.cli.services.init_project import init_project

        project_dir = tmp_path / "my-project"
        init_project(
            target_dir=project_dir,
            project_name="my-project",
            model="gpt-4o-mini",
            provider="litellm",
        )
        env_file = project_dir / ".env"
        assert env_file.is_file()

    def test_raises_if_directory_exists(self, tmp_path: Path) -> None:
        import pytest

        from miniautogen.cli.errors import ScaffoldError
        from miniautogen.cli.services.init_project import init_project

        project_dir = tmp_path / "existing"
        project_dir.mkdir()
        (project_dir / "miniautogen.yaml").write_text("exists")

        with pytest.raises(ScaffoldError, match="already exists"):
            init_project(
                target_dir=project_dir,
                project_name="existing",
                model="gpt-4o-mini",
                provider="litellm",
            )

    def test_full_directory_structure(self, tmp_path: Path) -> None:
        from miniautogen.cli.services.init_project import init_project

        project_dir = tmp_path / "full-project"
        init_project(
            target_dir=project_dir,
            project_name="full-project",
            model="gpt-4o-mini",
            provider="litellm",
        )
        expected_files = [
            "miniautogen.yaml",
            "agents/researcher.yaml",
            "skills/example/skill.yaml",
            "skills/example/SKILL.md",
            "tools/web_search.yaml",
            "memory/profiles.yaml",
            "pipelines/main.py",
            ".env",
        ]
        expected_dirs = ["mcp"]
        for f in expected_files:
            assert (project_dir / f).is_file(), f"Missing file: {f}"
        for d in expected_dirs:
            assert (project_dir / d).is_dir(), f"Missing dir: {d}"

    def test_custom_model_and_provider(self, tmp_path: Path) -> None:
        from miniautogen.cli.services.init_project import init_project

        project_dir = tmp_path / "custom"
        init_project(
            target_dir=project_dir,
            project_name="custom",
            model="claude-3-opus",
            provider="anthropic",
        )
        config = yaml.safe_load(
            (project_dir / "miniautogen.yaml").read_text()
        )
        assert config["engine_profiles"]["default_api"]["model"] == "claude-3-opus"
        assert config["engine_profiles"]["default_api"]["provider"] == "anthropic"
```

**Step 2: Run tests to verify they fail**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/test_init_service.py -v 2>&1 | head -20
```

**Expected output:** All tests FAIL with `ImportError`.

**Step 3: Implement init_project service**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/init_project.py`:

```python
"""Project scaffolding service.

Creates a new MiniAutoGen project directory with the canonical
multi-agent structure: agents, skills, tools, mcp, pipelines.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from miniautogen.cli.errors import ScaffoldError

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "project"

# Maps template path (relative to templates/project/) to output path
# (relative to the project root).
_TEMPLATE_MAP: list[tuple[str, str]] = [
    ("miniautogen.yaml.j2", "miniautogen.yaml"),
    ("agents/researcher.yaml.j2", "agents/researcher.yaml"),
    ("skills/example/skill.yaml.j2", "skills/example/skill.yaml"),
    ("skills/example/SKILL.md.j2", "skills/example/SKILL.md"),
    ("tools/web_search.yaml.j2", "tools/web_search.yaml"),
    ("memory/profiles.yaml.j2", "memory/profiles.yaml"),
    ("pipelines/main.py.j2", "pipelines/main.py"),
    (".env.j2", ".env"),
]

# Directories that are created but have no template files.
_EMPTY_DIRS: list[str] = [
    "mcp",
]


def init_project(
    *,
    target_dir: Path,
    project_name: str,
    model: str = "gpt-4o-mini",
    provider: str = "litellm",
) -> Path:
    """Scaffold a new MiniAutoGen project.

    Args:
        target_dir: Directory to create (must not contain miniautogen.yaml).
        project_name: Name for the project config.
        model: Default LLM model name.
        provider: Default LLM provider name.

    Returns:
        The path to the created project directory.

    Raises:
        ScaffoldError: If the target already contains a miniautogen.yaml.
    """
    if target_dir.exists() and (target_dir / "miniautogen.yaml").exists():
        msg = f"Project already exists at {target_dir}"
        raise ScaffoldError(msg)

    target_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        keep_trailing_newline=True,
    )
    context = {
        "project_name": project_name,
        "model": model,
        "provider": provider,
    }

    for template_path, output_path in _TEMPLATE_MAP:
        out_file = target_dir / output_path
        out_file.parent.mkdir(parents=True, exist_ok=True)
        template = env.get_template(template_path)
        rendered = template.render(**context)
        out_file.write_text(rendered, encoding="utf-8")

    for empty_dir in _EMPTY_DIRS:
        (target_dir / empty_dir).mkdir(parents=True, exist_ok=True)

    return target_dir
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/test_init_service.py -v
```

**Expected output:**
```
tests/cli/test_init_service.py::TestInitProject::test_creates_project_directory PASSED
tests/cli/test_init_service.py::TestInitProject::test_creates_miniautogen_yaml PASSED
tests/cli/test_init_service.py::TestInitProject::test_creates_agent_spec PASSED
tests/cli/test_init_service.py::TestInitProject::test_creates_skill_directory PASSED
tests/cli/test_init_service.py::TestInitProject::test_creates_tool_spec PASSED
tests/cli/test_init_service.py::TestInitProject::test_creates_mcp_directory PASSED
tests/cli/test_init_service.py::TestInitProject::test_creates_pipeline PASSED
tests/cli/test_init_service.py::TestInitProject::test_creates_env_file PASSED
tests/cli/test_init_service.py::TestInitProject::test_raises_if_directory_exists PASSED
tests/cli/test_init_service.py::TestInitProject::test_full_directory_structure PASSED
tests/cli/test_init_service.py::TestInitProject::test_custom_model_and_provider PASSED

11 passed
```

**Step 5: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/services/init_project.py tests/cli/test_init_service.py
git commit -m "feat(cli): add init_project service with full multi-agent scaffold"
```

**If Task Fails:**
1. Template not found: Verify `_TEMPLATES_DIR` resolves correctly. Print `_TEMPLATES_DIR` to debug.
2. ScaffoldError not raised: Check condition — it only raises when `miniautogen.yaml` exists inside the dir.
3. Rollback: `git checkout -- miniautogen/cli/services/ tests/cli/test_init_service.py`

---

## Task 8: Create commands/init.py — Click command + register with group

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/init.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_init_command.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/main.py` (register command)

**Prerequisites:**
- Task 7 complete (init_project service exists)
- Task 5 complete (output helpers exist)
- Task 4 complete (error hierarchy exists)

**Step 1: Write failing tests for the init command (Click CliRunner)**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_init_command.py`:

```python
"""Tests for the 'miniautogen init' CLI command."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner


class TestInitCommand:
    def test_init_creates_project(self, tmp_path: Path) -> None:
        from miniautogen.cli.main import cli

        runner = CliRunner()
        project_dir = tmp_path / "new-project"
        result = runner.invoke(cli, ["init", str(project_dir)])
        assert result.exit_code == 0, result.output
        assert (project_dir / "miniautogen.yaml").is_file()

    def test_init_with_custom_model(self, tmp_path: Path) -> None:
        from miniautogen.cli.main import cli

        runner = CliRunner()
        project_dir = tmp_path / "custom-model"
        result = runner.invoke(
            cli,
            ["init", str(project_dir), "--model", "claude-3-opus"],
        )
        assert result.exit_code == 0, result.output
        config = yaml.safe_load(
            (project_dir / "miniautogen.yaml").read_text()
        )
        assert config["engine_profiles"]["default_api"]["model"] == "claude-3-opus"

    def test_init_with_custom_provider(self, tmp_path: Path) -> None:
        from miniautogen.cli.main import cli

        runner = CliRunner()
        project_dir = tmp_path / "custom-provider"
        result = runner.invoke(
            cli,
            ["init", str(project_dir), "--provider", "anthropic"],
        )
        assert result.exit_code == 0, result.output
        config = yaml.safe_load(
            (project_dir / "miniautogen.yaml").read_text()
        )
        assert config["engine_profiles"]["default_api"]["provider"] == "anthropic"

    def test_init_success_message(self, tmp_path: Path) -> None:
        from miniautogen.cli.main import cli

        runner = CliRunner()
        project_dir = tmp_path / "msg-project"
        result = runner.invoke(cli, ["init", str(project_dir)])
        assert result.exit_code == 0
        assert "msg-project" in result.output or "created" in result.output.lower()

    def test_init_fails_if_project_exists(self, tmp_path: Path) -> None:
        from miniautogen.cli.main import cli

        runner = CliRunner()
        project_dir = tmp_path / "exists"
        project_dir.mkdir()
        (project_dir / "miniautogen.yaml").write_text("project:\n  name: x\n")
        result = runner.invoke(cli, ["init", str(project_dir)])
        assert result.exit_code != 0

    def test_init_creates_full_structure(self, tmp_path: Path) -> None:
        from miniautogen.cli.main import cli

        runner = CliRunner()
        project_dir = tmp_path / "full"
        result = runner.invoke(cli, ["init", str(project_dir)])
        assert result.exit_code == 0, result.output
        expected = [
            "miniautogen.yaml",
            "agents/researcher.yaml",
            "skills/example/skill.yaml",
            "skills/example/SKILL.md",
            "tools/web_search.yaml",
            "memory/profiles.yaml",
            "pipelines/main.py",
            ".env",
        ]
        for f in expected:
            assert (project_dir / f).is_file(), f"Missing: {f}"
        assert (project_dir / "mcp").is_dir()

    def test_init_uses_directory_basename_as_name(self, tmp_path: Path) -> None:
        from miniautogen.cli.main import cli

        runner = CliRunner()
        project_dir = tmp_path / "my-cool-project"
        result = runner.invoke(cli, ["init", str(project_dir)])
        assert result.exit_code == 0, result.output
        config = yaml.safe_load(
            (project_dir / "miniautogen.yaml").read_text()
        )
        assert config["project"]["name"] == "my-cool-project"
```

**Step 2: Run tests to verify they fail**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/test_init_command.py -v 2>&1 | head -20
```

**Expected output:** Tests FAIL — `init` command not registered yet.

**Step 3: Implement commands/init.py**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/init.py`:

```python
"""CLI command: miniautogen init <path>."""

from __future__ import annotations

from pathlib import Path

import click

from miniautogen.cli.errors import CLIError
from miniautogen.cli.output import echo_error, echo_info, echo_success
from miniautogen.cli.services.init_project import init_project


@click.command("init")
@click.argument("path", type=click.Path())
@click.option(
    "--model",
    default="gpt-4o-mini",
    show_default=True,
    help="Default LLM model for the project.",
)
@click.option(
    "--provider",
    default="litellm",
    show_default=True,
    help="Default LLM provider for the project.",
)
def init_cmd(path: str, model: str, provider: str) -> None:
    """Create a new MiniAutoGen project at PATH."""
    target = Path(path).resolve()
    project_name = target.name

    echo_info(f"Creating project '{project_name}' at {target}")

    try:
        init_project(
            target_dir=target,
            project_name=project_name,
            model=model,
            provider=provider,
        )
    except CLIError as exc:
        echo_error(str(exc))
        raise SystemExit(exc.exit_code) from exc

    echo_success(f"Project '{project_name}' created at {target}")
    echo_info("Next steps:")
    echo_info(f"  cd {target}")
    echo_info("  miniautogen check")
    echo_info("  miniautogen run main")
```

**Step 4: Register the init command in main.py**

Modify `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/main.py` — add the import and registration at the bottom of the file. The full file should now be:

```python
"""Click group and async bridge for the MiniAutoGen CLI."""

from __future__ import annotations

import functools
from typing import Any

import anyio
import click


def run_async(func):  # noqa: ANN001, ANN201
    """Decorator that bridges an async Click command to sync Click entry."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return anyio.from_thread.run(func, *args, **kwargs)

    return wrapper


@click.group()
@click.version_option(package_name="miniautogen")
def cli() -> None:
    """MiniAutoGen — Multi-agent orchestration framework."""


# -- Register commands --
from miniautogen.cli.commands.init import init_cmd  # noqa: E402

cli.add_command(init_cmd)
```

**Step 5: Run tests to verify they pass**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/test_init_command.py -v
```

**Expected output:**
```
tests/cli/test_init_command.py::TestInitCommand::test_init_creates_project PASSED
tests/cli/test_init_command.py::TestInitCommand::test_init_with_custom_model PASSED
tests/cli/test_init_command.py::TestInitCommand::test_init_with_custom_provider PASSED
tests/cli/test_init_command.py::TestInitCommand::test_init_success_message PASSED
tests/cli/test_init_command.py::TestInitCommand::test_init_fails_if_project_exists PASSED
tests/cli/test_init_command.py::TestInitCommand::test_init_creates_full_structure PASSED
tests/cli/test_init_command.py::TestInitCommand::test_init_uses_directory_basename_as_name PASSED

7 passed
```

**Step 6: Verify CLI integration**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m miniautogen init --help
```

**Expected output:**
```
Usage: python -m miniautogen init [OPTIONS] PATH

  Create a new MiniAutoGen project at PATH.

Options:
  --model TEXT     Default LLM model for the project.  [default: gpt-4o-mini]
  --provider TEXT  Default LLM provider for the project.  [default: litellm]
  --help           Show this message and exit.
```

**Step 7: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/commands/init.py miniautogen/cli/main.py tests/cli/test_init_command.py
git commit -m "feat(cli): implement 'miniautogen init' command with Click integration"
```

**If Task Fails:**
1. `init` not showing in `--help`: Check `cli.add_command(init_cmd)` is at module level in `main.py`.
2. CliRunner exit_code != 0: Read `result.output` and `result.exception` for details.
3. Rollback: `git checkout -- miniautogen/cli/commands/ miniautogen/cli/main.py tests/cli/test_init_command.py`

---

### Code Review Checkpoint (Tasks 1-8)

**Dispatch all 3 reviewers in parallel:**
- REQUIRED SUB-SKILL: Use requesting-code-review
- All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
- Wait for all to complete

**Handle findings by severity (MANDATORY):**

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

**Proceed only when:**
- Zero Critical/High/Medium issues remain
- All Low issues have TODO(review): comments added
- All Cosmetic issues have FIXME(nitpick): comments added

---

## Task 9: Architectural import boundary test

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_import_boundary.py`

**Prerequisites:**
- Tasks 2-8 complete (all CLI modules exist)

**Step 1: Write the architectural boundary test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_import_boundary.py`:

```python
"""Architectural test: CLI modules must not import internal packages.

The CLI is a pure consumer of miniautogen.api. It must NEVER import
from internal modules like core, stores, backends, adapters, etc.
This test enforces Design Decision D3 from the CLI design document.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

CLI_PACKAGE_DIR = (
    Path(__file__).resolve().parent.parent.parent / "miniautogen" / "cli"
)

# Imports from these top-level miniautogen subpackages are FORBIDDEN.
FORBIDDEN_PACKAGES = frozenset(
    {
        "miniautogen.core",
        "miniautogen.stores",
        "miniautogen.backends",
        "miniautogen.adapters",
        "miniautogen.policies",
        "miniautogen.observability",
        "miniautogen.pipeline",
        "miniautogen.app",
    }
)

# These are the ONLY miniautogen imports allowed.
ALLOWED_PREFIXES = (
    "miniautogen.api",
    "miniautogen.cli",
)


def _collect_cli_py_files() -> list[Path]:
    """Collect all .py files under miniautogen/cli/."""
    return sorted(CLI_PACKAGE_DIR.rglob("*.py"))


def _extract_imports(filepath: Path) -> list[str]:
    """Extract all import strings from a Python file using AST."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


class TestCLIImportBoundary:
    """Verify CLI code only imports from allowed sources."""

    @pytest.fixture()
    def cli_files(self) -> list[Path]:
        files = _collect_cli_py_files()
        assert len(files) > 0, "No CLI Python files found"
        return files

    def test_no_forbidden_imports(self, cli_files: list[Path]) -> None:
        violations: list[str] = []
        for filepath in cli_files:
            rel = filepath.relative_to(CLI_PACKAGE_DIR.parent.parent)
            for imp in _extract_imports(filepath):
                if not imp.startswith("miniautogen"):
                    continue  # external or stdlib — allowed
                if any(imp.startswith(prefix) for prefix in ALLOWED_PREFIXES):
                    continue  # explicitly allowed
                violations.append(f"{rel}: imports '{imp}'")

        assert violations == [], (
            "CLI modules must only import from miniautogen.api "
            "and miniautogen.cli.*. Violations:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_cli_modules_importable(self) -> None:
        """Verify all CLI modules can be imported without error."""
        modules = [
            "miniautogen.cli",
            "miniautogen.cli.main",
            "miniautogen.cli.config",
            "miniautogen.cli.errors",
            "miniautogen.cli.output",
            "miniautogen.cli.commands.init",
            "miniautogen.cli.services.init_project",
        ]
        for mod in modules:
            importlib.import_module(mod)
```

**Step 2: Run the architectural test**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/test_import_boundary.py -v
```

**Expected output:**
```
tests/cli/test_import_boundary.py::TestCLIImportBoundary::test_no_forbidden_imports PASSED
tests/cli/test_import_boundary.py::TestCLIImportBoundary::test_cli_modules_importable PASSED

2 passed
```

**If a violation is found:** The test will list the exact file and import. Fix the offending module to use `miniautogen.api` instead.

**Step 3: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add tests/cli/test_import_boundary.py
git commit -m "test(cli): add architectural import boundary enforcement test"
```

**If Task Fails:**
1. Violations found: The test output tells you exactly which file imports which forbidden module. Fix the import.
2. Import error in `test_cli_modules_importable`: A module has a syntax or dependency error — check the traceback.
3. Rollback: `git checkout -- tests/cli/test_import_boundary.py`

---

## Task 10: Full regression + verification

**Files:**
- No new files (verification only)

**Prerequisites:**
- Tasks 1-9 all complete

**Step 1: Run ALL CLI tests**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/ -v
```

**Expected output:**
```
tests/cli/test_config.py::TestEngineProfileConfig::test_api_profile PASSED
tests/cli/test_config.py::TestEngineProfileConfig::test_cli_profile PASSED
tests/cli/test_config.py::TestEngineProfileConfig::test_default_temperature PASSED
tests/cli/test_config.py::TestProjectConfig::test_full_config PASSED
tests/cli/test_config.py::TestProjectConfig::test_config_without_database PASSED
tests/cli/test_config.py::TestFindProjectRoot::test_finds_root_with_yaml PASSED
tests/cli/test_config.py::TestFindProjectRoot::test_returns_none_when_not_found PASSED
tests/cli/test_config.py::TestLoadConfig::test_loads_yaml_into_model PASSED
tests/cli/test_config.py::TestLoadConfig::test_raises_on_missing_file PASSED
tests/cli/test_config.py::TestLoadConfig::test_raises_on_invalid_yaml PASSED
tests/cli/test_errors.py::TestCLIErrorHierarchy::test_base_error PASSED
tests/cli/test_errors.py::TestCLIErrorHierarchy::test_config_error PASSED
tests/cli/test_errors.py::TestCLIErrorHierarchy::test_project_not_found_error PASSED
tests/cli/test_errors.py::TestCLIErrorHierarchy::test_scaffold_error PASSED
tests/cli/test_errors.py::TestCLIErrorHierarchy::test_pipeline_error PASSED
tests/cli/test_errors.py::TestExitCodes::test_exit_code_constants PASSED
tests/cli/test_output.py::TestOutputHelpers::test_echo_success PASSED
tests/cli/test_output.py::TestOutputHelpers::test_echo_error PASSED
tests/cli/test_output.py::TestOutputHelpers::test_echo_info PASSED
tests/cli/test_output.py::TestOutputHelpers::test_echo_json PASSED
tests/cli/test_output.py::TestOutputHelpers::test_echo_table PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_miniautogen_yaml_renders PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_researcher_yaml_renders PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_skill_yaml_renders PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_skill_md_renders PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_tool_yaml_renders PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_memory_profiles_yaml_renders PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_pipeline_main_renders PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_env_renders PASSED
tests/cli/test_templates.py::TestTemplateRendering::test_all_templates_exist PASSED
tests/cli/test_init_service.py::TestInitProject::test_creates_project_directory PASSED
tests/cli/test_init_service.py::TestInitProject::test_creates_miniautogen_yaml PASSED
tests/cli/test_init_service.py::TestInitProject::test_creates_agent_spec PASSED
tests/cli/test_init_service.py::TestInitProject::test_creates_skill_directory PASSED
tests/cli/test_init_service.py::TestInitProject::test_creates_tool_spec PASSED
tests/cli/test_init_service.py::TestInitProject::test_creates_mcp_directory PASSED
tests/cli/test_init_service.py::TestInitProject::test_creates_pipeline PASSED
tests/cli/test_init_service.py::TestInitProject::test_creates_env_file PASSED
tests/cli/test_init_service.py::TestInitProject::test_raises_if_directory_exists PASSED
tests/cli/test_init_service.py::TestInitProject::test_full_directory_structure PASSED
tests/cli/test_init_service.py::TestInitProject::test_custom_model_and_provider PASSED
tests/cli/test_init_command.py::TestInitCommand::test_init_creates_project PASSED
tests/cli/test_init_command.py::TestInitCommand::test_init_with_custom_model PASSED
tests/cli/test_init_command.py::TestInitCommand::test_init_with_custom_provider PASSED
tests/cli/test_init_command.py::TestInitCommand::test_init_success_message PASSED
tests/cli/test_init_command.py::TestInitCommand::test_init_fails_if_project_exists PASSED
tests/cli/test_init_command.py::TestInitCommand::test_init_creates_full_structure PASSED
tests/cli/test_init_command.py::TestInitCommand::test_init_uses_directory_basename_as_name PASSED
tests/cli/test_import_boundary.py::TestCLIImportBoundary::test_no_forbidden_imports PASSED
tests/cli/test_import_boundary.py::TestCLIImportBoundary::test_cli_modules_importable PASSED

48 passed
```

**Step 2: Run full test suite (regression check)**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest --tb=short -q
```

**Expected output:** All existing tests still pass. The new 48 CLI tests are additive. No regressions.

**Step 3: Lint all new files**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/cli/ tests/cli/
```

**Expected output:** No lint errors.

**Step 4: Verify end-to-end scaffold**

Run:
```bash
cd /tmp && python -m miniautogen init test-e2e-project && ls -la test-e2e-project/ && ls -la test-e2e-project/agents/ && ls -la test-e2e-project/skills/example/ && ls -la test-e2e-project/tools/ && ls -la test-e2e-project/mcp/ && cat test-e2e-project/miniautogen.yaml && rm -rf test-e2e-project
```

**Expected output:** Full directory structure visible, miniautogen.yaml content displayed with correct defaults.

**Step 5: Verify entry point works**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m miniautogen --help && python -m miniautogen init --help
```

**Expected output:** Both help messages display correctly.

**If Task Fails:**
1. Regressions in existing tests: Check if new imports or dependencies conflict. The CLI is isolated and should not affect existing code.
2. Lint errors: Fix with `ruff check --fix miniautogen/cli/ tests/cli/`.
3. E2E scaffold fails: Check template paths resolve correctly from installed package.

---

## Summary of Files Created/Modified

### New Files (Production)
| File | Purpose |
|---|---|
| `miniautogen/__main__.py` | `python -m miniautogen` entry point |
| `miniautogen/cli/__init__.py` | CLI package init |
| `miniautogen/cli/main.py` | Click group + async bridge + command registration |
| `miniautogen/cli/config.py` | ProjectConfig Pydantic models + YAML loading |
| `miniautogen/cli/errors.py` | CLI error hierarchy + BSD sysexits codes |
| `miniautogen/cli/output.py` | Terminal output helpers |
| `miniautogen/cli/commands/__init__.py` | Commands package init |
| `miniautogen/cli/commands/init.py` | `miniautogen init` Click command |
| `miniautogen/cli/services/__init__.py` | Services package init |
| `miniautogen/cli/services/init_project.py` | Project scaffolding service |
| `miniautogen/cli/templates/project/miniautogen.yaml.j2` | Project config template |
| `miniautogen/cli/templates/project/agents/researcher.yaml.j2` | Agent spec template |
| `miniautogen/cli/templates/project/skills/example/SKILL.md.j2` | Skill instructions template |
| `miniautogen/cli/templates/project/skills/example/skill.yaml.j2` | Skill metadata template |
| `miniautogen/cli/templates/project/tools/web_search.yaml.j2` | Tool spec template |
| `miniautogen/cli/templates/project/memory/profiles.yaml.j2` | Memory profiles template |
| `miniautogen/cli/templates/project/pipelines/main.py.j2` | Pipeline template |
| `miniautogen/cli/templates/project/.env.j2` | Environment file template |

### New Files (Tests)
| File | Purpose |
|---|---|
| `tests/cli/__init__.py` | Test package init |
| `tests/cli/test_config.py` | Config model + loading tests (10 tests) |
| `tests/cli/test_errors.py` | Error hierarchy tests (6 tests) |
| `tests/cli/test_output.py` | Output helper tests (5 tests) |
| `tests/cli/test_templates.py` | Template rendering tests (9 tests) |
| `tests/cli/test_init_service.py` | Init service tests (11 tests) |
| `tests/cli/test_init_command.py` | Init CLI command tests (7 tests) |
| `tests/cli/test_import_boundary.py` | Architectural boundary test (2 tests) |

### Modified Files
| File | Change |
|---|---|
| `pyproject.toml` | Added click, pyyaml deps + scripts entry point |

### Total: 50 new tests across 7 test files
