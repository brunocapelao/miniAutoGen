"""Tests for miniautogen.api public surface completeness."""

from __future__ import annotations


class TestApiExportsCompleteness:
    """Verify all expected types are importable from miniautogen.api."""

    # -- Policy chain types --

    def test_export_policy_chain(self) -> None:
        from miniautogen.api import PolicyChain
        assert PolicyChain is not None

    def test_export_policy_context(self) -> None:
        from miniautogen.api import PolicyContext
        assert PolicyContext is not None

    def test_export_policy_result(self) -> None:
        from miniautogen.api import PolicyResult
        assert PolicyResult is not None

    def test_export_policy_evaluator(self) -> None:
        from miniautogen.api import PolicyEvaluator
        assert PolicyEvaluator is not None

    def test_export_retry_policy(self) -> None:
        from miniautogen.api import RetryPolicy
        assert RetryPolicy is not None

    # -- Effect types --

    def test_export_effect_interceptor(self) -> None:
        from miniautogen.api import EffectInterceptor
        assert EffectInterceptor is not None

    def test_export_effect_policy(self) -> None:
        from miniautogen.api import EffectPolicy
        assert EffectPolicy is not None

    def test_export_effect_journal(self) -> None:
        from miniautogen.api import EffectJournal
        assert EffectJournal is not None

    def test_export_in_memory_effect_journal(self) -> None:
        from miniautogen.api import InMemoryEffectJournal
        assert InMemoryEffectJournal is not None

    # -- Store types --

    def test_export_checkpoint_store(self) -> None:
        from miniautogen.api import CheckpointStore
        assert CheckpointStore is not None

    def test_export_in_memory_checkpoint_store(self) -> None:
        from miniautogen.api import InMemoryCheckpointStore
        assert InMemoryCheckpointStore is not None

    # -- Approval types --

    def test_export_approval_gate(self) -> None:
        from miniautogen.api import ApprovalGate
        assert ApprovalGate is not None

    def test_export_auto_approve_gate(self) -> None:
        from miniautogen.api import AutoApproveGate
        assert AutoApproveGate is not None

    # -- Supervision types --

    def test_export_step_supervision(self) -> None:
        from miniautogen.api import StepSupervision
        assert StepSupervision is not None

    def test_export_supervision_decision(self) -> None:
        from miniautogen.api import SupervisionDecision
        assert SupervisionDecision is not None

    # -- Event types --

    def test_export_event_type(self) -> None:
        from miniautogen.api import EventType
        assert EventType is not None

    def test_export_null_event_sink(self) -> None:
        from miniautogen.api import NullEventSink
        assert NullEventSink is not None

    def test_export_event_sink(self) -> None:
        from miniautogen.api import EventSink
        assert EventSink is not None

    # -- Budget policy --

    def test_export_budget_policy(self) -> None:
        from miniautogen.api import BudgetPolicy
        assert BudgetPolicy is not None

    # -- Coordination --

    def test_export_coordination_mode(self) -> None:
        from miniautogen.api import CoordinationMode
        assert CoordinationMode is not None

    # -- Effect contracts --

    def test_export_effect_descriptor(self) -> None:
        from miniautogen.api import EffectDescriptor
        assert EffectDescriptor is not None

    def test_export_effect_record(self) -> None:
        from miniautogen.api import EffectRecord
        assert EffectRecord is not None

    def test_export_effect_status(self) -> None:
        from miniautogen.api import EffectStatus
        assert EffectStatus is not None

    # -- Agent hooks and memory --

    def test_export_agent_hook(self) -> None:
        from miniautogen.api import AgentHook
        assert AgentHook is not None

    def test_export_memory_provider(self) -> None:
        from miniautogen.api import MemoryProvider
        assert MemoryProvider is not None

    def test_export_in_memory_memory_provider(self) -> None:
        from miniautogen.api import InMemoryMemoryProvider
        assert InMemoryMemoryProvider is not None

    # -- Runtime interceptor --

    def test_export_runtime_interceptor(self) -> None:
        from miniautogen.api import RuntimeInterceptor
        assert RuntimeInterceptor is not None

    # -- Coordinator capability --

    def test_export_coordinator_capability(self) -> None:
        from miniautogen.api import CoordinatorCapability
        assert CoordinatorCapability is not None

    # -- Error category --

    def test_export_error_category(self) -> None:
        from miniautogen.api import ErrorCategory
        assert ErrorCategory is not None

    # -- Supervision strategy --

    def test_export_supervision_strategy(self) -> None:
        from miniautogen.api import SupervisionStrategy
        assert SupervisionStrategy is not None


class TestApiAllAttribute:
    """Verify __all__ includes every exported symbol."""

    def test_all_contains_new_exports(self) -> None:
        import miniautogen.api as api
        expected_new = {
            "PolicyChain", "PolicyContext", "PolicyResult", "PolicyEvaluator",
            "RetryPolicy", "EffectInterceptor", "EffectPolicy",
            "InMemoryEffectJournal", "EffectJournal",
            "CheckpointStore", "InMemoryCheckpointStore",
            "ApprovalGate", "AutoApproveGate",
            "StepSupervision", "SupervisionDecision",
            "EventType", "NullEventSink", "EventSink",
            "BudgetPolicy", "CoordinationMode",
            "EffectDescriptor", "EffectRecord", "EffectStatus",
            "AgentHook", "MemoryProvider", "InMemoryMemoryProvider",
            "RuntimeInterceptor", "CoordinatorCapability",
            "ErrorCategory", "SupervisionStrategy",
        }
        missing = expected_new - set(api.__all__)
        assert not missing, f"Missing from __all__: {missing}"

    def test_all_count_at_least_84(self) -> None:
        """After adding ~30 new exports, total should be >= 84."""
        import miniautogen.api as api
        assert len(api.__all__) >= 84, f"Only {len(api.__all__)} exports, expected >= 84"
