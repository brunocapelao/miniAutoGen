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
        # FrozenState.__setattr__ raises AttributeError on any write attempt,
        # enforcing true immutability (WS2-C2).
        with pytest.raises(AttributeError, match="immutable"):
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


class TestFrozenStateEquality:
    """Tests for __eq__ and __hash__ correctness (WS2-C1)."""

    def test_equal_instances_compare_equal(self) -> None:
        fs1 = FrozenState(a=1, b=2)
        fs2 = FrozenState(a=1, b=2)
        assert fs1 == fs2

    def test_different_instances_not_equal(self) -> None:
        fs1 = FrozenState(a=1)
        fs2 = FrozenState(a=2)
        assert fs1 != fs2

    def test_equal_instances_have_same_hash(self) -> None:
        fs1 = FrozenState(x=10, y="hello")
        fs2 = FrozenState(x=10, y="hello")
        assert hash(fs1) == hash(fs2)

    def test_empty_instances_are_equal(self) -> None:
        assert FrozenState() == FrozenState()

    def test_hash_is_not_zero_for_nonempty(self) -> None:
        fs = FrozenState(a=1)
        # hash should not be 0 (the broken sentinel value)
        assert hash(fs) != 0

    def test_can_be_used_in_set(self) -> None:
        fs1 = FrozenState(a=1)
        fs2 = FrozenState(a=1)
        fs3 = FrozenState(a=2)
        s = {fs1, fs2, fs3}
        assert len(s) == 2

    def test_not_equal_to_non_frozen_state(self) -> None:
        fs = FrozenState(a=1)
        assert fs != {"a": 1}
        assert fs != (("a", 1),)


class TestFrozenStateMutableValueIsolation:
    """Tests for deep-copy isolation of mutable values (WS2-C3)."""

    def test_mutable_list_is_isolated(self) -> None:
        original_list: list[int] = [1, 2, 3]
        fs = FrozenState(items=original_list)
        original_list.append(4)
        assert fs.get("items") == [1, 2, 3]

    def test_mutable_dict_is_isolated(self) -> None:
        original_dict: dict[str, int] = {"x": 1}
        fs = FrozenState(data=original_dict)
        original_dict["y"] = 2
        assert fs.get("data") == {"x": 1}

    def test_evolve_isolates_new_values_from_original_inputs(self) -> None:
        # When evolving with a new list, mutations to that list after the call
        # must not affect the evolved FrozenState.
        new_items: list[int] = [1, 2, 3]
        fs1 = FrozenState(items=[1, 2])
        fs2 = fs1.evolve(items=new_items)
        new_items.append(99)  # mutate the original input after evolve
        assert fs2.get("items") == [1, 2, 3]  # fs2 must be isolated
        assert fs1.get("items") == [1, 2]  # fs1 unaffected


class TestFrozenStateReservedKey:
    """Tests for reserved _data key guard (WS2-M3)."""

    def test_reserved_key_raises(self) -> None:
        with pytest.raises(ValueError, match="_data"):
            FrozenState(_data=(("a", 1),))


class TestFrozenStateDelattr:
    """Tests for __delattr__ immutability (WS2-C2)."""

    def test_delattr_raises(self) -> None:
        fs = FrozenState(a=1)
        with pytest.raises(AttributeError, match="immutable"):
            del fs._data  # type: ignore[misc]
