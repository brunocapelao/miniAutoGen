"""Tests for ErrorCategory enum and effect exception classes (WS3 TG-0)."""

from __future__ import annotations


class TestErrorCategory:
    def test_import(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory  # noqa: F401

    def test_has_transient(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert ErrorCategory.TRANSIENT == "transient"

    def test_has_permanent(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert ErrorCategory.PERMANENT == "permanent"

    def test_has_validation(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert ErrorCategory.VALIDATION == "validation"

    def test_has_timeout(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert ErrorCategory.TIMEOUT == "timeout"

    def test_has_cancellation(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert ErrorCategory.CANCELLATION == "cancellation"

    def test_has_adapter(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert ErrorCategory.ADAPTER == "adapter"

    def test_has_configuration(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert ErrorCategory.CONFIGURATION == "configuration"

    def test_has_state_consistency(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert ErrorCategory.STATE_CONSISTENCY == "state_consistency"

    def test_is_str_enum(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        assert isinstance(ErrorCategory.TRANSIENT, str)

    def test_all_eight_members(self) -> None:
        from miniautogen.core.contracts.enums import ErrorCategory
        names = {m.name for m in ErrorCategory}
        assert names == {
            "TRANSIENT", "PERMANENT", "VALIDATION", "TIMEOUT",
            "CANCELLATION", "ADAPTER", "CONFIGURATION", "STATE_CONSISTENCY",
        }


class TestEffectExceptions:
    def test_effect_denied_error_import(self) -> None:
        from miniautogen.core.contracts.effect import EffectDeniedError  # noqa: F401

    def test_effect_duplicate_error_import(self) -> None:
        from miniautogen.core.contracts.effect import EffectDuplicateError  # noqa: F401

    def test_effect_journal_unavailable_error_import(self) -> None:
        from miniautogen.core.contracts.effect import EffectJournalUnavailableError  # noqa: F401

    def test_effect_denied_has_validation_category(self) -> None:
        from miniautogen.core.contracts.effect import EffectDeniedError
        assert EffectDeniedError.category == "validation"

    def test_effect_duplicate_has_state_consistency_category(self) -> None:
        from miniautogen.core.contracts.effect import EffectDuplicateError
        assert EffectDuplicateError.category == "state_consistency"

    def test_effect_journal_unavailable_has_adapter_category(self) -> None:
        from miniautogen.core.contracts.effect import EffectJournalUnavailableError
        assert EffectJournalUnavailableError.category == "adapter"

    def test_effect_denied_is_exception(self) -> None:
        from miniautogen.core.contracts.effect import EffectDeniedError
        err = EffectDeniedError("type not allowed")
        assert isinstance(err, Exception)

    def test_effect_denied_carries_message(self) -> None:
        from miniautogen.core.contracts.effect import EffectDeniedError
        err = EffectDeniedError("type not allowed")
        assert "type not allowed" in str(err)

    def test_effect_duplicate_carries_message(self) -> None:
        from miniautogen.core.contracts.effect import EffectDuplicateError
        err = EffectDuplicateError("key already completed")
        assert "key already completed" in str(err)
