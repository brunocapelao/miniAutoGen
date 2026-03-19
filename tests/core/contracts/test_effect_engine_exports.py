"""Tests for Phase 2 public API exports from contracts package."""

from __future__ import annotations


class TestEffectEngineExports:
    def test_effect_status_importable_from_contracts(self) -> None:
        from miniautogen.core.contracts import EffectStatus  # noqa: F401

    def test_effect_descriptor_importable_from_contracts(self) -> None:
        from miniautogen.core.contracts import EffectDescriptor  # noqa: F401

    def test_effect_record_importable_from_contracts(self) -> None:
        from miniautogen.core.contracts import EffectRecord  # noqa: F401

    def test_effect_status_in_all(self) -> None:
        import miniautogen.core.contracts as contracts

        assert "EffectStatus" in contracts.__all__

    def test_effect_descriptor_in_all(self) -> None:
        import miniautogen.core.contracts as contracts

        assert "EffectDescriptor" in contracts.__all__

    def test_effect_record_in_all(self) -> None:
        import miniautogen.core.contracts as contracts

        assert "EffectRecord" in contracts.__all__
