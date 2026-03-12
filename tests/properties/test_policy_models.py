from hypothesis import given
from hypothesis import strategies as st

from miniautogen.policies import ExecutionPolicy, RetryPolicy


@given(st.integers(min_value=1, max_value=5))
def test_retry_policy_preserves_positive_attempt_counts(max_attempts: int) -> None:
    policy = RetryPolicy(max_attempts=max_attempts)

    assert policy.max_attempts == max_attempts


@given(st.one_of(st.none(), st.floats(min_value=0.1, max_value=30)))
def test_execution_policy_preserves_timeout(timeout_seconds: float | None) -> None:
    policy = ExecutionPolicy(timeout_seconds=timeout_seconds)

    assert policy.timeout_seconds == timeout_seconds
