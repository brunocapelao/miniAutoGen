"""Integration tests for engine_config -> factory -> driver pipeline.

Verifies that EngineResolver correctly translates EngineProfileConfig
into BackendConfig and passes the right parameters through to driver
factories for all supported providers.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from miniautogen.backends.config import BackendConfig, DriverType
from miniautogen.backends.engine_resolver import EngineResolver, _PROVIDER_TO_DRIVER
from miniautogen.backends.errors import BackendUnavailableError
from miniautogen.cli.config import (
    DefaultsConfig,
    EngineProfileConfig,
    ProjectConfig,
    ProjectMeta,
)
from tests.backends.conftest import FakeDriver


def _project(
    profiles: dict[str, EngineProfileConfig] | None = None,
) -> ProjectConfig:
    """Build a minimal ProjectConfig with the given engine profiles."""
    return ProjectConfig(
        project=ProjectMeta(name="integration-test"),
        defaults=DefaultsConfig(engine="default"),
        engine_profiles=profiles or {},
    )


def _capture_factory(driver_type: DriverType):
    """Return a factory that records the BackendConfig it receives."""
    captured: list[BackendConfig] = []

    def factory(cfg: BackendConfig) -> FakeDriver:
        captured.append(cfg)
        return FakeDriver()

    return factory, captured


class TestProviderToDriverMapping:
    """Each provider string resolves to the correct DriverType."""

    @pytest.mark.parametrize(
        ("provider", "expected_driver"),
        [
            ("openai", DriverType.OPENAI_SDK),
            ("anthropic", DriverType.ANTHROPIC_SDK),
            ("google", DriverType.GOOGLE_GENAI),
            ("openai-compat", DriverType.AGENT_API),
            ("litellm", DriverType.LITELLM),
            ("claude-code", DriverType.CLI),
            ("gemini-cli", DriverType.CLI),
            ("codex-cli", DriverType.CLI),
        ],
    )
    def test_provider_maps_to_correct_driver_type(
        self, provider: str, expected_driver: DriverType,
    ) -> None:
        assert _PROVIDER_TO_DRIVER[provider] == expected_driver


class TestEngineConfigToBackendConfig:
    """_engine_to_backend translates engine config fields correctly."""

    def test_openai_config_produces_correct_backend(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="openai",
            model="gpt-4o",
            api_key="sk-test-key",
            temperature=0.7,
            max_tokens=4096,
        )
        backend = resolver._engine_to_backend("openai-main", engine)

        assert backend.backend_id == "openai-main"
        assert backend.driver == DriverType.OPENAI_SDK
        assert backend.metadata["model"] == "gpt-4o"
        assert backend.metadata["temperature"] == 0.7
        assert backend.metadata["max_tokens"] == 4096

    def test_anthropic_config_produces_correct_backend(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="sk-ant-test",
            temperature=0.3,
        )
        backend = resolver._engine_to_backend("anthropic-main", engine)

        assert backend.backend_id == "anthropic-main"
        assert backend.driver == DriverType.ANTHROPIC_SDK
        assert backend.metadata["model"] == "claude-sonnet-4-20250514"
        assert backend.metadata["temperature"] == 0.3

    def test_google_config_produces_correct_backend(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="google",
            model="gemini-2.5-pro",
        )
        backend = resolver._engine_to_backend("google-main", engine)

        assert backend.backend_id == "google-main"
        assert backend.driver == DriverType.GOOGLE_GENAI
        assert backend.metadata["model"] == "gemini-2.5-pro"

    def test_retry_params_forwarded_to_metadata(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="openai",
            model="gpt-4o-mini",
            max_retries=5,
            retry_delay=2.5,
        )
        backend = resolver._engine_to_backend("retry-test", engine)

        assert backend.metadata["max_retries"] == 5
        assert backend.metadata["retry_delay"] == 2.5

    def test_timeout_forwarded_to_backend(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            timeout_seconds=300.0,
        )
        backend = resolver._engine_to_backend("timeout-test", engine)

        assert backend.timeout_seconds == 300.0

    def test_custom_metadata_preserved(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="openai",
            model="gpt-4o",
            metadata={"custom_key": "custom_value", "priority": 1},
        )
        backend = resolver._engine_to_backend("meta-test", engine)

        assert backend.metadata["custom_key"] == "custom_value"
        assert backend.metadata["priority"] == 1
        # Standard fields still present
        assert backend.metadata["model"] == "gpt-4o"

    def test_sdk_drivers_disable_health_endpoint(self) -> None:
        """SDK drivers (non-AGENT_API) set health_endpoint to None."""
        resolver = EngineResolver()
        for provider in ("openai", "anthropic", "google"):
            engine = EngineProfileConfig(provider=provider, model="test")
            backend = resolver._engine_to_backend(f"{provider}-health", engine)
            assert backend.metadata.get("health_endpoint") is None

    def test_agent_api_gets_default_endpoint(self) -> None:
        """openai-compat without explicit endpoint gets default OpenAI URL."""
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            provider="openai-compat",
            model="test-model",
        )
        backend = resolver._engine_to_backend("default-ep", engine)
        assert backend.endpoint == "https://api.openai.com/v1"

    def test_cli_provider_gets_default_command(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            kind="cli",
            provider="gemini-cli",
            model="gemini-2.5-pro",
        )
        backend = resolver._engine_to_backend("gemini-cli-test", engine)
        assert backend.command == ["gemini"]

    def test_cli_provider_custom_command(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(
            kind="cli",
            provider="claude-code",
            command="claude --agent --verbose",
        )
        backend = resolver._engine_to_backend("claude-custom", engine)
        assert backend.command == ["claude", "--agent", "--verbose"]


class TestFactoryReceivesCorrectConfig:
    """The factory callable receives a BackendConfig with all expected fields."""

    def test_openai_factory_receives_model_and_temperature(self) -> None:
        resolver = EngineResolver()
        factory, captured = _capture_factory(DriverType.OPENAI_SDK)
        resolver.register_factory(DriverType.OPENAI_SDK, factory)

        config = _project(profiles={
            "gpt": EngineProfileConfig(
                provider="openai",
                model="gpt-4o-mini",
                temperature=0.5,
                api_key="sk-test",
            ),
        })
        resolver.resolve("gpt", config)

        assert len(captured) == 1
        cfg = captured[0]
        assert cfg.driver == DriverType.OPENAI_SDK
        assert cfg.metadata["model"] == "gpt-4o-mini"
        assert cfg.metadata["temperature"] == 0.5

    def test_anthropic_factory_receives_correct_driver_type(self) -> None:
        resolver = EngineResolver()
        factory, captured = _capture_factory(DriverType.ANTHROPIC_SDK)
        resolver.register_factory(DriverType.ANTHROPIC_SDK, factory)

        config = _project(profiles={
            "claude": EngineProfileConfig(
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                api_key="sk-ant-test",
            ),
        })
        resolver.resolve("claude", config)

        assert len(captured) == 1
        assert captured[0].driver == DriverType.ANTHROPIC_SDK
        assert captured[0].metadata["model"] == "claude-sonnet-4-20250514"

    def test_google_factory_receives_correct_driver_type(self) -> None:
        resolver = EngineResolver()
        factory, captured = _capture_factory(DriverType.GOOGLE_GENAI)
        resolver.register_factory(DriverType.GOOGLE_GENAI, factory)

        config = _project(profiles={
            "gemini": EngineProfileConfig(
                provider="google",
                model="gemini-2.5-pro",
            ),
        })
        resolver.resolve("gemini", config)

        assert len(captured) == 1
        assert captured[0].driver == DriverType.GOOGLE_GENAI
        assert captured[0].metadata["model"] == "gemini-2.5-pro"

    def test_factory_receives_auth_when_api_key_provided(self) -> None:
        resolver = EngineResolver()
        factory, captured = _capture_factory(DriverType.OPENAI_SDK)
        resolver.register_factory(DriverType.OPENAI_SDK, factory)

        config = _project(profiles={
            "authed": EngineProfileConfig(
                provider="openai",
                model="gpt-4o",
                api_key="sk-literal-key",
            ),
        })
        resolver.resolve("authed", config)

        assert len(captured) == 1
        assert captured[0].auth is not None
        assert captured[0].auth.type == "bearer"

    def test_factory_receives_no_auth_when_no_key(self) -> None:
        resolver = EngineResolver()
        factory, captured = _capture_factory(DriverType.GOOGLE_GENAI)
        resolver.register_factory(DriverType.GOOGLE_GENAI, factory)

        config = _project(profiles={
            "no-key": EngineProfileConfig(
                provider="google",
                model="gemini-2.5-pro",
            ),
        })
        resolver.resolve("no-key", config)

        assert len(captured) == 1
        assert captured[0].auth is None


class TestErrorHandling:
    """Proper errors raised for invalid configurations."""

    def test_invalid_provider_raises_backend_unavailable(self) -> None:
        resolver = EngineResolver()
        engine = EngineProfileConfig(provider="nonexistent-provider")
        with pytest.raises(BackendUnavailableError, match="Unknown provider"):
            resolver._engine_to_backend("bad", engine)

    def test_missing_profile_raises_backend_unavailable(self) -> None:
        resolver = EngineResolver()
        config = _project()
        with pytest.raises(BackendUnavailableError, match="not found"):
            resolver.resolve("does-not-exist", config)

    def test_create_fresh_driver_missing_profile_raises(self) -> None:
        resolver = EngineResolver()
        config = _project()
        with pytest.raises(BackendUnavailableError, match="not found"):
            resolver.create_fresh_driver("missing", config)

    def test_env_var_api_key_resolves_correctly(self) -> None:
        resolver = EngineResolver()
        with patch.dict("os.environ", {"TEST_API_KEY": "sk-from-env"}):
            engine = EngineProfileConfig(
                provider="openai",
                model="gpt-4o",
                api_key="${TEST_API_KEY}",
            )
            backend = resolver._engine_to_backend("env-key", engine)

        assert backend.auth is not None
        assert backend.auth.type == "bearer"

    def test_missing_env_var_results_in_no_auth(self) -> None:
        resolver = EngineResolver()
        with patch.dict("os.environ", {}, clear=True):
            engine = EngineProfileConfig(
                provider="openai",
                model="gpt-4o",
                api_key="${MISSING_VAR}",
            )
            backend = resolver._engine_to_backend("missing-env", engine)

        # Missing env var -> None key -> no auth
        assert backend.auth is None


class TestCreateFreshDriverPipeline:
    """create_fresh_driver produces independent drivers through the full pipeline."""

    def test_fresh_drivers_have_unique_backend_ids(self) -> None:
        resolver = EngineResolver()
        captured_ids: list[str] = []

        def id_capturing_factory(cfg: BackendConfig) -> FakeDriver:
            captured_ids.append(cfg.backend_id)
            return FakeDriver()

        resolver.register_factory(DriverType.OPENAI_SDK, id_capturing_factory)

        config = _project(profiles={
            "main": EngineProfileConfig(
                provider="openai",
                model="gpt-4o-mini",
                api_key="sk-test",
            ),
        })

        resolver.create_fresh_driver("main", config)
        resolver.create_fresh_driver("main", config)

        assert len(captured_ids) == 2
        assert captured_ids[0] != captured_ids[1]
        assert all(cid.startswith("main_") for cid in captured_ids)

    def test_fresh_driver_config_matches_profile(self) -> None:
        """Full pipeline: EngineProfileConfig -> BackendConfig -> factory call."""
        resolver = EngineResolver()
        factory, captured = _capture_factory(DriverType.ANTHROPIC_SDK)
        resolver.register_factory(DriverType.ANTHROPIC_SDK, factory)

        config = _project(profiles={
            "smart": EngineProfileConfig(
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                temperature=0.1,
                max_tokens=8192,
                timeout_seconds=180.0,
                api_key="sk-ant-fresh",
            ),
        })

        driver = resolver.create_fresh_driver("smart", config)

        assert isinstance(driver, FakeDriver)
        assert len(captured) == 1

        cfg = captured[0]
        assert cfg.driver == DriverType.ANTHROPIC_SDK
        assert cfg.metadata["model"] == "claude-sonnet-4-20250514"
        assert cfg.metadata["temperature"] == 0.1
        assert cfg.metadata["max_tokens"] == 8192
        assert cfg.timeout_seconds == 180.0


class TestResolveEngineConfigService:
    """Tests for _resolve_engine_config from run_pipeline service."""

    def test_resolves_default_engine_config(self) -> None:
        from miniautogen.cli.services.run_pipeline import _resolve_engine_config

        config = _project(profiles={
            "default": EngineProfileConfig(
                provider="openai",
                model="gpt-4o",
                temperature=0.5,
                endpoint="https://api.openai.com/v1",
                timeout_seconds=60.0,
            ),
        })

        result = _resolve_engine_config(config)

        assert result is not None
        assert result["engine_name"] == "default"
        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4o"
        assert result["temperature"] == 0.5
        assert result["timeout_seconds"] == 60.0

    def test_returns_none_when_no_engine_configured(self) -> None:
        from miniautogen.cli.services.run_pipeline import _resolve_engine_config

        config = _project()
        result = _resolve_engine_config(config)
        assert result is None

    def test_returns_none_when_default_engine_missing(self) -> None:
        from miniautogen.cli.services.run_pipeline import _resolve_engine_config

        config = ProjectConfig(
            project=ProjectMeta(name="test"),
            defaults=DefaultsConfig(engine="nonexistent"),
            engine_profiles={
                "other": EngineProfileConfig(provider="openai", model="gpt-4o"),
            },
        )
        result = _resolve_engine_config(config)
        assert result is None
