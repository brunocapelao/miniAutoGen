import pytest

from miniautogen.stores import SQLAlchemyCheckpointStore, SQLAlchemyRunStore


@pytest.mark.asyncio
async def test_sqlalchemy_run_store_returns_none_for_missing_run(tmp_path) -> None:
    store = SQLAlchemyRunStore(db_url=f"sqlite+aiosqlite:///{tmp_path / 'runs-extra.db'}")
    await store.init_db()

    assert await store.get_run("missing") is None


@pytest.mark.asyncio
async def test_sqlalchemy_run_store_updates_existing_payload(tmp_path) -> None:
    store = SQLAlchemyRunStore(db_url=f"sqlite+aiosqlite:///{tmp_path / 'runs-update.db'}")
    await store.init_db()
    await store.save_run("run-1", {"status": "started"})
    await store.save_run("run-1", {"status": "finished"})

    assert await store.get_run("run-1") == {"status": "finished"}


@pytest.mark.asyncio
async def test_sqlalchemy_checkpoint_store_returns_none_for_missing_run(tmp_path) -> None:
    store = SQLAlchemyCheckpointStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'checkpoints-extra.db'}"
    )
    await store.init_db()

    assert await store.get_checkpoint("missing") is None


@pytest.mark.asyncio
async def test_sqlalchemy_checkpoint_store_updates_existing_payload(tmp_path) -> None:
    store = SQLAlchemyCheckpointStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'checkpoints-update.db'}"
    )
    await store.init_db()
    await store.save_checkpoint("run-1", {"step": "first"})
    await store.save_checkpoint("run-1", {"step": "second"})

    assert await store.get_checkpoint("run-1") == {"step": "second"}
