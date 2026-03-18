"""Store round-trip fidelity tests using DeepDiff.

Verifies that save -> load produces structurally identical data
for both CheckpointStore and RunStore implementations.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from deepdiff import DeepDiff

from miniautogen.stores.sqlalchemy_checkpoint_store import SQLAlchemyCheckpointStore
from miniautogen.stores.sqlalchemy_run_store import SQLAlchemyRunStore


@pytest.mark.asyncio
async def test_checkpoint_round_trip_zero_diff(tmp_path: Path) -> None:
    """Save then load a checkpoint and assert zero structural diff."""
    store = SQLAlchemyCheckpointStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'ckpt.db'}"
    )
    await store.init_db()

    original = {
        "run_id": "abc",
        "state": {"step": 3, "data": [1, 2, 3]},
        "config": {"nested": {"deep": True}},
    }

    await store.save_checkpoint("run-rt-1", original)
    restored = await store.get_checkpoint("run-rt-1")

    diff = DeepDiff(original, restored)
    assert diff == {}, f"Checkpoint round-trip fidelity violation: {diff}"


@pytest.mark.asyncio
async def test_run_store_round_trip_zero_diff(tmp_path: Path) -> None:
    """Save then load a run and assert zero structural diff."""
    store = SQLAlchemyRunStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'runs.db'}"
    )
    await store.init_db()

    original = {
        "run_id": "run-42",
        "status": "completed",
        "result": {"output": "hello", "tokens": [10, 20, 30]},
        "metadata": {"source": "test", "nested": {"key": "value"}},
    }

    await store.save_run("run-42", original)
    restored = await store.get_run("run-42")

    diff = DeepDiff(original, restored)
    assert diff == {}, f"Run store round-trip fidelity violation: {diff}"


@pytest.mark.asyncio
async def test_checkpoint_round_trip_with_special_types(tmp_path: Path) -> None:
    """Round-trip with types that commonly cause fidelity issues."""
    store = SQLAlchemyCheckpointStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'ckpt2.db'}"
    )
    await store.init_db()

    original = {
        "float_val": 3.14159,
        "bool_val": True,
        "null_val": None,
        "empty_list": [],
        "empty_dict": {},
        "nested_list": [[1, 2], [3, 4]],
    }

    await store.save_checkpoint("run-special", original)
    restored = await store.get_checkpoint("run-special")

    diff = DeepDiff(original, restored)
    assert diff == {}, f"Special types round-trip violation: {diff}"
