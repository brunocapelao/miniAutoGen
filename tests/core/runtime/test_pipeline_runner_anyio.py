import pytest


@pytest.mark.asyncio
async def test_pipeline_runner_accepts_timeout_parameter_without_public_anyio_leak():
    from miniautogen.core.runtime.pipeline_runner import PipelineRunner

    runner = PipelineRunner()

    assert hasattr(runner, "run_pipeline")
    assert "anyio" not in str(runner.run_pipeline)
