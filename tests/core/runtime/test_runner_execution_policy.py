import anyio
import pytest

from miniautogen.core.runtime import PipelineRunner
from miniautogen.policies import ExecutionPolicy


class SlowPipeline:
    async def run(self, state):
        await anyio.sleep(0.2)
        return state


@pytest.mark.asyncio
async def test_runner_applies_execution_policy_timeout() -> None:
    runner = PipelineRunner(execution_policy=ExecutionPolicy(timeout_seconds=0.01))

    with pytest.raises(TimeoutError):
        await runner.run_pipeline(SlowPipeline(), {})
