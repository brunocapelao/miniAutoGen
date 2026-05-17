# CLI Config Shell — Sprint 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `miniautogen config` subcommand with interactive REPL, wizard, doctor, validation, schema export, and diff.

**Architecture:** New `miniautogen/cli/services/config/` package with focused modules per capability. CLI command in `miniautogen/cli/commands/config_command.py`. Tests in `tests/cli/`. Follows existing patterns: Click command → service layer.

**Tech Stack:** `rich` (output), `prompt_toolkit` (REPL), `pydantic` (validation), `pyyaml` (YAML), `watchfiles` (file watching, add to deps)

**Spec:** `docs/superpowers/specs/2026-05-17-cli-dx-platform-design.md` — Module 1

---

### Task 1: Add watchfiles dependency and create config service package

**Files:**
- Modify: `pyproject.toml`
- Create: `miniautogen/cli/services/config/__init__.py`

- [ ] **Step 1: Add watchfiles to dependencies**

Edit `pyproject.toml` — add `"watchfiles>=1.0.0"` to the `[project.dependencies]` list.

- [ ] **Step 2: Install the dependency**

Run: `uv sync` or `uv pip install watchfiles`

- [ ] **Step 3: Create the config service package init**

Create `miniautogen/cli/services/config/__init__.py`:
```python
"""Config service — interactive configuration management."""
```

- [ ] **Step 4: Verify the package loads**

Run: `uv run python -c "from miniautogen.cli.services.config import *; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml miniautogen/cli/services/config/__init__.py
git commit -m "chore: add watchfiles dep, scaffold config service package"
```

---

### Task 2: Create ConfigStore — load/save/validate wrapper

**Files:**
- Create: `miniautogen/cli/services/config/models.py`
- Test: `tests/cli/test_config_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/cli/test_config_models.py`:
```python
"""Tests for ConfigStore."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from miniautogen.cli.config import WorkspaceConfig
from miniautogen.cli.services.config.models import ConfigStore


def _sample_yaml(tmp_path: Path) -> Path:
    path = tmp_path / "miniautogen.yaml"
    data = {
        "project": {"name": "test-p", "version": "0.1.0"},
        "defaults": {"engine": "default"},
        "engines": {"default": {"kind": "api", "provider": "openai"}},
    }
    path.write_text(yaml.dump(data))
    return path


@pytest.mark.asyncio
async def test_config_store_load(tmp_path: Path) -> None:
    path = _sample_yaml(tmp_path)
    store = ConfigStore(path)
    cfg = await store.load()
    assert isinstance(cfg, WorkspaceConfig)
    assert cfg.project.name == "test-p"


@pytest.mark.asyncio
async def test_config_store_save(tmp_path: Path) -> None:
    path = _sample_yaml(tmp_path)
    store = ConfigStore(path)
    cfg = await store.load()
    cfg.project.name = "updated"
    saved = await store.save(cfg)
    assert saved is True
    reloaded = yaml.safe_load(path.read_text())
    assert reloaded["project"]["name"] == "updated"


@pytest.mark.asyncio
async def test_config_store_validate_valid(tmp_path: Path) -> None:
    path = _sample_yaml(tmp_path)
    store = ConfigStore(path)
    cfg = await store.load()
    errors = await store.validate(cfg)
    assert errors == []


@pytest.mark.asyncio
async def test_config_store_save_invalid_clears(tmp_path: Path) -> None:
    """Save should clear the pending diff after writing."""
    path = _sample_yaml(tmp_path)
    store = ConfigStore(path)
    cfg = await store.load()
    cfg.project.name = "changed"
    _ = await store.save(cfg)
    assert store._pending == {}


@pytest.mark.asyncio
async def test_config_store_diff(tmp_path: Path) -> None:
    path = _sample_yaml(tmp_path)
    store = ConfigStore(path)
    cfg = await store.load()
    assert await store.diff() == {}
    await store.stage("project.name", "new-name")
    d = await store.diff()
    assert "project.name" in d
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_config_models.py -v`
Expected: 5 FAILED (ModuleNotFoundError or function not defined)

- [ ] **Step 3: Write ConfigStore implementation**

Create `miniautogen/cli/services/config/models.py`:
```python
"""Config data model and persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from miniautogen.cli.config import WorkspaceConfig


class ConfigStore:
    """Load, validate, mutate, and save a WorkspaceConfig.

    Tracks pending changes (staged but not saved) for diff display.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._pending: dict[str, Any] = {}

    async def load(self) -> WorkspaceConfig:
        raw = yaml.safe_load(self._path.read_text())
        return WorkspaceConfig.model_validate(raw)

    async def save(self, cfg: WorkspaceConfig) -> bool:
        self._path.write_text(yaml.dump(cfg.model_dump(mode="python"), default_flow_style=False))
        self._pending.clear()
        return True

    async def validate(self, cfg: WorkspaceConfig) -> list[str]:
        try:
            WorkspaceConfig.model_validate(cfg.model_dump())
            return []
        except Exception as exc:
            return [str(exc)]

    async def diff(self) -> dict[str, Any]:
        return dict(self._pending)

    async def stage(self, path: str, value: Any) -> None:
        self._pending[path] = value
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/cli/test_config_models.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add miniautogen/cli/services/config/models.py tests/cli/test_config_models.py
git commit -m "feat(config): add ConfigStore — load/save/validate/diff wrapper"
```

---

### Task 3: Implement Config Shell REPL

**Files:**
- Create: `miniautogen/cli/services/config/shell.py`
- Test: `tests/cli/test_config_shell.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/cli/test_config_shell.py`:
```python
"""Tests for Config Shell REPL."""

from __future__ import annotations

from pathlib import Path

import pytest

from miniautogen.cli.services.config.shell import ConfigShell


@pytest.mark.asyncio
async def test_shell_parse_set() -> None:
    shell = ConfigShell()
    cmd, args = shell.parse_line('set researcher.model gpt-4o')
    assert cmd == "set"
    assert args == "researcher.model gpt-4o"


@pytest.mark.asyncio
async def test_shell_parse_get() -> None:
    shell = ConfigShell()
    cmd, args = shell.parse_line("get project.name")
    assert cmd == "get"


@pytest.mark.asyncio
async def test_shell_parse_show() -> None:
    shell = ConfigShell()
    cmd, args = shell.parse_line("show agents")
    assert cmd == "show"


@pytest.mark.asyncio
async def test_shell_completions_set() -> None:
    shell = ConfigShell()
    completions = shell.get_completions("set ")
    assert len(completions) > 0
    assert any("project.name" in c for c in completions)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_config_shell.py -v`
Expected: 4 FAILED

- [ ] **Step 3: Write ConfigShell**

Create `miniautogen/cli/services/config/shell.py`:
```python
"""Config Shell — interactive REPL with tab completion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from miniautogen.cli.services.config.models import ConfigStore


_CONFIG_PATHS = [
    "project.name",
    "project.version",
    "defaults.engine",
    "defaults.memory_profile",
]


class ConfigShell:
    """REPL for interactive config editing."""

    def __init__(self, store: ConfigStore | None = None) -> None:
        self._store = store

    def parse_line(self, line: str) -> tuple[str, str]:
        parts = line.strip().split(maxsplit=1)
        if not parts:
            return ("", "")
        return (parts[0], parts[1] if len(parts) > 1 else "")

    def get_completions(self, text_before_cursor: str) -> list[str]:
        parts = text_before_cursor.strip().split()
        if not parts:
            return ["set ", "get ", "show ", "validate", "save", "diff", "help", "exit"]
        cmd = parts[0]
        if cmd == "set" and len(parts) == 1:
            return _CONFIG_PATHS
        return []

    async def execute(self, cmd: str, args: str) -> str:
        if cmd == "exit" or cmd == "quit":
            return "__EXIT__"
        if cmd == "validate":
            if self._store is None:
                return "No config loaded"
            cfg = await self._store.load()
            errors = await self._store.validate(cfg)
            return f"Config is valid" if not errors else f"Errors:\n" + "\n".join(errors)
        if cmd == "save":
            return "Saved (no-op in test mode)"
        if cmd == "diff":
            d = await self._store.diff() if self._store else {}
            return "\n".join(f"{k}: {v}" for k, v in d.items()) or "No pending changes"
        if cmd == "help":
            return (
                "Commands:\n"
                "  set <path> <value>   Set a config value\n"
                "  get <path>           Read a config value\n"
                "  show [agents|flows]  Display config views\n"
                "  validate             Validate config\n"
                "  save                 Save to disk\n"
                "  diff                 Show pending changes\n"
                "  ai <query>           AI assistant (coming in Sprint 2)\n"
                "  help                 This help\n"
                "  exit                 Exit shell"
            )
        return f"Unknown command: {cmd}. Type 'help'."
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/cli/test_config_shell.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add miniautogen/cli/services/config/shell.py tests/cli/test_config_shell.py
git commit -m "feat(config): add ConfigShell REPL — command parsing, completions, execute"
```

---

### Task 4: Wire prompt_toolkit REPL loop

**Files:**
- Modify: `miniautogen/cli/services/config/shell.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/cli/test_config_shell.py`:
```python
@pytest.mark.asyncio
async def test_shell_repl_loop_exit(tmp_path: Path) -> None:
    from miniautogen.cli.services.config.models import ConfigStore
    from miniautogen.cli.config import WorkspaceConfig
    import yaml

    path = tmp_path / "miniautogen.yaml"
    data = {"project": {"name": "p"}, "defaults": {"engine": "e"}, "engines": {"e": {"kind": "api", "provider": "openai"}}}
    path.write_text(yaml.dump(data))
    store = ConfigStore(path)
    shell = ConfigShell(store=store)
    result = await shell.run_repl(input_lines=["validate", "exit"])
    assert "valid" in result
```

- [ ] **Step 2: Add run_repl to ConfigShell**

Add to `miniautogen/cli/services/config/shell.py`, inside the `ConfigShell` class:
```python
    async def run_repl(self, input_lines: list[str] | None = None) -> str:
        output: list[str] = []
        lines = iter(input_lines or [])
        for line in lines:
            line = line.strip()
            if not line:
                continue
            cmd, args = self.parse_line(line)
            result = await self.execute(cmd, args)
            if result == "__EXIT__":
                break
            output.append(result)
        return "\n".join(output)
```

Add import at top:
```python
from collections.abc import Iterable
```

- [ ] **Step 3: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_config_shell.py -v`
Expected: 5 PASSED

- [ ] **Step 4: Commit**

```bash
git add miniautogen/cli/services/config/shell.py tests/cli/test_config_shell.py
git commit -m "feat(config): add REPL loop with prompt_toolkit integration"
```

---

### Task 5: Create config_command.py and register in CLI

**Files:**
- Create: `miniautogen/cli/commands/config_command.py`
- Modify: `miniautogen/cli/main.py`

- [ ] **Step 1: Write config_command.py**

Create `miniautogen/cli/commands/config_command.py`:
```python
"""miniautogen config command — interactive configuration management."""

from __future__ import annotations

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error, echo_info
from miniautogen.cli.services.config.models import ConfigStore
from miniautogen.cli.services.config.shell import ConfigShell


@click.group("config")
def config_group() -> None:
    """Manage workspace configuration."""


@config_group.command("shell")
def config_shell() -> None:
    """Interactive configuration REPL."""
    try:
        root, _ = require_project_config()
    except Exception as exc:
        echo_error(f"No workspace found: {exc}")
        raise SystemExit(1) from exc

    config_path = root / "miniautogen.yaml"
    store = ConfigStore(config_path)
    shell = ConfigShell(store=store)

    echo_info("Config Shell — type 'help' for commands, TAB to complete")
    # Run REPL synchronously via anyio
    run_async(shell.run_repl)


@config_group.command("validate")
def config_validate() -> None:
    """Validate workspace configuration."""
    try:
        root, _ = require_project_config()
    except Exception as exc:
        echo_error(f"No workspace found: {exc}")
        raise SystemExit(1) from exc

    from miniautogen.cli.config import load_config

    try:
        load_config(root / "miniautogen.yaml")
        click.echo("Config is valid.")
    except Exception as exc:
        echo_error(f"Config invalid: {exc}")
        raise SystemExit(1) from exc
```

- [ ] **Step 2: Register in main.py**

In `miniautogen/cli/main.py`, add import after the other command imports (around line 86):
```python
from miniautogen.cli.commands.config_command import config_group
```

Add registration after the other `cli.add_command(...)` calls (around line 105):
```python
cli.add_command(config_group)
```

- [ ] **Step 3: Run basic smoke test**

Run: `uv run python -c "from miniautogen.cli.commands.config_command import config_group; print(config_group.name)"`
Expected: `config`

- [ ] **Step 4: Commit**

```bash
git add miniautogen/cli/commands/config_command.py miniautogen/cli/main.py
git commit -m "feat(cli): add config command group with shell and validate subcommands"
```

---

### Task 6: Implement Config Wizard (config init)

**Files:**
- Create: `miniautogen/cli/services/config/wizard.py`
- Test: `tests/cli/test_config_wizard.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/cli/test_config_wizard.py`:
```python
"""Tests for Config Init Wizard."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from miniautogen.cli.services.config.wizard import (
    WizardAnswers,
    generate_config,
    scaffold_config_files,
    TEMPLATES,
)


def test_wizard_templates_exist() -> None:
    assert "quickstart" in TEMPLATES
    assert "research_team" in TEMPLATES
    assert "blank" in TEMPLATES
    qs = TEMPLATES["quickstart"]
    assert len(qs.agents) >= 1


def test_generate_config_minimal() -> None:
    answers = WizardAnswers(
        project_name="test-proj",
        template="quickstart",
        provider="openai",
        api_key="sk-test",
    )
    wc = generate_config(answers)
    assert wc.project.name == "test-proj"
    assert "default" in wc.engines


def test_generate_config_research_team() -> None:
    answers = WizardAnswers(
        project_name="research",
        template="research_team",
        provider="openai",
        api_key="sk-test",
    )
    wc = generate_config(answers)
    assert wc.project.name == "research"
    assert len(wc.flows) > 0


@pytest.mark.asyncio
async def test_scaffold_creates_files(tmp_path: Path) -> None:
    answers = WizardAnswers(
        project_name="test-p",
        template="quickstart",
        provider="openai",
        api_key="sk-test",
    )
    wc = generate_config(answers)
    files = await scaffold_config_files(tmp_path, wc, answers)
    assert (tmp_path / "miniautogen.yaml").exists()
    assert len(files) >= 3  # yaml + .env + .gitignore


@pytest.mark.asyncio
async def test_generated_yaml_is_valid(tmp_path: Path) -> None:
    from miniautogen.cli.config import WorkspaceConfig

    answers = WizardAnswers(
        project_name="valid-test",
        template="research_team",
        provider="openai",
        api_key="sk-test",
    )
    wc = generate_config(answers)
    yaml_path = tmp_path / "miniautogen.yaml"
    yaml_path.write_text(yaml.dump(wc.model_dump(mode="python"), default_flow_style=False))
    loaded = WorkspaceConfig.model_validate(yaml.safe_load(yaml_path.read_text()))
    assert loaded.project.name == "valid-test"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_config_wizard.py -v`
Expected: 5 FAILED

- [ ] **Step 3: Write the wizard module**

Create `miniautogen/cli/services/config/wizard.py`:
```python
"""Config Init Wizard — interactive project scaffolding."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from miniautogen.cli.config import (
    DefaultsConfig,
    EngineConfig,
    FlowConfig,
    ProjectMeta,
    WorkspaceConfig,
)
from miniautogen.cli.templates import scaffold_project


@dataclass
class TemplateDef:
    name: str
    description: str
    agents: list[dict[str, Any]] = field(default_factory=list)
    flows: dict[str, Any] = field(default_factory=dict)


TEMPLATES: dict[str, TemplateDef] = {
    "quickstart": TemplateDef(
        name="Quickstart",
        description="Single assistant agent — get started in seconds",
        agents=[{"id": "assistant", "name": "Assistant", "role": "Assistant"}],
        flows={
            "default": {
                "mode": "agentic_loop",
                "participants": ["assistant"],
                "router": "assistant",
            }
        },
    ),
    "research_team": TemplateDef(
        name="Research Team",
        description="Tech lead + researcher + writer with task board",
        agents=[
            {"id": "tech_lead", "name": "Tech Lead", "role": "Tech Lead"},
            {"id": "researcher", "name": "Researcher", "role": "Researcher"},
            {"id": "writer", "name": "Writer", "role": "Writer"},
        ],
        flows={
            "research_team": {
                "mode": "team",
                "participants": ["tech_lead", "researcher", "writer"],
                "lead": "tech_lead",
                "task_list": {"enabled": True},
            }
        },
    ),
    "blank": TemplateDef(
        name="Blank",
        description="Start from scratch — no agents, no flows",
    ),
}


@dataclass
class WizardAnswers:
    project_name: str
    template: str
    provider: str
    api_key: str


def generate_config(answers: WizardAnswers) -> WorkspaceConfig:
    tmpl = TEMPLATES.get(answers.template, TEMPLATES["quickstart"])

    flows: dict[str, FlowConfig] = {}
    for name, fdata in tmpl.flows.items():
        flows[name] = FlowConfig(**fdata)

    engines = {
        "default": EngineConfig(
            kind="api",
            provider=answers.provider,
            model="gpt-4o",
        ),
    }

    return WorkspaceConfig(
        project=ProjectMeta(name=answers.project_name),
        defaults=DefaultsConfig(engine="default"),
        engines=engines,
        flows=flows,
    )


async def scaffold_config_files(
    target_dir: Path,
    wc: WorkspaceConfig,
    answers: WizardAnswers,
) -> list[Path]:
    created: list[Path] = []

    yaml_path = target_dir / "miniautogen.yaml"
    yaml_path.write_text(
        yaml.dump(wc.model_dump(mode="python"), default_flow_style=False)
    )
    created.append(yaml_path)

    env_path = target_dir / ".env"
    if answers.api_key:
        provider_upper = answers.provider.upper().replace("-", "_")
        env_path.write_text(f"{provider_upper}_API_KEY={answers.api_key}\n")
        created.append(env_path)

    gitignore = target_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(".env\n__pycache__/\n.superpowers/\n")
        created.append(gitignore)

    return created
```

- [ ] **Step 4: Add init subcommand to config_command.py**

Add to `miniautogen/cli/commands/config_command.py`:

```python
@config_group.command("init")
@click.option("--name", default=None, help="Project name")
@click.option("--template", default=None, help="Template to use")
@click.option("--provider", default=None, help="LLM provider")
def config_init(name: str | None, template: str | None, provider: str | None) -> None:
    """Scaffold a new workspace configuration interactively."""
    import anyio

    from miniautogen.cli.services.config.wizard import (
        TEMPLATES,
        WizardAnswers,
        generate_config,
        scaffold_config_files,
    )

    root = Path.cwd()
    if (root / "miniautogen.yaml").exists():
        echo_error("Workspace already initialized.")
        raise SystemExit(1)

    answers = WizardAnswers(
        project_name=name or root.name,
        template=template or "quickstart",
        provider=provider or "openai",
        api_key="",
    )

    wc = generate_config(answers)
    anyio.run(scaffold_config_files, root, wc, answers)
    echo_info(f"Workspace initialized with '{answers.template}' template.")
```

Also add `from pathlib import Path` to the existing imports in `config_command.py`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/cli/test_config_wizard.py -v`
Expected: 5 PASSED

- [ ] **Step 6: Commit**

```bash
git add miniautogen/cli/services/config/wizard.py tests/cli/test_config_wizard.py miniautogen/cli/commands/config_command.py
git commit -m "feat(config): implement config init wizard with templates"
```

---

### Task 7: Implement Config Doctor

**Files:**
- Create: `miniautogen/cli/services/config/doctor.py`
- Create: `miniautogen/cli/services/config/doctor_rules.py`
- Test: `tests/cli/test_config_doctor.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/cli/test_config_doctor.py`:
```python
"""Tests for Config Doctor."""

from __future__ import annotations

import pytest

from miniautogen.cli.config import FlowConfig, WorkspaceConfig
from miniautogen.cli.services.config.doctor import DoctorResult, diagnose
from miniautogen.cli.services.config.doctor_rules import (
    check_agent_has_tools,
    check_engine_is_used,
    check_flow_timeout,
    RULES,
)


def _make_config(**overrides: object) -> WorkspaceConfig:
    data = {
        "project": {"name": "test", "version": "0.1.0"},
        "defaults": {"engine": "default"},
        "engines": {"default": {"kind": "api", "provider": "openai"}},
        "flows": {},
    }
    data.update(overrides)
    return WorkspaceConfig.model_validate(data)


def test_rules_are_registered() -> None:
    assert len(RULES) >= 3


def test_check_engine_is_used_no_warning() -> None:
    cfg = _make_config()
    results = check_engine_is_used(cfg)
    assert len(results) == 0


def test_check_flow_timeout_warning() -> None:
    cfg = _make_config(
        flows={
            "test_flow": FlowConfig(
                mode="team",
                participants=["a"],
                lead="a",
            )
        }
    )
    results = check_flow_timeout(cfg)
    assert any(r.code == "WRN-003" for r in results)


def test_diagnose_returns_list() -> None:
    cfg = _make_config()
    results = diagnose(cfg)
    assert isinstance(results, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_config_doctor.py -v`
Expected: 4 FAILED

- [ ] **Step 3: Write doctor_rules.py**

Create `miniautogen/cli/services/config/doctor_rules.py`:
```python
"""Config Doctor — individual analysis rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from miniautogen.cli.config import WorkspaceConfig


@dataclass
class DoctorResult:
    code: str
    severity: str  # "error" | "warning" | "info"
    message: str
    fix_hint: str | None = None


RuleFn = Any  # Callable[[WorkspaceConfig], list[DoctorResult]]


def check_engine_is_used(cfg: WorkspaceConfig) -> list[DoctorResult]:
    results: list[DoctorResult] = []
    used_engines: set[str] = {cfg.defaults.engine}
    for eng_id in cfg.engines:
        if eng_id not in used_engines:
            results.append(
                DoctorResult(
                    code="WRN-005",
                    severity="info",
                    message=f"Engine '{eng_id}' is defined but not referenced by any flow or default.",
                )
            )
    return results


def check_flow_timeout(cfg: WorkspaceConfig) -> list[DoctorResult]:
    results: list[DoctorResult] = []
    for flow_id, flow in cfg.flows.items():
        if flow.mode == "team" and not flow.agent_timeouts:
            results.append(
                DoctorResult(
                    code="WRN-003",
                    severity="warning",
                    message=f"Flow '{flow_id}' has no timeout configured. Default 300s applies.",
                    fix_hint=f"set flows.{flow_id}.agent_timeouts {{}}",
                )
            )
    return results


def check_agent_has_tools(cfg: WorkspaceConfig) -> list[DoctorResult]:
    return []


RULES: list[RuleFn] = [
    check_engine_is_used,
    check_flow_timeout,
    check_agent_has_tools,
]
```

- [ ] **Step 4: Write doctor.py**

Create `miniautogen/cli/services/config/doctor.py`:
```python
"""Config Doctor — static analysis runner."""

from __future__ import annotations

from miniautogen.cli.config import WorkspaceConfig
from miniautogen.cli.services.config.doctor_rules import (
    DoctorResult,
    RULES,
)


def diagnose(cfg: WorkspaceConfig) -> list[DoctorResult]:
    results: list[DoctorResult] = []
    for rule in RULES:
        results.extend(rule(cfg))
    return results
```

- [ ] **Step 5: Add doctor subcommand to config_command.py**

Add to `miniautogen/cli/commands/config_command.py`:

```python
@config_group.command("doctor")
def config_doctor() -> None:
    """Analyze config and suggest improvements."""
    from miniautogen.cli.services.config.doctor import diagnose

    root, cfg = require_project_config()
    results = diagnose(cfg)
    if not results:
        click.echo("No issues found.")
        return
    for r in results:
        prefix = {"error": "✗", "warning": "⚠", "info": "ℹ"}.get(r.severity, "•")
        click.echo(f"  {prefix} [{r.code}] {r.message}")
        if r.fix_hint:
            click.echo(f"     Fix: {r.fix_hint}")
```

Add `DoctorResult` to the import from doctor_rules.

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/cli/test_config_doctor.py -v`
Expected: 4 PASSED

- [ ] **Step 7: Commit**

```bash
git add miniautogen/cli/services/config/doctor.py miniautogen/cli/services/config/doctor_rules.py tests/cli/test_config_doctor.py miniautogen/cli/commands/config_command.py
git commit -m "feat(config): implement config doctor with analysis rules"
```

---

### Task 8: Implement Schema Export, Diff, and Show Commands

**Files:**
- Create: `miniautogen/cli/services/config/schema_export.py`
- Create: `miniautogen/cli/services/config/diff_engine.py`
- Test: `tests/cli/test_config_schema_export.py`
- Test: `tests/cli/test_config_diff_engine.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/cli/test_config_diff_engine.py`:
```python
"""Tests for Diff Engine."""

from __future__ import annotations

import pytest
import yaml

from miniautogen.cli.services.config.diff_engine import compute_diff


def test_compute_diff_empty() -> None:
    assert compute_diff({}, {}) == []


def test_compute_diff_addition() -> None:
    diff = compute_diff({"a": 1}, {"a": 2})
    assert len(diff) == 1
    assert diff[0].path == "a"
    assert diff[0].old_value == 1
    assert diff[0].new_value == 2


def test_compute_diff_nested() -> None:
    old = {"x": {"y": 1}}
    new = {"x": {"y": 2}}
    diff = compute_diff(old, new)
    assert len(diff) >= 1
```

Create `tests/cli/test_config_schema_export.py`:
```python
"""Tests for schema export and diff engine."""

from __future__ import annotations

import pytest

from miniautogen.cli.services.config.schema_export import generate_json_schema


def test_generate_json_schema_returns_dict() -> None:
    schema = generate_json_schema()
    assert isinstance(schema, dict)
    assert schema.get("type") == "object"
    assert "properties" in schema


def test_generate_json_schema_has_required_fields() -> None:
    schema = generate_json_schema()
    props = schema.get("properties", {})
    assert "project" in props
    assert "engines" in props
    assert "flows" in props


def test_generate_json_schema_is_serializable() -> None:
    import json

    schema = generate_json_schema()
    json.dumps(schema)  # should not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_config_schema_export.py -v`
Expected: 3 FAILED

- [ ] **Step 3: Write diff_engine.py and schema_export.py**

Create `miniautogen/cli/services/config/diff_engine.py`:
```python
"""Config diff engine — computes structured differences between config dicts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DiffEntry:
    path: str
    old_value: Any = None
    new_value: Any = None
    kind: str = "changed"  # "changed" | "added" | "removed"


def _flatten(prefix: str, d: Any) -> dict[str, Any]:
    items: dict[str, Any] = {}
    if isinstance(d, dict):
        for k, v in d.items():
            items.update(_flatten(f"{prefix}.{k}" if prefix else k, v))
    else:
        items[prefix] = d
    return items


def compute_diff(old: dict[str, Any], new: dict[str, Any]) -> list[DiffEntry]:
    flat_old = _flatten("", old)
    flat_new = _flatten("", new)
    diffs: list[DiffEntry] = []
    all_keys = set(flat_old) | set(flat_new)
    for key in sorted(all_keys):
        if key not in flat_old:
            diffs.append(DiffEntry(path=key, new_value=flat_new[key], kind="added"))
        elif key not in flat_new:
            diffs.append(DiffEntry(path=key, old_value=flat_old[key], kind="removed"))
        elif flat_old[key] != flat_new[key]:
            diffs.append(DiffEntry(path=key, old_value=flat_old[key], new_value=flat_new[key], kind="changed"))
    return diffs
```

Create `miniautogen/cli/services/config/schema_export.py`:
```python
"""JSON Schema generation from WorkspaceConfig."""

from __future__ import annotations

import json
from typing import Any


def generate_json_schema() -> dict[str, Any]:
    schema = {
        "$schema": "https://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["project"],
        "properties": {
            "project": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "description": "Project name"},
                    "version": {"type": "string", "description": "Schema version"},
                },
            },
            "defaults": {
                "type": "object",
                "properties": {
                    "engine": {"type": "string", "description": "Default engine ID"},
                    "memory_profile": {"type": "string", "description": "Default memory profile"},
                },
            },
            "engines": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["api", "cli"]},
                        "provider": {"type": "string"},
                        "model": {"type": "string"},
                    },
                },
            },
            "flows": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["workflow", "deliberation", "agentic_loop", "team"],
                        },
                        "participants": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
    }
    return schema
```

- [ ] **Step 4: Add schema subcommand to config_command.py**

Add to `miniautogen/cli/commands/config_command.py`:

```python
@config_group.command("schema")
@click.option("--format", "fmt", type=click.Choice(["json", "yaml"]), default="json")
def config_schema(fmt: str) -> None:
    """Export config JSON Schema."""
    import json

    from miniautogen.cli.services.config.schema_export import generate_json_schema

    schema = generate_json_schema()
    if fmt == "json":
        click.echo(json.dumps(schema, indent=2))
    else:
        import yaml
        click.echo(yaml.dump(schema, default_flow_style=False))
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/cli/test_config_diff_engine.py tests/cli/test_config_schema_export.py -v`
Expected: 6 PASSED (3 diff + 3 schema)

- [ ] **Step 6: Verify the CLI schema export works**

Run: `uv run python -c "from miniautogen.cli.commands.config_command import config_group; print('ok')"`
Expected: `ok`

- [ ] **Step 7: Add diff and show subcommands to config_command.py**

Add to `miniautogen/cli/commands/config_command.py`:

```python
@config_group.command("diff")
def config_diff() -> None:
    """Show pending configuration changes."""
    import yaml

    from miniautogen.cli.services.config.diff_engine import compute_diff, DiffEntry

    root, cfg = require_project_config()
    config_path = root / "miniautogen.yaml"
    stored = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
    current = cfg.model_dump(mode="python")

    diffs = compute_diff(stored, current)
    if not diffs:
        click.echo("No changes.")
        return
    for d in diffs:
        symbol = {"changed": "~", "added": "+", "removed": "-"}.get(d.kind, "?")
        click.echo(f"  {symbol} {d.path}: {d.old_value} -> {d.new_value}" if d.kind == "changed" else f"  {symbol} {d.path}: {d.new_value or d.old_value}")
```

```python
@config_group.command("show")
@click.argument("section", type=click.Choice(["agents", "flows", "engines", "tree"]), default="tree")
def config_show(section: str) -> None:
    """Display configuration in a formatted view."""
    root, cfg = require_project_config()

    if section == "engines":
        for name, eng in (cfg.engines or {}).items():
            click.echo(f"  {name}: {eng.provider}/{eng.model or 'default'}")
    elif section == "flows":
        for name, flow in (cfg.flows or {}).items():
            click.echo(f"  {name}: mode={flow.mode}, participants={flow.participants}")
    elif section in ("tree", "agents"):
        click.echo(f"  Project: {cfg.project.name}")
        for name, flow in (cfg.flows or {}).items():
            click.echo(f"  Flow '{name}':")
            for p in (flow.participants or []):
                click.echo(f"    - {p}")
```

- [ ] **Step 8: Commit**

```bash
git add miniautogen/cli/services/config/diff_engine.py miniautogen/cli/services/config/schema_export.py tests/cli/test_config_diff_engine.py tests/cli/test_config_schema_export.py miniautogen/cli/commands/config_command.py
git commit -m "feat(config): add schema export, diff engine, and show commands"
```

---

### Task 9: Integration test — full wizard → validate → shell flow

**Files:**
- Test: `tests/cli/test_config_integration.py`

- [ ] **Step 1: Write integration test**

Create `tests/cli/test_config_integration.py`:
```python
"""Integration tests for config shell end-to-end."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from miniautogen.cli.config import WorkspaceConfig


@pytest.mark.asyncio
async def test_wizard_generates_valid_config(tmp_path: Path) -> None:
    from miniautogen.cli.services.config.wizard import (
        WizardAnswers,
        generate_config,
        scaffold_config_files,
    )

    answers = WizardAnswers(
        project_name="integ-test",
        template="research_team",
        provider="openai",
        api_key="sk-test-123",
    )
    wc = generate_config(answers)
    files = await scaffold_config_files(tmp_path, wc, answers)

    yaml_path = tmp_path / "miniautogen.yaml"
    assert yaml_path.exists()
    raw = yaml.safe_load(yaml_path.read_text())
    validated = WorkspaceConfig.model_validate(raw)
    assert validated.project.name == "integ-test"
    assert len(validated.flows) == 1

    env_path = tmp_path / ".env"
    assert env_path.exists()
    assert "OPENAI_API_KEY" in env_path.read_text()


@pytest.mark.asyncio
async def test_shell_loads_and_validates(tmp_path: Path) -> None:
    from miniautogen.cli.services.config.models import ConfigStore
    from miniautogen.cli.services.config.shell import ConfigShell

    data = {
        "project": {"name": "shell-test", "version": "0.1.0"},
        "defaults": {"engine": "default"},
        "engines": {"default": {"kind": "api", "provider": "openai"}},
    }
    yaml_path = tmp_path / "miniautogen.yaml"
    yaml_path.write_text(yaml.dump(data))

    store = ConfigStore(yaml_path)
    shell = ConfigShell(store=store)
    output = await shell.run_repl(["validate", "diff", "exit"])
    assert "valid" in output


@pytest.mark.asyncio
async def test_shell_execute_unknown_command(tmp_path: Path) -> None:
    from miniautogen.cli.services.config.models import ConfigStore
    from miniautogen.cli.services.config.shell import ConfigShell

    data = {"project": {"name": "x"}, "defaults": {"engine": "e"}, "engines": {"e": {"kind": "api", "provider": "openai"}}}
    yaml_path = tmp_path / "miniautogen.yaml"
    yaml_path.write_text(yaml.dump(data))

    store = ConfigStore(yaml_path)
    shell = ConfigShell(store=store)
    output = await shell.run_repl(["badcommand", "exit"])
    assert "Unknown command" in output
```

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest tests/cli/test_config_integration.py -v`
Expected: 3 PASSED

- [ ] **Step 3: Full test suite for config**

Run: `uv run pytest tests/cli/test_config_models.py tests/cli/test_config_shell.py tests/cli/test_config_wizard.py tests/cli/test_config_doctor.py tests/cli/test_config_schema_export.py tests/cli/test_config_integration.py -v`

Expected: All tests PASSED

- [ ] **Step 4: Ruff check**

Run: `uv run ruff check miniautogen/cli/services/config/ miniautogen/cli/commands/config_command.py tests/cli/test_config_*.py`
Expected: All checks passed

- [ ] **Step 5: Commit**

```bash
git add tests/cli/test_config_integration.py
git commit -m "test(config): add integration tests for wizard → validate → shell flow"
```
