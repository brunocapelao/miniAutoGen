# tests/backends/agentapi/test_factory.py
"""Tests for AgentAPIDriver factory and resolver integration."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from miniautogen.backends.agentapi.driver import AgentAPIDriver
from miniautogen.backends.agentapi.factory import agentapi_factory
from miniautogen.backends.config import AuthConfig, BackendConfig, DriverType
from miniautogen.backends.resolver import BackendResolver


class TestAgentAPIFactory:
    def test_creates_driver_from_config(self) -> None:
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.AGENT_API,
            endpoint="http://localhost:8000",
        )
        driver = agentapi_factory(config)
        assert isinstance(driver, AgentAPIDriver)

    def test_extracts_model_from_metadata(self) -> None:
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.AGENT_API,
            endpoint="http://localhost:8000",
            metadata={"model": "gemini-2.5-pro"},
        )
        driver = agentapi_factory(config)
        assert driver._model == "gemini-2.5-pro"

    def test_disables_health_check_from_metadata(self) -> None:
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.AGENT_API,
            endpoint="http://localhost:8000",
            metadata={"health_endpoint": None},
        )
        driver = agentapi_factory(config)
        assert driver._client._health_endpoint is None

    @patch.dict(os.environ, {"MY_TOKEN": "secret-123"})
    def test_resolves_api_key_from_env(self) -> None:
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.AGENT_API,
            endpoint="http://localhost:8000",
            auth=AuthConfig(type="bearer", token_env="MY_TOKEN"),
        )
        driver = agentapi_factory(config)
        assert "authorization" in driver._client._client.headers
        assert driver._client._client.headers["authorization"] == "Bearer secret-123"

    def test_no_auth_when_type_none(self) -> None:
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.AGENT_API,
            endpoint="http://localhost:8000",
            auth=AuthConfig(type="none"),
        )
        driver = agentapi_factory(config)
        assert "authorization" not in driver._client._client.headers

    def test_timeout_from_config(self) -> None:
        config = BackendConfig(
            backend_id="test",
            driver=DriverType.AGENT_API,
            endpoint="http://localhost:8000",
            timeout_seconds=30.0,
        )
        driver = agentapi_factory(config)
        # httpx stores timeout as Timeout object
        assert driver._client._client.timeout.read == 30.0


class TestResolverIntegration:
    def test_register_and_resolve(self) -> None:
        resolver = BackendResolver()
        resolver.register_factory(DriverType.AGENT_API, agentapi_factory)
        resolver.add_backend(
            BackendConfig(
                backend_id="gemini",
                driver=DriverType.AGENT_API,
                endpoint="http://localhost:8000",
            ),
        )
        driver = resolver.get_driver("gemini")
        assert isinstance(driver, AgentAPIDriver)

    def test_driver_is_cached(self) -> None:
        resolver = BackendResolver()
        resolver.register_factory(DriverType.AGENT_API, agentapi_factory)
        resolver.add_backend(
            BackendConfig(
                backend_id="gemini",
                driver=DriverType.AGENT_API,
                endpoint="http://localhost:8000",
            ),
        )
        d1 = resolver.get_driver("gemini")
        d2 = resolver.get_driver("gemini")
        assert d1 is d2
