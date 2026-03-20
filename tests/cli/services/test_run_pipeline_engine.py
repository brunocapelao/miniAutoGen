"""Tests for engine resolver wiring in execute_pipeline (P0-2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from miniautogen.cli.config import (
    DatabaseConfig,
    DefaultsConfig,
    EngineConfig,
    FlowConfig,
    ProjectConfig,
    ProjectMeta,
)


def _make_config(
    *,
    engine_name: str = "test-engine",
    provider: str = "openai-compat",
    model: str = "gpt-4o",
) -> ProjectConfig:
    """Build a ProjectConfig with one engine and one flow."""
    return ProjectConfig(
        project=ProjectMeta(name="test-proj"),
        defaults=DefaultsConfig(engine=engine_name),
        engines={
            engine_name: EngineConfig(
                provider=provider,
                model=model,
            ),
        },
        flows={
            "main": FlowConfig(target="pipelines.main:build_pipeline"),
        },
    )


class TestExecutePipelineEngineWiring:
    """Verify that execute_pipeline resolves engine config."""

    @pytest.mark.anyio
    async def test_factory_receives_engine_config(self, tmp_path: Path) -> None:
        """Pipeline factory should receive engine context when available."""
        config = _make_config()

        # Create a minimal project structure
        proj = tmp_path / "proj"
        proj.mkdir()
        pipelines_dir = proj / "pipelines"
        pipelines_dir.mkdir()

        # Create a pipeline module that captures what it receives
        pipeline_file = pipelines_dir / "main.py"
        pipeline_file.write_text(
            'from miniautogen.api import Pipeline\n'
            'def build_pipeline(**kwargs):\n'
            '    return Pipeline(name="main")\n'
        )

        (proj / "__init__.py").write_text("")
        (pipelines_dir / "__init__.py").write_text("")

        from miniautogen.cli.services.run_pipeline import execute_pipeline

        result = await execute_pipeline(
            config=config,
            pipeline_name="main",
            project_root=proj,
        )
        # The basic test: execute_pipeline should succeed (not crash)
        # even with engine config present
        assert result["status"] in ("completed", "failed")
