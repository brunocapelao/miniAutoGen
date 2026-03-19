"""Tests for effect journal exports from stores package."""

from __future__ import annotations


class TestEffectJournalExports:
    def test_effect_journal_importable_from_stores(self) -> None:
        from miniautogen.stores import EffectJournal  # noqa: F401

    def test_in_memory_effect_journal_importable_from_stores(self) -> None:
        from miniautogen.stores import InMemoryEffectJournal  # noqa: F401

    def test_effect_journal_in_all(self) -> None:
        import miniautogen.stores as stores

        assert "EffectJournal" in stores.__all__

    def test_in_memory_effect_journal_in_all(self) -> None:
        import miniautogen.stores as stores

        assert "InMemoryEffectJournal" in stores.__all__
