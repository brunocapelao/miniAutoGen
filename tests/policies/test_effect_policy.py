"""Tests for EffectPolicy frozen model."""

from __future__ import annotations

import pytest


class TestEffectPolicy:
    def test_import(self) -> None:
        from miniautogen.policies.effect import EffectPolicy  # noqa: F401

    def test_default_max_effects_per_step(self) -> None:
        from miniautogen.policies.effect import EffectPolicy

        policy = EffectPolicy()
        assert policy.max_effects_per_step == 10

    def test_default_allowed_effect_types_is_none(self) -> None:
        from miniautogen.policies.effect import EffectPolicy

        policy = EffectPolicy()
        assert policy.allowed_effect_types is None

    def test_default_require_idempotency(self) -> None:
        from miniautogen.policies.effect import EffectPolicy

        policy = EffectPolicy()
        assert policy.require_idempotency is True

    def test_default_stale_pending_timeout_seconds(self) -> None:
        from miniautogen.policies.effect import EffectPolicy

        policy = EffectPolicy()
        assert policy.stale_pending_timeout_seconds == 3600.0

    def test_custom_values(self) -> None:
        from miniautogen.policies.effect import EffectPolicy

        policy = EffectPolicy(
            max_effects_per_step=5,
            allowed_effect_types=frozenset({"tool_call", "api_request"}),
            require_idempotency=False,
            stale_pending_timeout_seconds=1800.0,
        )
        assert policy.max_effects_per_step == 5
        assert policy.allowed_effect_types == frozenset({"tool_call", "api_request"})
        assert policy.require_idempotency is False
        assert policy.stale_pending_timeout_seconds == 1800.0

    def test_frozen_rejects_mutation(self) -> None:
        from miniautogen.policies.effect import EffectPolicy

        policy = EffectPolicy()
        with pytest.raises(Exception):
            policy.max_effects_per_step = 20  # type: ignore[misc]

    def test_allowed_effect_types_frozenset(self) -> None:
        from miniautogen.policies.effect import EffectPolicy

        policy = EffectPolicy(
            allowed_effect_types=frozenset({"tool_call"}),
        )
        assert isinstance(policy.allowed_effect_types, frozenset)

    def test_serialization_round_trip(self) -> None:
        from miniautogen.policies.effect import EffectPolicy

        policy = EffectPolicy(
            max_effects_per_step=3,
            allowed_effect_types=frozenset({"tool_call"}),
            stale_pending_timeout_seconds=900.0,
        )
        data = policy.model_dump()
        restored = EffectPolicy.model_validate(data)
        assert restored.max_effects_per_step == 3
        assert restored.stale_pending_timeout_seconds == 900.0
