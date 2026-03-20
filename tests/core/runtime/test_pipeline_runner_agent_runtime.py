"""Tests for PipelineRunner._build_agent_runtimes() factory method.

Validates that the factory:
- Exists on PipelineRunner
- Creates separate AgentRuntime instances per agent
- Gives each agent its own driver (not shared)
- Sets per-agent config_dir correctly
- Falls back to InMemory implementations when config_dir doesn't exist
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from miniautogen.cli.config import EngineConfig, ProjectMeta, WorkspaceConfig
from miniautogen.core.contracts.agent_spec import AgentSpec
from miniautogen.core.runtime.agent_runtime import AgentRuntime
from miniautogen.core.runtime.pipeline_runner import PipelineRunner


def _make_config(engines: dict[str, dict]) -> WorkspaceConfig:
    """Build a minimal WorkspaceConfig with the given engines."""
    engine_profiles = {
        name: EngineConfig(**params) for name, params in engines.items()
    }
    return WorkspaceConfig(
        project=ProjectMeta(name="test-project"),
        engines=engine_profiles,
    )


def _make_agent_specs(
    agents: dict[str, str],
) -> dict[str, AgentSpec]:
    """Build agent specs mapping agent_name -> AgentSpec with engine_profile."""
    return {
        name: AgentSpec(
            id=name,
            name=name,
            engine_profile=engine,
            description=f"Test agent {name}",
        )
        for name, engine in agents.items()
    }


def _make_mock_resolver() -> tuple[MagicMock, list[MagicMock]]:
    """Create a mock EngineResolver that tracks created drivers."""
    drivers_created: list[MagicMock] = []

    def create_fresh(profile_name, config):
        driver = MagicMock()
        driver.profile_name = profile_name
        driver.driver_id = f"driver-{len(drivers_created)}"
        drivers_created.append(driver)
        return driver

    resolver = MagicMock()
    resolver.create_fresh_driver.side_effect = create_fresh
    return resolver, drivers_created


class TestBuildAgentRuntimesExists:
    """The factory method must exist on PipelineRunner."""

    def test_method_exists(self) -> None:
        runner = PipelineRunner()
        assert hasattr(runner, "_build_agent_runtimes")
        assert callable(runner._build_agent_runtimes)


class TestBuildAgentRuntimesCreation:
    """Given a config with 2 agents using different engines, creates 2 AgentRuntimes."""

    @pytest.fixture()
    def config(self) -> WorkspaceConfig:
        return _make_config({
            "fast-engine": {"provider": "openai-compat", "model": "gpt-4o-mini"},
            "smart-engine": {"provider": "openai-compat", "model": "gpt-4o"},
        })

    @pytest.fixture()
    def agent_specs(self) -> dict[str, AgentSpec]:
        return _make_agent_specs({
            "researcher": "fast-engine",
            "writer": "smart-engine",
        })

    def test_creates_two_runtimes(
        self, config, agent_specs, tmp_path,
    ) -> None:
        resolver, _ = _make_mock_resolver()
        runner = PipelineRunner(engine_resolver=resolver)

        runtimes = runner._build_agent_runtimes(
            agent_specs=agent_specs,
            workspace=tmp_path,
            config=config,
        )

        assert len(runtimes) == 2
        assert "researcher" in runtimes
        assert "writer" in runtimes

    def test_each_runtime_is_agent_runtime(
        self, config, agent_specs, tmp_path,
    ) -> None:
        resolver, _ = _make_mock_resolver()
        runner = PipelineRunner(engine_resolver=resolver)

        runtimes = runner._build_agent_runtimes(
            agent_specs=agent_specs,
            workspace=tmp_path,
            config=config,
        )

        for name, rt in runtimes.items():
            assert isinstance(rt, AgentRuntime), (
                f"Expected AgentRuntime for '{name}', got {type(rt)}"
            )

    def test_each_agent_has_own_driver(
        self, config, agent_specs, tmp_path,
    ) -> None:
        resolver, drivers_created = _make_mock_resolver()
        runner = PipelineRunner(engine_resolver=resolver)

        runtimes = runner._build_agent_runtimes(
            agent_specs=agent_specs,
            workspace=tmp_path,
            config=config,
        )

        # create_fresh_driver called once per agent
        assert resolver.create_fresh_driver.call_count == 2

        # Drivers are distinct objects
        driver_ids = {d.driver_id for d in drivers_created}
        assert len(driver_ids) == 2, "Each agent must get its own driver"

    def test_correct_engine_profiles_resolved(
        self, config, agent_specs, tmp_path,
    ) -> None:
        resolver, _ = _make_mock_resolver()
        runner = PipelineRunner(engine_resolver=resolver)

        runner._build_agent_runtimes(
            agent_specs=agent_specs,
            workspace=tmp_path,
            config=config,
        )

        call_profiles = {
            call.args[0]
            for call in resolver.create_fresh_driver.call_args_list
        }
        assert call_profiles == {"fast-engine", "smart-engine"}


class TestBuildAgentRuntimesConfigDir:
    """Per-agent config_dir is set correctly."""

    def test_config_dir_follows_convention(self, tmp_path) -> None:
        resolver, _ = _make_mock_resolver()
        config = _make_config({
            "default": {"provider": "openai-compat"},
        })
        specs = _make_agent_specs({"planner": "default"})

        runner = PipelineRunner(engine_resolver=resolver)
        runtimes = runner._build_agent_runtimes(
            agent_specs=specs,
            workspace=tmp_path,
            config=config,
        )

        rt = runtimes["planner"]
        expected_dir = tmp_path / ".miniautogen" / "agents" / "planner"
        assert rt._config_dir == expected_dir


class TestBuildAgentRuntimesInMemoryFallback:
    """Falls back to InMemory implementations when config_dir doesn't exist."""

    def test_uses_inmemory_when_no_config_dir(self, tmp_path) -> None:
        from miniautogen.core.contracts.memory_provider import (
            InMemoryMemoryProvider,
        )
        from miniautogen.core.runtime.tool_registry import InMemoryToolRegistry

        resolver, _ = _make_mock_resolver()
        config = _make_config({
            "default": {"provider": "openai-compat"},
        })
        specs = _make_agent_specs({"agent-a": "default"})

        runner = PipelineRunner(engine_resolver=resolver)
        runtimes = runner._build_agent_runtimes(
            agent_specs=specs,
            workspace=tmp_path,
            config=config,
        )

        rt = runtimes["agent-a"]
        assert isinstance(rt._memory, InMemoryMemoryProvider)
        assert isinstance(rt._tool_registry, InMemoryToolRegistry)

    def test_uses_inmemory_even_when_config_dir_exists(self, tmp_path) -> None:
        """For now, always uses InMemory (FileSystem impls come in Tasks 8-9)."""
        from miniautogen.core.contracts.memory_provider import (
            InMemoryMemoryProvider,
        )
        from miniautogen.core.runtime.tool_registry import InMemoryToolRegistry

        resolver, _ = _make_mock_resolver()
        config = _make_config({
            "default": {"provider": "openai-compat"},
        })
        specs = _make_agent_specs({"agent-b": "default"})

        # Create the config dir
        config_dir = tmp_path / ".miniautogen" / "agents" / "agent-b"
        config_dir.mkdir(parents=True)

        runner = PipelineRunner(engine_resolver=resolver)
        runtimes = runner._build_agent_runtimes(
            agent_specs=specs,
            workspace=tmp_path,
            config=config,
        )

        rt = runtimes["agent-b"]
        # Currently InMemory; FileSystem impls will replace in Tasks 8-9
        assert isinstance(rt._memory, InMemoryMemoryProvider)
        assert isinstance(rt._tool_registry, InMemoryToolRegistry)
