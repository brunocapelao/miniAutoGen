import pytest

from miniautogen.app.settings import MiniAutoGenSettings
from miniautogen.stores import SQLAlchemyCheckpointStore, SQLAlchemyRunStore


@pytest.mark.asyncio
async def test_startup_smoke_builds_settings_and_initializes_persistent_stores(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'startup.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    settings = MiniAutoGenSettings()
    run_store = SQLAlchemyRunStore(db_url=settings.database_url)
    checkpoint_store = SQLAlchemyCheckpointStore(db_url=settings.database_url)

    await run_store.init_db()
    await checkpoint_store.init_db()

    await run_store.save_run("run-1", {"status": "started"})
    await checkpoint_store.save_checkpoint("run-1", {"step": "boot"})

    assert await run_store.get_run("run-1") == {"status": "started"}
    assert await checkpoint_store.get_checkpoint("run-1") == {"step": "boot"}
