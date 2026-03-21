"""Tests for config-driven pipeline validation in check_project service.

Config-driven flows use mode/participants instead of target (Python callable).
This validates that the check service correctly handles both formats.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from miniautogen.cli.config import (
    CONFIG_FILENAME,
    FlowConfig,
    WorkspaceConfig,
    load_config,
)
from miniautogen.cli.services.check_project import (
    _check_pipeline_participants,
    _check_pipelines,
    check_project,
)


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data))


def _base_config_target() -> dict:
    """Base config using target-based (callable) pipeline."""
    return {
        "project": {"name": "test", "version": "0.1.0"},
        "defaults": {"engine": "default_api"},
        "engines": {
            "default_api": {"provider": "litellm", "model": "gpt-4o-mini"},
        },
        "flows": {
            "main": {"target": "pipelines.main:build_pipeline"},
        },
    }


def _base_config_driven() -> dict:
    """Base config using config-driven pipeline (mode + participants)."""
    return {
        "project": {"name": "test", "version": "0.1.0"},
        "defaults": {"engine": "default_api"},
        "engines": {
            "default_api": {"provider": "litellm", "model": "gpt-4o-mini"},
        },
        "flows": {
            "build": {
                "mode": "workflow",
                "participants": ["architect", "developer"],
            },
        },
    }


def _make_project(tmp_path: Path, config: dict) -> Path:
    _write_yaml(tmp_path / CONFIG_FILENAME, config)
    return tmp_path


def _make_agent(project: Path, name: str) -> None:
    agents_dir = project / "agents"
    agents_dir.mkdir(exist_ok=True)
    _write_yaml(agents_dir / f"{name}.yaml", {
        "id": name,
        "name": name.title(),
        "engine_profile": "default_api",
    })


# ── FlowConfig model validation ─────────────────────────────────────────


class TestFlowConfigModelValidation:
    """Tests for Pydantic-level validation of FlowConfig."""

    def test_config_driven_with_mode_and_participants_valid(self) -> None:
        """Config-driven flow with mode + participants is valid."""
        fc = FlowConfig(mode="workflow", participants=["a1", "a2"])
        assert fc.mode == "workflow"
        assert fc.participants == ["a1", "a2"]
        assert fc.target is None

    def test_config_driven_mode_without_participants_fails(self) -> None:
        """Config-driven flow with mode but no participants is rejected."""
        with pytest.raises(ValidationError, match="participants"):
            FlowConfig(mode="workflow")

    def test_neither_target_nor_mode_fails(self) -> None:
        """Flow with neither target nor mode is rejected."""
        with pytest.raises(ValidationError, match="target.*mode|mode.*target"):
            FlowConfig()

    def test_target_based_flow_valid(self) -> None:
        """Target-based flow is valid without mode/participants."""
        fc = FlowConfig(target="pipelines.main:build")
        assert fc.target == "pipelines.main:build"
        assert fc.mode is None

    def test_deliberation_mode_requires_leader(self) -> None:
        """Deliberation mode without leader is rejected."""
        with pytest.raises(ValidationError, match="leader"):
            FlowConfig(
                mode="deliberation",
                participants=["a1", "a2"],
            )

    def test_deliberation_mode_with_leader_valid(self) -> None:
        """Deliberation mode with leader is valid."""
        fc = FlowConfig(
            mode="deliberation",
            participants=["a1", "a2"],
            leader="a1",
        )
        assert fc.leader == "a1"

    def test_loop_mode_requires_router(self) -> None:
        """Loop mode without router is rejected."""
        with pytest.raises(ValidationError, match="router"):
            FlowConfig(
                mode="loop",
                participants=["a1"],
            )

    def test_loop_mode_with_router_valid(self) -> None:
        """Loop mode with router is valid."""
        fc = FlowConfig(
            mode="loop",
            participants=["a1"],
            router="a1",
        )
        assert fc.router == "a1"

    def test_target_with_mode_skips_mode_validations(self) -> None:
        """When both target and mode are set, mode-specific validations
        are skipped (target takes precedence)."""
        fc = FlowConfig(
            target="pipelines.main:build",
            mode="deliberation",
            # No leader — allowed because target is set
        )
        assert fc.target is not None
        assert fc.mode == "deliberation"


# ── WorkspaceConfig loading ──────────────────────────────────────────────


class TestWorkspaceConfigLoading:
    """Tests that config-driven flows load correctly from YAML."""

    def test_config_driven_flow_loads(self, tmp_path: Path) -> None:
        """Config-driven flow in YAML loads successfully."""
        cfg = _base_config_driven()
        project = _make_project(tmp_path, cfg)
        config = load_config(project / CONFIG_FILENAME)
        assert "build" in config.flows
        flow = config.flows["build"]
        assert flow.mode == "workflow"
        assert flow.participants == ["architect", "developer"]
        assert flow.target is None

    def test_both_target_and_config_driven_coexist(self, tmp_path: Path) -> None:
        """Target-based and config-driven flows can coexist in same config."""
        cfg = _base_config_target()
        cfg["flows"]["review"] = {
            "mode": "deliberation",
            "participants": ["architect", "developer"],
            "leader": "architect",
        }
        project = _make_project(tmp_path, cfg)
        config = load_config(project / CONFIG_FILENAME)
        assert "main" in config.flows
        assert config.flows["main"].target is not None
        assert "review" in config.flows
        assert config.flows["review"].mode == "deliberation"

    def test_invalid_config_driven_flow_rejects_at_load(self, tmp_path: Path) -> None:
        """Config-driven flow with missing participants is rejected at load."""
        cfg = _base_config_driven()
        cfg["flows"]["bad"] = {"mode": "workflow"}  # no participants
        project = _make_project(tmp_path, cfg)
        with pytest.raises(ValidationError, match="participants"):
            load_config(project / CONFIG_FILENAME)


# ── _check_pipelines with config-driven flows ───────────────────────────


class TestCheckPipelinesConfigDriven:
    """Tests for _check_pipelines() handling of config-driven flows.

    _check_pipelines() currently only validates target-based flows.
    Config-driven flows (target=None) cause a TypeError because
    the function does `":" not in target` where target is None.
    These tests document this gap — a fix should skip config-driven
    flows in _check_pipelines (they have no target to resolve).
    """

    def test_config_driven_flow_skipped_or_handled(self, tmp_path: Path) -> None:
        """Config-driven flow should not crash _check_pipelines.

        If target is None, the function should skip this flow
        (target resolution is not applicable for config-driven flows).
        """
        cfg = _base_config_driven()
        project = _make_project(tmp_path, cfg)
        config = load_config(project / CONFIG_FILENAME)
        # This may raise TypeError if _check_pipelines doesn't guard
        # against target=None. If so, this test documents the bug.
        try:
            results = _check_pipelines(config, project)
            # If it doesn't crash, config-driven flows were handled
            assert isinstance(results, list)
        except TypeError as exc:
            pytest.fail(
                f"_check_pipelines crashes on config-driven flow (target=None): {exc}"
            )

    def test_mixed_flows_check_pipelines(self, tmp_path: Path) -> None:
        """Mixed target + config-driven flows should not crash."""
        cfg = _base_config_target()
        cfg["flows"]["review"] = {
            "mode": "workflow",
            "participants": ["arch"],
        }
        project = _make_project(tmp_path, cfg)
        # Create the target module so the target-based flow passes
        (project / "pipelines").mkdir(exist_ok=True)
        (project / "pipelines" / "main.py").write_text("def build_pipeline(): pass")
        config = load_config(project / CONFIG_FILENAME)
        try:
            results = _check_pipelines(config, project)
            # Target-based flow should have a result
            target_results = [r for r in results if "main" in r.name]
            assert len(target_results) >= 1
        except TypeError as exc:
            pytest.fail(
                f"_check_pipelines crashes on mixed flows: {exc}"
            )


# ── _check_pipeline_participants with config-driven flows ────────────────


class TestCheckPipelineParticipantsConfigDriven:
    """Tests for participant validation in config-driven flows."""

    def test_participants_referencing_existing_agents_pass(
        self, tmp_path: Path,
    ) -> None:
        """All participant agents exist as YAML files — no failures."""
        cfg = _base_config_driven()
        project = _make_project(tmp_path, cfg)
        _make_agent(project, "architect")
        _make_agent(project, "developer")
        config = load_config(project / CONFIG_FILENAME)
        results = _check_pipeline_participants(config, project)
        failed = [r for r in results if not r.passed]
        assert len(failed) == 0

    def test_participants_referencing_nonexistent_agents_fail(
        self, tmp_path: Path,
    ) -> None:
        """Participant agents missing from agents/ — should fail."""
        cfg = _base_config_driven()
        project = _make_project(tmp_path, cfg)
        (project / "agents").mkdir()
        # Don't create agent files
        config = load_config(project / CONFIG_FILENAME)
        results = _check_pipeline_participants(config, project)
        failed = [r for r in results if not r.passed]
        assert len(failed) == 2
        names = {r.message for r in failed}
        assert any("architect" in msg for msg in names)
        assert any("developer" in msg for msg in names)

    def test_deliberation_leader_validation(self, tmp_path: Path) -> None:
        """Leader referenced in deliberation flow must exist as agent file."""
        cfg = _base_config_driven()
        cfg["flows"]["review"] = {
            "mode": "deliberation",
            "participants": ["architect", "developer"],
            "leader": "architect",
        }
        project = _make_project(tmp_path, cfg)
        (project / "agents").mkdir()
        _make_agent(project, "developer")
        # architect missing — should fail for both participant and leader
        config = load_config(project / CONFIG_FILENAME)
        results = _check_pipeline_participants(config, project)
        failed = [r for r in results if not r.passed]
        assert any("architect" in r.message for r in failed)

    def test_deliberation_leader_exists_passes(self, tmp_path: Path) -> None:
        """Leader and all participants exist — no failures."""
        cfg = _base_config_driven()
        cfg["flows"] = {
            "review": {
                "mode": "deliberation",
                "participants": ["architect", "developer"],
                "leader": "architect",
            },
        }
        project = _make_project(tmp_path, cfg)
        _make_agent(project, "architect")
        _make_agent(project, "developer")
        config = load_config(project / CONFIG_FILENAME)
        results = _check_pipeline_participants(config, project)
        failed = [r for r in results if not r.passed]
        assert len(failed) == 0

    def test_leader_missing_file_reported(self, tmp_path: Path) -> None:
        """Leader agent file missing — specific failure reported."""
        cfg = _base_config_driven()
        cfg["flows"] = {
            "review": {
                "mode": "deliberation",
                "participants": ["developer"],
                "leader": "ghost_leader",
            },
        }
        project = _make_project(tmp_path, cfg)
        _make_agent(project, "developer")
        config = load_config(project / CONFIG_FILENAME)
        results = _check_pipeline_participants(config, project)
        failed = [r for r in results if not r.passed]
        assert any("ghost_leader" in r.message for r in failed)


# ── Full check_project integration with config-driven flows ─────────────


class TestCheckProjectConfigDriven:
    """Integration tests for check_project with config-driven flows."""

    def test_full_check_config_driven_project(self, tmp_path: Path) -> None:
        """Full check_project on a project with config-driven flows."""
        cfg = _base_config_driven()
        project = _make_project(tmp_path, cfg)
        _make_agent(project, "architect")
        _make_agent(project, "developer")
        config = load_config(project / CONFIG_FILENAME)
        try:
            results = check_project(config, project)
            # Should not crash; may have warnings but no unexpected errors
            assert isinstance(results, list)
            assert len(results) > 0
        except TypeError as exc:
            pytest.fail(
                f"check_project crashes on config-driven flows: {exc}"
            )

    def test_full_check_mixed_project(self, tmp_path: Path) -> None:
        """Full check_project with both target and config-driven flows."""
        cfg = _base_config_target()
        cfg["flows"]["review"] = {
            "mode": "workflow",
            "participants": ["architect"],
        }
        project = _make_project(tmp_path, cfg)
        (project / "pipelines").mkdir(exist_ok=True)
        (project / "pipelines" / "main.py").write_text("def build_pipeline(): pass")
        _make_agent(project, "architect")
        config = load_config(project / CONFIG_FILENAME)
        try:
            results = check_project(config, project)
            assert isinstance(results, list)
        except TypeError as exc:
            pytest.fail(
                f"check_project crashes on mixed flows: {exc}"
            )
