"""Test that general deliberation contracts are exported from the contracts package."""


def test_contribution_importable_from_contracts() -> None:
    from miniautogen.core.contracts import Contribution
    assert Contribution is not None


def test_review_importable_from_contracts() -> None:
    from miniautogen.core.contracts import Review
    assert Review is not None
