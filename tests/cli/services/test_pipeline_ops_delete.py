"""Tests for delete_pipeline in pipeline_ops (P0-4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml


def _make_project(
    tmp_path: Path,
    *,
    pipelines: dict[str, Any] | None = None,
    agents: list[str] | None = None,
) -> Path:
    """Scaffold a minimal project directory."""
    root = tmp_path / "proj"
    root.mkdir()
    agents_dir = root / "agents"
    agents_dir.mkdir()

    data: dict[str, Any] = {"project": {"name": "test-proj"}}
    if pipelines is not None:
        data["pipelines"] = pipelines
    (root / "miniautogen.yaml").write_text(yaml.dump(data, sort_keys=False))

    if agents:
        for name in agents:
            (agents_dir / f"{name}.yaml").write_text(
                yaml.dump({"name": name, "role": "assistant"}, sort_keys=False),
            )
    return root


class TestDeletePipeline:
    def test_delete_existing_pipeline(self, tmp_path: Path) -> None:
        from miniautogen.cli.services.pipeline_ops import delete_pipeline

        root = _make_project(
            tmp_path,
            pipelines={"etl": {"mode": "workflow", "target": "pipelines.etl:build_pipeline"}},
        )
        result = delete_pipeline(root, "etl")
        assert result["deleted"] == "etl"

        # Verify removed from YAML
        cfg = yaml.safe_load((root / "miniautogen.yaml").read_text())
        assert "etl" not in cfg.get("pipelines", {})

    def test_delete_nonexistent_raises(self, tmp_path: Path) -> None:
        from miniautogen.cli.services.pipeline_ops import delete_pipeline

        root = _make_project(tmp_path, pipelines={})
        with pytest.raises(KeyError, match="not found"):
            delete_pipeline(root, "nope")

    def test_delete_blocks_when_agents_reference(self, tmp_path: Path) -> None:
        """Cannot delete a flow that agents reference in their config."""
        from miniautogen.cli.services.pipeline_ops import delete_pipeline

        root = _make_project(
            tmp_path,
            pipelines={"etl": {"mode": "workflow", "target": "pipelines.etl:build_pipeline"}},
            agents=["writer"],
        )
        # Add a flow reference in agent config
        agent_file = root / "agents" / "writer.yaml"
        agent_file.write_text(
            yaml.dump(
                {"name": "writer", "role": "assistant", "flow": "etl"},
                sort_keys=False,
            ),
        )
        with pytest.raises(ValueError, match="referenced"):
            delete_pipeline(root, "etl")

    def test_delete_blocks_when_composite_references(self, tmp_path: Path) -> None:
        """Cannot delete a flow used in a composite chain."""
        from miniautogen.cli.services.pipeline_ops import delete_pipeline

        root = _make_project(
            tmp_path,
            pipelines={
                "step1": {"mode": "workflow", "target": "pipelines.step1:build_pipeline"},
                "combo": {"mode": "composite", "chain": ["step1"]},
            },
        )
        with pytest.raises(ValueError, match="referenced"):
            delete_pipeline(root, "step1")
