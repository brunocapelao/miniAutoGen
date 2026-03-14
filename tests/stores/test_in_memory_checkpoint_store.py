import pytest

from miniautogen.stores import InMemoryCheckpointStore


@pytest.mark.asyncio
async def test_in_memory_checkpoint_store_roundtrip() -> None:
    store = InMemoryCheckpointStore()

    await store.save_checkpoint("run-1", {"step": "llm"})

    assert await store.get_checkpoint("run-1") == {"step": "llm"}
