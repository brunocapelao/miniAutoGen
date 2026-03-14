import pytest

from miniautogen.stores import InMemoryRunStore


@pytest.mark.asyncio
async def test_in_memory_run_store_roundtrip() -> None:
    store = InMemoryRunStore()

    await store.save_run("run-1", {"status": "started"})

    assert await store.get_run("run-1") == {"status": "started"}
