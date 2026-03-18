"""Tests for EngineResolver — the bridge between config and drivers."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from miniautogen.backends.config import BackendConfig, DriverType
from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.engine_resolver import EngineResolver
from miniautogen.backends.errors import BackendUnavailableError
from miniautogen.cli.config import (
    DefaultsConfig,
    EngineProfileConfig,
    ProjectConfig,
    ProjectMeta,
)
from tests.backends.conftest import FakeDriver


def _make_project_config(
    profiles: dict[str, EngineProfileConfig] | None = None,
) -> ProjectConfig:
    return ProjectConfig(
        project=ProjectMeta(name="test-project"),
        defaults=DefaultsConfig(engine_profile="default"),
        engine_profiles=profiles or {},
    )


class TestEngineResolverResolveApiKey:
    def test_resolves_env_var_reference(self) -> None:
        resolver = EngineResolver()
        with patch.dict(os.environ, {"MY_API_KEY": "sk-secret-123"}):
            result = resolver._resolve_api_key("${MY_API_KEY}")
        assert result == "sk-secret-123"

    def test_returns_literal_key_unchanged(self) -> None:
        resolver = EngineResolver()
        result = resolver._resolve_api_key("sk-literal-key")
        assert result == "sk-literal-key"

    def test_returns_none_for_none(self) -> None:
        resolver = EngineResolver()
        result = resolver._resolve_api_key(None)
        assert result is None

    def test_missing_env_var_returns_none(self) -> None:
        resolver = EngineResolver()
        with patch.dict(os.environ, {}, clear=True):
            result = resolver._resolve_api_key("${NONEXISTENT_KEY}")
        assert result is None


class TestEngineResolverEngineToBackend:
    def test_maps_openai_compat_to_agent_api(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="openai-compat",
            endpoint="http://localhost:11434/v1",
            model="llama3.2",
        )
        backend = resolver._engine_to_backend("local-ollama", engine)
        assert backend.backend_id == "local-ollama"
        assert backend.driver == DriverType.AGENT_API
        assert backend.endpoint == "http://localhost:11434/v1"

    def test_maps_openai_to_openai_sdk(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key="sk-test",
        )
        backend = resolver._engine_to_backend("fast-cheap", engine)
        assert backend.driver == DriverType.OPENAI_SDK

    def test_maps_anthropic_to_anthropic_sdk(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="sk-ant-test",
        )
        backend = resolver._engine_to_backend("smart", engine)
        assert backend.driver == DriverType.ANTHROPIC_SDK

    def test_maps_google_to_google_genai(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="google",
            model="gemini-2.5-pro",
        )
        backend = resolver._engine_to_backend("vision", engine)
        assert backend.driver == DriverType.GOOGLE_GENAI

    def test_maps_cli_provider_to_cli(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            kind="cli",
            provider="claude-code",
            model="claude-sonnet-4-20250514",
        )
        backend = resolver._engine_to_backend("claude-agent", engine)
        assert backend.driver == DriverType.CLI
        assert backend.command is not None

    def test_stores_model_in_metadata(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="openai-compat",
            endpoint="http://localhost:8000",
            model="gemini-2.5-pro",
        )
        backend = resolver._engine_to_backend("test", engine)
        assert backend.metadata.get("model") == "gemini-2.5-pro"

    def test_stores_api_key_in_auth(self) -> None:
        resolver = EngineResolver()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-real"}):
            engine = EngineProfileConfig(
                provider="openai-compat",
                endpoint="http://localhost:8000",
                api_key="${OPENAI_API_KEY}",
            )
            backend = resolver._engine_to_backend("test", engine)
        assert backend.auth is not None
        assert backend.auth.type == "bearer"

    def test_unknown_provider_raises(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(provider="unknown-provider")
        with pytest.raises(BackendUnavailableError, match="Unknown provider"):
            resolver._engine_to_backend("test", engine)


class TestEngineResolverResolve:
    def test_resolves_known_profile(self) -> None:
        resolver = EngineResolver()
        # Register a factory for AGENT_API so resolution completes
        resolver._resolver.register_factory(
            DriverType.AGENT_API, lambda cfg: FakeDriver(),
        )
        config = _make_project_config(
            profiles={
                "local": EngineProfileConfig(
                    provider="openai-compat",
                    endpoint="http://localhost:11434/v1",
                    model="llama3.2",
                ),
            },
        )
        driver = resolver.resolve("local", config)
        assert isinstance(driver, AgentDriver)

    def test_unknown_profile_raises(self) -> None:
        resolver = EngineResolver()
        config = _make_project_config()
        with pytest.raises(BackendUnavailableError, match="not found"):
            resolver.resolve("nonexistent", config)

    def test_driver_is_cached(self) -> None:
        resolver = EngineResolver()
        call_count = 0

        def counting_factory(cfg: BackendConfig) -> FakeDriver:
            nonlocal call_count
            call_count += 1
            return FakeDriver()

        resolver._resolver.register_factory(DriverType.AGENT_API, counting_factory)
        config = _make_project_config(
            profiles={
                "local": EngineProfileConfig(
                    provider="openai-compat",
                    endpoint="http://localhost:11434/v1",
                ),
            },
        )
        d1 = resolver.resolve("local", config)
        d2 = resolver.resolve("local", config)
        assert d1 is d2
        assert call_count == 1


class TestEngineResolverWithAgentAPI:
    def test_openai_compat_resolves_to_agentapi_driver(self) -> None:
        from miniautogen.backends.agentapi.driver import AgentAPIDriver

        resolver = EngineResolver()
        config = _make_project_config(
            profiles={
                "local": EngineProfileConfig(
                    provider="openai-compat",
                    endpoint="http://localhost:11434/v1",
                    model="llama3.2",
                ),
            },
        )
        driver = resolver.resolve("local", config)
        assert isinstance(driver, AgentAPIDriver)

    def test_agentapi_driver_has_correct_model(self) -> None:
        from miniautogen.backends.agentapi.driver import AgentAPIDriver

        resolver = EngineResolver()
        config = _make_project_config(
            profiles={
                "test": EngineProfileConfig(
                    provider="openai-compat",
                    endpoint="http://localhost:8000",
                    model="gemini-2.5-pro",
                ),
            },
        )
        driver = resolver.resolve("test", config)
        assert isinstance(driver, AgentAPIDriver)
        assert driver._model == "gemini-2.5-pro"


class TestEngineResolverFactoryRegistration:
    def test_all_driver_types_have_factories(self) -> None:
        resolver = EngineResolver()
        expected_types = {
            DriverType.AGENT_API,
            DriverType.OPENAI_SDK,
            DriverType.ANTHROPIC_SDK,
            DriverType.GOOGLE_GENAI,
            DriverType.CLI,
        }
        registered = set(resolver._resolver._factories.keys())
        assert expected_types.issubset(registered)
