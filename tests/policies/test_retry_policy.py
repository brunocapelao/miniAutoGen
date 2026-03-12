import pytest

from miniautogen.policies.retry import RetryPolicy, build_retrying_call


@pytest.mark.asyncio
async def test_retry_policy_wrapper_returns_operation_result_without_retries() -> None:
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    wrapped = build_retrying_call(RetryPolicy(max_attempts=1))
    result = await wrapped(operation)

    assert result == "ok"
    assert calls == 1
