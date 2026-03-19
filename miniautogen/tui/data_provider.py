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
    list_pipelines as _list_pipelines,
    show_pipeline as _show_pipeline,
    update_pipeline as _update_pipeline,
)
from miniautogen.cli.services.server_ops import (
    server_status as _server_status,
    start_server as _start_server,
    stop_server as _stop_server,
)
from miniautogen.cli.services.yaml_ops import read_yaml


class DashDataProvider:
    """Single bridge between TUI views and the CLI service layer.

    All data access and CRUD goes through this class, keeping views
    decoupled from service internals.
    """

    def __init__(self, project_root: Path) -> None:
        self._root = project_root.resolve()
        self._config_path = self._root / CONFIG_FILENAME

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

        Currently returns an empty list since runs are in-memory only.
        Future: wire to persistent run store.
        """
        return []

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

        Returns info about the deleted pipeline.
        Raises KeyError if not found.
        """
        from miniautogen.cli.services.yaml_ops import write_yaml

        data = read_yaml(self._config_path)
        pipelines = data.get("flows", data.get("pipelines", {}))
        if name not in pipelines:
            available = ", ".join(pipelines) or "(none)"
            msg = f"Pipeline '{name}' not found. Available: {available}"
            raise KeyError(msg)

        pipeline_data = pipelines.pop(name)
        write_yaml(self._config_path, data)

        result = pipeline_data if isinstance(pipeline_data, dict) else {"target": str(pipeline_data)}
        return {"deleted": name, "config": result}

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
