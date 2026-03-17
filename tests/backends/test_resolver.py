# tests/backends/test_resolver.py
"""Tests for BackendResolver."""

from __future__ import annotations

import pytest

from miniautogen.backends.config import BackendConfig, DriverType
from miniautogen.backends.driver import AgentDriver
from miniautogen.backends.errors import BackendUnavailableError
from miniautogen.backends.resolver import BackendResolver
from tests.backends.conftest import FakeDriver


class TestBackendResolver:
    def test_register_and_resolve(self) -> None:
        resolver = BackendResolver()
        resolver.register_factory(
            DriverType.ACP,
            lambda cfg: FakeDriver(),
        )
        config = BackendConfig(backend_id="test", driver=DriverType.ACP, command=["acpx"])
        resolver.add_backend(config)
        driver = resolver.get_driver("test")
        assert isinstance(driver, AgentDriver)

    def test_resolve_unknown_backend_raises(self) -> None:
        resolver = BackendResolver()
        with pytest.raises(BackendUnavailableError, match="not configured"):
            resolver.get_driver("nonexistent")

    def test_resolve_unregistered_driver_type_raises(self) -> None:
        resolver = BackendResolver()
        config = BackendConfig(backend_id="test", driver=DriverType.PTY, command=["legacy"])
        resolver.add_backend(config)
        with pytest.raises(BackendUnavailableError, match="No factory"):
            resolver.get_driver("test")

    def test_list_backends(self) -> None:
        resolver = BackendResolver()
        resolver.add_backend(
            BackendConfig(backend_id="a", driver=DriverType.ACP, command=["acpx"]),
        )
        resolver.add_backend(
            BackendConfig(backend_id="b", driver=DriverType.PTY, command=["legacy"]),
        )
        ids = resolver.list_backends()
        assert set(ids) == {"a", "b"}

    def test_get_config(self) -> None:
        resolver = BackendResolver()
        cfg = BackendConfig(backend_id="x", driver=DriverType.AGENT_API, endpoint="http://localhost:8080")
        resolver.add_backend(cfg)
        assert resolver.get_config("x") == cfg

    def test_get_config_unknown_returns_none(self) -> None:
        resolver = BackendResolver()
        assert resolver.get_config("nope") is None

    def test_driver_is_cached(self) -> None:
        resolver = BackendResolver()
        call_count = 0

        def factory(cfg: BackendConfig) -> FakeDriver:
            nonlocal call_count
            call_count += 1
            return FakeDriver()

        resolver.register_factory(DriverType.ACP, factory)
        resolver.add_backend(
            BackendConfig(backend_id="c", driver=DriverType.ACP, command=["acpx"]),
        )
        d1 = resolver.get_driver("c")
        d2 = resolver.get_driver("c")
        assert d1 is d2
        assert call_count == 1

    def test_add_duplicate_backend_raises(self) -> None:
        resolver = BackendResolver()
        cfg = BackendConfig(backend_id="dup", driver=DriverType.ACP, command=["acpx"])
        resolver.add_backend(cfg)
        with pytest.raises(ValueError, match="already configured"):
            resolver.add_backend(cfg)
