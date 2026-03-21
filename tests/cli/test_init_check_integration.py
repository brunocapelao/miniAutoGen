"""Integration test: init-generated projects must pass check.

Validates that scaffold_project() produces projects that pass
all check_project() validations, catching template regressions
before they reach users at runtime.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from miniautogen.cli.config import CONFIG_FILENAME, ProjectConfig
from miniautogen.cli.services.check_project import check_project
from miniautogen.cli.services.init_project import scaffold_project


def _load_config(project_dir: Path) -> ProjectConfig:
    """Load and parse the project config from a scaffolded project."""
    config_path = project_dir / CONFIG_FILENAME
    raw = yaml.safe_load(config_path.read_text())
    return ProjectConfig.model_validate(raw)


def _run_check(project_dir: Path, monkeypatch) -> list:
    """Run check_project and return results."""
    config = _load_config(project_dir)
    return check_project(config, project_dir)


class TestInitCheckIntegration:
    """Verify that scaffolded projects pass all validations."""

    def test_default_project_passes_all_checks(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """Default scaffold (with examples) passes every check."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        project_dir = scaffold_project("testproject", tmp_path)
        results = _run_check(project_dir, monkeypatch)

        failures = [r for r in results if not r.passed]
        assert len(failures) == 0, (
            f"Expected all checks to pass, got {len(failures)} failure(s):\n"
            + "\n".join(f"  - {r.name}: {r.message}" for r in failures)
        )

    def test_default_project_validates_all_categories(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """Default scaffold produces results for all expected check areas."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        project_dir = scaffold_project("testproject", tmp_path)
        results = _run_check(project_dir, monkeypatch)

        result_names = {r.name for r in results}

        # Config schema
        assert "config_schema" in result_names
        # Agent validation
        assert any(n.startswith("agent:") for n in result_names)
        # Skill validation
        assert any(n.startswith("skill:") for n in result_names)
        # Tool validation
        assert any(n.startswith("tool:") for n in result_names)
        # Pipeline validation
        assert any(n.startswith("pipeline:") for n in result_names)
        # Engine profiles
        assert "default_engine_profile" in result_names
        # Memory profiles
        assert "default_memory_profile" in result_names
        # Environment check
        assert any(n.startswith("env:") for n in result_names)

    def test_no_examples_project_passes_all_checks(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """Scaffold with --no-examples also passes all checks."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        project_dir = scaffold_project(
            "noexamples", tmp_path, include_examples=False,
        )
        results = _run_check(project_dir, monkeypatch)

        failures = [r for r in results if not r.passed]
        assert len(failures) == 0, (
            f"Expected all checks to pass (no-examples), "
            f"got {len(failures)} failure(s):\n"
            + "\n".join(f"  - {r.name}: {r.message}" for r in failures)
        )

    def test_custom_provider_passes_checks(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """Scaffold with custom provider/model passes checks."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        project_dir = scaffold_project(
            "geminiproject",
            tmp_path,
            model="gemini-2.5-pro",
            provider="gemini",
        )
        results = _run_check(project_dir, monkeypatch)

        failures = [r for r in results if not r.passed]
        assert len(failures) == 0, (
            f"Expected all checks to pass (gemini provider), "
            f"got {len(failures)} failure(s):\n"
            + "\n".join(f"  - {r.name}: {r.message}" for r in failures)
        )

    def test_no_warnings_in_default_project(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """Default scaffold should not produce warnings."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        project_dir = scaffold_project("testproject", tmp_path)
        results = _run_check(project_dir, monkeypatch)

        warnings = [r for r in results if r.warning]
        assert len(warnings) == 0, (
            f"Unexpected warnings:\n"
            + "\n".join(f"  - {r.name}: {r.message}" for r in warnings)
        )

    def test_missing_api_key_fails_environment_check(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """Without OPENAI_API_KEY, environment check should fail."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        project_dir = scaffold_project("testproject", tmp_path)
        results = _run_check(project_dir, monkeypatch)

        env_results = [r for r in results if r.name.startswith("env:")]
        env_failures = [r for r in env_results if not r.passed]
        assert len(env_failures) > 0, (
            "Expected environment check failure without API key"
        )
