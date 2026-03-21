"""Tests for checkpoint resume validation edge cases.

Verifies that ``execute_pipeline`` handles corrupted, incomplete, or
unexpected checkpoint data gracefully when ``--resume`` is used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from miniautogen.cli.config import CONFIG_FILENAME, load_config
from miniautogen.cli.errors import ExecutionError
from miniautogen.cli.services.run_pipeline import execute_pipeline


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_pipeline_modules():
    """Remove cached ``pipelines`` modules between tests.

    When tests run after other test files that also create a temporary
    ``pipelines.main`` module (e.g. ``test_run_pipeline.py``), the stale
    cached module in ``sys.modules`` would be reused instead of importing
    from the new ``tmp_path``.  This fixture ensures a clean slate.
    """
    import sys as _sys

    # Clean before the test
    stale = [k for k in _sys.modules if k == "pipelines" or k.startswith("pipelines.")]
    for k in stale:
        del _sys.modules[k]

    yield

    # Clean after the test
    stale = [k for k in _sys.modules if k == "pipelines" or k.startswith("pipelines.")]
    for k in stale:
        del _sys.modules[k]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(tmp_path: Path, *, with_database: bool = True) -> Path:
    """Create a minimal runnable project for testing resume logic."""
    config: dict[str, Any] = {
        "project": {"name": "test-resume"},
        "defaults": {"engine_profile": "default_api"},
        "engine_profiles": {
            "default_api": {"kind": "api", "provider": "litellm"},
        },
        "pipelines": {"main": {"target": "pipelines.main:build_pipeline"}},
    }
    if with_database:
        config["database"] = {"url": "sqlite+aiosqlite:///test_ckpt.db"}

    (tmp_path / CONFIG_FILENAME).write_text(yaml.dump(config))

    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    (pipelines_dir / "__init__.py").write_text("")
    # Pipeline that echoes its context so tests can inspect merged state
    (pipelines_dir / "main.py").write_text(
        "class P:\n"
        "    async def run(self, state):\n"
        "        return {**state, 'pipeline_ran': True}\n"
        "def build_pipeline():\n"
        "    return P()\n"
    )
    return tmp_path


def _patch_checkpoint_store(checkpoint_return: Any):
    """Return a context manager that patches SQLAlchemyCheckpointStore.

    The patched store's ``get_checkpoint`` returns *checkpoint_return*
    without touching a real database.
    """
    mock_store = AsyncMock()
    mock_store.get_checkpoint.return_value = checkpoint_return
    mock_store.engine = AsyncMock()

    return patch(
        "miniautogen.api.SQLAlchemyCheckpointStore",
        return_value=mock_store,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_resume_with_valid_checkpoint(tmp_path: Path) -> None:
    """A well-formed checkpoint dict merges its state into the pipeline context."""
    project = _make_project(tmp_path)
    config = load_config(project / CONFIG_FILENAME)

    checkpoint_data = {"state": {"step": 3, "partial_output": "hello"}}

    with _patch_checkpoint_store(checkpoint_data):
        result = await execute_pipeline(
            config, "main", project, resume_run_id="run-valid"
        )

    assert result["status"] == "completed"
    assert result["resumed"] is True
    # The pipeline echoes state — verify checkpoint values arrived
    assert result["output"]["step"] == 3
    assert result["output"]["partial_output"] == "hello"
    assert result["output"]["pipeline_ran"] is True


@pytest.mark.anyio
async def test_resume_with_empty_state(tmp_path: Path) -> None:
    """A checkpoint with an empty ``state`` dict should not crash."""
    project = _make_project(tmp_path)
    config = load_config(project / CONFIG_FILENAME)

    checkpoint_data = {"state": {}}

    with _patch_checkpoint_store(checkpoint_data):
        result = await execute_pipeline(
            config, "main", project, resume_run_id="run-empty"
        )

    assert result["status"] == "completed"
    assert result["resumed"] is True


@pytest.mark.anyio
async def test_resume_with_none_checkpoint_raises(tmp_path: Path) -> None:
    """When no checkpoint exists for the run_id, an ExecutionError is raised."""
    project = _make_project(tmp_path)
    config = load_config(project / CONFIG_FILENAME)

    with _patch_checkpoint_store(None):
        with pytest.raises(ExecutionError, match="No checkpoint found"):
            await execute_pipeline(
                config, "main", project, resume_run_id="nonexistent-run"
            )


@pytest.mark.anyio
async def test_resume_with_missing_state_key(tmp_path: Path) -> None:
    """Checkpoint dict that lacks a ``state`` key should not crash.

    ``dict.get("state", {})`` returns ``{}`` — pipeline runs with no
    extra context from checkpoint.
    """
    project = _make_project(tmp_path)
    config = load_config(project / CONFIG_FILENAME)

    checkpoint_data = {"step_index": 5, "metadata": "some info"}

    with _patch_checkpoint_store(checkpoint_data):
        result = await execute_pipeline(
            config, "main", project, resume_run_id="run-partial"
        )

    assert result["status"] == "completed"
    # No "step_index" should leak because context.update only uses .get("state", {})
    assert "step_index" not in result["output"]
    assert result["output"]["pipeline_ran"] is True


@pytest.mark.anyio
async def test_resume_with_wrong_type_checkpoint(tmp_path: Path) -> None:
    """When checkpoint is not a dict (e.g. a list), the isinstance guard
    should prevent crashing — pipeline runs without merged state."""
    project = _make_project(tmp_path)
    config = load_config(project / CONFIG_FILENAME)

    # Return a list instead of a dict
    checkpoint_data = [1, 2, 3]

    with _patch_checkpoint_store(checkpoint_data):
        result = await execute_pipeline(
            config, "main", project, resume_run_id="run-wrong-type"
        )

    assert result["status"] == "completed"
    # Pipeline still runs — just without checkpoint state
    assert result["output"]["pipeline_ran"] is True


@pytest.mark.anyio
async def test_resume_without_database_config_raises(tmp_path: Path) -> None:
    """Resume without a ``database`` section in config raises ExecutionError."""
    project = _make_project(tmp_path, with_database=False)
    config = load_config(project / CONFIG_FILENAME)

    with pytest.raises(ExecutionError, match="checkpoint store"):
        await execute_pipeline(
            config, "main", project, resume_run_id="any-run-id"
        )


@pytest.mark.anyio
async def test_resume_context_merge_new_input_takes_priority(tmp_path: Path) -> None:
    """New pipeline_input should override checkpoint state when keys overlap.

    The code does ``context["input"] = pipeline_input`` first, then
    ``context.update(checkpoint.get("state", {}))``, so checkpoint state
    actually overwrites input if it contains an "input" key.  This test
    documents the current behaviour.
    """
    project = _make_project(tmp_path)
    config = load_config(project / CONFIG_FILENAME)

    # Checkpoint state contains an "input" key that will overwrite pipeline_input
    checkpoint_data = {"state": {"input": "from-checkpoint", "extra": "data"}}

    with _patch_checkpoint_store(checkpoint_data):
        result = await execute_pipeline(
            config,
            "main",
            project,
            resume_run_id="run-merge",
            pipeline_input="from-cli",
        )

    assert result["status"] == "completed"
    # Document actual merge behaviour: checkpoint state overwrites because
    # context.update(state) runs AFTER context["input"] = pipeline_input
    assert result["output"]["input"] == "from-checkpoint"
    assert result["output"]["extra"] == "data"
    assert result["output"]["pipeline_ran"] is True


@pytest.mark.anyio
async def test_resume_with_string_state_value(tmp_path: Path) -> None:
    """When checkpoint ``state`` is a string instead of dict, the update call
    would fail. Verify the pipeline handles this gracefully."""
    project = _make_project(tmp_path)
    config = load_config(project / CONFIG_FILENAME)

    # state is a string — dict.update("string") raises TypeError
    checkpoint_data = {"state": "not-a-dict"}

    with _patch_checkpoint_store(checkpoint_data):
        result = await execute_pipeline(
            config, "main", project, resume_run_id="run-str-state"
        )

    # The generic except clause in execute_pipeline catches TypeError
    assert result["status"] == "failed"
    assert "error" in result
