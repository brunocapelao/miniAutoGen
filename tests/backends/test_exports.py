"""Tests for backend package exports."""


class TestBackendsPackageExports:
    def test_import_from_backends(self) -> None:
        from miniautogen.backends import (  # noqa: F401
            AgentDriver,
            AgentEvent,
            ArtifactRef,
            BackendCapabilities,
            BackendConfig,
            BackendResolver,
            CancelTurnRequest,
            DriverType,
            SendTurnRequest,
            SessionManager,
            StartSessionRequest,
            StartSessionResponse,
        )

    def test_import_from_api(self) -> None:
        from miniautogen.api import (  # noqa: F401
            AgentDriver,
            BackendCapabilities,
            BackendResolver,
        )

    def test_import_engine_resolver(self) -> None:
        from miniautogen.backends import EngineResolver  # noqa: F401

    def test_import_base_driver(self) -> None:
        from miniautogen.backends import BaseDriver  # noqa: F401

    def test_import_message_transformer(self) -> None:
        from miniautogen.backends import MessageTransformer  # noqa: F401

    def test_errors_importable(self) -> None:
        from miniautogen.backends.errors import (  # noqa: F401
            AgentDriverError,
            ArtifactCollectionError,
            BackendUnavailableError,
            CancelNotSupportedError,
            EventMappingError,
            SessionStartError,
            TurnExecutionError,
        )
