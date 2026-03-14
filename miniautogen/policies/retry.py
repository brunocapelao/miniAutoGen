from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    retry_exceptions: tuple[type[BaseException], ...] = (RuntimeError,)


def build_retrying_call(
    policy: RetryPolicy,
) -> Callable[[Callable[[], Awaitable[T]]], Awaitable[T]]:
    async def run(operation: Callable[[], Awaitable[T]]) -> T:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(policy.retry_exceptions),
            stop=stop_after_attempt(policy.max_attempts),
            reraise=True,
        ):
            with attempt:
                return await operation()
        raise RuntimeError("Retry policy exhausted without executing the operation.")

    return run
