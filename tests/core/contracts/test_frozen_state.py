"""Tests for FrozenState immutable state container."""

from typing import Any

import pytest
from pydantic import ValidationError

from miniautogen.core.contracts.run_context import FrozenState


class TestFrozenStateConstruction:
    def test_empty_construction(self) -> None:
        fs = FrozenState()
        assert fs.to_dict() == {}

    def test_keyword_construction(self) -> None:
        fs = FrozenState(step=1, agent="writer")
        assert fs.to_dict() == {"step": 1, "agent": "writer"}

    def test_data_is_sorted(self) -> None:
        fs = FrozenState(z=1, a=2)
        assert fs._data == (("a", 2), ("z", 1))


class TestFrozenStateGet:
    def test_get_existing_key(self) -> None:
        fs = FrozenState(name="alice")
        assert fs.get("name") == "alice"

    def test_get_missing_key_returns_default(self) -> None:
        fs = FrozenState()
        assert fs.get("missing") is None

    def test_get_missing_key_custom_default(self) -> None:
        fs = FrozenState()
        assert fs.get("missing", 42) == 42


class TestFrozenStateEvolve:
    def test_evolve_adds_new_key(self) -> None:
        fs = FrozenState(a=1)
        fs2 = fs.evolve(b=2)
        assert fs2.to_dict() == {"a": 1, "b": 2}

    def test_evolve_overrides_existing_key(self) -> None:
        fs = FrozenState(a=1)
        fs2 = fs.evolve(a=99)
        assert fs2.get("a") == 99

    def test_evolve_does_not_mutate_original(self) -> None:
        fs = FrozenState(a=1)
        fs.evolve(a=99)
        assert fs.get("a") == 1


class TestFrozenStateImmutability:
    def test_frozen_rejects_attribute_assignment(self) -> None:
        fs = FrozenState(a=1)
        # Private attributes on frozen Pydantic models silently ignore writes,
        # preserving the original value. Verify the data cannot be changed.
        fs._data = (("a", 2),)  # type: ignore[misc]
        assert fs._data == (("a", 1),)  # original unchanged


class TestFrozenStateSerialization:
    def test_model_dump_returns_dict(self) -> None:
        fs = FrozenState(step=1, agent="writer")
        dumped = fs.model_dump()
        assert dumped == {"agent": "writer", "step": 1}

    def test_round_trip(self) -> None:
        fs = FrozenState(step=1, agent="writer")
        dumped = fs.model_dump()
        restored = FrozenState(**dumped)
        assert restored == fs

    def test_empty_round_trip(self) -> None:
        fs = FrozenState()
        dumped = fs.model_dump()
        restored = FrozenState(**dumped)
        assert restored == fs
