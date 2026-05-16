"""Tests for backend driver error hierarchy."""

from miniautogen.backends.errors import (
    AgentDriverError,
    ArtifactCollectionError,
    BackendConfigurationError,
    BackendError,
    BackendUnavailableError,
    CancelNotSupportedError,
    EventMappingError,
    SessionStartError,
    TurnExecutionError,
)


class TestErrorHierarchy:
    def test_all_inherit_from_agent_driver_error(self) -> None:
        for cls in (
            BackendUnavailableError,
            BackendError,
            BackendConfigurationError,
            SessionStartError,
            TurnExecutionError,
            EventMappingError,
            CancelNotSupportedError,
            ArtifactCollectionError,
        ):
            err = cls("test")
            assert isinstance(err, AgentDriverError)
            assert isinstance(err, Exception)

    def test_agent_driver_error_message(self) -> None:
        err = AgentDriverError("something broke")
        assert str(err) == "something broke"

    def test_backend_unavailable_with_backend_id(self) -> None:
        err = BackendUnavailableError("claude_code")
        assert "claude_code" in str(err)

    def test_cancel_not_supported(self) -> None:
        err = CancelNotSupportedError("pty driver")
        assert "pty driver" in str(err)

    def test_backend_configuration_inheritance(self) -> None:
        err = BackendConfigurationError("missing api_key")
        assert isinstance(err, BackendError)
        assert isinstance(err, AgentDriverError)

    def test_backend_error_inheritance(self) -> None:
        err = BackendError("generic backend error")
        assert isinstance(err, AgentDriverError)
        assert "generic backend error" in str(err)
