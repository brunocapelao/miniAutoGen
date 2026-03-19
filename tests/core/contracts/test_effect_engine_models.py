"""Tests for Phase 2 Effect Engine data models: EffectStatus, EffectDescriptor, EffectRecord."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

import pytest


class TestEffectStatus:
    def test_import(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus  # noqa: F401

    def test_is_str_enum(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus

        assert issubclass(EffectStatus, str)
        assert issubclass(EffectStatus, Enum)

    def test_has_pending(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus

        assert EffectStatus.PENDING == "pending"

    def test_has_completed(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus

        assert EffectStatus.COMPLETED == "completed"

    def test_has_failed(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus

        assert EffectStatus.FAILED == "failed"

    def test_exactly_three_members(self) -> None:
        from miniautogen.core.contracts.effect import EffectStatus

        assert {m.name for m in EffectStatus} == {"PENDING", "COMPLETED", "FAILED"}


class TestEffectDescriptor:
    def test_import(self) -> None:
        from miniautogen.core.contracts.effect import EffectDescriptor  # noqa: F401

    def test_create_with_required_fields(self) -> None:
        from miniautogen.core.contracts.effect import EffectDescriptor

        desc = EffectDescriptor(
            effect_type="tool_call",
            tool_name="send_email",
            args_hash="abc123",
            run_id="run-1",
            step_id="step-1",
        )
        assert desc.effect_type == "tool_call"
        assert desc.tool_name == "send_email"
        assert desc.args_hash == "abc123"
        assert desc.run_id == "run-1"
        assert desc.step_id == "step-1"

    def test_metadata_defaults_to_empty_tuple(self) -> None:
        from miniautogen.core.contracts.effect import EffectDescriptor

        desc = EffectDescriptor(
            effect_type="tool_call",
            tool_name="charge_card",
            args_hash="def456",
            run_id="run-1",
            step_id="step-2",
        )
        assert desc.metadata == ()

    def test_metadata_accepts_tuple_of_tuples(self) -> None:
        from miniautogen.core.contracts.effect import EffectDescriptor

        desc = EffectDescriptor(
            effect_type="api_request",
            tool_name="create_user",
            args_hash="ghi789",
            run_id="run-2",
            step_id="step-1",
            metadata=(("source", "cli"), ("priority", 1)),
        )
        assert desc.metadata == (("source", "cli"), ("priority", 1))

    def test_frozen_rejects_mutation(self) -> None:
        from miniautogen.core.contracts.effect import EffectDescriptor

        desc = EffectDescriptor(
            effect_type="tool_call",
            tool_name="send_email",
            args_hash="abc123",
            run_id="run-1",
            step_id="step-1",
        )
        with pytest.raises(Exception):
            desc.tool_name = "other"  # type: ignore[misc]

    def test_inherits_base_model(self) -> None:
        from miniautogen.core.contracts.base import MiniAutoGenBaseModel
        from miniautogen.core.contracts.effect import EffectDescriptor

        assert issubclass(EffectDescriptor, MiniAutoGenBaseModel)

    def test_serialization_round_trip(self) -> None:
        from miniautogen.core.contracts.effect import EffectDescriptor

        desc = EffectDescriptor(
            effect_type="tool_call",
            tool_name="send_email",
            args_hash="abc123",
            run_id="run-1",
            step_id="step-1",
            metadata=(("key", "val"),),
        )
        json_str = desc.model_dump_json()
        restored = EffectDescriptor.model_validate_json(json_str)
        assert restored.tool_name == desc.tool_name
        assert restored.args_hash == desc.args_hash
        assert restored.run_id == desc.run_id


class TestEffectRecord:
    def test_import(self) -> None:
        from miniautogen.core.contracts.effect import EffectRecord  # noqa: F401

    def test_create_pending_record(self) -> None:
        from miniautogen.core.contracts.effect import (
            EffectDescriptor,
            EffectRecord,
            EffectStatus,
        )

        desc = EffectDescriptor(
            effect_type="tool_call",
            tool_name="send_email",
            args_hash="abc123",
            run_id="run-1",
            step_id="step-1",
        )
        now = datetime.now(timezone.utc)
        record = EffectRecord(
            idempotency_key="key-abc",
            descriptor=desc,
            status=EffectStatus.PENDING,
            created_at=now,
        )
        assert record.idempotency_key == "key-abc"
        assert record.descriptor.tool_name == "send_email"
        assert record.status == EffectStatus.PENDING
        assert record.created_at == now
        assert record.completed_at is None
        assert record.result_hash is None
        assert record.error_info is None

    def test_create_completed_record(self) -> None:
        from miniautogen.core.contracts.effect import (
            EffectDescriptor,
            EffectRecord,
            EffectStatus,
        )

        desc = EffectDescriptor(
            effect_type="tool_call",
            tool_name="charge_card",
            args_hash="def456",
            run_id="run-1",
            step_id="step-2",
        )
        now = datetime.now(timezone.utc)
        record = EffectRecord(
            idempotency_key="key-def",
            descriptor=desc,
            status=EffectStatus.COMPLETED,
            created_at=now,
            completed_at=now,
            result_hash="sha256-result",
        )
        assert record.status == EffectStatus.COMPLETED
        assert record.completed_at == now
        assert record.result_hash == "sha256-result"

    def test_create_failed_record(self) -> None:
        from miniautogen.core.contracts.effect import (
            EffectDescriptor,
            EffectRecord,
            EffectStatus,
        )

        desc = EffectDescriptor(
            effect_type="tool_call",
            tool_name="send_email",
            args_hash="abc123",
            run_id="run-1",
            step_id="step-1",
        )
        now = datetime.now(timezone.utc)
        record = EffectRecord(
            idempotency_key="key-ghi",
            descriptor=desc,
            status=EffectStatus.FAILED,
            created_at=now,
            error_info="TimeoutError: connection timed out",
        )
        assert record.status == EffectStatus.FAILED
        assert record.error_info == "TimeoutError: connection timed out"

    def test_frozen_rejects_mutation(self) -> None:
        from miniautogen.core.contracts.effect import (
            EffectDescriptor,
            EffectRecord,
            EffectStatus,
        )

        desc = EffectDescriptor(
            effect_type="tool_call",
            tool_name="send_email",
            args_hash="abc123",
            run_id="run-1",
            step_id="step-1",
        )
        record = EffectRecord(
            idempotency_key="key-abc",
            descriptor=desc,
            status=EffectStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        with pytest.raises(Exception):
            record.status = EffectStatus.COMPLETED  # type: ignore[misc]

    def test_inherits_base_model(self) -> None:
        from miniautogen.core.contracts.base import MiniAutoGenBaseModel
        from miniautogen.core.contracts.effect import EffectRecord

        assert issubclass(EffectRecord, MiniAutoGenBaseModel)

    def test_serialization_round_trip(self) -> None:
        from miniautogen.core.contracts.effect import (
            EffectDescriptor,
            EffectRecord,
            EffectStatus,
        )

        desc = EffectDescriptor(
            effect_type="tool_call",
            tool_name="send_email",
            args_hash="abc123",
            run_id="run-1",
            step_id="step-1",
        )
        now = datetime.now(timezone.utc)
        record = EffectRecord(
            idempotency_key="key-abc",
            descriptor=desc,
            status=EffectStatus.COMPLETED,
            created_at=now,
            completed_at=now,
            result_hash="sha256-result",
        )
        json_str = record.model_dump_json()
        restored = EffectRecord.model_validate_json(json_str)
        assert restored.idempotency_key == record.idempotency_key
        assert restored.status == EffectStatus.COMPLETED
        assert restored.descriptor.tool_name == "send_email"
