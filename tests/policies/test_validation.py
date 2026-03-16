import pytest

from miniautogen.policies.validation import (
    ValidationError,
    ValidationPolicy,
    Validator,
    validate_with_policy,
)
from typing import Any


class GoodValidator:
    def validate(self, data: Any) -> None:
        pass


class StrictValidator:
    def validate(self, data: Any) -> None:
        if not isinstance(data, str):
            raise ValidationError("Expected a string")


class TestValidationPolicyDisabled:
    def test_disabled_skips_validation(self):
        policy = ValidationPolicy(enabled=False)
        validator = StrictValidator()
        # Should not raise even with invalid data
        validate_with_policy(policy, validator, 12345)


class TestValidationPolicyEnabled:
    def test_enabled_runs_validator(self):
        policy = ValidationPolicy(enabled=True)
        validator = StrictValidator()
        with pytest.raises(ValidationError, match="Expected a string"):
            validate_with_policy(policy, validator, 12345)

    def test_enabled_passes_on_valid_data(self):
        policy = ValidationPolicy(enabled=True)
        validator = StrictValidator()
        validate_with_policy(policy, validator, "hello")


class TestValidatorProtocol:
    def test_isinstance_check(self):
        assert isinstance(GoodValidator(), Validator)
        assert isinstance(StrictValidator(), Validator)

    def test_non_validator_fails_isinstance(self):
        assert not isinstance("not a validator", Validator)
