# Milestone 2 — Chunk 1: CLI Foundation + init Command

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Set up CLI infrastructure (main group, config, errors, output) and implement the first command (`miniautogen init <name>`) that scaffolds a new project.

**Architecture:** CLI as pure SDK consumer. `commands/` are Click adapters (parse args, render output). `services/` contain testable application logic that never touches Click. `config.py` handles YAML project resolution. All CLI code may only import from `miniautogen.api` and `miniautogen.cli.*` — never from internal modules. An architectural import boundary test enforces this automatically.

**Tech Stack:** Python 3.10+, Click 8+, PyYAML 6+, Jinja2 3.1+, Pydantic v2, AnyIO 4+, pytest 7+, ruff (line-length=100)

**Global Prerequisites:**
- Environment: macOS, Python 3.10 or 3.11
- Tools: `python --version`, `pytest --version`, `ruff --version`, `poetry --version`
- State: Work from `main` branch, clean working tree
- Existing: 542+ tests passing, `miniautogen/api.py` with 47 exports

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
- Poetry installed and functional

**Step 1: Add dependencies and scripts entry**

Open `/Users/brunocapelao/Projects/miniAutoGen/pyproject.toml` and make these changes:

In the `[tool.poetry.dependencies]` section, add two lines after the existing `httpx` entry:

```toml
click = ">=8.0"
pyyaml = ">=6.0"
```

After the `[tool.poetry.group.dev.dependencies]` section (before `[tool.ruff]`), add:

```toml
[tool.poetry.scripts]
miniautogen = "miniautogen.cli.main:cli"
```

The full `[tool.poetry.dependencies]` section should read:

```toml
[tool.poetry.dependencies]
python = ">3.10, <3.12"
openai = ">=1.3.9"
python-dotenv = "1.0.0"
sqlalchemy = ">=2.0.23"
litellm = ">=1.16.12"
pydantic = ">=2.5.0"
aiosqlite = ">=0.19.0"
anyio = ">=4.0.0"
jinja2 = ">=3.1.0"
structlog = ">=24.0.0"
tenacity = ">=8.2.0"
fastapi = ">=0.115.0"
uvicorn = ">=0.32.0"
httpx = ">=0.28.0"
click = ">=8.0"
pyyaml = ">=6.0"
```

**Step 2: Lock and install**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && poetry lock --no-update && poetry install
```

**Expected output:** No errors. Lock file updated, packages installed.

**Step 3: Verify imports**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -c "import click; import yaml; print('ok')"
```

**Expected output:**
```
ok
```

**Step 4: Verify existing tests still pass**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && pytest --co -q 2>&1 | tail -1
```

**Expected output:** `NNN tests collected` (same count as before, no errors)

**Step 5: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && git add pyproject.toml poetry.lock && git commit -m "chore: add click and pyyaml dependencies, add CLI scripts entry"
```

**If Task Fails:**
1. **poetry lock fails:** Check for version conflicts. Try `poetry lock` (without `--no-update`) to resolve.
2. **Import fails:** Run `poetry install` again, verify virtual environment is active.
3. **Can't recover:** `git checkout -- pyproject.toml poetry.lock` and start over.

---

## Task 2: Create CLI foundation — __main__.py and cli package skeleton

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/__main__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/main.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_main.py`

**Prerequisites:**
- Task 1 complete (click installed)
- Directory `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/` exists

**Step 1: Create directory structure**

Run:
```bash
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/tests/cli
```

**Step 2: Create __main__.py**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/__main__.py`:

```python
"""Support ``python -m miniautogen``."""

from miniautogen.cli.main import cli

cli()
```

**Step 3: Create cli/__init__.py**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/__init__.py`:

```python
"""MiniAutoGen CLI — developer experience layer on top of the public SDK."""
```

**Step 4: Create cli/main.py**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/main.py`:

```python
"""CLI entry point and async bridge.

This module defines the top-level Click group and a helper to bridge
synchronous Click commands to asynchronous service functions via AnyIO.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar

import anyio
import click

F = TypeVar("F", bound=Callable[..., Any])

_VERSION = "0.1.0"


def run_async(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run an async function synchronously using AnyIO.

    Used by Click commands to call async service functions::

        result = run_async(scaffold_project, name="demo", model="gpt-4o-mini")
    """
    return anyio.from_thread.run(func, *args, **kwargs) if False else anyio.run(
        functools.partial(func, *args, **kwargs),
    )


def _get_version() -> str:
    """Return package version from metadata, falling back to hardcoded value."""
    try:
        from importlib.metadata import version

        return version("miniautogen")
    except Exception:
        return _VERSION


@click.group()
@click.version_option(version=_get_version(), prog_name="miniautogen")
def cli() -> None:
    """MiniAutoGen — multi-agent orchestration framework."""
```

**Step 5: Create tests/cli/__init__.py**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/__init__.py`:

```python
```

(Empty file.)

**Step 6: Write the tests**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_main.py`:

```python
"""Tests for CLI entry point and version flag."""

from __future__ import annotations

from click.testing import CliRunner

from miniautogen.cli.main import cli, run_async


def test_cli_version_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert "miniautogen" in result.output
    assert "0.1.0" in result.output or "version" in result.output.lower()


def test_cli_help_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "multi-agent orchestration" in result.output.lower()


def test_cli_no_args_shows_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, [])

    assert result.exit_code == 0
    assert "Usage" in result.output or "usage" in result.output.lower()


async def _async_add(a: int, b: int) -> int:
    return a + b


def test_run_async_executes_coroutine() -> None:
    result = run_async(_async_add, 2, 3)
    assert result == 5
```

**Step 7: Run the tests**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/cli/test_main.py -v
```

**Expected output:**
```
tests/cli/test_main.py::test_cli_version_flag PASSED
tests/cli/test_main.py::test_cli_help_flag PASSED
tests/cli/test_main.py::test_cli_no_args_shows_help PASSED
tests/cli/test_main.py::test_run_async_executes_coroutine PASSED
```

**Step 8: Run ruff**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/cli/ miniautogen/__main__.py tests/cli/ --fix
```

**Expected output:** No errors, or only auto-fixed formatting issues.

**Step 9: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && git add miniautogen/__main__.py miniautogen/cli/__init__.py miniautogen/cli/main.py tests/cli/__init__.py tests/cli/test_main.py && git commit -m "feat: add CLI foundation with Click group and async bridge"
```

**If Task Fails:**
1. **Import error on click:** Verify Task 1 completed. Run `poetry install`.
2. **run_async test hangs:** Ensure AnyIO 4+ is installed. Check `anyio.run` is called correctly.
3. **Can't recover:** `git checkout -- .` and revisit.

---

## Task 3: Create CLI error hierarchy

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/errors.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_errors.py`

**Prerequisites:**
- Task 2 complete (cli package exists)

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_errors.py`:

```python
"""Tests for CLI error hierarchy and exit codes."""

from __future__ import annotations

import click
import pytest

from miniautogen.cli.errors import (
    CLIError,
    ConfigurationError,
    PipelineNotFoundError,
    ProjectNotFoundError,
    ValidationError,
)


def test_cli_error_is_click_exception() -> None:
    err = CLIError("something failed")
    assert isinstance(err, click.ClickException)


def test_cli_error_default_exit_code() -> None:
    err = CLIError("fail")
    assert err.exit_code == 1


def test_cli_error_custom_exit_code() -> None:
    err = CLIError("fail", exit_code=42)
    assert err.exit_code == 42


def test_cli_error_message() -> None:
    err = CLIError("bad input")
    assert err.format_message() == "bad input"


def test_project_not_found_error_exit_code() -> None:
    err = ProjectNotFoundError()
    assert err.exit_code == 2
    assert "miniautogen.yaml" in err.format_message().lower()


def test_project_not_found_error_custom_message() -> None:
    err = ProjectNotFoundError("custom msg")
    assert err.format_message() == "custom msg"
    assert err.exit_code == 2


def test_configuration_error_exit_code() -> None:
    err = ConfigurationError("bad yaml")
    assert err.exit_code == 3


def test_pipeline_not_found_error_exit_code() -> None:
    err = PipelineNotFoundError("main")
    assert err.exit_code == 4
    assert "main" in err.format_message()


def test_validation_error_exit_code() -> None:
    err = ValidationError("field X missing")
    assert err.exit_code == 5


@pytest.mark.parametrize(
    "cls,code",
    [
        (ProjectNotFoundError, 2),
        (ConfigurationError, 3),
        (PipelineNotFoundError, 4),
        (ValidationError, 5),
    ],
)
def test_all_errors_are_cli_errors(
    cls: type[CLIError], code: int,
) -> None:
    err = cls("test")
    assert isinstance(err, CLIError)
    assert isinstance(err, click.ClickException)
    assert err.exit_code == code
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/cli/test_errors.py -v 2>&1 | head -5
```

**Expected output:**
```
FAILED ... ModuleNotFoundError: No module named 'miniautogen.cli.errors'
```

**Step 3: Write the implementation**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/errors.py`:

```python
"""CLI error hierarchy with stable exit codes.

Exit codes:
    1 — Generic CLI error
    2 — Project not found (no miniautogen.yaml)
    3 — Configuration error (invalid YAML / schema)
    4 — Pipeline not found
    5 — Validation error
"""

from __future__ import annotations

import click


class CLIError(click.ClickException):
    """Base CLI error with a configurable exit code."""

    exit_code: int = 1

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


class ProjectNotFoundError(CLIError):
    """Raised when miniautogen.yaml cannot be found."""

    exit_code: int = 2

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message or "No miniautogen.yaml found in current or parent directories.",
        )


class ConfigurationError(CLIError):
    """Raised when configuration is invalid or unparseable."""

    exit_code: int = 3


class PipelineNotFoundError(CLIError):
    """Raised when a referenced pipeline cannot be resolved."""

    exit_code: int = 4


class ValidationError(CLIError):
    """Raised when input or schema validation fails."""

    exit_code: int = 5
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/cli/test_errors.py -v
```

**Expected output:** All tests PASSED (11 tests).

**Step 5: Run ruff**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/cli/errors.py tests/cli/test_errors.py --fix
```

**Step 6: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && git add miniautogen/cli/errors.py tests/cli/test_errors.py && git commit -m "feat: add CLI error hierarchy with stable exit codes"
```

**If Task Fails:**
1. **exit_code not sticking on subclass:** The `exit_code` class attribute must be set as a class variable, not an instance attribute in the base. The pattern above handles this correctly because `click.ClickException.__init__` does not set `exit_code` — Click reads `self.exit_code` which falls back to the class variable.
2. **Can't recover:** `git checkout -- .` and revisit.

---

## Task 4: Create config.py — project resolution and YAML loading

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/config.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_config.py`

**Prerequisites:**
- Task 1 complete (pyyaml installed)
- Task 3 complete (errors module exists)

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_config.py`:

```python
"""Tests for project configuration resolution and loading."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from miniautogen.cli.config import ProjectConfig, find_project_root, load_config


# --- ProjectConfig model ---


def test_project_config_minimal() -> None:
    cfg = ProjectConfig(
        project={"name": "demo", "version": "0.1.0"},
        provider={"default": "litellm", "model": "gpt-4o-mini"},
        pipelines={"main": {"target": "pipelines.main:build_pipeline"}},
    )
    assert cfg.project["name"] == "demo"
    assert cfg.provider["model"] == "gpt-4o-mini"


def test_project_config_with_database() -> None:
    cfg = ProjectConfig(
        project={"name": "demo", "version": "0.1.0"},
        provider={"default": "litellm", "model": "gpt-4o-mini"},
        pipelines={"main": {"target": "pipelines.main:build"}},
        database={"url": "sqlite+aiosqlite:///test.db"},
    )
    assert cfg.database is not None
    assert cfg.database["url"] == "sqlite+aiosqlite:///test.db"


def test_project_config_database_defaults_to_none() -> None:
    cfg = ProjectConfig(
        project={"name": "demo", "version": "0.1.0"},
        provider={"default": "litellm", "model": "gpt-4o-mini"},
        pipelines={"main": {"target": "pipelines.main:build"}},
    )
    assert cfg.database is None


def test_project_config_rejects_missing_project() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProjectConfig(
            provider={"default": "litellm", "model": "gpt-4o-mini"},
            pipelines={"main": {"target": "x:y"}},
        )  # type: ignore[call-arg]


def test_project_config_rejects_missing_provider() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProjectConfig(
            project={"name": "demo", "version": "0.1.0"},
            pipelines={"main": {"target": "x:y"}},
        )  # type: ignore[call-arg]


def test_project_config_rejects_missing_pipelines() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProjectConfig(
            project={"name": "demo", "version": "0.1.0"},
            provider={"default": "litellm", "model": "gpt-4o-mini"},
        )  # type: ignore[call-arg]


# --- find_project_root ---


def test_find_project_root_in_current_dir(tmp_path: Path) -> None:
    (tmp_path / "miniautogen.yaml").write_text("project:\n  name: test\n")
    result = find_project_root(tmp_path)
    assert result == tmp_path


def test_find_project_root_in_parent_dir(tmp_path: Path) -> None:
    (tmp_path / "miniautogen.yaml").write_text("project:\n  name: test\n")
    child = tmp_path / "subdir"
    child.mkdir()
    result = find_project_root(child)
    assert result == tmp_path


def test_find_project_root_returns_none_when_missing(tmp_path: Path) -> None:
    result = find_project_root(tmp_path)
    assert result is None


def test_find_project_root_stops_at_filesystem_root(tmp_path: Path) -> None:
    deep = tmp_path / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    result = find_project_root(deep)
    assert result is None


# --- load_config ---


def test_load_config_happy_path(tmp_path: Path) -> None:
    content = {
        "project": {"name": "my-app", "version": "1.0.0"},
        "provider": {"default": "litellm", "model": "gpt-4o-mini"},
        "pipelines": {"main": {"target": "pipelines.main:build_pipeline"}},
    }
    config_path = tmp_path / "miniautogen.yaml"
    config_path.write_text(yaml.dump(content))

    cfg = load_config(config_path)
    assert cfg.project["name"] == "my-app"
    assert cfg.pipelines["main"]["target"] == "pipelines.main:build_pipeline"


def test_load_config_with_database(tmp_path: Path) -> None:
    content = {
        "project": {"name": "my-app", "version": "1.0.0"},
        "provider": {"default": "litellm", "model": "gpt-4o-mini"},
        "pipelines": {"main": {"target": "pipelines.main:build"}},
        "database": {"url": "sqlite+aiosqlite:///miniautogen.db"},
    }
    config_path = tmp_path / "miniautogen.yaml"
    config_path.write_text(yaml.dump(content))

    cfg = load_config(config_path)
    assert cfg.database is not None
    assert "sqlite" in cfg.database["url"]


def test_load_config_file_not_found(tmp_path: Path) -> None:
    from miniautogen.cli.errors import ConfigurationError

    with pytest.raises(ConfigurationError, match="not found"):
        load_config(tmp_path / "nonexistent.yaml")


def test_load_config_invalid_yaml(tmp_path: Path) -> None:
    from miniautogen.cli.errors import ConfigurationError

    config_path = tmp_path / "miniautogen.yaml"
    config_path.write_text("{{invalid yaml: [")

    with pytest.raises(ConfigurationError, match="parse"):
        load_config(config_path)


def test_load_config_schema_validation_error(tmp_path: Path) -> None:
    from miniautogen.cli.errors import ConfigurationError

    config_path = tmp_path / "miniautogen.yaml"
    config_path.write_text(yaml.dump({"project": {"name": "x"}}))

    with pytest.raises(ConfigurationError, match="valid"):
        load_config(config_path)
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/cli/test_config.py -v 2>&1 | head -5
```

**Expected output:**
```
FAILED ... ModuleNotFoundError: No module named 'miniautogen.cli.config'
```

**Step 3: Write the implementation**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/config.py`:

```python
"""Project configuration resolution and YAML loading.

Responsibilities:
- Locate ``miniautogen.yaml`` by walking up from a start directory.
- Parse and validate the YAML into a ``ProjectConfig`` Pydantic model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from miniautogen.cli.errors import ConfigurationError

CONFIG_FILENAME = "miniautogen.yaml"


class ProjectConfig(BaseModel):
    """Schema for ``miniautogen.yaml``."""

    project: dict[str, Any]
    provider: dict[str, Any]
    pipelines: dict[str, dict[str, Any]]
    database: dict[str, Any] | None = None


def find_project_root(start: Path) -> Path | None:
    """Walk up from *start* looking for ``miniautogen.yaml``.

    Returns the directory containing the config file, or ``None``
    if the filesystem root is reached without finding one.
    """
    current = start.resolve()
    while True:
        if (current / CONFIG_FILENAME).is_file():
            return current
        parent = current.parent
        if parent == current:
            # Reached filesystem root.
            return None
        current = parent


def load_config(path: Path) -> ProjectConfig:
    """Load and validate a ``miniautogen.yaml`` file.

    Parameters
    ----------
    path:
        Absolute path to the YAML file.

    Returns
    -------
    ProjectConfig
        Validated configuration model.

    Raises
    ------
    ConfigurationError
        If the file is not found, cannot be parsed, or fails validation.
    """
    if not path.is_file():
        raise ConfigurationError(f"Configuration file not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Failed to parse {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigurationError(f"Configuration file is not valid YAML mapping: {path}")

    try:
        return ProjectConfig.model_validate(raw)
    except Exception as exc:
        raise ConfigurationError(
            f"Configuration is not valid: {exc}",
        ) from exc
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/cli/test_config.py -v
```

**Expected output:** All tests PASSED (13 tests).

**Step 5: Run ruff**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/cli/config.py tests/cli/test_config.py --fix
```

**Step 6: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && git add miniautogen/cli/config.py tests/cli/test_config.py && git commit -m "feat: add project config resolution and YAML loading"
```

**If Task Fails:**
1. **YAML parse test not raising ConfigurationError:** Ensure the invalid YAML string actually causes `yaml.safe_load` to raise. The string `{{invalid yaml: [` should trigger a `yaml.YAMLError`.
2. **Schema validation test not raising:** The incomplete config `{"project": {"name": "x"}}` is missing required fields `provider` and `pipelines`, which Pydantic will reject.
3. **Can't recover:** `git checkout -- .` and revisit.

---

## Task 5: Create output.py — presentation layer

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/output.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_output.py`

**Prerequisites:**
- Task 2 complete (cli package exists)

**Step 1: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_output.py`:

```python
"""Tests for CLI output formatting utilities."""

from __future__ import annotations

import json

from click.testing import CliRunner

import click

from miniautogen.cli.output import echo_error, echo_info, echo_json, echo_success, echo_table


def _capture(func, *args, **kwargs) -> str:  # noqa: ANN001
    """Run an echo function inside a Click command and capture output."""

    @click.command()
    def _cmd() -> None:
        func(*args, **kwargs)

    runner = CliRunner()
    result = runner.invoke(_cmd)
    return result.output


def test_echo_success_contains_message() -> None:
    output = _capture(echo_success, "All good")
    assert "All good" in output


def test_echo_error_contains_message() -> None:
    output = _capture(echo_error, "Something broke")
    assert "Something broke" in output


def test_echo_info_contains_message() -> None:
    output = _capture(echo_info, "FYI")
    assert "FYI" in output


def test_echo_json_valid_json() -> None:
    data = {"name": "demo", "version": "1.0"}
    output = _capture(echo_json, data)
    parsed = json.loads(output)
    assert parsed == data


def test_echo_json_is_indented() -> None:
    data = {"key": "value"}
    output = _capture(echo_json, data)
    assert "  " in output  # indented


def test_echo_table_renders_headers_and_rows() -> None:
    headers = ["Name", "Status"]
    rows = [["alpha", "ok"], ["beta", "fail"]]
    output = _capture(echo_table, headers, rows)
    assert "Name" in output
    assert "Status" in output
    assert "alpha" in output
    assert "beta" in output
    assert "ok" in output
    assert "fail" in output


def test_echo_table_aligns_columns() -> None:
    headers = ["Col1", "Col2"]
    rows = [["short", "x"], ["very long value", "y"]]
    output = _capture(echo_table, headers, rows)
    lines = [line for line in output.strip().split("\n") if line.strip()]
    # All data lines should have consistent structure
    assert len(lines) >= 3  # header + separator + 2 rows


def test_echo_table_empty_rows() -> None:
    headers = ["A", "B"]
    output = _capture(echo_table, headers, [])
    assert "A" in output
    assert "B" in output
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/cli/test_output.py -v 2>&1 | head -5
```

**Expected output:**
```
FAILED ... ModuleNotFoundError: No module named 'miniautogen.cli.output'
```

**Step 3: Write the implementation**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/output.py`:

```python
"""Presentation layer for CLI terminal output.

Provides coloured echoing and simple table rendering.
All output goes through ``click.echo`` / ``click.secho`` so it
integrates with Click's output capturing in tests.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

import click


def echo_success(message: str) -> None:
    """Print a green success message."""
    click.secho(f"[OK] {message}", fg="green")


def echo_error(message: str) -> None:
    """Print a red error message."""
    click.secho(f"[ERROR] {message}", fg="red")


def echo_info(message: str) -> None:
    """Print a blue informational message."""
    click.secho(f"[INFO] {message}", fg="blue")


def echo_json(data: dict[str, Any]) -> None:
    """Print *data* as indented JSON."""
    click.echo(json.dumps(data, indent=2, default=str))


def echo_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
) -> None:
    """Render a simple aligned text table.

    Example output::

        Name     Status
        ------   ------
        alpha    ok
        beta     fail
    """
    if not headers:
        return

    # Compute column widths from headers + data.
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(str(cell)))

    def _format_row(cells: Sequence[str]) -> str:
        parts = []
        for i, cell in enumerate(cells):
            w = widths[i] if i < len(widths) else 0
            parts.append(str(cell).ljust(w))
        return "  ".join(parts)

    click.echo(_format_row(headers))
    click.echo("  ".join("-" * w for w in widths))
    for row in rows:
        click.echo(_format_row(row))
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/cli/test_output.py -v
```

**Expected output:** All tests PASSED (8 tests).

**Step 5: Run ruff**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/cli/output.py tests/cli/test_output.py --fix
```

**Step 6: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && git add miniautogen/cli/output.py tests/cli/test_output.py && git commit -m "feat: add CLI output formatting utilities"
```

**If Task Fails:**
1. **Colors cause test issues:** Click's `CliRunner` strips ANSI by default. If not, pass `color=False` to `CliRunner()`.
2. **Can't recover:** `git checkout -- .` and revisit.

---

## Task 6: Create Jinja2 templates for project scaffolding

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/miniautogen.yaml.j2`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/agents/__init__.py.j2`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/pipelines/main.py.j2`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/.env.j2`

**Prerequisites:**
- Task 2 complete (cli package exists)

**Step 1: Create directory structure**

Run:
```bash
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/agents
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/pipelines
```

**Step 2: Create templates/__init__.py**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/__init__.py`:

```python
"""Jinja2 templates for project scaffolding."""
```

**Step 3: Create miniautogen.yaml.j2**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/miniautogen.yaml.j2`:

```
project:
  name: {{ project_name }}
  version: "0.1.0"

provider:
  default: {{ provider }}
  model: {{ model }}

pipelines:
  main:
    target: pipelines.main:build_pipeline

database:
  url: sqlite+aiosqlite:///miniautogen.db
```

**Step 4: Create agents/__init__.py.j2**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/agents/__init__.py.j2`:

```
"""Agents for {{ project_name }}."""
```

**Step 5: Create pipelines/main.py.j2**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/pipelines/main.py.j2`:

```
"""Main pipeline for {{ project_name }}."""

from miniautogen.api import Pipeline, PipelineComponent


def build_pipeline() -> Pipeline:
    """Build and return the main pipeline.

    This is the entry point referenced in miniautogen.yaml.
    Customize this function to define your agent orchestration.
    """
    return Pipeline(name="{{ project_name }}-main", components=[])
```

**Step 6: Create .env.j2**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/templates/project/.env.j2`:

```
# Environment variables for {{ project_name }}
# Uncomment and set your API keys:

# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

DATABASE_URL=sqlite+aiosqlite:///miniautogen.db
MINIAUTOGEN_DEFAULT_PROVIDER={{ provider }}
MINIAUTOGEN_DEFAULT_MODEL={{ model }}
```

**Step 7: Verify templates are syntactically valid**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('miniautogen/cli/templates/project'))
for name in ['miniautogen.yaml.j2', 'agents/__init__.py.j2', 'pipelines/main.py.j2', '.env.j2']:
    t = env.get_template(name)
    out = t.render(project_name='demo', provider='litellm', model='gpt-4o-mini')
    assert len(out) > 0, f'Empty render for {name}'
print('All templates render OK')
"
```

**Expected output:**
```
All templates render OK
```

**Step 8: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && git add miniautogen/cli/templates/ && git commit -m "feat: add Jinja2 templates for project scaffolding"
```

**If Task Fails:**
1. **Jinja2 template syntax error:** Check for unmatched `{{` or `}}`. All template variables use `{{ variable_name }}` syntax.
2. **FileSystemLoader path wrong:** Ensure the path is relative to cwd, or use absolute path.
3. **Can't recover:** `git checkout -- .` and revisit.

---

## Task 7: Create init_project service

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/init_project.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_init_project.py`

**Prerequisites:**
- Task 6 complete (templates exist)
- Jinja2 installed (already in deps)

**Step 1: Create directories**

Run:
```bash
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/tests/cli/services
```

**Step 2: Create services/__init__.py**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/__init__.py`:

```python
"""CLI application services — testable logic independent of Click."""
```

**Step 3: Create tests/cli/services/__init__.py**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/__init__.py`:

```python
```

(Empty file.)

**Step 4: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_init_project.py`:

```python
"""Tests for project scaffolding service."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from miniautogen.cli.services.init_project import scaffold_project


@pytest.mark.anyio
async def test_scaffold_creates_directory_structure(tmp_path: Path) -> None:
    result = await scaffold_project(
        name="my-app",
        model="gpt-4o-mini",
        provider="litellm",
        target_dir=tmp_path,
        include_examples=True,
    )

    assert result == tmp_path / "my-app"
    assert (result / "miniautogen.yaml").is_file()
    assert (result / "agents" / "__init__.py").is_file()
    assert (result / "pipelines" / "main.py").is_file()
    assert (result / ".env").is_file()
    assert (result / "tools").is_dir()


@pytest.mark.anyio
async def test_scaffold_yaml_content(tmp_path: Path) -> None:
    result = await scaffold_project(
        name="test-proj",
        model="claude-3-haiku",
        provider="anthropic",
        target_dir=tmp_path,
        include_examples=True,
    )

    content = yaml.safe_load((result / "miniautogen.yaml").read_text())
    assert content["project"]["name"] == "test-proj"
    assert content["provider"]["default"] == "anthropic"
    assert content["provider"]["model"] == "claude-3-haiku"
    assert "main" in content["pipelines"]


@pytest.mark.anyio
async def test_scaffold_env_content(tmp_path: Path) -> None:
    result = await scaffold_project(
        name="my-app",
        model="gpt-4o-mini",
        provider="litellm",
        target_dir=tmp_path,
        include_examples=True,
    )

    env_text = (result / ".env").read_text()
    assert "litellm" in env_text
    assert "gpt-4o-mini" in env_text


@pytest.mark.anyio
async def test_scaffold_pipeline_references_project(tmp_path: Path) -> None:
    result = await scaffold_project(
        name="cool-agents",
        model="gpt-4o-mini",
        provider="litellm",
        target_dir=tmp_path,
        include_examples=True,
    )

    pipeline_text = (result / "pipelines" / "main.py").read_text()
    assert "cool-agents" in pipeline_text
    assert "build_pipeline" in pipeline_text


@pytest.mark.anyio
async def test_scaffold_raises_on_existing_directory(tmp_path: Path) -> None:
    (tmp_path / "existing").mkdir()

    with pytest.raises(FileExistsError, match="already exists"):
        await scaffold_project(
            name="existing",
            model="gpt-4o-mini",
            provider="litellm",
            target_dir=tmp_path,
            include_examples=True,
        )


@pytest.mark.anyio
async def test_scaffold_no_examples_still_creates_structure(tmp_path: Path) -> None:
    result = await scaffold_project(
        name="minimal",
        model="gpt-4o-mini",
        provider="litellm",
        target_dir=tmp_path,
        include_examples=False,
    )

    assert (result / "miniautogen.yaml").is_file()
    assert (result / "agents").is_dir()
    assert (result / "pipelines").is_dir()
    assert (result / "tools").is_dir()
    assert (result / ".env").is_file()
```

**Step 5: Run test to verify it fails**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/cli/services/test_init_project.py -v 2>&1 | head -5
```

**Expected output:**
```
FAILED ... ModuleNotFoundError: No module named 'miniautogen.cli.services'
```

**Step 6: Write the implementation**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/init_project.py`:

```python
"""Project scaffolding service.

Renders Jinja2 templates into a target directory to create a new
MiniAutoGen project with canonical structure.

This module does NOT import Click — it is a pure application service.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader


async def scaffold_project(
    name: str,
    model: str,
    provider: str,
    target_dir: Path,
    include_examples: bool = True,
) -> Path:
    """Create a new MiniAutoGen project directory.

    Parameters
    ----------
    name:
        Project name (used as directory name and in templates).
    model:
        Default LLM model identifier.
    provider:
        Default LLM provider name.
    target_dir:
        Parent directory where the project folder will be created.
    include_examples:
        Whether to include example agent/pipeline files.

    Returns
    -------
    Path
        Absolute path to the created project directory.

    Raises
    ------
    FileExistsError
        If the target project directory already exists.
    """
    project_dir = target_dir / name
    if project_dir.exists():
        msg = f"Directory already exists: {project_dir}"
        raise FileExistsError(msg)

    project_dir.mkdir(parents=True)

    context = {
        "project_name": name,
        "model": model,
        "provider": provider,
    }

    env = Environment(
        loader=PackageLoader("miniautogen.cli", "templates/project"),
        keep_trailing_newline=True,
    )

    # Render templates into project directory.
    _render_template(env, "miniautogen.yaml.j2", project_dir / "miniautogen.yaml", context)
    _render_template(env, ".env.j2", project_dir / ".env", context)

    # Create directories.
    (project_dir / "agents").mkdir()
    (project_dir / "pipelines").mkdir()
    (project_dir / "tools").mkdir()

    # Render agent and pipeline files.
    _render_template(
        env,
        "agents/__init__.py.j2",
        project_dir / "agents" / "__init__.py",
        context,
    )

    if include_examples:
        _render_template(
            env,
            "pipelines/main.py.j2",
            project_dir / "pipelines" / "main.py",
            context,
        )
    else:
        # Create empty pipeline module even without examples.
        (project_dir / "pipelines" / "__init__.py").write_text("")

    return project_dir


def _render_template(
    env: Environment,
    template_name: str,
    output_path: Path,
    context: dict[str, str],
) -> None:
    """Render a single Jinja2 template to a file."""
    template = env.get_template(template_name)
    output_path.write_text(template.render(**context))
```

**Step 7: Run tests to verify they pass**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/cli/services/test_init_project.py -v
```

**Expected output:** All tests PASSED (6 tests).

**Step 8: Run ruff**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/cli/services/ tests/cli/services/ --fix
```

**Step 9: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && git add miniautogen/cli/services/__init__.py miniautogen/cli/services/init_project.py tests/cli/services/__init__.py tests/cli/services/test_init_project.py && git commit -m "feat: add project scaffolding service with Jinja2 templates"
```

**If Task Fails:**
1. **PackageLoader cannot find templates:** Ensure `miniautogen/cli/templates/__init__.py` exists (Task 6). The `PackageLoader("miniautogen.cli", "templates/project")` expects the `miniautogen.cli` package to be importable and `templates/project/` to be a subdirectory of it.
2. **anyio test marker not recognized:** Ensure `pytest-anyio` or `anyio[pytest]` is available. If using `pytest-asyncio`, change `@pytest.mark.anyio` to `@pytest.mark.asyncio` throughout this task's tests. Check your existing test configuration first.
3. **Can't recover:** `git checkout -- .` and revisit.

---

## Task 8: Create init command

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/init.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/main.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/__init__.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/test_init.py`

**Prerequisites:**
- Task 2 complete (main.py with cli group)
- Task 5 complete (output.py)
- Task 7 complete (init_project service)

**Step 1: Create directories**

Run:
```bash
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands
```

**Step 2: Create commands/__init__.py**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/__init__.py`:

```python
"""CLI command adapters — Click commands that delegate to services."""
```

**Step 3: Create tests/cli/commands/__init__.py**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/__init__.py`:

```python
```

(Empty file.)

**Step 4: Write the failing test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/test_init.py`:

```python
"""Tests for the ``miniautogen init`` command."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from miniautogen.cli.main import cli


def test_init_creates_project(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "my-app", "--target-dir", str(tmp_path)])

    assert result.exit_code == 0, f"Failed: {result.output}"
    project_dir = tmp_path / "my-app"
    assert project_dir.is_dir()
    assert (project_dir / "miniautogen.yaml").is_file()
    assert (project_dir / "agents" / "__init__.py").is_file()
    assert (project_dir / "pipelines" / "main.py").is_file()
    assert (project_dir / ".env").is_file()
    assert (project_dir / "tools").is_dir()


def test_init_yaml_has_correct_values(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "init", "test-proj",
            "--target-dir", str(tmp_path),
            "--model", "claude-3-haiku",
            "--provider", "anthropic",
        ],
    )

    assert result.exit_code == 0, f"Failed: {result.output}"
    content = yaml.safe_load((tmp_path / "test-proj" / "miniautogen.yaml").read_text())
    assert content["project"]["name"] == "test-proj"
    assert content["provider"]["model"] == "claude-3-haiku"
    assert content["provider"]["default"] == "anthropic"


def test_init_default_model_and_provider(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "demo", "--target-dir", str(tmp_path)])

    assert result.exit_code == 0, f"Failed: {result.output}"
    content = yaml.safe_load((tmp_path / "demo" / "miniautogen.yaml").read_text())
    assert content["provider"]["default"] == "litellm"
    assert content["provider"]["model"] == "gpt-4o-mini"


def test_init_no_examples(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli, ["init", "minimal", "--target-dir", str(tmp_path), "--no-examples"],
    )

    assert result.exit_code == 0, f"Failed: {result.output}"
    project_dir = tmp_path / "minimal"
    assert project_dir.is_dir()
    assert (project_dir / "miniautogen.yaml").is_file()
    # No example pipeline main.py, but __init__.py should exist
    assert not (project_dir / "pipelines" / "main.py").exists()


def test_init_error_on_existing_directory(tmp_path: Path) -> None:
    (tmp_path / "existing").mkdir()
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "existing", "--target-dir", str(tmp_path)])

    assert result.exit_code != 0
    assert "already exists" in result.output.lower()


def test_init_success_message(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "hello", "--target-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "hello" in result.output.lower() or "created" in result.output.lower()
```

**Step 5: Run test to verify it fails**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/cli/commands/test_init.py -v 2>&1 | head -10
```

**Expected output:** Failures — the `init` command is not yet registered.

**Step 6: Write the init command**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/init.py`:

```python
"""``miniautogen init`` command — scaffolds a new project."""

from __future__ import annotations

from pathlib import Path

import click

from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error, echo_success
from miniautogen.cli.services.init_project import scaffold_project


@click.command("init")
@click.argument("name")
@click.option(
    "--model",
    default="gpt-4o-mini",
    show_default=True,
    help="Default LLM model.",
)
@click.option(
    "--provider",
    default="litellm",
    show_default=True,
    help="Default LLM provider.",
)
@click.option(
    "--no-examples",
    is_flag=True,
    default=False,
    help="Skip example agent and pipeline files.",
)
@click.option(
    "--target-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Parent directory for the new project.",
)
def init_command(
    name: str,
    model: str,
    provider: str,
    no_examples: bool,
    target_dir: Path,
) -> None:
    """Create a new MiniAutoGen project."""
    try:
        project_path = run_async(
            scaffold_project,
            name=name,
            model=model,
            provider=provider,
            target_dir=target_dir,
            include_examples=not no_examples,
        )
        echo_success(f"Project created at {project_path}")
    except FileExistsError as exc:
        echo_error(str(exc))
        raise SystemExit(1) from exc
```

**Step 7: Register the init command in main.py**

Modify `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/main.py`. Add these lines **after** the `cli` group definition (at the bottom of the file):

```python
# --- Register commands ---
from miniautogen.cli.commands.init import init_command  # noqa: E402

cli.add_command(init_command)
```

The full file should now be:

```python
"""CLI entry point and async bridge.

This module defines the top-level Click group and a helper to bridge
synchronous Click commands to asynchronous service functions via AnyIO.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar

import anyio
import click

F = TypeVar("F", bound=Callable[..., Any])

_VERSION = "0.1.0"


def run_async(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run an async function synchronously using AnyIO.

    Used by Click commands to call async service functions::

        result = run_async(scaffold_project, name="demo", model="gpt-4o-mini")
    """
    return anyio.from_thread.run(func, *args, **kwargs) if False else anyio.run(
        functools.partial(func, *args, **kwargs),
    )


def _get_version() -> str:
    """Return package version from metadata, falling back to hardcoded value."""
    try:
        from importlib.metadata import version

        return version("miniautogen")
    except Exception:
        return _VERSION


@click.group()
@click.version_option(version=_get_version(), prog_name="miniautogen")
def cli() -> None:
    """MiniAutoGen — multi-agent orchestration framework."""


# --- Register commands ---
from miniautogen.cli.commands.init import init_command  # noqa: E402

cli.add_command(init_command)
```

**Step 8: Run tests to verify they pass**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/cli/commands/test_init.py -v
```

**Expected output:** All tests PASSED (6 tests).

**Step 9: Run all CLI tests together**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/cli/ -v
```

**Expected output:** All CLI tests pass (main + errors + config + output + services + commands).

**Step 10: Run ruff**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/cli/ tests/cli/ --fix
```

**Step 11: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && git add miniautogen/cli/commands/__init__.py miniautogen/cli/commands/init.py miniautogen/cli/main.py tests/cli/commands/__init__.py tests/cli/commands/test_init.py && git commit -m "feat: add 'miniautogen init' command with project scaffolding"
```

**If Task Fails:**
1. **CliRunner path validation fails:** The `--target-dir` option uses `click.Path(exists=True)`. When using `CliRunner`, `tmp_path` should exist. If Click cannot find the path, check that `tmp_path` is an absolute path and exists.
2. **run_async raises "cannot be called from a running event loop":** If Click's test runner already has an event loop, change `run_async` to detect and handle this case. However, `CliRunner` is synchronous, so this should not occur.
3. **Can't recover:** `git checkout -- .` and revisit.

---

## Task 9: Architectural import boundary test

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_import_boundary.py`

**Prerequisites:**
- Tasks 2-8 complete (all cli/ files exist)

**Step 1: Write the boundary test**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/test_import_boundary.py`:

```python
"""Architectural test: CLI code must not import internal SDK modules.

The CLI is a pure consumer of ``miniautogen.api``.  It must never reach
into ``miniautogen.core``, ``miniautogen.stores``, ``miniautogen.backends``,
``miniautogen.policies``, ``miniautogen.adapters``, ``miniautogen.pipeline``,
or ``miniautogen.observability`` directly.

This test scans all ``.py`` files under ``miniautogen/cli/`` using the
``ast`` module and asserts that no prohibited imports are found.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Root of the CLI package.
CLI_ROOT = Path(__file__).resolve().parent.parent.parent / "miniautogen" / "cli"

# Prefixes that CLI code is NOT allowed to import.
PROHIBITED_PREFIXES = (
    "miniautogen.core",
    "miniautogen.stores",
    "miniautogen.backends",
    "miniautogen.policies",
    "miniautogen.adapters",
    "miniautogen.pipeline",
    "miniautogen.observability",
    "miniautogen.storage",
    "miniautogen.app",
    "miniautogen.agent",
    "miniautogen.chat",
    "miniautogen.llms",
    "miniautogen.schemas",
    "miniautogen.compat",
)

# Prefixes that ARE allowed.
ALLOWED_PREFIXES = (
    "miniautogen.api",
    "miniautogen.cli",
)


def _collect_imports(filepath: Path) -> list[tuple[str, int]]:
    """Return list of (module_path, line_number) for all imports in file."""
    source = filepath.read_text()
    tree = ast.parse(source, filename=str(filepath))
    imports: list[tuple[str, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.module, node.lineno))

    return imports


def _find_violations() -> list[str]:
    """Scan all .py files in CLI package for prohibited imports."""
    violations = []

    for py_file in CLI_ROOT.rglob("*.py"):
        rel_path = py_file.relative_to(CLI_ROOT.parent.parent)
        for module, lineno in _collect_imports(py_file):
            if not module.startswith("miniautogen"):
                continue
            if any(module.startswith(p) for p in ALLOWED_PREFIXES):
                continue
            if any(module.startswith(p) for p in PROHIBITED_PREFIXES):
                violations.append(
                    f"{rel_path}:{lineno} imports '{module}' "
                    f"(only miniautogen.api and miniautogen.cli.* allowed)"
                )

    return violations


def test_cli_only_imports_from_public_api() -> None:
    """CLI code must only import from miniautogen.api or miniautogen.cli.*."""
    violations = _find_violations()
    assert violations == [], (
        "CLI import boundary violated:\n" + "\n".join(f"  - {v}" for v in violations)
    )


def test_cli_directory_has_python_files() -> None:
    """Sanity check: ensure the test actually scans files."""
    py_files = list(CLI_ROOT.rglob("*.py"))
    assert len(py_files) >= 5, (
        f"Expected at least 5 .py files in {CLI_ROOT}, found {len(py_files)}"
    )
```

**Step 2: Run the test**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/cli/test_import_boundary.py -v
```

**Expected output:**
```
tests/cli/test_import_boundary.py::test_cli_only_imports_from_public_api PASSED
tests/cli/test_import_boundary.py::test_cli_directory_has_python_files PASSED
```

If it FAILS with import violations, fix the offending file to import from `miniautogen.api` instead, then re-run.

**Step 3: Run ruff**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && ruff check tests/cli/test_import_boundary.py --fix
```

**Step 4: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && git add tests/cli/test_import_boundary.py && git commit -m "test: add architectural import boundary test for CLI package"
```

**If Task Fails:**
1. **Violations found in CLI code:** This means a previous task introduced a prohibited import. Fix the offending file to use `miniautogen.api` instead of the internal module. The most likely offenders are `services/init_project.py` or `config.py` — but as written they only import stdlib, pydantic, yaml, jinja2, and click.
2. **CLI_ROOT path resolution wrong:** The test computes `CLI_ROOT` as `tests/cli/../../miniautogen/cli`. Verify the file is at `tests/cli/test_import_boundary.py` and the project root is two levels up.
3. **Can't recover:** `git checkout -- .` and revisit.

---

## Task 10: Run full test suite and verify everything passes

**Files:**
- No new files

**Prerequisites:**
- Tasks 1-9 all complete

**Step 1: Run all CLI tests**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && pytest tests/cli/ -v --tb=short
```

**Expected output:** All CLI tests pass. Expected count: approximately 45+ tests.

**Step 2: Run the full test suite**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && pytest --tb=short -q
```

**Expected output:** All tests pass. Count should be 542 + ~45 new CLI tests = ~587 tests. Zero failures.

**Step 3: Run ruff on all new code**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && ruff check miniautogen/cli/ miniautogen/__main__.py tests/cli/ --fix
```

**Expected output:** No errors remaining.

**Step 4: Verify CLI entry point works**

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m miniautogen --version
```

**Expected output:**
```
miniautogen, version 0.1.0
```

Run:
```bash
cd /Users/brunocapelao/Projects/miniAutoGen && python -m miniautogen --help
```

**Expected output:** Shows help text with `init` command listed.

Run:
```bash
cd /tmp && python -m miniautogen init test-project && ls test-project/ && rm -rf test-project
```

**Expected output:**
```
[OK] Project created at /tmp/test-project
agents  miniautogen.yaml  pipelines  tools  .env
```

**If Task Fails:**
1. **Some existing tests broke:** Run `pytest --tb=long` to identify the failing test. Likely caused by an import side-effect. Fix the import or isolate the issue.
2. **python -m miniautogen fails:** Check `miniautogen/__main__.py` exists and imports correctly.
3. **Can't recover:** Document what failed, `git stash`, and return to human partner.

---

## Task 11: Code Review Checkpoint

**Prerequisites:**
- Tasks 1-10 complete, all tests passing

**Step 1: Dispatch all 3 reviewers in parallel**

- REQUIRED SUB-SKILL: Use requesting-code-review
- All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
- Wait for all to complete

**Step 2: Handle findings by severity (MANDATORY)**

**Critical/High/Medium Issues:**
- Fix immediately (do NOT add TODO comments for these severities)
- Re-run all 3 reviewers in parallel after fixes
- Repeat until zero Critical/High/Medium issues remain

**Low Issues:**
- Add `TODO(review):` comments in code at the relevant location
- Format: `TODO(review): [Issue description] (reported by [reviewer] on [date], severity: Low)`
- This tracks tech debt for future resolution

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location
- Format: `FIXME(nitpick): [Issue description] (reported by [reviewer] on [date], severity: Cosmetic)`
- Low-priority improvements tracked inline

**Step 3: Proceed only when:**
- Zero Critical/High/Medium issues remain
- All Low issues have `TODO(review):` comments added
- All Cosmetic issues have `FIXME(nitpick):` comments added

**Step 4: Final commit with review fixes (if any)**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen && git add -A && git commit -m "fix: address code review findings for CLI chunk 1"
```

---

## Summary of Files Created

| File | Purpose |
|------|---------|
| `miniautogen/__main__.py` | `python -m miniautogen` support |
| `miniautogen/cli/__init__.py` | CLI package marker |
| `miniautogen/cli/main.py` | Click group, `run_async` helper, version |
| `miniautogen/cli/errors.py` | Error hierarchy with exit codes |
| `miniautogen/cli/config.py` | `ProjectConfig`, `find_project_root`, `load_config` |
| `miniautogen/cli/output.py` | `echo_success/error/info/json/table` |
| `miniautogen/cli/templates/__init__.py` | Templates package marker |
| `miniautogen/cli/templates/project/miniautogen.yaml.j2` | Project config template |
| `miniautogen/cli/templates/project/agents/__init__.py.j2` | Agents module template |
| `miniautogen/cli/templates/project/pipelines/main.py.j2` | Pipeline example template |
| `miniautogen/cli/templates/project/.env.j2` | Environment file template |
| `miniautogen/cli/services/__init__.py` | Services package marker |
| `miniautogen/cli/services/init_project.py` | `scaffold_project` async service |
| `miniautogen/cli/commands/__init__.py` | Commands package marker |
| `miniautogen/cli/commands/init.py` | `init` Click command |
| `tests/cli/__init__.py` | Test package marker |
| `tests/cli/test_main.py` | CLI foundation tests |
| `tests/cli/test_errors.py` | Error hierarchy tests |
| `tests/cli/test_config.py` | Config loading tests |
| `tests/cli/test_output.py` | Output formatting tests |
| `tests/cli/test_import_boundary.py` | Architectural boundary test |
| `tests/cli/services/__init__.py` | Test package marker |
| `tests/cli/services/test_init_project.py` | Scaffolding service tests |
| `tests/cli/commands/__init__.py` | Test package marker |
| `tests/cli/commands/test_init.py` | Init command integration tests |

**Files Modified:**
| File | Change |
|------|--------|
| `pyproject.toml` | Added click, pyyaml deps + scripts entry |
| `poetry.lock` | Updated by poetry lock |
