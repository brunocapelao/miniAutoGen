"""Tests for RunContext v1->v2 migration utility."""

from miniautogen.compat.migration import migrate_run_context_v1_to_v2


def test_migrate_execution_state_to_state() -> None:
    v1 = {
        "run_id": "r1",
        "started_at": "2026-01-01T00:00:00",
        "correlation_id": "c1",
        "execution_state": {"step": 1, "agent": "writer"},
        "metadata": {"source": "cli"},
    }
    v2 = migrate_run_context_v1_to_v2(v1)
    assert "execution_state" not in v2
    assert v2["state"] == {"step": 1, "agent": "writer"}
    assert v2["metadata"] == [("source", "cli")]


def test_migrate_already_v2_is_noop() -> None:
    v2 = {
        "run_id": "r1",
        "started_at": "2026-01-01T00:00:00",
        "correlation_id": "c1",
        "state": {"step": 1},
        "metadata": [("source", "cli")],
    }
    result = migrate_run_context_v1_to_v2(v2)
    assert result["state"] == {"step": 1}
    assert result["metadata"] == [("source", "cli")]


def test_migrate_metadata_dict_to_sorted_pairs() -> None:
    v1 = {
        "run_id": "r1",
        "started_at": "2026-01-01T00:00:00",
        "correlation_id": "c1",
        "metadata": {"z_key": "last", "a_key": "first"},
    }
    v2 = migrate_run_context_v1_to_v2(v1)
    assert v2["metadata"] == [("a_key", "first"), ("z_key", "last")]


def test_migrate_preserves_other_fields() -> None:
    v1 = {
        "run_id": "r1",
        "started_at": "2026-01-01T00:00:00",
        "correlation_id": "c1",
        "execution_state": {"k": "v"},
        "input_payload": {"text": "hello"},
        "timeout_seconds": 30,
    }
    v2 = migrate_run_context_v1_to_v2(v1)
    assert v2["input_payload"] == {"text": "hello"}
    assert v2["timeout_seconds"] == 30


def test_migrate_does_not_mutate_input() -> None:
    v1 = {
        "run_id": "r1",
        "started_at": "2026-01-01T00:00:00",
        "correlation_id": "c1",
        "execution_state": {"k": "v"},
    }
    original_keys = set(v1.keys())
    migrate_run_context_v1_to_v2(v1)
    assert set(v1.keys()) == original_keys


def test_migrated_data_deserializes_to_run_context() -> None:
    from miniautogen.core.contracts.run_context import RunContext

    v1 = {
        "run_id": "r1",
        "started_at": "2026-01-01T00:00:00",
        "correlation_id": "c1",
        "execution_state": {"step": 1},
        "metadata": {"source": "cli"},
    }
    v2 = migrate_run_context_v1_to_v2(v1)
    ctx = RunContext.model_validate(v2)
    assert ctx.state.get("step") == 1
    assert ctx.get_metadata("source") == "cli"
