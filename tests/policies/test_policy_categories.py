import dataclasses

from miniautogen.policies import (
    BudgetPolicy,
    ExecutionPolicy,
    PermissionPolicy,
    RetryPolicy,
    ValidationPolicy,
)


def test_execution_policy_exposes_timeout_configuration() -> None:
    policy = ExecutionPolicy(timeout_seconds=5)

    assert policy.timeout_seconds == 5


def test_execution_policy_is_immutable() -> None:
    policy = ExecutionPolicy(timeout_seconds=5)

    try:
        policy.timeout_seconds = 10
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError("ExecutionPolicy should be immutable")


def test_policy_categories_have_clear_default_shapes() -> None:
    assert RetryPolicy().max_attempts == 1
    assert ValidationPolicy().enabled is True
    assert BudgetPolicy().max_cost is None
    assert PermissionPolicy().allowed_actions == ()
