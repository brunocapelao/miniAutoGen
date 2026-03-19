"""Tests for EffectJournal ABC contract."""

from __future__ import annotations

from abc import ABC

import pytest


class TestEffectJournalABC:
    def test_import(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal  # noqa: F401

    def test_is_abstract(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal

        assert issubclass(EffectJournal, ABC)

    def test_cannot_instantiate(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal

        with pytest.raises(TypeError, match="abstract"):
            EffectJournal()  # type: ignore[abstract]

    def test_has_register_method(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal

        assert hasattr(EffectJournal, "register")

    def test_has_get_method(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal

        assert hasattr(EffectJournal, "get")

    def test_has_update_status_method(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal

        assert hasattr(EffectJournal, "update_status")

    def test_has_list_by_run_method(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal

        assert hasattr(EffectJournal, "list_by_run")

    def test_has_delete_by_run_method(self) -> None:
        from miniautogen.stores.effect_journal import EffectJournal

        assert hasattr(EffectJournal, "delete_by_run")
