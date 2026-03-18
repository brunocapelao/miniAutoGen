"""Tests for EngineProfileConfig v2.1 fields."""

from __future__ import annotations

from miniautogen.cli.config import EngineProfileConfig


class TestEngineProfileConfigV21:
    def test_default_provider_is_openai_compat(self) -> None:
        cfg = EngineProfileConfig()
        assert cfg.provider == "openai-compat"

    def test_default_kind_is_api(self) -> None:
        cfg = EngineProfileConfig()
        assert cfg.kind == "api"

    def test_new_fields_have_defaults(self) -> None:
        cfg = EngineProfileConfig()
        assert cfg.fallbacks == []
        assert cfg.max_retries == 3
        assert cfg.retry_delay == 1.0
        assert cfg.max_tokens is None
        assert cfg.timeout_seconds == 120.0

    def test_metadata_field_exists(self) -> None:
        cfg = EngineProfileConfig(metadata={"custom": "value"})
        assert cfg.metadata == {"custom": "value"}

    def test_full_config_roundtrip(self) -> None:
        cfg = EngineProfileConfig(
            kind="cli",
            provider="claude-code",
            model="claude-sonnet-4-20250514",
            endpoint="http://localhost:8080",
            api_key="${ANTHROPIC_API_KEY}",
            temperature=0.5,
            max_tokens=4096,
            timeout_seconds=60.0,
            fallbacks=["fast-cheap", "local-ollama"],
            max_retries=5,
            retry_delay=2.0,
            capabilities=["streaming", "tools"],
            metadata={"region": "us-east-1"},
        )
        restored = EngineProfileConfig.model_validate(cfg.model_dump())
        assert restored == cfg

    def test_backward_compat_existing_fields_unchanged(self) -> None:
        cfg = EngineProfileConfig(
            kind="api",
            provider="openai-compat",
            model="gpt-4o",
            temperature=0.7,
            endpoint="http://localhost:11434/v1",
            api_key="sk-test",
            capabilities=["streaming"],
        )
        assert cfg.model == "gpt-4o"
        assert cfg.temperature == 0.7
        assert cfg.endpoint == "http://localhost:11434/v1"
