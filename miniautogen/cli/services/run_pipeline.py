"""Pipeline execution service for the CLI.

Resolves pipeline targets and executes them via PipelineRunner.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Callable

from miniautogen.api import (
    ExecutionPolicy,
    InMemoryEventSink,
    PipelineRunner,
)
from miniautogen.cli.config import ProjectConfig


def resolve_pipeline_target(target: str) -> Callable:
    """Parse 'module.path:callable' and return the callable.

    Raises ImportError or AttributeError on failure.
    """
    if ":" not in target:
        msg = (
            f"Invalid pipeline target '{target}': "
            "expected 'module.path:callable_name'"
        )
        raise ValueError(msg)

    module_path, callable_name = target.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, callable_name)


async def execute_pipeline(
    config: ProjectConfig,
    pipeline_name: str,
    project_root: Path,
    *,
    timeout: float | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """Execute a named pipeline from the project config.

    Args:
        config: Project configuration.
        pipeline_name: Key in config.pipelines.
        project_root: Path to project root (added to sys.path).
        timeout: Optional timeout in seconds.
        verbose: If True, log events to console.

    Returns:
        Result dict with run_id, status, output.
    """
    if pipeline_name not in config.pipelines:
        msg = f"Pipeline '{pipeline_name}' not found in config"
        raise KeyError(msg)

    target = config.pipelines[pipeline_name].target

    # Temporarily add project root to sys.path for imports
    project_str = str(project_root)
    added_to_path = False
    if project_str not in sys.path:
        sys.path.insert(0, project_str)
        added_to_path = True

    try:
        factory = resolve_pipeline_target(target)
        pipeline = factory()

        event_sink = InMemoryEventSink()
        execution_policy = None
        if timeout is not None:
            execution_policy = ExecutionPolicy(
                timeout_seconds=timeout,
            )

        runner = PipelineRunner(
            event_sink=event_sink,
            execution_policy=execution_policy,
        )

        result = await runner.run_pipeline(pipeline, {})

        return {
            "status": "completed",
            "output": result,
            "events": len(event_sink.events),
        }
    except Exception as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "error_type": type(exc).__name__,
        }
    finally:
        if added_to_path and project_str in sys.path:
            sys.path.remove(project_str)
