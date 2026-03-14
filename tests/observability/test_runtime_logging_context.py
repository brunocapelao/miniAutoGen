import pytest
from structlog.testing import capture_logs

from miniautogen.core.runtime import PipelineRunner


class DummyPipeline:
    async def run(self, state):
        return {"ok": True}


@pytest.mark.asyncio
async def test_runner_logs_with_run_and_correlation_context() -> None:
    runner = PipelineRunner()

    with capture_logs() as logs:
        result = await runner.run_pipeline(DummyPipeline(), {"ok": True})

    assert result == {"ok": True}
    assert [entry["event"] for entry in logs] == ["run_started", "run_finished"]
    assert logs[0]["run_id"] == logs[1]["run_id"]
    assert logs[0]["correlation_id"] == logs[1]["correlation_id"]
    assert logs[0]["scope"] == "pipeline_runner"
