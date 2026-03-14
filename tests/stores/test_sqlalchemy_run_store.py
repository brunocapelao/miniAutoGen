import pytest

from miniautogen.stores import SQLAlchemyRunStore


@pytest.mark.asyncio
async def test_sqlalchemy_run_store_roundtrip(tmp_path) -> None:
    store = SQLAlchemyRunStore(db_url=f"sqlite+aiosqlite:///{tmp_path / 'runs.db'}")
    await store.init_db()
    await store.save_run("run-1", {"status": "finished"})

    assert await store.get_run("run-1") == {"status": "finished"}
