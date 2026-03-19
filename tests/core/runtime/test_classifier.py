"""Tests for classify_error() function and extensible registry."""

from __future__ import annotations

import asyncio

from miniautogen.backends.errors import (
    AgentDriverError,
    BackendUnavailableError,
    SessionStartError,
    TurnExecutionError,
)
from miniautogen.core.contracts.effect import (
    EffectDeniedError,
    EffectDuplicateError,
    EffectJournalUnavailableError,
)
from miniautogen.core.contracts.enums import ErrorCategory
from miniautogen.core.runtime.classifier import classify_error, register_error_mapping
from miniautogen.policies.budget import BudgetExceededError
from miniautogen.policies.permission import PermissionDeniedError


class TestClassifyErrorDefaults:
    """Test default mapping rules."""

    def test_timeout_error(self) -> None:
        assert classify_error(TimeoutError("timed out")) == ErrorCategory.TIMEOUT

    def test_cancellation_via_anyio(self) -> None:
        # anyio.get_cancelled_exc_class() requires a running event loop,
        # so we use asyncio.CancelledError directly (what anyio returns on asyncio backend).
        assert classify_error(asyncio.CancelledError()) == ErrorCategory.CANCELLATION

    def test_cancellation_via_asyncio(self) -> None:
        assert classify_error(asyncio.CancelledError()) == ErrorCategory.CANCELLATION

    def test_permission_error_is_permanent_not_transient(self) -> None:
        """PermissionError is subclass of OSError but must be PERMANENT, not TRANSIENT."""
        assert classify_error(PermissionError("denied")) == ErrorCategory.PERMANENT

    def test_value_error(self) -> None:
        assert classify_error(ValueError("bad input")) == ErrorCategory.VALIDATION

    def test_type_error(self) -> None:
        assert classify_error(TypeError("wrong type")) == ErrorCategory.VALIDATION

    def test_permission_denied_error(self) -> None:
        assert classify_error(PermissionDeniedError("not allowed")) == ErrorCategory.VALIDATION

    def test_budget_exceeded_error(self) -> None:
        assert classify_error(BudgetExceededError("over limit")) == ErrorCategory.VALIDATION

    def test_backend_unavailable_error(self) -> None:
        assert classify_error(BackendUnavailableError("down")) == ErrorCategory.ADAPTER

    def test_agent_driver_error_subclass(self) -> None:
        assert classify_error(SessionStartError("failed")) == ErrorCategory.ADAPTER

    def test_agent_driver_error_base(self) -> None:
        assert classify_error(AgentDriverError("generic")) == ErrorCategory.ADAPTER

    def test_turn_execution_error(self) -> None:
        assert classify_error(TurnExecutionError("turn failed")) == ErrorCategory.ADAPTER

    def test_connection_error(self) -> None:
        assert classify_error(ConnectionError("reset")) == ErrorCategory.TRANSIENT

    def test_os_error(self) -> None:
        assert classify_error(OSError("io failed")) == ErrorCategory.TRANSIENT

    def test_key_error_is_permanent(self) -> None:
        assert classify_error(KeyError("missing")) == ErrorCategory.PERMANENT

    def test_attribute_error_is_permanent(self) -> None:
        assert classify_error(AttributeError("no attr")) == ErrorCategory.PERMANENT

    def test_not_implemented_error_is_permanent(self) -> None:
        assert classify_error(NotImplementedError("todo")) == ErrorCategory.PERMANENT

    def test_unknown_exception_defaults_to_permanent(self) -> None:
        class CustomError(Exception):
            pass
        assert classify_error(CustomError("unknown")) == ErrorCategory.PERMANENT


class TestClassifyErrorSelfClassifying:
    """Test that EffectError subclasses self-classify via .category."""

    def test_effect_denied(self) -> None:
        assert classify_error(EffectDeniedError("denied")) == ErrorCategory.VALIDATION

    def test_effect_duplicate(self) -> None:
        assert classify_error(EffectDuplicateError("dup")) == ErrorCategory.STATE_CONSISTENCY

    def test_effect_journal_unavailable(self) -> None:
        assert classify_error(EffectJournalUnavailableError("down")) == ErrorCategory.ADAPTER


class TestRegisterErrorMapping:
    """Test user-extensible error mapping registry."""

    def test_custom_mapping_takes_priority(self) -> None:
        class MyLibraryError(Exception):
            pass

        register_error_mapping(MyLibraryError, ErrorCategory.TRANSIENT)
        assert classify_error(MyLibraryError("retry me")) == ErrorCategory.TRANSIENT

    def test_custom_mapping_overrides_default(self) -> None:
        """Custom mapping can override default classification."""

        class SpecialOSError(OSError):
            pass

        # By default, OSError -> TRANSIENT. But we can override for a subclass.
        register_error_mapping(SpecialOSError, ErrorCategory.PERMANENT)
        assert classify_error(SpecialOSError("permanent")) == ErrorCategory.PERMANENT

    def test_custom_mapping_checked_before_defaults(self) -> None:
        class AnotherCustomError(Exception):
            pass

        register_error_mapping(AnotherCustomError, ErrorCategory.CONFIGURATION)
        assert classify_error(AnotherCustomError("config issue")) == ErrorCategory.CONFIGURATION
