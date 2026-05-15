"""Public API facade for CLI and external consumers.

All SDK interaction from CLI must go through this module.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from miniautogen.backends.engine_resolver import EngineResolver
from miniautogen.core.contracts.agent_spec import AgentSpec
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.contracts.skill_spec import SkillSpec
from miniautogen.core.contracts.tool_spec import ToolSpec
from miniautogen.core.events.event_sink import (
    CompositeEventSink,
    EventSink,
    InMemoryEventSink,
    NullEventSink,
)
from miniautogen.core.runtime.agent_runtime import AgentRuntime
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.pipeline.pipeline import Pipeline
from miniautogen.policies.execution import ExecutionPolicy
from miniautogen.server.app import create_app
from miniautogen.server.standalone_provider import StandaloneProvider
from miniautogen.stores.in_memory_event_store import InMemoryEventStore
from miniautogen.stores.in_memory_run_store import InMemoryRunStore
from miniautogen.stores.run_store import RunStore
from miniautogen.stores.sqlalchemy_checkpoint_store import SQLAlchemyCheckpointStore
from miniautogen.stores.sqlalchemy_event_store import SQLAlchemyEventStore
from miniautogen.stores.sqlalchemy_run_store import SQLAlchemyRunStore

__all__ = [
    "AgentRuntime",
    "AgentSpec",
    "CompositeEventSink",
    "EngineResolver",
    "EventSink",
    "ExecutionEvent",
    "ExecutionPolicy",
    "InMemoryEventSink",
    "InMemoryEventStore",
    "InMemoryRunStore",
    "NullEventSink",
    "Pipeline",
    "PipelineRunner",
    "RunContext",
    "RunStore",
    "SQLAlchemyCheckpointStore",
    "SQLAlchemyEventStore",
    "SQLAlchemyRunStore",
    "SkillSpec",
    "StandaloneProvider",
    "ToolSpec",
    "create_app",
    "create_runtime",
]


async def create_runtime(
    project_root: Path,
    agent_name: str,
    run_id_prefix: str = "run",
    system_prompt: str = "",
) -> tuple[AgentRuntime, str]:
    """Load agent config, create driver, build and initialize AgentRuntime.

    Args:
        project_root: Path to the workspace root.
        agent_name: Name of the agent to use.
        run_id_prefix: Prefix for the auto-generated run ID.
        system_prompt: Optional override. Falls back to agent spec goal.

    Returns:
        Tuple of (initialized AgentRuntime, run_id).

    Raises:
        ValueError: If agent not found.
    """
    from miniautogen.cli.config import CONFIG_FILENAME, load_config
    from miniautogen.cli.services.agent_ops import load_agent_specs

    config = load_config(project_root / CONFIG_FILENAME)
    agent_specs = load_agent_specs(project_root)
    spec = agent_specs[agent_name]
    run_id = f"{run_id_prefix}-{uuid.uuid4().hex[:8]}"

    engine_resolver = EngineResolver()
    engine_name = getattr(spec, "engine_profile", None) or config.defaults.engine
    driver = engine_resolver.create_fresh_driver(engine_name, config)

    run_context = RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id=run_id,
    )

    runtime = AgentRuntime(
        agent_id=agent_name,
        driver=driver,
        run_context=run_context,
        event_sink=NullEventSink(),
        system_prompt=system_prompt or getattr(spec, "goal", None) or "",
    )
    await runtime.initialize()
    return runtime, run_id
