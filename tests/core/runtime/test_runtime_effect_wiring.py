"""Tests for EffectInterceptor wiring into coordination runtimes.

Verifies that all 3 runtimes (Workflow, Deliberation, AgenticLoop) correctly
create an EffectInterceptor when an EffectPolicy is provided, and leave it
as None when no policy is given.
"""

from __future__ import annotations

from miniautogen.core.effect_interceptor import EffectInterceptor
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.core.runtime.agentic_loop_runtime import AgenticLoopRuntime
from miniautogen.core.runtime.deliberation_runtime import DeliberationRuntime
from miniautogen.core.runtime.pipeline_runner import PipelineRunner
from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime
from miniautogen.policies.effect import EffectPolicy


def _make_runner() -> PipelineRunner:
    """Create a minimal PipelineRunner with an InMemoryEventSink."""
    sink = InMemoryEventSink()
    return PipelineRunner(event_sink=sink)


# ---- No interceptor when no policy ----


class TestNoPolicy:
    """All runtimes should have _effect_interceptor=None without a policy."""

    def test_workflow_no_interceptor(self) -> None:
        runner = _make_runner()
        rt = WorkflowRuntime(runner=runner)
        assert rt._effect_interceptor is None

    def test_deliberation_no_interceptor(self) -> None:
        runner = _make_runner()
        rt = DeliberationRuntime(runner=runner)
        assert rt._effect_interceptor is None

    def test_agentic_loop_no_interceptor(self) -> None:
        runner = _make_runner()
        rt = AgenticLoopRuntime(runner=runner)
        assert rt._effect_interceptor is None


# ---- Interceptor created when policy provided ----


class TestWithPolicy:
    """All runtimes should create an EffectInterceptor when a policy is given."""

    def test_workflow_creates_interceptor(self) -> None:
        runner = _make_runner()
        policy = EffectPolicy()
        rt = WorkflowRuntime(runner=runner, effect_policy=policy)
        assert rt._effect_interceptor is not None
        assert isinstance(rt._effect_interceptor, EffectInterceptor)

    def test_deliberation_creates_interceptor(self) -> None:
        runner = _make_runner()
        policy = EffectPolicy()
        rt = DeliberationRuntime(runner=runner, effect_policy=policy)
        assert rt._effect_interceptor is not None
        assert isinstance(rt._effect_interceptor, EffectInterceptor)

    def test_agentic_loop_creates_interceptor(self) -> None:
        runner = _make_runner()
        policy = EffectPolicy()
        rt = AgenticLoopRuntime(runner=runner, effect_policy=policy)
        assert rt._effect_interceptor is not None
        assert isinstance(rt._effect_interceptor, EffectInterceptor)


# ---- Policy settings propagated to interceptor ----


class TestPolicyPropagation:
    """Verify that policy settings are propagated to the interceptor."""

    def test_custom_policy_propagated_workflow(self) -> None:
        runner = _make_runner()
        policy = EffectPolicy(
            max_effects_per_step=5,
            allowed_effect_types=frozenset({"tool_call", "file_write"}),
            stale_pending_timeout_seconds=120.0,
        )
        rt = WorkflowRuntime(runner=runner, effect_policy=policy)
        interceptor = rt._effect_interceptor
        assert interceptor is not None
        assert interceptor._policy.max_effects_per_step == 5
        assert interceptor._policy.allowed_effect_types == frozenset(
            {"tool_call", "file_write"}
        )
        assert interceptor._policy.stale_pending_timeout_seconds == 120.0

    def test_custom_policy_propagated_deliberation(self) -> None:
        runner = _make_runner()
        policy = EffectPolicy(max_effects_per_step=3)
        rt = DeliberationRuntime(runner=runner, effect_policy=policy)
        interceptor = rt._effect_interceptor
        assert interceptor is not None
        assert interceptor._policy.max_effects_per_step == 3

    def test_custom_policy_propagated_agentic_loop(self) -> None:
        runner = _make_runner()
        policy = EffectPolicy(max_effects_per_step=7)
        rt = AgenticLoopRuntime(runner=runner, effect_policy=policy)
        interceptor = rt._effect_interceptor
        assert interceptor is not None
        assert interceptor._policy.max_effects_per_step == 7

    def test_event_sink_wired_from_runner(self) -> None:
        """The interceptor's event_sink should be the runner's event_sink."""
        sink = InMemoryEventSink()
        runner = PipelineRunner(event_sink=sink)
        policy = EffectPolicy()
        rt = WorkflowRuntime(runner=runner, effect_policy=policy)
        interceptor = rt._effect_interceptor
        assert interceptor is not None
        assert interceptor._event_sink is sink
