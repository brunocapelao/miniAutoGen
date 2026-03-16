import pytest

from miniautogen.policies.budget import BudgetExceededError, BudgetPolicy, BudgetTracker


class TestBudgetTrackerNoLimit:
    def test_no_limit_always_passes(self):
        tracker = BudgetTracker(policy=BudgetPolicy(max_cost=None))
        tracker.record(1000.0)
        assert tracker.check() is True

    def test_no_limit_remaining_is_none(self):
        tracker = BudgetTracker(policy=BudgetPolicy(max_cost=None))
        assert tracker.remaining is None


class TestBudgetTrackerTracking:
    def test_records_costs_and_tracks_spent(self):
        tracker = BudgetTracker(policy=BudgetPolicy(max_cost=10.0))
        tracker.record(3.0)
        tracker.record(2.0)
        assert tracker.spent == 5.0

    def test_remaining_calculates_correctly(self):
        tracker = BudgetTracker(policy=BudgetPolicy(max_cost=10.0))
        tracker.record(3.0)
        assert tracker.remaining == 7.0

    def test_remaining_floors_at_zero(self):
        tracker = BudgetTracker(policy=BudgetPolicy(max_cost=5.0))
        with pytest.raises(BudgetExceededError):
            tracker.record(10.0)
        assert tracker.remaining == 0.0


class TestBudgetTrackerExceeded:
    def test_raises_budget_exceeded_error(self):
        tracker = BudgetTracker(policy=BudgetPolicy(max_cost=5.0))
        tracker.record(3.0)
        with pytest.raises(BudgetExceededError, match="Budget exceeded"):
            tracker.record(3.0)

    def test_negative_cost_raises_value_error(self):
        tracker = BudgetTracker(policy=BudgetPolicy(max_cost=10.0))
        with pytest.raises(ValueError, match="Cost cannot be negative"):
            tracker.record(-1.0)


class TestBudgetTrackerCheck:
    def test_check_true_within_budget(self):
        tracker = BudgetTracker(policy=BudgetPolicy(max_cost=10.0))
        tracker.record(5.0)
        assert tracker.check() is True

    def test_check_true_at_exact_limit(self):
        tracker = BudgetTracker(policy=BudgetPolicy(max_cost=5.0))
        tracker.record(5.0)
        assert tracker.check() is True

    def test_check_false_over_budget(self):
        tracker = BudgetTracker(policy=BudgetPolicy(max_cost=5.0))
        with pytest.raises(BudgetExceededError):
            tracker.record(6.0)
        assert tracker.check() is False
