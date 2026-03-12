from miniautogen import STABILITY_EXPERIMENTAL, STABILITY_INTERNAL, STABILITY_STABLE


def test_stability_markers_are_available() -> None:
    assert STABILITY_STABLE == "stable"
    assert STABILITY_EXPERIMENTAL == "experimental"
    assert STABILITY_INTERNAL == "internal"
