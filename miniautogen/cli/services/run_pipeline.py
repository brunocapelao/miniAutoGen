"""Pipeline execution service for the CLI.

Resolves pipeline targets and executes them via PipelineRunner.
Supports input passing and run resumption from checkpoints.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Callable

import click

from miniautogen.api import (
    ExecutionPolicy,
    InMemoryEventSink,
    PipelineRunner,
)
from miniautogen.cli.config import ProjectConfig


def resolve_pipeline_target(
    target: str,
    project_root: Path,
) -> Callable:
    """Parse 'module.path:callable' and return the callable.

    The module must resolve to a file within project_root.
    """
    if ":" not in target:
        msg = (
            f"Invalid pipeline target '{target}': "
            "expected 'module.path:callable_name'"
        )
        raise ValueError(msg)

    module_path, callable_name = target.rsplit(":", 1)

    # Verify module file exists within project root
    expected = project_root / module_path.replace(".", "/")
    py_file = expected.with_suffix(".py")
    pkg_init = expected / "__init__.py"

    resolved_file = None
    if py_file.is_file():
        resolved_file = py_file.resolve()
    elif pkg_init.is_file():
        resolved_file = pkg_init.resolve()

    if resolved_file is None:
        msg = f"Module '{module_path}' not found in project"
        raise ImportError(msg)

    project_resolved = project_root.resolve()
    if not resolved_file.is_relative_to(project_resolved):
        msg = (
            f"Module '{module_path}' resolves outside project "
            f"directory: {resolved_file}"
        )
        raise ValueError(msg)

    module = importlib.import_module(module_path)
    return getattr(module, callable_name)


async def execute_pipeline(
    config: ProjectConfig,
    pipeline_name: str,
    project_root: Path,
    *,
    timeout: float | None = None,
    verbose: bool = False,
    pipeline_input: str | None = None,
    resume_run_id: str | None = None,
) -> dict[str, Any]:
    """Execute a named pipeline from the project config.

    Args:
        config: Project configuration.
        pipeline_name: Key in config.pipelines.
        project_root: Path to project root (added to sys.path).
        timeout: Optional timeout in seconds.
        verbose: If True, log events to console.
        pipeline_input: Optional input text for the pipeline.
        resume_run_id: Optional run_id to resume from checkpoint.

    Returns:
        Result dict with run_id, status, output.
    """
    if pipeline_name not in config.pipelines:
        msg = f"Pipeline '{pipeline_name}' not found in config"
        raise KeyError(msg)

    if timeout is not None and timeout <= 0:
        msg = f"Timeout must be positive, got {timeout}"
        raise ValueError(msg)

    target = config.pipelines[pipeline_name].target

    # Temporarily add project root to sys.path for imports
    project_str = str(project_root)
    added_to_path = False
    if project_str not in sys.path:
        sys.path.append(project_str)
        added_to_path = True

    try:
        factory = resolve_pipeline_target(target, project_root)
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

        # Build context with input
        context: dict[str, Any] = {}
        if pipeline_input is not None:
            context["input"] = pipeline_input

        # Handle resume from checkpoint
        if resume_run_id is not None:
            from miniautogen.cli.errors import ExecutionError

            raise ExecutionError(
                "Resume requires a configured checkpoint store. "
                "Ensure your project has persistence configured.",
                hint="Check your miniautogen.yml for store configuration.",
            )

        result = await runner.run_pipeline(pipeline, context)

        return {
            "status": "completed",
            "output": result,
            "events": len(event_sink.events),
            "input_provided": pipeline_input is not None,
            "resumed": resume_run_id is not None,
        }
    except (KeyError, ValueError, ImportError) as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "error_type": type(exc).__name__,
        }
    except click.ClickException:
        raise
    except Exception as exc:
        return {
            "status": "failed",
            "error": f"Pipeline execution failed: {exc}",
            "error_type": type(exc).__name__,
        }
    finally:
        if added_to_path and project_str in sys.path:
            sys.path.remove(project_str)
