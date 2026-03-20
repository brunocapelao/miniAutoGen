"""Tests for PipelineRunner._build_agent_runtimes() factory method.

Validates that the factory:
- Exists on PipelineRunner
- Creates separate AgentRuntime instances per agent
- Gives each agent its own driver (not shared)
- Sets per-agent config_dir correctly
- Uses real implementations (CompositeToolRegistry, PersistentMemoryProvider)
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

    @pytest.mark.anyio()
    async def test_creates_two_runtimes(
        self, config, agent_specs, tmp_path,
    ) -> None:
        resolver, _ = _make_mock_resolver()
        runner = PipelineRunner(engine_resolver=resolver)

        runtimes = await runner._build_agent_runtimes(
            agent_specs=agent_specs,
            workspace=tmp_path,
            config=config,
            run_id="test-run-1",
        )

        assert len(runtimes) == 2
        assert "researcher" in runtimes
        assert "writer" in runtimes

    @pytest.mark.anyio()
    async def test_each_runtime_is_agent_runtime(
        self, config, agent_specs, tmp_path,
    ) -> None:
        resolver, _ = _make_mock_resolver()
        runner = PipelineRunner(engine_resolver=resolver)

        runtimes = await runner._build_agent_runtimes(
            agent_specs=agent_specs,
            workspace=tmp_path,
            config=config,
            run_id="test-run-2",
        )

        for name, rt in runtimes.items():
            assert isinstance(rt, AgentRuntime), (
                f"Expected AgentRuntime for '{name}', got {type(rt)}"
            )

    @pytest.mark.anyio()
    async def test_each_agent_has_own_driver(
        self, config, agent_specs, tmp_path,
    ) -> None:
        resolver, drivers_created = _make_mock_resolver()
        runner = PipelineRunner(engine_resolver=resolver)

        runtimes = await runner._build_agent_runtimes(
            agent_specs=agent_specs,
            workspace=tmp_path,
            config=config,
            run_id="test-run-3",
        )

        # create_fresh_driver called once per agent
        assert resolver.create_fresh_driver.call_count == 2

        # Drivers are distinct objects
        driver_ids = {d.driver_id for d in drivers_created}
        assert len(driver_ids) == 2, "Each agent must get its own driver"

    @pytest.mark.anyio()
    async def test_correct_engine_profiles_resolved(
        self, config, agent_specs, tmp_path,
    ) -> None:
        resolver, _ = _make_mock_resolver()
        runner = PipelineRunner(engine_resolver=resolver)

        await runner._build_agent_runtimes(
            agent_specs=agent_specs,
            workspace=tmp_path,
            config=config,
            run_id="test-run-4",
        )

        call_profiles = {
            call.args[0]
            for call in resolver.create_fresh_driver.call_args_list
        }
        assert call_profiles == {"fast-engine", "smart-engine"}


class TestBuildAgentRuntimesConfigDir:
    """Per-agent config_dir is set correctly."""

    @pytest.mark.anyio()
    async def test_config_dir_follows_convention(self, tmp_path) -> None:
        resolver, _ = _make_mock_resolver()
        config = _make_config({
            "default": {"provider": "openai-compat"},
        })
        specs = _make_agent_specs({"planner": "default"})

        runner = PipelineRunner(engine_resolver=resolver)
        runtimes = await runner._build_agent_runtimes(
            agent_specs=specs,
            workspace=tmp_path,
            config=config,
            run_id="test-run-5",
        )

        rt = runtimes["planner"]
        expected_dir = tmp_path / ".miniautogen" / "agents" / "planner"
        assert rt._config_dir == expected_dir


class TestBuildAgentRuntimesRealImplementations:
    """Uses real implementations: CompositeToolRegistry, PersistentMemoryProvider."""

    @pytest.mark.anyio()
    async def test_uses_composite_tool_registry(self, tmp_path) -> None:
        from miniautogen.core.runtime.composite_tool_registry import (
            CompositeToolRegistry,
        )

        resolver, _ = _make_mock_resolver()
        config = _make_config({
            "default": {"provider": "openai-compat"},
        })
        specs = _make_agent_specs({"agent-a": "default"})

        runner = PipelineRunner(engine_resolver=resolver)
        runtimes = await runner._build_agent_runtimes(
            agent_specs=specs,
            workspace=tmp_path,
            config=config,
            run_id="test-run-6",
        )

        rt = runtimes["agent-a"]
        assert isinstance(rt._tool_registry, CompositeToolRegistry)

    @pytest.mark.anyio()
    async def test_uses_persistent_memory_provider(self, tmp_path) -> None:
        from miniautogen.core.runtime.persistent_memory import (
            PersistentMemoryProvider,
        )

        resolver, _ = _make_mock_resolver()
        config = _make_config({
            "default": {"provider": "openai-compat"},
        })
        specs = _make_agent_specs({"agent-b": "default"})

        runner = PipelineRunner(engine_resolver=resolver)
        runtimes = await runner._build_agent_runtimes(
            agent_specs=specs,
            workspace=tmp_path,
            config=config,
            run_id="test-run-7",
        )

        rt = runtimes["agent-b"]
        assert isinstance(rt._memory, PersistentMemoryProvider)

    @pytest.mark.anyio()
    async def test_loads_prompt_md_when_present(self, tmp_path) -> None:
        resolver, _ = _make_mock_resolver()
        config = _make_config({
            "default": {"provider": "openai-compat"},
        })
        specs = _make_agent_specs({"agent-c": "default"})
        specs["agent-c"] = AgentSpec(
            id="agent-c",
            name="agent-c",
            engine_profile="default",
            role="tester",
        )

        # Create prompt.md
        config_dir = tmp_path / ".miniautogen" / "agents" / "agent-c"
        config_dir.mkdir(parents=True)
        (config_dir / "prompt.md").write_text("You are a testing expert.")

        runner = PipelineRunner(engine_resolver=resolver)
        runtimes = await runner._build_agent_runtimes(
            agent_specs=specs,
            workspace=tmp_path,
            config=config,
            run_id="test-run-8",
        )

        rt = runtimes["agent-c"]
        assert rt._system_prompt is not None
        assert "You are a testing expert." in rt._system_prompt
        assert "Role: tester" in rt._system_prompt
