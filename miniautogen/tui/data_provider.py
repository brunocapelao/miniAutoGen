"""Data provider bridging TUI views to CLI service layer.

DashDataProvider is the SINGLE bridge between TUI views and the CLI
service layer. It reads project config and provides data to views,
and delegates CRUD operations to existing CLI services.

This module imports from miniautogen.cli.services -- the CLI layer,
NOT from core internals, keeping zero-coupling intact.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from miniautogen.cli.config import (
    CONFIG_FILENAME,
    find_project_root,
    load_config,
)
from miniautogen.cli.services.agent_ops import (
    create_agent as _create_agent,
    delete_agent as _delete_agent,
    list_agents as _list_agents,
    show_agent as _show_agent,
    update_agent as _update_agent,
)
from miniautogen.cli.services.engine_ops import (
    create_engine as _create_engine,
    delete_engine as _delete_engine,
    list_engines as _list_engines,
    show_engine as _show_engine,
    update_engine as _update_engine,
)
from miniautogen.cli.services.pipeline_ops import (
    create_pipeline as _create_pipeline,
    delete_pipeline as _delete_pipeline,
    list_pipelines as _list_pipelines,
    show_pipeline as _show_pipeline,
    update_pipeline as _update_pipeline,
)
from miniautogen.cli.services.server_ops import (
    server_status as _server_status,
    start_server as _start_server,
    stop_server as _stop_server,
)
from miniautogen.cli.services.check_project import check_project as _check_project
from miniautogen.cli.services.run_pipeline import (
    execute_pipeline as _execute_pipeline,
)


class DashDataProvider:
    """Single bridge between TUI views and the CLI service layer.

    All data access and CRUD goes through this class, keeping views
    decoupled from service internals.
    """

    def __init__(self, project_root: Path) -> None:
        self._root = project_root.resolve()
        self._config_path = self._root / CONFIG_FILENAME
        self._run_history: list[dict[str, Any]] = []

    @classmethod
    def from_cwd(cls) -> DashDataProvider | None:
        """Create a provider from the current working directory.

        Returns None if no project is found.
        """
        root = find_project_root()
        if root is None:
            return None
        return cls(root)

    @property
    def project_root(self) -> Path:
        return self._root

    def has_project(self) -> bool:
        """Check if a valid project config exists."""
        return self._config_path.is_file()

    # ── Read operations ──────────────────────────────────────

    def get_config(self) -> dict[str, Any]:
        """Get the full project configuration as a summary dict."""
        if not self._config_path.is_file():
            return {}
        try:
            config = load_config(self._config_path)
            return {
                "project_name": config.project.name,
                "version": config.project.version,
                "default_engine": config.defaults.engine,
                "default_memory": config.defaults.memory_profile,
                "engine_count": len(config.engine_profiles),
                "agent_count": len(self.get_agents()),
                "pipeline_count": len(config.pipelines),
                "database": config.database.url if config.database else "(none)",
            }
        except Exception:
            return {}

    def get_engines(self) -> list[dict[str, Any]]:
        """List all engine profiles (explicit YAML + discovered).

        Returns engines from 3 sources (priority: yaml > env > local):
        - YAML config (miniautogen.yaml)
        - Environment variables (OPENAI_API_KEY, etc.)
        - Local servers (Ollama, LMStudio)

        Each engine dict includes a "source" field: "yaml", "env", or "local".
        """
        try:
            from miniautogen.backends.engine_resolver import EngineResolver

            yaml_engines = _list_engines(self._root)

            # Mark YAML engines with source
            for eng in yaml_engines:
                eng.setdefault("source", "yaml")

            # Get discovered engines
            resolver = EngineResolver()
            config = load_config(self._config_path)
            available = resolver.list_available_engines(config)

            # Merge: YAML engines first, then discovered (skip duplicates)
            yaml_names = {e.get("name") for e in yaml_engines}
            for eng in available:
                if eng["name"] not in yaml_names:
                    yaml_engines.append(eng)

            return yaml_engines
        except Exception:
            # Fallback to YAML-only if discovery fails
            try:
                return _list_engines(self._root)
            except Exception:
                return []

    def get_agents(self) -> list[dict[str, Any]]:
        """List all agents."""
        try:
            return _list_agents(self._root)
        except Exception:
            return []

    def get_pipelines(self) -> list[dict[str, Any]]:
        """List all pipelines."""
        try:
            return _list_pipelines(self._root)
        except Exception:
            return []

    def get_runs(self) -> list[dict[str, Any]]:
        """List recent runs.

        Returns runs recorded during this session. Pipeline executions
        via run_pipeline() automatically append results here.
        """
        return list(self._run_history)

    def get_events(self) -> list[dict[str, Any]]:
        """Get recent events.

        Currently returns an empty list. Events are streamed live
        via TuiEventSink during pipeline execution.
        """
        return []

    def get_engine(self, name: str) -> dict[str, Any]:
        """Get a single engine by name."""
        return _show_engine(self._root, name)

    def get_agent(self, name: str) -> dict[str, Any]:
        """Get a single agent by name."""
        return _show_agent(self._root, name)

    def get_pipeline(self, name: str) -> dict[str, Any]:
        """Get a single pipeline by name."""
        return _show_pipeline(self._root, name)

    # ── Engine CRUD ──────────────────────────────────────────

    def create_engine(
        self,
        name: str,
        *,
        provider: str,
        model: str,
        kind: str = "api",
        temperature: float = 0.2,
        api_key_env: str | None = None,
        endpoint: str | None = None,
    ) -> dict[str, Any]:
        """Create a new engine profile."""
        return _create_engine(
            self._root,
            name,
            provider=provider,
            model=model,
            kind=kind,
            temperature=temperature,
            api_key_env=api_key_env,
            endpoint=endpoint,
        )

    def update_engine(self, name: str, **updates: Any) -> dict[str, Any]:
        """Update an existing engine profile."""
        return _update_engine(self._root, name, **updates)

    def delete_engine(self, name: str) -> dict[str, Any]:
        """Delete an engine profile."""
        return _delete_engine(self._root, name)

    # ── Agent CRUD ───────────────────────────────────────────

    def create_agent(
        self,
        name: str,
        *,
        role: str,
        goal: str,
        engine_profile: str,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Create a new agent."""
        return _create_agent(
            self._root,
            name,
            role=role,
            goal=goal,
            engine_profile=engine_profile,
            temperature=temperature,
        )

    def update_agent(self, name: str, **updates: Any) -> dict[str, Any]:
        """Update an existing agent."""
        return _update_agent(self._root, name, **updates)

    def delete_agent(self, name: str) -> dict[str, Any]:
        """Delete an agent."""
        return _delete_agent(self._root, name)

    # ── Pipeline CRUD ────────────────────────────────────────

    def create_pipeline(
        self,
        name: str,
        *,
        mode: str = "workflow",
        participants: list[str] | None = None,
        leader: str | None = None,
        target: str | None = None,
    ) -> dict[str, Any]:
        """Create a new pipeline."""
        return _create_pipeline(
            self._root,
            name,
            mode=mode,
            participants=participants,
            leader=leader,
            target=target,
        )

    def update_pipeline(self, name: str, **updates: Any) -> dict[str, Any]:
        """Update an existing pipeline."""
        return _update_pipeline(self._root, name, **updates)

    def delete_pipeline(self, name: str) -> dict[str, Any]:
        """Delete a pipeline from project config.

        Delegates to pipeline_ops.delete_pipeline which performs referential
        integrity checks (agents referencing the flow, composite chains).

        Returns info about the deleted pipeline.
        Raises KeyError if not found, ValueError if referenced by other resources.
        """
        return _delete_pipeline(self._root, name)

    # ── Pipeline Execution ────────────────────────────────────

    async def run_pipeline(
        self,
        pipeline_name: str,
        *,
        event_sink: Any | None = None,
        timeout: float | None = None,
        pipeline_input: str | None = None,
    ) -> dict[str, Any]:
        """Execute a named pipeline, optionally streaming events to a sink.

        Args:
            pipeline_name: Key in project config pipelines section.
            event_sink: Optional event sink (e.g., TuiEventSink) for live events.
            timeout: Optional timeout in seconds.
            pipeline_input: Optional input text for the pipeline.

        Returns:
            Result dict with status, output, events count.
        """
        if not self._config_path.is_file():
            return {"status": "failed", "error": "No project config found"}
        try:
            config = load_config(self._config_path)
            result = await _execute_pipeline(
                config,
                pipeline_name,
                self._root,
                timeout=timeout,
                pipeline_input=pipeline_input,
                event_sink=event_sink,
            )
            # Record run in session history
            from datetime import datetime, timezone
            from uuid import uuid4

            run_record: dict[str, Any] = {
                "run_id": str(uuid4()),
                "pipeline": pipeline_name,
                "status": result.get("status", "unknown"),
                "started": datetime.now(timezone.utc).isoformat(),
                "events": result.get("events", 0),
            }
            self._run_history.append(run_record)
            return result
        except Exception as exc:
            return {
                "status": "failed",
                "error": str(exc),
                "error_type": type(exc).__name__,
            }

    # ── Project Validation ───────────────────────────────────

    def check_project(self):
        """Run all validation checks on the project.

        Returns a list of CheckResult objects, or an empty list if no
        project config is present.
        """
        if not self._config_path.is_file():
            return []
        try:
            config = load_config(self._config_path)
            return _check_project(config, self._root)
        except Exception:
            return []

    # ── Server ───────────────────────────────────────────────

    def server_status(self) -> dict[str, Any]:
        """Get server status."""
        return _server_status(self._root)

    def start_server(self, *, host: str = "127.0.0.1", port: int = 8080, daemon: bool = True) -> dict[str, Any]:
        """Start the gateway server."""
        return _start_server(self._root, host=host, port=port, daemon=daemon)

    def stop_server(self) -> dict[str, Any]:
        """Stop the gateway server."""
        return _stop_server(self._root)
