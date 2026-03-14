import pytest

from miniautogen.stores import SQLAlchemyCheckpointStore


@pytest.mark.asyncio
async def test_sqlalchemy_checkpoint_store_roundtrip(tmp_path) -> None:
    store = SQLAlchemyCheckpointStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'checkpoints.db'}"
    )
    await store.init_db()
    await store.save_checkpoint("run-1", {"step": "checkpoint"})

    assert await store.get_checkpoint("run-1") == {"step": "checkpoint"}
