"""Tests for engine auto-discovery from environment and local servers."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from miniautogen.backends.discovery import EngineDiscovery
from miniautogen.backends.engine_resolver import EngineResolver
from miniautogen.cli.config import (
    DefaultsConfig,
    EngineProfileConfig,
    ProjectConfig,
    ProjectMeta,
)


def _make_project_config(
    profiles: dict[str, EngineProfileConfig] | None = None,
) -> ProjectConfig:
    return ProjectConfig(
        project=ProjectMeta(name="test-project"),
        defaults=DefaultsConfig(engine_profile="default"),
        engine_profiles=profiles or {},
    )


class TestDiscoverFromEnv:
    def test_discover_openai_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
        discovery = EngineDiscovery()
        engines = discovery.discover_from_env()

        assert "openai" in engines
        assert engines["openai"].provider == "openai"
        assert engines["openai"].model == "gpt-4o-mini"
        assert engines["openai"].api_key == "${OPENAI_API_KEY}"

    def test_discover_anthropic_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        discovery = EngineDiscovery()
        engines = discovery.discover_from_env()

        assert "anthropic" in engines
        assert engines["anthropic"].provider == "anthropic"
        assert engines["anthropic"].model == "claude-sonnet-4-20250514"

    def test_discover_google_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOOGLE_API_KEY", "goog-test")
        discovery = EngineDiscovery()
        engines = discovery.discover_from_env()

        assert "google" in engines
        assert engines["google"].provider == "google"
        assert engines["google"].model == "gemini-2.5-flash"

    def test_discover_google_from_gemini_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GEMINI_API_KEY also maps to the 'google' engine."""
        monkeypatch.setenv("GEMINI_API_KEY", "gemini-test")
        discovery = EngineDiscovery()
        engines = discovery.discover_from_env()

        assert "google" in engines
        assert engines["google"].api_key == "${GEMINI_API_KEY}"

    def test_discover_groq_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
        discovery = EngineDiscovery()
        engines = discovery.discover_from_env()

        assert "groq" in engines
        assert engines["groq"].provider == "openai-compat"
        assert engines["groq"].endpoint == "https://api.groq.com/openai/v1"
        assert engines["groq"].model == "llama-3.3-70b-versatile"

    def test_discover_no_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No API keys set returns empty dict."""
        # Clear all known env vars
        for var in [
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
            "GEMINI_API_KEY", "GROQ_API_KEY", "DEEPSEEK_API_KEY",
            "OPENROUTER_API_KEY", "TOGETHER_API_KEY", "MISTRAL_API_KEY",
        ]:
            monkeypatch.delenv(var, raising=False)

        discovery = EngineDiscovery()
        engines = discovery.discover_from_env()
        assert engines == {}

    def test_discover_multiple_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("GROQ_API_KEY", "gsk-test")

        discovery = EngineDiscovery()
        engines = discovery.discover_from_env()

        assert len(engines) == 3
        assert "openai" in engines
        assert "anthropic" in engines
        assert "groq" in engines

    def test_env_var_stored_as_reference(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """api_key must be '${VAR_NAME}', never the actual secret value."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret-value")
        discovery = EngineDiscovery()
        engines = discovery.discover_from_env()

        assert engines["openai"].api_key == "${OPENAI_API_KEY}"
        assert "sk-super-secret-value" not in str(engines["openai"])

    def test_google_api_key_takes_precedence_over_gemini(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When both GOOGLE_API_KEY and GEMINI_API_KEY are set,
        GOOGLE_API_KEY wins because it's checked first."""
        monkeypatch.setenv("GOOGLE_API_KEY", "goog-key")
        monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
        discovery = EngineDiscovery()
        engines = discovery.discover_from_env()

        assert "google" in engines
        assert engines["google"].api_key == "${GOOGLE_API_KEY}"


class TestDiscoverLocalServers:
    def test_discover_local_ollama(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mock httpx to detect Ollama on port 11434."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        def mock_get(url: str, timeout: float = 1.0) -> MagicMock:
            if ":11434" in url:
                return mock_response
            raise ConnectionError("refused")

        with patch("miniautogen.backends.discovery.httpx") as mock_httpx:
            mock_httpx.get = mock_get
            discovery = EngineDiscovery()
            engines = discovery.discover_local_servers()

        assert "ollama" in engines
        assert engines["ollama"].provider == "openai-compat"
        assert engines["ollama"].endpoint == "http://localhost:11434/v1"
        assert engines["ollama"].model == "auto"

    def test_discover_local_lmstudio(self) -> None:
        """Mock httpx to detect LM Studio on port 1234."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        def mock_get(url: str, timeout: float = 1.0) -> MagicMock:
            if ":1234" in url:
                return mock_response
            raise ConnectionError("refused")

        with patch("miniautogen.backends.discovery.httpx") as mock_httpx:
            mock_httpx.get = mock_get
            discovery = EngineDiscovery()
            engines = discovery.discover_local_servers()

        assert "lmstudio" in engines
        assert engines["lmstudio"].endpoint == "http://localhost:1234/v1"

    def test_discover_local_no_servers(self) -> None:
        """No servers respond — returns empty dict."""
        def mock_get(url: str, timeout: float = 1.0) -> None:
            raise ConnectionError("refused")

        with patch("miniautogen.backends.discovery.httpx") as mock_httpx:
            mock_httpx.get = mock_get
            discovery = EngineDiscovery()
            engines = discovery.discover_local_servers()

        assert engines == {}

    def test_discover_local_server_500_ignored(self) -> None:
        """Server errors (5xx) are treated as unavailable."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        def mock_get(url: str, timeout: float = 1.0) -> MagicMock:
            return mock_response

        with patch("miniautogen.backends.discovery.httpx") as mock_httpx:
            mock_httpx.get = mock_get
            discovery = EngineDiscovery()
            engines = discovery.discover_local_servers()

        assert engines == {}


class TestExplicitConfigOverridesEnv:
    def test_explicit_config_overrides_env(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """YAML engine with same name as discovered engine wins."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        explicit_profile = EngineProfileConfig(
            provider="openai",
            model="gpt-4-turbo",
            api_key="${OPENAI_API_KEY}",
        )
        config = _make_project_config(profiles={"openai": explicit_profile})

        resolver = EngineResolver()
        merged = resolver.resolve_with_discovery(config)

        # The explicit config's model should win
        assert merged["openai"].model == "gpt-4-turbo"

    def test_discovered_engines_fill_gaps(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Discovered engines appear for names not in explicit config."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        config = _make_project_config(profiles={
            "my-openai": EngineProfileConfig(
                provider="openai",
                model="gpt-4o",
                api_key="${OPENAI_API_KEY}",
            ),
        })

        resolver = EngineResolver()
        merged = resolver.resolve_with_discovery(config)

        # Explicit engine preserved
        assert "my-openai" in merged
        # Discovered engine added
        assert "anthropic" in merged
        assert merged["anthropic"].provider == "anthropic"


class TestListAvailableEngines:
    def test_list_available_engines(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        explicit_profile = EngineProfileConfig(
            provider="openai",
            model="gpt-4o",
            api_key="${OPENAI_API_KEY}",
        )
        config = _make_project_config(profiles={"my-gpt": explicit_profile})

        # Mock out local server detection
        with patch(
            "miniautogen.backends.discovery.EngineDiscovery.discover_local_servers",
            return_value={},
        ):
            resolver = EngineResolver()
            available = resolver.list_available_engines(config)

        names = {e["name"] for e in available}
        assert "my-gpt" in names
        assert "anthropic" in names
        # openai from env should also be present (different name from my-gpt)
        assert "openai" in names

        # Check sources
        sources = {e["name"]: e["source"] for e in available}
        assert sources["my-gpt"] == "yaml"
        assert sources["anthropic"] == "env"
        assert sources["openai"] == "env"

    def test_yaml_source_overrides_env_source(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When YAML has an engine named 'openai', source should be 'yaml'."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        config = _make_project_config(profiles={
            "openai": EngineProfileConfig(
                provider="openai",
                model="gpt-4-turbo",
                api_key="${OPENAI_API_KEY}",
            ),
        })

        with patch(
            "miniautogen.backends.discovery.EngineDiscovery.discover_local_servers",
            return_value={},
        ):
            resolver = EngineResolver()
            available = resolver.list_available_engines(config)

        sources = {e["name"]: e["source"] for e in available}
        assert sources["openai"] == "yaml"


class TestDiscoverAll:
    def test_discover_all_merges_env_and_local(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        mock_response = MagicMock()
        mock_response.status_code = 200

        def mock_get(url: str, timeout: float = 1.0) -> MagicMock:
            if ":11434" in url:
                return mock_response
            raise ConnectionError("refused")

        with patch("miniautogen.backends.discovery.httpx") as mock_httpx:
            mock_httpx.get = mock_get
            discovery = EngineDiscovery()
            engines = discovery.discover_all()

        assert "openai" in engines
        assert "ollama" in engines
