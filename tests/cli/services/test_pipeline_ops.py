"""Comprehensive tests for miniautogen.cli.services.pipeline_ops."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from miniautogen.cli.services.pipeline_ops import (
    create_pipeline,
    list_pipelines,
    show_pipeline,
    update_pipeline,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(tmp_path: Path, *, pipelines: dict[str, Any] | None = None) -> Path:
    """Scaffold a minimal project directory with miniautogen.yaml and agents/."""
    root = tmp_path / "proj"
    root.mkdir()
    agents_dir = root / "agents"
    agents_dir.mkdir()

    data: dict[str, Any] = {"project": {"name": "test-proj"}}
    if pipelines is not None:
        data["pipelines"] = pipelines
    (root / "miniautogen.yaml").write_text(yaml.dump(data, sort_keys=False))
    return root


def _add_agent(root: Path, name: str) -> None:
    """Create a stub agent YAML file."""
    agents_dir = root / "agents"
    agents_dir.mkdir(exist_ok=True)
    (agents_dir / f"{name}.yaml").write_text(
        yaml.dump({"name": name, "role": "assistant"}, sort_keys=False)
    )


# ---------------------------------------------------------------------------
# create_pipeline
# ---------------------------------------------------------------------------

class TestCreatePipeline:
    """Tests for create_pipeline covering all modes and validation paths."""

    def test_create_workflow_mode(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        result = create_pipeline(root, "etl", mode="workflow")
        assert result["mode"] == "workflow"
        assert result["target"] == "pipelines.etl:build_pipeline"
        # Verify persisted in YAML
        cfg = yaml.safe_load((root / "miniautogen.yaml").read_text())
        assert "etl" in cfg["pipelines"]
        assert cfg["pipelines"]["etl"]["mode"] == "workflow"

    def test_create_deliberation_mode(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        result = create_pipeline(root, "debate", mode="deliberation")
        assert result["mode"] == "deliberation"

    def test_create_loop_mode(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        result = create_pipeline(root, "retry", mode="loop")
        assert result["mode"] == "loop"

    def test_create_composite_mode_with_chain(self, tmp_path: Path) -> None:
        """Composite mode with chain_pipelines referencing existing pipelines."""
        root = _make_project(tmp_path, pipelines={
            "step1": {"mode": "workflow", "target": "pipelines.step1:build_pipeline"},
            "step2": {"mode": "workflow", "target": "pipelines.step2:build_pipeline"},
        })
        result = create_pipeline(
            root, "combo", mode="composite",
            chain_pipelines=["step1", "step2"],
        )
        assert result["mode"] == "composite"
        assert result["chain"] == ["step1", "step2"]

    def test_create_composite_missing_chain_pipeline_raises(self, tmp_path: Path) -> None:
        """chain_pipelines referencing a non-existent pipeline must fail."""
        root = _make_project(tmp_path)
        with pytest.raises(ValueError, match="not found.*composite chain"):
            create_pipeline(root, "combo", mode="composite", chain_pipelines=["nope"])

    def test_create_with_participants_valid(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        _add_agent(root, "alice")
        _add_agent(root, "bob")
        result = create_pipeline(
            root, "team", mode="workflow", participants=["alice", "bob"],
        )
        assert result["participants"] == ["alice", "bob"]

    def test_create_with_missing_participant_raises(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        _add_agent(root, "alice")
        with pytest.raises(ValueError, match="Agent 'ghost' not found"):
            create_pipeline(root, "team", mode="workflow", participants=["alice", "ghost"])

    def test_create_with_leader_valid(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        _add_agent(root, "leader1")
        result = create_pipeline(root, "led", mode="deliberation", leader="leader1")
        assert result["leader"] == "leader1"

    def test_create_with_missing_leader_raises(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        with pytest.raises(ValueError, match="Leader agent 'phantom' not found"):
            create_pipeline(root, "led", mode="deliberation", leader="phantom")

    def test_create_duplicate_raises(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "workflow", "target": "pipelines.main:build_pipeline"},
        })
        with pytest.raises(ValueError, match="already exists"):
            create_pipeline(root, "main", mode="workflow")

    def test_create_duplicate_uses_flow_terminology(self, tmp_path: Path) -> None:
        """Error message for duplicate pipeline should use 'miniautogen flow update', not 'pipeline update'."""
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "workflow", "target": "pipelines.main:build_pipeline"},
        })
        with pytest.raises(ValueError, match="miniautogen flow update") as exc_info:
            create_pipeline(root, "main", mode="workflow")
        # Must NOT contain stale 'pipeline update' terminology
        assert "pipeline update" not in str(exc_info.value)

    def test_create_invalid_name_raises(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        with pytest.raises(ValueError, match="Invalid pipeline name"):
            create_pipeline(root, "../evil", mode="workflow")

    def test_create_with_explicit_target(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        result = create_pipeline(root, "custom", mode="workflow", target="my.module:fn")
        assert result["target"] == "my.module:fn"

    def test_create_with_max_rounds(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        result = create_pipeline(root, "rounds", mode="loop", max_rounds=10)
        assert result["max_rounds"] == 10

    def test_create_generates_pipeline_module(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        create_pipeline(root, "gen", mode="workflow")
        py_file = root / "pipelines" / "gen.py"
        assert py_file.exists()
        content = py_file.read_text()
        assert "def build_pipeline" in content
        assert "workflow" in content

    def test_create_does_not_overwrite_existing_module(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        pipelines_dir = root / "pipelines"
        pipelines_dir.mkdir()
        existing = pipelines_dir / "keep.py"
        existing.write_text("# custom code\n")
        create_pipeline(root, "keep", mode="workflow")
        assert existing.read_text() == "# custom code\n"

    def test_create_invalid_participant_name_raises(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        with pytest.raises(ValueError, match="Invalid agent name"):
            create_pipeline(root, "bad", mode="workflow", participants=["../bad"])

    def test_create_invalid_leader_name_raises(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        with pytest.raises(ValueError, match="Invalid agent name"):
            create_pipeline(root, "bad", mode="deliberation", leader="../bad")


# ---------------------------------------------------------------------------
# list_pipelines
# ---------------------------------------------------------------------------

class TestListPipelines:

    def test_list_empty(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        result = list_pipelines(root)
        assert result == []

    def test_list_dict_pipelines(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path, pipelines={
            "a": {"mode": "workflow", "target": "t1", "participants": ["x"]},
            "b": {"mode": "loop", "target": "t2"},
        })
        result = list_pipelines(root)
        assert len(result) == 2
        names = {r["name"] for r in result}
        assert names == {"a", "b"}

    def test_list_non_dict_pipeline_entry(self, tmp_path: Path) -> None:
        """Covers line 120: when pipeline value is a plain string, not a dict."""
        root = _make_project(tmp_path, pipelines={"legacy": "some.module:fn"})
        result = list_pipelines(root)
        assert len(result) == 1
        assert result[0]["name"] == "legacy"
        assert result[0]["mode"] == "?"
        assert result[0]["target"] == "some.module:fn"
        assert result[0]["participants"] == []

    def test_list_non_dict_pipeline_none_value(self, tmp_path: Path) -> None:
        """Non-dict pipeline with None value -> target should be '?'."""
        root = _make_project(tmp_path, pipelines={"empty": None})
        result = list_pipelines(root)
        assert result[0]["target"] == "?"


# ---------------------------------------------------------------------------
# show_pipeline
# ---------------------------------------------------------------------------

class TestShowPipeline:

    def test_show_existing(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "workflow", "target": "t", "participants": ["a"]},
        })
        result = show_pipeline(root, "main")
        assert result["name"] == "main"
        assert result["mode"] == "workflow"

    def test_show_not_found_raises(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        with pytest.raises(KeyError, match="not found"):
            show_pipeline(root, "nope")

    def test_show_not_found_lists_available(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path, pipelines={
            "alpha": {"mode": "workflow", "target": "t"},
        })
        with pytest.raises(KeyError, match="alpha"):
            show_pipeline(root, "beta")

    def test_show_not_found_no_pipelines(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        with pytest.raises(KeyError, match="\\(none\\)"):
            show_pipeline(root, "x")

    def test_show_non_dict_pipeline(self, tmp_path: Path) -> None:
        """Covers line 146: when the pipeline cfg is a plain string."""
        root = _make_project(tmp_path, pipelines={"legacy": "some.module:fn"})
        result = show_pipeline(root, "legacy")
        assert result["name"] == "legacy"
        assert result["target"] == "some.module:fn"

    def test_show_invalid_name_raises(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        with pytest.raises(ValueError, match="Invalid pipeline name"):
            show_pipeline(root, "../evil")


# ---------------------------------------------------------------------------
# update_pipeline
# ---------------------------------------------------------------------------

class TestUpdatePipeline:

    def test_update_mode(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "workflow", "target": "t"},
        })
        result = update_pipeline(root, "main", mode="deliberation")
        assert result["before"]["mode"] == "workflow"
        assert result["after"]["mode"] == "deliberation"
        # Verify persisted
        cfg = yaml.safe_load((root / "miniautogen.yaml").read_text())
        assert cfg["pipelines"]["main"]["mode"] == "deliberation"

    def test_update_not_found_raises(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        with pytest.raises(KeyError, match="not found"):
            update_pipeline(root, "nope", mode="workflow")

    def test_update_not_found_lists_available(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path, pipelines={
            "alpha": {"mode": "workflow", "target": "t"},
        })
        with pytest.raises(KeyError, match="alpha"):
            update_pipeline(root, "beta", mode="workflow")

    def test_update_dry_run_does_not_persist(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "workflow", "target": "t"},
        })
        result = update_pipeline(root, "main", dry_run=True, mode="loop")
        assert result["after"]["mode"] == "loop"
        # YAML should be unchanged
        cfg = yaml.safe_load((root / "miniautogen.yaml").read_text())
        assert cfg["pipelines"]["main"]["mode"] == "workflow"

    def test_update_add_participant(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "workflow", "target": "t", "participants": ["alice"]},
        })
        _add_agent(root, "bob")
        result = update_pipeline(root, "main", add_participant="bob")
        assert "bob" in result["after"]["participants"]
        assert "alice" in result["after"]["participants"]

    def test_update_add_participant_already_present(self, tmp_path: Path) -> None:
        """Adding an already-present participant should not duplicate."""
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "workflow", "target": "t", "participants": ["alice"]},
        })
        _add_agent(root, "alice")
        result = update_pipeline(root, "main", add_participant="alice")
        assert result["after"]["participants"].count("alice") == 1

    def test_update_add_participant_missing_agent_raises(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "workflow", "target": "t"},
        })
        with pytest.raises(ValueError, match="Agent 'ghost' not found"):
            update_pipeline(root, "main", add_participant="ghost")

    def test_update_add_participant_invalid_name_raises(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "workflow", "target": "t"},
        })
        with pytest.raises(ValueError, match="Invalid agent name"):
            update_pipeline(root, "main", add_participant="../bad")

    def test_update_remove_participant(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "workflow", "target": "t", "participants": ["alice", "bob"]},
        })
        result = update_pipeline(root, "main", remove_participant="alice")
        assert "alice" not in result["after"]["participants"]
        assert "bob" in result["after"]["participants"]

    def test_update_remove_participant_not_present(self, tmp_path: Path) -> None:
        """Removing a participant that isn't in the list should not error."""
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "workflow", "target": "t", "participants": ["alice"]},
        })
        result = update_pipeline(root, "main", remove_participant="ghost")
        assert result["after"]["participants"] == ["alice"]

    def test_update_replace_participants(self, tmp_path: Path) -> None:
        """Directly setting participants replaces the list."""
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "workflow", "target": "t", "participants": ["alice"]},
        })
        _add_agent(root, "charlie")
        _add_agent(root, "dave")
        result = update_pipeline(
            root, "main", participants=["charlie", "dave"],
        )
        assert result["after"]["participants"] == ["charlie", "dave"]

    def test_update_replace_participants_missing_agent_raises(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "workflow", "target": "t"},
        })
        _add_agent(root, "charlie")
        with pytest.raises(ValueError, match="Agent 'nope' not found"):
            update_pipeline(root, "main", participants=["charlie", "nope"])

    def test_update_replace_participants_invalid_name_raises(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "workflow", "target": "t"},
        })
        with pytest.raises(ValueError, match="Invalid agent name"):
            update_pipeline(root, "main", participants=["../bad"])

    def test_update_leader_valid(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "deliberation", "target": "t"},
        })
        _add_agent(root, "boss")
        result = update_pipeline(root, "main", leader="boss")
        assert result["after"]["leader"] == "boss"

    def test_update_leader_missing_raises(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "deliberation", "target": "t"},
        })
        with pytest.raises(ValueError, match="Leader agent 'phantom' not found"):
            update_pipeline(root, "main", leader="phantom")

    def test_update_leader_invalid_name_raises(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "deliberation", "target": "t"},
        })
        with pytest.raises(ValueError, match="Invalid agent name"):
            update_pipeline(root, "main", leader="../bad")

    def test_update_invalid_pipeline_name_raises(self, tmp_path: Path) -> None:
        root = _make_project(tmp_path)
        with pytest.raises(ValueError, match="Invalid pipeline name"):
            update_pipeline(root, "../evil", mode="workflow")

    def test_update_add_participant_no_existing_participants(self, tmp_path: Path) -> None:
        """add_participant when pipeline has no participants key yet."""
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "workflow", "target": "t"},
        })
        _add_agent(root, "alice")
        result = update_pipeline(root, "main", add_participant="alice")
        assert result["after"]["participants"] == ["alice"]

    def test_update_remove_participant_no_existing_participants(self, tmp_path: Path) -> None:
        """remove_participant when pipeline has no participants key yet."""
        root = _make_project(tmp_path, pipelines={
            "main": {"mode": "workflow", "target": "t"},
        })
        result = update_pipeline(root, "main", remove_participant="ghost")
        assert result["after"]["participants"] == []

    def test_update_non_dict_pipeline_config(self, tmp_path: Path) -> None:
        """Pipeline config is a plain string (legacy format)."""
        root = _make_project(tmp_path, pipelines={"legacy": "some.module:fn"})
        result = update_pipeline(root, "legacy", mode="workflow")
        assert result["before"] == {"target": "some.module:fn"}
        assert result["after"]["mode"] == "workflow"
