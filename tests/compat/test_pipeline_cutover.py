"""Tests for legacy pipeline cutover."""

import warnings

import pytest

from miniautogen.compat.state_bridge import RUNTIME_RUNNER_CUTOVER_READY


def test_cutover_flag_is_enabled() -> None:
    assert RUNTIME_RUNNER_CUTOVER_READY is True


@pytest.mark.anyio
async def test_pipeline_run_emits_deprecation_warning() -> None:
    from miniautogen.pipeline.pipeline import Pipeline

    class _NoOpComponent:
        async def process(self, state: dict) -> dict:
            return state

    pipeline = Pipeline(components=[_NoOpComponent()])
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        await pipeline.run({})
        deprecation_warnings = [
            x for x in w if issubclass(x.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) >= 1
        assert "deprecated" in str(deprecation_warnings[0].message).lower()
