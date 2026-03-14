import pytest

from miniautogen.core.runtime import PipelineRunner
from miniautogen.stores import InMemoryCheckpointStore, InMemoryRunStore


class DummyPipeline:
    async def run(self, state):
        return {"ok": True}


@pytest.mark.asyncio
async def test_runner_persists_run_lifecycle() -> None:
    run_store = InMemoryRunStore()
    checkpoint_store = InMemoryCheckpointStore()
    runner = PipelineRunner(run_store=run_store, checkpoint_store=checkpoint_store)

    result = await runner.run_pipeline(DummyPipeline(), {"ok": True})

    assert result == {"ok": True}
    stored_run = await run_store.get_run(runner.last_run_id or "")
    assert stored_run is not None
    assert stored_run["status"] == "finished"
    assert await checkpoint_store.get_checkpoint(runner.last_run_id or "") == {"ok": True}
