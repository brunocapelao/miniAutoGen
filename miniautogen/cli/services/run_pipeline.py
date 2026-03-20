"""Flow execution service for the CLI.

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
    CompositeEventSink,
    EventSink,
    ExecutionEvent,
    ExecutionPolicy,
    InMemoryEventSink,
    PipelineRunner,
)
from miniautogen.cli.config import ProjectConfig


class _VerboseEventSink:
    """Event sink that echoes events to stderr for --verbose mode."""

    async def publish(self, event: ExecutionEvent) -> None:
        click.echo(
            f"[{event.type}] run_id={event.run_id} scope={event.scope}",
            err=True,
        )


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


def _resolve_engine_config(config: ProjectConfig) -> dict[str, Any] | None:
    """Resolve the default engine profile from project config.

    Returns a dict with engine configuration details that can be
    passed to pipeline factories, or None if no engine is configured.
    """
    default_engine_name = config.defaults.engine
    engine_profiles = config.engines

    if not engine_profiles or default_engine_name not in engine_profiles:
        return None

    engine = engine_profiles[default_engine_name]
    return {
        "engine_name": default_engine_name,
        "provider": engine.provider,
        "model": engine.model,
        "kind": engine.kind,
        "temperature": engine.temperature,
        "endpoint": engine.endpoint,
        "timeout_seconds": engine.timeout_seconds,
    }


async def execute_pipeline(
    config: ProjectConfig,
    pipeline_name: str,
    project_root: Path,
    *,
    timeout: float | None = None,
    verbose: bool = False,
    pipeline_input: str | None = None,
    resume_run_id: str | None = None,
    event_sink: Any = None,
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
        msg = f"Flow '{pipeline_name}' not found in config"
        raise KeyError(msg)

    if timeout is not None and timeout <= 0:
        msg = f"Timeout must be positive, got {timeout}"
        raise ValueError(msg)

    target = config.pipelines[pipeline_name].target

    # Resolve engine configuration from project defaults
    engine_config = _resolve_engine_config(config)

    # Temporarily add project root to sys.path for imports
    project_str = str(project_root)
    added_to_path = False
    if project_str not in sys.path:
        sys.path.append(project_str)
        added_to_path = True

    try:
        factory = resolve_pipeline_target(target, project_root)

        # Pass engine config to factory if it accepts keyword arguments.
        # Factories may use this to configure LLM-backed pipeline components.
        if engine_config is not None:
            try:
                pipeline = factory(engine_config=engine_config)
            except TypeError:
                # Factory does not accept engine_config -- call without it
                pipeline = factory()
        else:
            pipeline = factory()

        internal_sink = InMemoryEventSink()
        sinks: list[Any] = [internal_sink]
        if verbose:
            sinks.append(_VerboseEventSink())
        if event_sink is not None:
            sinks.append(event_sink)
        effective_sink: EventSink = CompositeEventSink(sinks=sinks) if len(sinks) > 1 else internal_sink
        execution_policy = None
        if timeout is not None:
            execution_policy = ExecutionPolicy(
                timeout_seconds=timeout,
            )

        runner = PipelineRunner(
            event_sink=effective_sink,
            execution_policy=execution_policy,
        )

        # Build context with input
        context: dict[str, Any] = {}
        if pipeline_input is not None:
            context["input"] = pipeline_input
        if engine_config is not None:
            context["engine_config"] = engine_config

        # Handle resume from checkpoint
        if resume_run_id is not None:
            from miniautogen.cli.errors import ExecutionError

            if config.database is None:
                raise ExecutionError(
                    "Resume requires a configured checkpoint store. "
                    "Ensure your project has persistence configured.",
                    hint="Add a 'database' section to your miniautogen.yaml.",
                )

            from miniautogen.api import SQLAlchemyCheckpointStore

            checkpoint_store = SQLAlchemyCheckpointStore(config.database.url)
            await checkpoint_store.init_db()

            checkpoint = await checkpoint_store.get_checkpoint(resume_run_id)
            await checkpoint_store.engine.dispose()

            if checkpoint is None:
                raise ExecutionError(
                    f"No checkpoint found for run_id '{resume_run_id}'.",
                    hint="Verify the run_id is correct with 'miniautogen sessions list'.",
                )

            # Merge checkpoint state into context for resumed execution
            if isinstance(checkpoint, dict):
                context.update(checkpoint.get("state", {}))

        result = await runner.run_pipeline(pipeline, context)

        return {
            "status": "completed",
            "output": result,
            "events": len(internal_sink.events),
            "input_provided": pipeline_input is not None,
            "resumed": resume_run_id is not None,
            "engine": engine_config["engine_name"] if engine_config else None,
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
