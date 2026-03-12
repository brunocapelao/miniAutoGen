import pytest

from miniautogen.pipeline.components.pipelinecomponent import PipelineComponent
from miniautogen.pipeline.pipeline import Pipeline


class MarkerComponent(PipelineComponent):
    async def process(self, state):
        state["visited"] = True
        return state


@pytest.mark.asyncio
async def test_pipeline_runner_executes_existing_pipeline_components_in_order():
    from miniautogen.core.runtime.pipeline_runner import PipelineRunner

    runner = PipelineRunner()
    pipeline = Pipeline([MarkerComponent()])

    result = await runner.run_pipeline(pipeline, {"visited": False})
    assert result["visited"] is True
