def test_runtime_cutover_marker_exists():
    from miniautogen.compat.state_bridge import RUNTIME_RUNNER_CUTOVER_READY

    assert RUNTIME_RUNNER_CUTOVER_READY is True
