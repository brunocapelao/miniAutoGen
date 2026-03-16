# tests/backends/test_config.py
"""Tests for backend configuration models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from miniautogen.backends.config import AuthConfig, BackendConfig, DriverType


class TestDriverType:
    def test_valid_types(self) -> None:
        assert DriverType.ACP.value == "acp"
        assert DriverType.AGENT_API.value == "agentapi"
        assert DriverType.PTY.value == "pty"


class TestBackendConfig:
    def test_minimal_acp(self) -> None:
        cfg = BackendConfig(
            backend_id="claude_code",
            driver=DriverType.ACP,
            command=["acpx"],
        )
        assert cfg.backend_id == "claude_code"
        assert cfg.endpoint is None

    def test_acp_with_launcher(self) -> None:
        cfg = BackendConfig(
            backend_id="claude_code",
            driver=DriverType.ACP,
            command=["acpx"],
            agent="claude-code",
            capabilities_override={"sessions": True, "streaming": True},
        )
        assert cfg.command == ["acpx"]
        assert cfg.agent == "claude-code"

    def test_agentapi_with_endpoint(self) -> None:
        cfg = BackendConfig(
            backend_id="gemini_bridge",
            driver=DriverType.AGENT_API,
            endpoint="http://127.0.0.1:8090",
            auth=AuthConfig(type="bearer", token_env="AGENTAPI_TOKEN"),
        )
        assert cfg.endpoint == "http://127.0.0.1:8090"
        assert cfg.auth is not None
        assert cfg.auth.token_env == "AGENTAPI_TOKEN"

    def test_pty_with_command(self) -> None:
        cfg = BackendConfig(
            backend_id="legacy_cli",
            driver=DriverType.PTY,
            command=["legacy-agent", "--interactive"],
            parse_mode="line",
            timeout_seconds=180,
        )
        assert cfg.command == ["legacy-agent", "--interactive"]
        assert cfg.timeout_seconds == 180

    def test_driver_required(self) -> None:
        with pytest.raises(ValidationError):
            BackendConfig(backend_id="x")  # type: ignore[call-arg]

    def test_backend_id_required(self) -> None:
        with pytest.raises(ValidationError):
            BackendConfig(driver=DriverType.ACP)  # type: ignore[call-arg]

    def test_serialization_roundtrip(self) -> None:
        cfg = BackendConfig(
            backend_id="test",
            driver=DriverType.ACP,
            command=["acpx"],
            env={"API_KEY": "secret"},
        )
        restored = BackendConfig.model_validate(cfg.model_dump())
        assert restored == cfg

    # --- Conditional validation tests (D3/point 3) ---

    def test_acp_without_command_raises(self) -> None:
        with pytest.raises(ValidationError, match="command"):
            BackendConfig(backend_id="x", driver=DriverType.ACP)

    def test_agentapi_without_endpoint_raises(self) -> None:
        with pytest.raises(ValidationError, match="endpoint"):
            BackendConfig(backend_id="x", driver=DriverType.AGENT_API)

    def test_pty_without_command_raises(self) -> None:
        with pytest.raises(ValidationError, match="command"):
            BackendConfig(backend_id="x", driver=DriverType.PTY)

    def test_bearer_auth_without_token_env_raises(self) -> None:
        with pytest.raises(ValidationError, match="token_env"):
            BackendConfig(
                backend_id="x",
                driver=DriverType.AGENT_API,
                endpoint="http://localhost:8080",
                auth=AuthConfig(type="bearer"),
            )


class TestAuthConfig:
    def test_bearer(self) -> None:
        auth = AuthConfig(type="bearer", token_env="MY_TOKEN")
        assert auth.type == "bearer"

    def test_defaults(self) -> None:
        auth = AuthConfig(type="none")
        assert auth.token_env is None

    def test_bearer_requires_token_env(self) -> None:
        with pytest.raises(ValidationError, match="token_env"):
            AuthConfig(type="bearer")
